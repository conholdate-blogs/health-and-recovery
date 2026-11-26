"""Fix tags and categories that break their URLs, in a blog repo (blog.groupdocs.cloud, 26 Nov 2026; found by Shoaib Khan).

    .venv/bin/python scripts/ops/taxonomy_fix.py <repo> --hash        [--write]  # tag 'c# …' -> 'csharp …'
    .venv/bin/python scripts/ops/taxonomy_fix.py <repo> --escaped     [--write]  # tag/category \\"x\\" -> x
    .venv/bin/python scripts/ops/taxonomy_fix.py <repo> --categories  [--write]  # translation categories = English
    .venv/bin/python scripts/ops/taxonomy_fix.py <repo> --tags        [--write]  # translation tags = English
    .venv/bin/python scripts/ops/taxonomy_fix.py <repo> --keys        [--write]  # translated keys -> tags/categories
    Order: --keys, --escaped, --hash, --tags, --categories (tags and categories are never translated: the translation
    agent's translatable_fields are title, seoTitle, description, summary, cover alt/caption, steps, faqs).
    add --skipped <csv> to write the queued translations it left alone (TR-11: they go to after-retranslation.csv)

Why: Hugo keeps '#' and '\\' in a slug: /tag/c#-ai-summarization/ is cut at '#' by the browser (the link opens
/tag/c), /tag/\\get-text\\/ has backslashes browsers turn into '/'. A translated, escaped or missing category gives
the translation its own category page (or none) instead of the English one.

Rules: only the tags / categories lines change (other lines byte-identical, line endings kept; each file re-parsed
and compared); an English post is fixed together with its current translations (one commit, so nothing is queued);
a queued translation (last commit older than the English post's, the translation agent's OUTDATED rule) is skipped
and listed, because editing it would drop it from the queue (playbook trap).
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

FM = re.compile(r"^(﻿?---\r?\n)(.*?)(\r?\n---)", re.S)


def commit_times(repo: Path) -> dict[str, int]:
    out = subprocess.run(["git", "-C", str(repo), "log", "--format=@%ct", "--name-only", "--no-renames", "--",
                          "content"], capture_output=True, text=True, check=True).stdout
    times, t = {}, 0
    for ln in out.splitlines():
        if ln.startswith("@"):
            t = int(ln[1:])
        elif ln and ln not in times:
            times[ln] = t
    return times


def parse(fm: str):
    try:
        d = yaml.safe_load(fm)
    except yaml.YAMLError:
        return None
    return d if isinstance(d, dict) else None


def region(fm: str, nl: str, key: str):
    """(start, end, style, indent) of a top-level key's lines in the front matter text; None if absent."""
    m = re.search(rf"^{key}[ \t]*:[ \t]*(.*)$", fm, re.M)
    if not m:
        return None
    start = m.start()
    if m.group(1).strip():  # inline: tags: [...] (may continue on following lines until the closing bracket)
        end = m.end()
        if m.group(1).strip().startswith("[") and "]" not in m.group(1):
            close = fm.find("]", end)
            end = fm.find(nl, close) if fm.find(nl, close) != -1 else len(fm)
        return start, end, "inline", ""
    end, indent = m.end(), None
    while end < len(fm):  # the list items directly below, line by line (a top-level key ends the block)
        nxt = fm.find(nl, end + len(nl))
        line = fm[end + len(nl): nxt if nxt != -1 else len(fm)]
        if not line.strip() or not line.startswith((" ", "\t", "-")):
            break
        if indent is None:
            indent = re.match(r"[ \t]*", line).group(0)
        end = nxt if nxt != -1 else len(fm)
    return start, end, "block", indent if indent is not None else "  "


def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid double-quoted YAML scalar


def render(key: str, values: list[str], style: str, indent: str, nl: str) -> str:
    if style == "inline":
        return f"{key}: [{', '.join(q(v) for v in values)}]"
    return f"{key}:" + "".join(f"{nl}{indent}- {q(v)}" for v in values)


# translated front-matter keys for tags / categories seen in translations (Hugo ignores them, so the page has no
# tags or category): blog.groupdocs.cloud 26 Nov 2026
KEY_NAMES = {"теги": "tags", "etiketler": "tags", "برچسب‌ها": "tags", "étiquettes": "tags", "etiquetas": "tags",
             "タグ": "tags", "태그": "tags", "标签": "tags", "標籤": "tags",
             "категории": "categories", "kategoriler": "categories", "دسته‌ها": "categories",
             "catégories": "categories", "categorías": "categories", "categorias": "categories",
             "カテゴリー": "categories", "카테고리": "categories", "分类": "categories", "分類": "categories"}


def fix_hash(v: str) -> str:
    return re.sub(r"(?i)\bc#", lambda m: "CSharp" if m.group(0) == "C#" else "csharp", v)


QUOTES = '"“”'


def fix_escaped(v: str) -> list[str]:
    """One escaped value -> its clean value(s). Seen: \\"x\\", mismatched \\"x" and \\"x\\” (curly), and items where
    the pipeline ran several tags into one: x\\" - \\"y\\" - \\"z."""
    out = []
    for part in re.split(r'\\?["“”]\s+-\s+\\?["“”]', v):
        s = re.sub(rf"^(\\*[{QUOTES}])+", "", part.strip())
        s = re.sub(rf"(\\*[{QUOTES}])+$", "", s).replace('\\"', '"').strip()
        if s:
            out.append(s)
    return out


