"""Link audit for multilingual Hugo blogs: every internal link in every post (from the local source repo), checked
against the live site; plus translation sets (posts missing supported languages, unsupported languages published).

Run on the Mac after discover.py (needs the host's sitemap inventory and network). Hosts need `local_path` in the
tenant YAML; the clone is read only (pull it yourself first: the script warns when its last commit is old).

    python scripts/audit_links.py                                  # all tenant hosts with a local repo
    python scripts/audit_links.py --hosts blog.aspose.cloud --max-live 200

Read-only and polite: targets not in the sitemaps are fetched once each (GET, robots.txt respected, one request
per host per --interval seconds), at most --max-live per run; the rest stay unchecked and are not reported.

Writes the report to reports/<tenant>/link-audit-<date>-run<id>.json, the complete fix list to
reports/<tenant>/link-audit-<date>-run<id>-issues.csv, and the findings to the findings store (exported to
reports/<tenant>/findings.json). Run prioritize.py afterwards to score the new findings.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.audit.links import audit, import_report  # noqa: E402
from core.audit.store import AuditStore  # noqa: E402
from core.discovery.fetch import DEFAULT_USER_AGENT, PoliteFetcher  # noqa: E402
from core.findings import FindingsStore  # noqa: E402
from core.paths import tenant_paths  # noqa: E402
from core.tenant import load_tenant  # noqa: E402
from scripts.findings import export, import_seed, print_changes  # noqa: E402

ISSUE_COLS = ["check", "lang", "page", "file", "line", "link", "fix", "note", "commit", "by_translation_commit"]


def _csv(value: str | None) -> list[str] | None:
    return [v.strip() for v in value.split(",") if v.strip()] if value else None


def print_summary(report: dict) -> None:
    print(f"\n== Hosts ({report['requests']} requests, {report['duration_s']}s) ==")
    for host, h in report["summary"].items():
        checks = ", ".join(f"{k} {v}" for k, v in sorted(h["by_check"].items())) or "no link issues"
        repo = h["repo"]
        print(f"  {host:24} repo {repo['commit']} ({repo['date']}{', STALE' if repo['stale'] else ''}) "
              f"posts={h['posts']} links={h['links']:,} live={h['live_checked']} unchecked={h['not_checked']}")
        print(f"  {'':24} {checks}; partial sets={h['partial']} unsupported={','.join(h['unsupported']) or '-'}")
    findings = report["findings"]
    print(f"\n== Findings ({len(findings)}) ==")
    for f in findings:
        print(f"  {f['id']:<12} {f['type']:<13} {f['subdomain']:<24} {f['title']} ({f['affected_pages']} pages)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tenant", default=os.environ.get("TENANT", "aspose.app"))
    ap.add_argument("--hosts", help="comma-separated hosts (default: all tenant hosts with a local_path)")
    ap.add_argument("--max-live", type=int, help="most targets fetched live per run (default: tenant "
                    "audit.links.max_live, else 5000)")
    ap.add_argument("--no-blame", action="store_true", help="skip git blame (no commit per issue)")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between requests to one host")
    ap.add_argument("--user-agent", default=os.environ.get("AUDIT_USER_AGENT", DEFAULT_USER_AGENT))
    ap.add_argument("--inventory", help="discovery inventory (default: data/<tenant>/inventory.sqlite)")
    ap.add_argument("--db", help="audit runs (default: data/<tenant>/audit.sqlite)")
    ap.add_argument("--out-dir", help="default: reports/<tenant>/")
    ap.add_argument("--findings-store", help="default: data/<tenant>/findings.sqlite; '' to skip the findings store")
    ap.add_argument("--quiet", action="store_true", help="no per-host progress lines")
    args = ap.parse_args(argv)

    tenant = load_tenant(args.tenant)
    paths = tenant_paths(tenant.property)
    inventory = Path(args.inventory or paths.inventory)
    if not inventory.is_file():
        print(f"No discovery inventory at {inventory}; run scripts/discover.py first", file=sys.stderr)
        return 2
    args.db = args.db or str(paths.audit_db)
    args.out_dir = args.out_dir or str(paths.reports)
    if args.findings_store is None:
        args.findings_store = str(paths.findings_store)
    hosts = _csv(args.hosts)
    with_repo = [h["host"] for h in tenant.hosts if h.get("local_path") and h["host"] in tenant.host_names]
    unknown = [h for h in hosts or [] if h not in with_repo]
    if unknown:
        print(f"Not tenant hosts with a local_path: {', '.join(unknown)}", file=sys.stderr)
        return 2
    if not with_repo:
        print("No tenant host has a local_path (source repo); nothing to audit", file=sys.stderr)
        return 2

    max_live = args.max_live or ((tenant.raw.get("audit") or {}).get("links") or {}).get("max_live", 5000)
    fetcher = PoliteFetcher(user_agent=args.user_agent, min_interval=args.interval)
    report = audit(tenant, fetcher, AuditStore(args.db), sqlite3.connect(str(inventory)), hosts=hosts,
                   max_live=max_live, blame=not args.no_blame, log=None if args.quiet else print)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"link-audit-{date.today().isoformat()}-run{report['run_id']}"
    out_file = out_dir / f"{stem}.json"
    out_file.write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    issues_file = out_dir / f"{stem}-issues.csv"
    with issues_file.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["host", *ISSUE_COLS], extrasaction="ignore")
        w.writeheader()
        for host, r in report["hosts"].items():
            for i in r["issues"]:
                w.writerow({"host": host, **i})
    print_summary(report)
    print(f"\nFull report: {out_file}\nFix list: {issues_file}")
    if args.findings_store:
        fstore = FindingsStore(args.findings_store)
        import_seed(fstore, tenant.property)
        print(f"\nFindings store: {args.findings_store}")
        print_changes(import_report(fstore, report))
        print(f"Findings export: {export(fstore, paths.findings_export)}  (run prioritize.py to score them)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
