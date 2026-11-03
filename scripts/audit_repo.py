"""Repo file check for blogs with a local source repo: what is malformed and committed, and a live sample of redirects.

    python scripts/audit_repo.py --tenant aspose.com

The clone is read only (pull it first: run_cycle.py does). Writes reports/<tenant>/repo-audit-<date>-run<id>.json, the
fix list reports/<tenant>/repo-audit-<date>-run<id>-issues.csv, and the findings to the findings store. Run
track_items.py (fix counts) and prioritize.py afterwards.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.audit.repo import LIVE_SAMPLE, audit, import_report  # noqa: E402
from core.audit.store import AuditStore  # noqa: E402
from core.discovery.fetch import DEFAULT_USER_AGENT, PoliteFetcher  # noqa: E402
from core.findings import FindingsStore  # noqa: E402
from core.paths import tenant_paths  # noqa: E402
from core.tenant import load_tenant  # noqa: E402
from scripts.findings import export, import_seed, print_changes  # noqa: E402

ISSUE_COLS = ["check", "file", "line", "link", "fix", "note", "commit"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tenant", default=os.environ.get("TENANT", "aspose.app"))
    ap.add_argument("--sample", type=int, default=LIVE_SAMPLE, help="redirects tested live per host")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between requests to one host")
    ap.add_argument("--user-agent", default=os.environ.get("AUDIT_USER_AGENT", DEFAULT_USER_AGENT))
    ap.add_argument("--quiet", action="store_true", help="no per-host progress lines")
    args = ap.parse_args(argv)

    tenant = load_tenant(args.tenant)
    paths = tenant_paths(tenant.property)
    if not any(h.get("local_path") for h in tenant.hosts):
        print("No tenant host has a local_path (source repo); nothing to audit", file=sys.stderr)
        return 2
    fetcher = PoliteFetcher(user_agent=args.user_agent, min_interval=args.interval)
    report = audit(tenant, fetcher, AuditStore(str(paths.audit_db)), sample=args.sample,
                   log=None if args.quiet else print)

    paths.reports.mkdir(parents=True, exist_ok=True)
    stem = f"repo-audit-{date.today().isoformat()}-run{report['run_id']}"
    out_file = paths.reports / f"{stem}.json"
    out_file.write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    issues_file = paths.reports / f"{stem}-issues.csv"
    with issues_file.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["host", *ISSUE_COLS], extrasaction="ignore")
        w.writeheader()
        for host, r in report["hosts"].items():
            for i in r["issues"]:
                w.writerow({"host": host, **i})
    for host, s in report["summary"].items():
        print(f"{host}: commit {s['commit']}; {s['entries']} redirects, invalid: {s['invalid'] or 'no'}"
              f"{'; since ' + s['broke_it'] if s['broke_it'] else ''}\n  live {s['live']}\n  {s['by_check']}")
    print(f"Full report: {out_file}\nFix list: {issues_file}")
    fstore = FindingsStore(str(paths.findings_store))
    import_seed(fstore, tenant.property)
    print_changes(import_report(fstore, report))
    print(f"Findings export: {export(fstore, paths.findings_export)}  (run track_items.py, then prioritize.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