def needs_escape_fix(v: str) -> bool:
    return "\\" in v or any(c in v for c in QUOTES)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--hash", action="store_true")
    mode.add_argument("--escaped", action="store_true")
    mode.add_argument("--categories", action="store_true")
    mode.add_argument("--tags", action="store_true")
    mode.add_argument("--keys", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--skipped", type=Path)
    a = ap.parse_args()
    repo = a.repo
    times = commit_times(repo)
    changed, skipped, problems = [], [], []
    for en in sorted(repo.glob("content/**/index.md")):
        files = [en] + sorted(en.parent.glob("index.*.md"))
        raw_en = en.read_bytes().decode("utf-8")
        m_en = FM.match(raw_en)
        E = parse(m_en.group(2)) if m_en else None
        if E is None:
            continue
        en_time = times.get(str(en.relative_to(repo)), 0)
        for f in files:
            rel = str(f.relative_to(repo))
            raw = f.read_bytes().decode("utf-8")
            m = FM.match(raw)
            d = parse(m.group(2)) if m else None
            if d is None:
                continue
            fm = m.group(2)
            nl = "\r\n" if "\r\n" in fm else "\n"
            if a.keys:  # rename a translated tags/categories key to the English name (translations only)
                if f is en:
                    continue
                renames = {k: v for k, v in KEY_NAMES.items() if k in d and v not in d}
                drops = [k for k, v in KEY_NAMES.items() if k in d and v in d]  # English key there too: leftover
                if not renames and not drops:
                    continue
                if times.get(rel, 0) < en_time:
                    skipped.append((rel, ", ".join(list(renames) + drops)))
                    continue
                new_fm = fm
                for k, v in renames.items():
                    new_fm = re.sub(rf"^{re.escape(k)}[ \t]*:", f"{v}:", new_fm, count=1, flags=re.M)
                for k in drops:
                    s, e, _, _ = region(new_fm, nl, re.escape(k))
                    new_fm = new_fm[:s].rstrip("\r\n") + new_fm[e:] if s else new_fm[e:].lstrip("\r\n")
                after = parse(new_fm)
                want = {renames.get(k, k): val for k, val in d.items() if k not in drops}
                if after != want:
                    problems.append(rel)
                    continue
                changed.append((rel, {"renamed": renames}))
                if a.write:
                    f.write_bytes((raw[:m.start(2)] + new_fm + raw[m.end(2):]).encode("utf-8"))
                continue
            edits = {}  # key -> new values
            if a.hash or a.escaped:
                keys = ("tags",) if a.hash else ("tags", "categories")
                for key in keys:
                    old = [str(x) for x in d.get(key) or []]
                    if a.hash:
                        new = [fix_hash(v) for v in old]
                    else:
                        new = [w for v in old for w in (fix_escaped(v) if needs_escape_fix(v) else [v])]
                    if new != old:
                        edits[key] = new
            elif f is not en:  # tags / categories of a translation = the English post's (never translated)
                key = "tags" if a.tags else "categories"
                want = [str(t).strip() for t in E.get(key) or []]
                cur = [str(c).strip() for c in d.get(key) or []]
                if want and cur != want:
                    edits[key] = want
            if not edits:
                continue
            queued = f is not en and times.get(rel, 0) < en_time
            if queued:
                skipped.append((rel, ", ".join(edits)))
                continue
            new_fm = fm
            for key, values in edits.items():
                r = region(new_fm, nl, key)
                if r is None:  # missing key (categories): add it after the tags block, else at the end
                    t = region(new_fm, nl, "tags")
                    at = t[1] if t else len(new_fm)
                    new_fm = new_fm[:at] + nl + render(key, values, "inline", "", nl) + new_fm[at:]
                else:
                    s, e, style, indent = r
                    new_fm = new_fm[:s] + render(key, values, style, indent, nl) + new_fm[e:]
            after = parse(new_fm)
            ok = after is not None and all([str(x) for x in after.get(k) or []] == v for k, v in edits.items())
            if ok:
                rest_a = {k: v for k, v in d.items() if k not in edits}
                rest_b = {k: v for k, v in after.items() if k not in edits}
                ok = rest_a == rest_b
            if not ok:
                problems.append(rel)
                continue
            changed.append((rel, edits))
            if a.write:
                f.write_bytes((raw[:m.start(2)] + new_fm + raw[m.end(2):]).encode("utf-8"))
    posts = {str(Path(r).parent) for r, _ in changed}
    print(f"{'written' if a.write else 'would change'}: {len(changed)} files in {len(posts)} posts; "
          f"queued translations skipped: {len(skipped)}; files needing a hand fix: {len(problems)}")
    for r in problems:
        print("  hand fix:", r)
    for r, e in changed[:5]:
        print("  e.g.", r, json.dumps(e, ensure_ascii=False)[:160])
    if a.skipped and skipped:
        with a.skipped.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "fields", "reason"])
            for r, fields in skipped:
                w.writerow([r, fields, "queued translation: fix with the retranslation (TR-11)"])
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
