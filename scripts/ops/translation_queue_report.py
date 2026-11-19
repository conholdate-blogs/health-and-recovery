"""Translation queue report for one blog: the analyses that decided 'fix here or retranslate' on blog.conholdate.com
(18-19 Nov 2026), plus by-hand items of docs/check-sheet.md, as one read-only command.

    .venv/bin/python scripts/ops/translation_queue_report.py --tenant groupdocs.cloud

Writes reports/<tenant>/queue-report-<date>.md and prints the summary. Sections:
 1. Queued translations (the translation agent's OUTDATED rule: translation committed before index.md), per post:
    how much the English changed since the oldest queued translation (front matter only / body <=5 / 6-20 / >20
    lines, ignoring heading levels and link targets) and who changed it (optimizer / Health and Recovery Agent /
    other). Rule TR-9: front matter or a few lines -> fix here; body rewritten -> retranslate.
 2. English issues of fully queued posts (from the newest repo and link check CSVs): fix the English first (TR-10).
 3. Optimizer cuts: commits by the optimization agent that removed >= 40 lines of an English post, and whether the
    post still has fewer H2 sections than before the cut (TD-5; post_body_cut_off only sees cuts at the end).
 4. Check-sheet by-hand items: translated titles that start with the English title's first word (half translated,
    F11), translations with front-matter keys the English post does not have (translated keys, F8), cover images
    whose file does not exist (F7), translation tag lists that differ from the English post (F15).
"""
import argparse
import collections
import csv
import datetime as dt
import difflib
import glob
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from core.tenant import load_tenant  # noqa: E402

FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
OPTIMIZER = re.compile(r"optimizer-agent|Blog Optimization Agent|Optimized Blog Posts|Auto-merge", re.I)
VERBS = {"Convert", "Combine", "Render", "Compare", "Edit", "Create", "Add", "Merge", "Split", "Extract", "Export",
         "Read", "Remove", "Delete", "Insert", "Generate", "View", "Protect", "Find", "Replace", "Get", "How", "Unlock",
         "Compress", "Rotate", "Resize", "Crop", "Flip", "Print", "Sign", "Annotate", "Redact", "Parse", "Search",
         "Free", "Online", "Open", "Load", "Save", "Change", "Set", "Hide", "Unhide", "Apply", "Draw", "Fuzzy", "Text"}
OURS = re.compile(r"Fixed by Health and Recovery Agent|Health and Recovery", re.I)


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout


def front(text):
    m = FM.match(text.lstrip("﻿").replace("\r\n", "\n"))
    try:
        d = yaml.safe_load(m.group(1)) if m else None
    except yaml.YAMLError:
        return {}, text
    return (d if isinstance(d, dict) else {}), (text[m.end():] if m else text)


