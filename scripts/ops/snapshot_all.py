"""Snapshot the report of each of the six blog tenants with one label (build_report.py --snapshot), one after another.

    .venv/bin/python scripts/ops/snapshot_all.py "Label shown in the archive"

Archive rule first: if a tenant's live page is not archived yet (its latest snapshot was not built from what is live),
download it into reports/<tenant>/archive/ before running this (see CLAUDE.md, Working rules).
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BLOGS = ["conholdate.cloud", "conholdate.com", "aspose.cloud", "groupdocs.cloud", "aspose.com", "groupdocs.com"]


def main() -> int:
    label = sys.argv[1]
    failed = 0
    for t in BLOGS:
        r = subprocess.run([sys.executable, "scripts/build_report.py", "--tenant", t, "--out",
                            f"reports/{t}/discovery-latest.html", "--snapshot", label],
                           cwd=REPO, capture_output=True, text=True)
        failed += r.returncode != 0
        print(t, "OK" if r.returncode == 0 else "FAILED", (r.stdout.splitlines() or [""])[0], r.stderr[-300:])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
