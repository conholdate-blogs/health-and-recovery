"""Site structure per blog: tags, categories and the listing pages Hugo builds, from each blog's local repo, plus
tag URLs in the sitemaps (latest discovery run) and Search Console clicks on tag and paginated pages (newest traffic
cache). Writes reports/<tenant>/structure-<date>.json (older ones are replaced: git keeps them).

    .venv/bin/python scripts/audit_structure.py --tenant conholdate.com

Read-only; no network. Runs in run_cycle.py after the repo file check (blogs with a local_path repo only).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.audit.structure import AUDITOR, findings, scan, search_numbers, tag_robots  # noqa: E402
from core.discovery.fetch import PoliteFetcher  # noqa: E402
from core.findings import FindingsStore  # noqa: E402
from core.paths import tenant_paths  # noqa: E402
from core.tenant import load_tenant  # noqa: E402
from scripts.findings import export, print_changes  # noqa: E402


def sitemap_numbers(inventory: Path, host: str) -> dict:
    """URLs and tag URLs of the host in the latest discovery run."""
    if not inventory.is_file():
        return {}
    db = sqlite3.connect(inventory)
    run = db.execute("SELECT MAX(run_id) FROM urls WHERE host = ?", (host,)).fetchone()[0]
    if run is None:
        return {}
    total, tags = db.execute("SELECT COUNT(*), SUM(template = 'tag') FROM urls WHERE run_id = ? AND host = ?",
                             (run, host)).fetchone()
    return {"discovery_run": run, "sitemap_urls": total, "sitemap_tag_urls": tags or 0}


def gsc_rows(data_dir: Path, tenant: str) -> tuple[list[dict], list | None]:
    caches = sorted(data_dir.glob(f"traffic-{tenant}-*.json"))
    if not caches:
        return [], None
    data = json.loads(caches[-1].read_text(encoding="utf-8"))
    return [r for rows in (data.get("gsc") or {}).values() for r in rows], data.get("window")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tenant", default=os.environ.get("TENANT", "aspose.app"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    tenant = load_tenant(args.tenant)
    paths = tenant_paths(args.tenant)
    default_lang = (tenant.raw.get("audit") or {}).get("default_lang") or "en"
    rows, window = gsc_rows(paths.data, args.tenant)
    fetcher = PoliteFetcher(min_interval=1.0)

    def get(url):
        r = fetcher.get(url)
        return r.status, r.headers, r.body.decode("utf-8", "replace"), r.blocked_by_robots

    hosts = {}
    for h in tenant.raw.get("hosts") or []:
        if not h.get("local_path"):
            continue
        host = h["host"]
        hosts[host] = {**scan(Path(h["local_path"]), default_lang), **sitemap_numbers(paths.inventory, host),
                       "search": search_numbers(rows, host), "tag_robots": tag_robots(get, host)}
        s = hosts[host]
        print(f"{host}: {s['posts']:,} posts, {s['tags']:,} tags ({s['tags_one_post']:,} with one post), "
              f"{s['listing_pages']:,} listing pages ({s['tag_listing_pages']:,} tag), "
              f"{s.get('sitemap_tag_urls', 0):,} tag URLs in sitemaps; tag pages noindex: "
              f"{'yes' if s['tag_robots']['all_noindex'] else 'no'} ({len(s['tag_robots']['pages'])} read)")
    if not hosts:
        print("No blog repo (local_path) in this tenant; nothing to do")
        return 0
    out = paths.reports / f"structure-{date.today().isoformat()}.json"
    for old in paths.reports.glob("structure-*.json"):
        if old != out:
            old.unlink()
    out.write_text(json.dumps({"tenant": args.tenant, "date": date.today().isoformat(), "search_window": window,
                               "hosts": hosts}, indent=1) + "\n", encoding="utf-8")
    print(f"Site structure: {out}")
    # scored findings from these numbers (thin tag pages, tag pages in sitemaps); the run covers its hosts in full
    channels = {h["host"]: h.get("fix_channel") for h in tenant.raw.get("hosts") or []}
    found = [f for host, s in hosts.items() for f in findings(tenant.property, host, s, channels.get(host))]
    fstore = FindingsStore(str(paths.findings_store))
    print_changes(fstore.import_run(found, f"{AUDITOR}-{date.today().isoformat()}", AUDITOR, hosts=list(hosts),
                                    resolve_unsectioned=True))
    print(f"Findings export: {export(fstore, paths.findings_export)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
