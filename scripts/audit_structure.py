"""Site structure per blog: tags, categories and the listing pages Hugo builds, from each blog's local repo, plus
tag URLs in the sitemaps (latest discovery run) and Search Console clicks on tag and paginated pages (newest traffic
cache). Writes reports/<tenant>/structure-<date>.json (older ones are replaced: git keeps them).

    .venv/bin/python scripts/audit_structure.py --tenant conholdate.com

Read-only. Network: the tags list and two tag pages, the section page, one Search Console query (junk URLs over
~16 months) and up to 400 of those URLs live. Runs in run_cycle.py after the repo file check (blogs with a
local_path repo only).
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

from core.audit.structure import (  # noqa: E402
    AUDITOR,
    JUNK_GSC_REGEX,
    findings,
    junk_live,
    scan,
    search_numbers,
    section_robots,
    tag_robots,
    taxonomy_feeds,
)
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


def sitemap_url_set(inventory: Path, host: str) -> set[str]:
    """Every URL of the host in the latest discovery run (real pages: never junk)."""
    if not inventory.is_file():
        return set()
    db = sqlite3.connect(inventory)
    run = db.execute("SELECT MAX(run_id) FROM urls WHERE host = ?", (host,)).fetchone()[0]
    return {u for (u,) in db.execute("SELECT url FROM urls WHERE run_id = ? AND host = ?", (run, host))}


def gsc_rows(data_dir: Path, tenant: str) -> tuple[list[dict], list | None]:
    caches = sorted(data_dir.glob(f"traffic-{tenant}-*.json"))
    if not caches:
        return [], None
    data = json.loads(caches[-1].read_text(encoding="utf-8"))
    return [r for rows in (data.get("gsc") or {}).values() for r in rows], data.get("window")


JUNK_DAYS = 480  # Search Console keeps about 16 months


def known_junk_rows(tenant, host: str) -> tuple[list[dict], list[str]]:
    """Page rows of the host's Search Console property that match JUNK_GSC_REGEX over ~16 months."""
    from datetime import timedelta

    from core.google_auth import GSC_READONLY, get_credentials
    from core.gsc import API_MAX_ROWS, GSCClient, default_window

    end = default_window()[1]
    start = (date.fromisoformat(end) - timedelta(days=JUNK_DAYS)).isoformat()
    gsc = GSCClient(get_credentials((GSC_READONLY,), key_env=tenant.credentials_env)[0])
    rows = []
    for site in tenant.gsc_properties:
        if host not in site:
            continue
        offset = 0
        while True:
            batch = gsc.search_analytics(site, start, end, dimensions=["page"], row_limit=API_MAX_ROWS,
                                         start_row=offset, filters=[{"dimension": "page", "operator": "includingRegex",
                                                                     "expression": JUNK_GSC_REGEX}])
            rows += [{"page": r["keys"][0], "clicks": int(r.get("clicks", 0)),
                      "impressions": int(r.get("impressions", 0))} for r in batch]
            if len(batch) < API_MAX_ROWS:
                break
            offset += API_MAX_ROWS
    return [r for r in rows if f"//{host}/" in r["page"]], [start, end]


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
        # a redirected URL is not the page asked for (blog.groupdocs.cloud 26 Nov: a Redirects.json entry sends
        # /tag/.net-html-to-xps-conversion/ to a post, whose 'index, follow' is not the tag page's robots)
        status = 301 if r.redirects else r.status
        return status, r.headers, r.body.decode("utf-8", "replace"), r.blocked_by_robots

    fast = PoliteFetcher(min_interval=0.25)  # junk URLs: up to JUNK_LIVE_CAP plain GETs

    def get_fast(url):
        r = fast.get(url)
        return (301 if r.redirects else r.status), r.headers, "", r.blocked_by_robots

    previous = {}
    for old in sorted(paths.reports.glob("structure-*.json")):
        previous = json.loads(old.read_text(encoding="utf-8")).get("hosts") or {}

    hosts = {}
    for h in tenant.raw.get("hosts") or []:
        if not h.get("local_path"):
            continue
        host = h["host"]
        feeds = taxonomy_feeds(Path(h["local_path"]))
        try:
            jrows, jwindow = known_junk_rows(tenant, host)
            junk = {**junk_live(get_fast, jrows, feeds_built=feeds["term"],
                                sitemap_urls=sitemap_url_set(paths.inventory, host)), "window": jwindow}
        except Exception as exc:  # noqa: BLE001  no Search Console: keep the last result, so nothing resolves falsely
            junk = dict((previous.get(host) or {}).get("known_junk") or {}, error=str(exc)[:120])
        hosts[host] = {**scan(Path(h["local_path"]), default_lang), **sitemap_numbers(paths.inventory, host),
                       "search": search_numbers(rows, host), "tag_robots": tag_robots(get, host),
                       "section_robots": section_robots(get, host, Path(h["local_path"])),
                       "taxonomy_feeds": feeds, "known_junk": junk}
        s = hosts[host]
        print(f"{host}: taxonomy feeds term={feeds['term']} taxonomy={feeds['taxonomy']} ({feeds['config']}); "
              f"junk URLs in Search Console {junk.get('urls', 0):,}, checked {junk.get('checked', 0):,}, "
              f"answer 200: {len(junk.get('served') or [])}" + (f" [GSC error: {junk['error']}]"
                                                                 if junk.get("error") else ""))
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
