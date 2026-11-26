"""Replace links listed by the link check (link-audit-*-issues.csv) in a blog repo (blog.groupdocs.cloud, 26 Nov 2026).

    .venv/bin/python scripts/ops/link_fix.py <repo> <csv> --checks link_broken --rule '/category/x/=>/y/' [--write]
    .venv/bin/python scripts/ops/link_fix.py <repo> <issues.csv> --checks link_wrong_language --use-fix [--write]

--rule 'old=>new' (repeatable): replace that part of each listed link; --use-fix: take the check's `fix` column.
Only the listed line changes, only the listed link on it (exact text, first occurrence); line endings kept.
Queued translations (last commit older than the English post's) are skipped and listed: editing them would drop them
from the translation queue (playbook trap). When an English post changes, its current translations must change in the
same commit too, or they are queued: the tool reports English posts whose translations were not all touched.
"""
import argparse
import csv
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--checks", required=True, help="comma list of check names")
    ap.add_argument("--rule", action="append", default=[], help="'old=>new' part of the link to replace")
    ap.add_argument("--use-fix", action="store_true")
    ap.add_argument("--match", default="", help="only links containing this text")
    ap.add_argument("--exclude", action="append", default=[], help="skip links containing this text")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    rules = [tuple(r.split("=>", 1)) for r in a.rule]
    checks = set(a.checks.split(","))
    times = commit_times(a.repo)
    by_file = defaultdict(list)
    for r in csv.DictReader(a.csv.open(encoding="utf-8")):
        if r["check"] in checks and a.match in r["link"] and not any(x in r["link"] for x in a.exclude):
            by_file[r["file"]].append(r)
    done, skipped, missing, plan = 0, [], [], {}
    for rel, rows in sorted(by_file.items()):
        f = a.repo / rel
        en_rel = str(Path(rel).parent / "index.md")
        if not rel.endswith("/index.md") and times.get(rel, 0) < times.get(en_rel, 0):
            skipped.append(rel)
            continue
        lines = f.read_bytes().decode("utf-8").splitlines(keepends=True)
        for r in rows:
            new = r["fix"] if a.use_fix else r["link"]
            for old_part, new_part in rules:
                new = new.replace(old_part, new_part)
            if a.use_fix and new and "#" in r["link"] and "#" not in new:  # keep the heading anchor
                new += "#" + r["link"].split("#", 1)[1]
            if not new or new == r["link"]:
                missing.append((rel, r["link"], "no replacement"))
                continue
            i = int(r["line"]) - 1
            if not (0 <= i < len(lines)) or r["link"] not in lines[i]:
                missing.append((rel, r["link"], f"not on line {r['line']}"))
                continue
            lines[i] = lines[i].replace(r["link"], new, 1)
            done += 1
        plan[rel] = "".join(lines)
    partial = []
    for rel in plan:
        if rel.endswith("/index.md"):
            folder = Path(rel).parent
            current = [str(p.relative_to(a.repo)) for p in (a.repo / folder).glob("index.*.md")
                       if times.get(str(p.relative_to(a.repo)), 0) >= times.get(rel, 0)]
            left = [c for c in current if c not in plan]
            if left:
                partial.append((rel, len(left)))
    if a.write:
        for rel, text in plan.items():
            (a.repo / rel).write_bytes(text.encode("utf-8"))
    print(f"{'replaced' if a.write else 'would replace'} {done} links in {len(plan)} files; "
          f"queued translations skipped: {len(skipped)}; not replaced: {len(missing)}; "
          f"English posts with untouched current translations: {len(partial)}")
    for m in missing[:10]:
        print("  not replaced:", *m)
    for p in partial[:10]:
        print("  partial:", *p)
    for s in skipped[:10]:
        print("  queued:", s)
    return 1 if missing or partial else 0


if __name__ == "__main__":
    sys.exit(main())
