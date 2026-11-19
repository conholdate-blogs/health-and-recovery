"""Proofread the English body of every post whose translations wait for retranslation (SK, 2026-11-19: the English a
retranslation copies must be perfect). One LLM call per post (internal endpoint, core/llm.py), 4 at a time; answers
cached per text in data/<tenant>/english-body-cache.json, so a rerun on unchanged posts makes no calls. An answer is
kept only if its 'wrong' text occurs in the post. Output: reports/<tenant>/english-body-check-<date>.csv (one row per
finding) for review by hand; the fixes are made in the English post before the translator picks it up.

    .venv/bin/python scripts/ops/english_body_check.py --tenant conholdate.com [--all] [--limit N]

--all checks every English post, not only queued ones. Queued = a translation last committed before index.md (the
translation agent's OUTDATED rule).
"""
import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from core.llm import LLM, parse_json  # noqa: E402
from core.tenant import load_tenant  # noqa: E402

PROMPT_VERSION = 2
MAX_CHARS = 12000
KINDS = {"misspelling", "repeated_word", "stray_word", "copied_from_other_post", "wrong_product", "broken_sentence"}
SYSTEM = """You proofread the English text of a technical blog post (code, links and images removed).
Input: JSON {title, description, topic, body}. topic is the post's subject from its folder name.

Report only clear, certain errors a careful editor would fix:
- misspelling: a misspelled word or two words run together.
- repeated_word: the same word typed twice by mistake.
- stray_word: a leftover placeholder, template key or test word ("lorem", "TODO", "{{ … }}").
- copied_from_other_post: a sentence or heading that belongs to a different post (it names another product,
  format or task than the topic, e.g. "C# QR Code Detector library" in a post about converting WebP to JPG).
- wrong_product: a product, file format or language that contradicts the topic (e.g. "Java" in a C# post's steps).
- broken_sentence: a sentence cut off or garbled so it no longer makes sense.

Never report: product, brand or API names; file extensions; style, tone, wordiness, capitalization, punctuation,
American vs British spelling, marketing phrasing; related products or formats mentioned on purpose ("See also",
"you may also like", other conversions the SDK supports). When in doubt, do not report it.

Answer with JSON only: {"issues": [{"kind": "<one of the kinds>", "wrong": "<the wrong text exactly as written,
at most one sentence>", "fix": "<corrected text, empty to delete>", "why": "<a few words>"}]}.
Return {"issues": []} when there is nothing to report."""

FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
FENCE = re.compile(r"^\s*(```|~~~).*?^\s*\1\s*$", re.S | re.M)


def body_text(md: str) -> str:
    t = FENCE.sub("", md)
    t = re.sub(r"\{\{[<%].*?[%>]\}\}", "", t, flags=re.S)       # shortcodes
    t = re.sub(r"^\s*\[\d+\]:.*$", "", t, flags=re.M)             # reference definitions
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)                     # images
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)                 # inline links -> text
    t = re.sub(r"\[([^\]]+)\]\[\d+\]", r"\1", t)                   # reference links -> text
    # raw HTML outside `inline code` is dropped by Hugo's Markdown renderer (goldmark unsafe: false, the default), so
    # '**<input>** element' renders as an empty bold: strip it as readers see it, keep tags inside backticks
    t = "".join(part if i % 2 else re.sub(r"<[^>]+>", "", part)
                for i, part in enumerate(re.split(r"(`[^`\n]*`)", t)))
    t = re.sub(r"^ {4,}.*$", "", t, flags=re.M)                    # indented code
    return re.sub(r"\n{3,}", "\n\n", t).strip()[:MAX_CHARS]


def last_commits(repo: Path) -> dict:
    out = subprocess.run(["git", "-C", str(repo), "log", "--format=@%ct", "--name-only", "--no-renames", "--",
                          "content"], capture_output=True, text=True).stdout
    ct, t = {}, None
    for line in out.splitlines():
        if line.startswith("@"):
            t = int(line[1:])
        elif line and line not in ct:
            ct[line] = t
    return ct


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    import yaml

    ten = load_tenant(a.tenant)
    host = next(h for h in ten.raw["hosts"] if h.get("local_path"))
    repo = Path(host["local_path"])
    ct = last_commits(repo)
    posts = []
    for en in sorted(repo.glob("content/**/index.md")):
        rel = str(en.relative_to(repo))
        trs = list(en.parent.glob("index.*.md"))
        queued = [t for t in trs if ct.get(str(t.relative_to(repo)), 0) < ct.get(rel, 0)]
        if not a.all and not queued:
            continue
        text = en.read_text("utf-8").replace("\r\n", "\n")
        m = FM.match(text)
        try:
            fm = yaml.safe_load(m.group(1)) if m else {}
        except yaml.YAMLError:
            fm = {}
        fm = fm if isinstance(fm, dict) else {}
        if fm.get("draft"):
            continue
        item = {"title": str(fm.get("title") or ""), "description": str(fm.get("description") or ""),
                "topic": en.parent.name, "body": body_text(text[m.end():] if m else text)}
        posts.append((rel, len(queued), item))
    if a.limit:
        posts = posts[:a.limit]
    cache_path = REPO / "data" / a.tenant / "english-body-cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    llm = LLM.from_env()

    def key(item):
        return hashlib.sha256(json.dumps({"v": PROMPT_VERSION, "m": llm.model, **item}, sort_keys=True,
                                         ensure_ascii=False).encode()).hexdigest()

    todo = [(rel, item) for rel, _, item in posts if key(item) not in cache]
    print(f"{len(posts)} English posts ({'all' if a.all else 'with queued translations'}): "
          f"{len(posts) - len(todo)} cached, {len(todo)} LLM calls")

    def ask(item):
        try:
            return parse_json(llm.complete(SYSTEM, json.dumps(item, ensure_ascii=False))).get("issues") or []
        except Exception as e:  # noqa: BLE001 - one failed post must not stop the run
            return {"error": str(e)[:100]}

    with cf.ThreadPoolExecutor(4) as ex:
        for (rel, item), ans in zip(todo, ex.map(lambda x: ask(x[1]), todo), strict=True):
            if isinstance(ans, list):
                cache[key(item)] = ans
            else:
                print("  unchecked:", rel, ans["error"])
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False))
    rows = []
    for rel, nq, item in posts:
        hay = (item["title"] + "\n" + item["description"] + "\n" + item["body"]).casefold()
        for i in cache.get(key(item)) or []:
            wrong = str(i.get("wrong") or "").strip()
            if i.get("kind") in KINDS and wrong and wrong.casefold() in hay and wrong != str(i.get("fix") or ""):
                rows.append({"file": rel, "queued_translations": nq, "kind": i["kind"], "wrong": wrong,
                             "fix": str(i.get("fix") or ""), "why": str(i.get("why") or "")[:120]})
    out = REPO / "reports" / a.tenant / f"english-body-check-{dt.date.today()}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "queued_translations", "kind", "wrong", "fix", "why"])
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by[r["kind"]] = by.get(r["kind"], 0) + 1
    print(f"{len(rows)} findings in {len({r['file'] for r in rows})} posts {by} -> {out.relative_to(REPO)}")
    print(f"LLM usage: {llm.usage.as_dict()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