def norm_body(b):
    b = re.sub(r"\]\([^)]*\)", "]()", b)
    b = re.sub(r"^\s*\[\d+\]:.*$", "", b, flags=re.M)
    b = re.sub(r"^#+", "#", b, flags=re.M)
    return [ln.strip() for ln in b.split("\n") if ln.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    a = ap.parse_args()
    ten = load_tenant(a.tenant)
    host = next(h for h in ten.raw["hosts"] if h.get("local_path"))
    repo = Path(host["local_path"])
    # one git log pass: last commit time, author and subject per file
    hist = collections.defaultdict(list)
    cur = None
    for ln in git(repo, "log", "--format=@%H\t%ct\t%an\t%s%n%b%x00", "--name-only", "--no-renames", "--",
                  "content").split("\n"):
        if ln.startswith("@"):
            h, t, an, s = ln[1:].split("\t", 3)
            cur = {"sha": h, "t": int(t), "who": an, "msg": s}
        elif cur and ln.endswith(".md") and ln.startswith("content/"):
            hist[ln].append(cur)
        elif cur and ln.strip("\x00").strip():
            cur["msg"] += " " + ln

    def kind(c):
        return "optimizer" if OPTIMIZER.search(c["who"] + " " + c["msg"]) else \
            ("ours" if OURS.search(c["msg"]) else "other")

    out, summary = [], {}
    # 1. queued translations
    sizes, whos, rows1 = collections.Counter(), collections.Counter(), []
    posts = sorted(repo.glob("content/**/index.md"))
    for en in posts:
        rel = str(en.relative_to(repo))
        eh = hist.get(rel)
        if not eh:
            continue
        trs = sorted(en.parent.glob("index.*.md"))
        q = [t for t in trs if (th := hist.get(str(t.relative_to(repo)))) and th[0]["t"] < eh[0]["t"]]
        if not q:
            continue
        t0 = min(hist[str(t.relative_to(repo))][0]["t"] for t in q)
        base = next((c for c in eh if c["t"] <= t0), None)
        after = {kind(c) for c in eh if c["t"] > t0}
        size = "no base"
        if base:
            old = git(repo, "show", f"{base['sha']}:{rel}")
            if old:
                (_, bo), (_, bn) = front(old), front(en.read_text("utf-8"))
                n = sum(1 for x in difflib.ndiff(norm_body(bo), norm_body(bn)) if x[:1] in "+-")
                size = ("front matter only" if n == 0 else "body 1-5" if n <= 5 else "body 6-20" if n <= 20
                        else "body >20")
        sizes[size] += len(q)
        whos[" + ".join(sorted(after))] += len(q)
        rows1.append((size, " + ".join(sorted(after)), en.parent.name, len(q), len(trs)))
    out.append("## 1. Queued translations\n")
    out.append(f"{sum(sizes.values())} queued translations in {len(rows1)} posts.\n")
    out.append("| English change since the translation | Translations |\n|---|---|")
    out += [f"| {k} | {v} |" for k, v in sizes.most_common()]
    out.append("\n| Who changed the English after it | Translations |\n|---|---|")
    out += [f"| {k} | {v} |" for k, v in whos.most_common()]
    out.append("\nFix here (TR-9): posts with 'front matter only' or 'body 1-5':\n")
    out += [f"- {p} ({n} of {m} queued; {w})" for s, w, p, n, m in sorted(rows1) if s in ("front matter only",
                                                                                          "body 1-5")]
    summary["queued translations"] = sum(sizes.values())
    summary["fix-here candidates (posts)"] = sum(1 for r in rows1 if r[0] in ("front matter only", "body 1-5"))
    # 2. English issues of fully queued posts
    full = {f"{p}" for s, w, p, n, m in rows1 if n == m}
    rows2 = []
    for pat in ("repo-audit-*-issues.csv", "link-audit-*-issues.csv"):
        files = sorted(glob.glob(str(REPO / "reports" / a.tenant / pat)))
        if files:
            for r in csv.DictReader(open(files[-1], encoding="utf-8")):
                f = r.get("file") or ""
                if f.endswith("/index.md") and Path(f).parent.name in full:
                    rows2.append((Path(f).parent.name, r["check"], (r.get("note") or r.get("link") or "")[:90]))
    out.append("\n## 2. English issues of fully queued posts (fix first, TR-10)\n")
    out += [f"- {p}: `{c}` {n}" for p, c, n in sorted(rows2)] or ["- none"]
    summary["English issues in fully queued posts"] = len(rows2)
    # 3. optimizer cuts
    rows3 = []
    log = git(repo, "log", "--format=@%h\t%an\t%s", "--numstat", "--", "content/*index.md")
    c = None
    for ln in log.split("\n"):
        if ln.startswith("@"):
            c = ln[1:].split("\t")
            continue
        p = ln.split("\t")
        if c and len(p) == 3 and p[0].isdigit() and p[2].endswith("/index.md") and OPTIMIZER.search(c[1] + c[2]):
            if int(p[1]) - int(p[0]) >= 40:
                before = git(repo, "show", f"{c[0]}^:{p[2]}")
                now = (repo / p[2]).read_text("utf-8") if (repo / p[2]).exists() else ""
                h2b, h2n = before.count("\n## "), now.count("\n## ")
                rows3.append((p[2].split("/")[-2], c[0], int(p[1]) - int(p[0]), h2b, h2n))
    out.append("\n## 3. Optimizer cuts (>= 40 lines removed in one commit)\n")
    out.append("| Post | Commit | Lines removed | H2 before | H2 now | State |\n|---|---|---|---|---|---|")
    out += [f"| {p} | {s} | {n} | {b} | {w} | {'**still fewer sections**' if w < b else 'restored or reworded'} |"
            for p, s, n, b, w in sorted(rows3, key=lambda r: -r[2])]
    summary["optimizer cuts / still short"] = f"{len(rows3)} / {sum(1 for r in rows3 if r[4] < r[3])}"
    # 4. by-hand items
    half, keys, imgs, tags = [], [], [], 0
    for en in posts:
        E, _ = front(en.read_text("utf-8"))
        cov = E.get("cover") if isinstance(E.get("cover"), dict) else {}
        if cov.get("image") and not (en.parent / str(cov["image"])).exists():
            imgs.append(f"{en.parent.name}: {cov['image']}")
        et = str(E.get("title") or "").split()
        for t in sorted(en.parent.glob("index.*.md")):
            T, _ = front(t.read_text("utf-8"))
            lang = t.name[6:-3]
            tt = str(T.get("title") or "")
            if et and tt and tt != " ".join(et) and tt.split()[0] == et[0] and et[0] in VERBS:
                half.append(f"{lang} {en.parent.name}: {tt[:70]}")
            extra = set(T) - set(E)
            if extra:
                keys.append(f"{lang} {en.parent.name}: {', '.join(sorted(map(str, extra)))[:80]}")
            tc = T.get("cover") if isinstance(T.get("cover"), dict) else {}
            if tc.get("image") and not (en.parent / str(tc["image"])).exists():
                imgs.append(f"{lang} {en.parent.name}: {tc['image']}")
            if [str(x) for x in T.get("tags") or []] != [str(x) for x in E.get("tags") or []]:
                tags += 1
    out.append("\n## 4. Check-sheet by-hand items\n")
    out.append(f"- F11 titles starting with the English first word (half translated?): {len(half)}")
    out += [f"  - {x}" for x in half[:40]]
    out.append(f"- F8 front-matter keys the English post does not have: {len(keys)}")
    out += [f"  - {x}" for x in keys[:40]]
    out.append(f"- F7 cover image files that do not exist: {len(imgs)}")
    out += [f"  - {x}" for x in imgs[:40]]
    out.append(f"- F15 translations whose tag list differs from the English post: {tags}")
    summary.update({"F11 half-translated titles?": len(half), "F8 extra keys": len(keys),
                    "F7 missing cover files": len(imgs), "F15 tag lists differ": tags})
    path = REPO / "reports" / a.tenant / f"queue-report-{dt.date.today()}.md"
    path.write_text(f"# Translation queue report: {host['host'] if 'host' in host else a.tenant}, "
                    f"{dt.date.today()}\n\n" + "\n".join(out) + "\n", encoding="utf-8")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print("->", path.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
