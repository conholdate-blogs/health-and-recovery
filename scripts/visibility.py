"""Visibility numbers per host (SK, 2026-11-19): organic keywords (Search Console), AI-assistant referrals (GA4)
and Domain Rating (Ahrefs), for the 28-day window and the same window six months earlier.

    .venv/bin/python scripts/visibility.py --tenant conholdate.com
    .venv/bin/python scripts/visibility.py --tenant conholdate.com --dr blog.conholdate.com=28   # DR read by hand

Read-only. Writes reports/<tenant>/visibility.json (committed; one entry per day, a re-run replaces that day's).
Domain Rating needs AHREFS_API_KEY in .env (Ahrefs' free DR endpoint); without it the last known value is kept
with its date, and --dr records values read elsewhere (e.g. from the Ahrefs connector in a Claude session).
Only counts are stored, never query text. A source that fails is left out of the entry and reported; the rest is
still written.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.gsc import API_MAX_ROWS, default_window  # noqa: E402
from core.paths import tenant_paths  # noqa: E402
from core.tenant import load_tenant  # noqa: E402
from core.visibility import ai_referrals, keyword_counts, upsert_entry  # noqa: E402
from scripts.prioritize import history_windows  # noqa: E402

MAX_QUERY_ROWS = 200_000  # per host and window; blog.aspose.com is the largest
AHREFS_DR_URL = "https://api.ahrefs.com/v3/public/domain-rating-free"


def _err(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}"


def gsc_site(tenant, host: str) -> str | None:
    """The URL-prefix property of a host (blogs have one each)."""
    for s in tenant.gsc_properties:
        if s.rstrip("/").split("://")[-1].lower() == host.lower():
            return s
    return None


def retry(call, tries: int = 3, wait: float = 10.0):
    """Search Console answers a transient HTTP 500 now and then (19 Nov 2026): try again after a pause."""
    import time

    for n in range(tries):
        try:
            return call()
        except Exception:  # noqa: BLE001
            if n == tries - 1:
                raise
            time.sleep(wait)


def fetch_keywords(gsc, site: str, start: str, end: str) -> dict:
    rows, offset, capped = [], 0, False
    while True:
        batch = retry(lambda: gsc.search_analytics(site, start, end, dimensions=["query"], row_limit=API_MAX_ROWS,
                                                   start_row=offset))  # noqa: B023 (called at once)
        rows += batch
        if len(batch) < API_MAX_ROWS:
            break
        offset += API_MAX_ROWS
        if offset >= MAX_QUERY_ROWS:
            capped = True
            break
    total = retry(lambda: gsc.search_analytics(site, start, end, dimensions=None, row_limit=1))
    impressions = int(total[0].get("impressions", 0)) if total else 0
    return keyword_counts(rows, impressions, capped)


def fetch_dr(hosts: list[str], key: str) -> dict[str, float]:
    import requests

    resp = requests.get(AHREFS_DR_URL, params={"targets": ",".join(hosts)},
                        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"}, timeout=60)
    resp.raise_for_status()
    out = {}
    for t in (resp.json().get("domain_rating") or {}).get("targets") or []:
        out[t["target"].rstrip("/").lower()] = t.get("domain_rating")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tenant", default=os.environ.get("TENANT", "aspose.app"))
    ap.add_argument("--dr", action="append", default=[], help="host=value, a Domain Rating read by hand (repeatable)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    say = (lambda *a: None) if args.quiet else print

    tenant = load_tenant(args.tenant)
    hosts = [h for h in tenant.host_names if gsc_site(tenant, h)]
    if not hosts:
        print(f"{args.tenant}: no host with a Search Console property; nothing to do")
        return 0
    start, end = default_window(28)
    windows = {"current": [start, end], "six_months_ago": history_windows([start, end])["six_months_ago"]}
    today = date.today().isoformat()
    entry: dict = {"date": today, "windows": windows, "hosts": {h: {} for h in hosts}, "errors": {}}

    from core.google_auth import get_credentials
    from core.gsc import GSCClient

    credentials, _ = get_credentials(key_env=tenant.credentials_env)
    gsc = GSCClient(credentials)
    for h in hosts:
        for label, (s, e) in windows.items():
            try:
                k = fetch_keywords(gsc, gsc_site(tenant, h), s, e)
                entry["hosts"][h]["keywords" if label == "current" else "keywords_six_months_ago"] = k
                say(f"  {h} {label}: {k['queries']:,} queries, {k['top10']:,} in top 10, hidden {k['hidden_share']}")
            except Exception as exc:  # noqa: BLE001
                entry["errors"][f"gsc {h} {label}"] = _err(exc)

    if tenant.ga4_property_id:
        from core.ga4 import GA4Client

        ga4 = GA4Client(credentials)
        for label, (s, e) in windows.items():
            try:
                rows = ga4.run_report(tenant.ga4_property_id, ["hostName", "sessionSource"], ["sessions"], start=s,
                                      end=e, limit=100_000)
                for h in hosts:
                    ai = ai_referrals(rows, h)
                    entry["hosts"][h]["ai" if label == "current" else "ai_six_months_ago"] = ai
                    say(f"  {h} {label}: {ai['sessions']:,} AI referral sessions {ai['by_platform']}")
            except Exception as exc:  # noqa: BLE001
                entry["errors"][f"ga4 {label}"] = _err(exc)

    manual = dict(x.split("=", 1) for x in args.dr if "=" in x)
    key = os.environ.get("AHREFS_API_KEY")
    if key:
        try:
            got = fetch_dr(hosts, key)
            for h in hosts:
                if got.get(h.lower()) is not None:
                    entry["hosts"][h].update(dr=got[h.lower()], dr_date=today)
        except Exception as exc:  # noqa: BLE001
            entry["errors"]["ahrefs dr"] = _err(exc)
    for h, v in manual.items():
        if h in entry["hosts"]:
            entry["hosts"][h].update(dr=float(v), dr_date=today)
    if not entry["errors"]:
        del entry["errors"]
    for k, v in (entry.get("errors") or {}).items():
        print(f"  error: {k}: {v}", file=sys.stderr)

    path = tenant_paths(args.tenant).reports / "visibility.json"
    history = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    history = upsert_entry(history, entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=1) + "\n", encoding="utf-8")
    print(f"Visibility: {path} ({len(history)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
