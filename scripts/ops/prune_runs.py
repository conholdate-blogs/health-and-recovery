"""Usage: .venv/bin/python scripts/ops/prune_runs.py [--go]  (dry run without --go; 2026-11-07 removed 84 files).
List (and with --go, git rm) run files that newer runs replace: per blog tenant and audit type keep the newest
run (repo-audit: every run of the newest day); a run's -issues.csv goes with its JSON. aspose.app is not touched."""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TENANTS = ["conholdate.cloud", "conholdate.com", "aspose.cloud", "groupdocs.cloud", "aspose.com", "groupdocs.com"]
KINDS = ["discovery", "crawl-audit", "ai-audit", "perf-audit", "text-audit", "link-audit", "repo-audit"]
RX = re.compile(r"^(?P<kind>[a-z-]+?)-(?P<date>\d{4}-\d\d-\d\d)-run(?P<run>\d+)\.json$")
go = "--go" in sys.argv
doomed = []
for t in TENANTS:
    folder = REPO / "reports" / t
    for kind in KINDS:
        runs = []
        for f in folder.glob(f"{kind}-*-run*.json"):
            m = RX.match(f.name)
            if m and m["kind"] == kind:
                runs.append((int(m["run"]), m["date"], f))
        if len(runs) < 2:
            continue
        runs.sort()
        newest_run, newest_date, _ = runs[-1]
        keep = {f for r, d, f in runs if (d == newest_date if kind == "repo-audit" else r == newest_run)}
        for _r, _d, f in runs:
            if f in keep:
                continue
            doomed.append(f)
            csv = f.with_name(f.stem + "-issues.csv")
            if csv.exists():
                doomed.append(csv)
        print(f"{t:17} {kind:12} keep {', '.join(sorted(k.name for k in keep))}")
size = sum(f.stat().st_size for f in doomed) / 1e6
print(f"\n{len(doomed)} files to delete, {size:.1f} MB:")
for f in doomed:
    print("  ", f.relative_to(REPO))
if go and doomed:
    rels = [str(f.relative_to(REPO)) for f in doomed]
    tracked = set(subprocess.run(["git", "-C", str(REPO), "ls-files", "-z", "--", *rels], capture_output=True,
                                 text=True, check=True).stdout.split("\0")) - {""}
    if tracked:
        subprocess.run(["git", "-C", str(REPO), "rm", "-q", *sorted(tracked)], check=True)
    for f in doomed:
        f.unlink(missing_ok=True)  # untracked runs of this session
    print(f"done: {len(tracked)} git rm, {len(doomed) - len(tracked)} untracked deleted")
