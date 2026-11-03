"""Update the item ledger (reports/<tenant>/items.json) with every link-check and discovery run it does not have yet.

    .venv/bin/python scripts/track_items.py --tenant aspose.cloud

Runs after audit_links (run_cycle.py does this). Fixed vs removed is decided against each blog's local clone,
which the cycle has just pulled to the commit the link check read, and for discovery items against the run's
URL inventory (data/<tenant>/inventory.sqlite); see core/items.py. Discovery runs from before 2026-10-30 have no
`items` and are skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.discovery.store import InventoryStore  # noqa: E402
from core.items import counts, discovery_items, in_repo, in_sitemaps, repo_items, run_items, update  # noqa: E402
from core.paths import tenant_paths  # noqa: E402
from core.tenant import load_tenant  # noqa: E402
from scripts.build_report import run_date_of, runs_by_name  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tenant", default=os.environ.get("TENANT", "aspose.app"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    tenant = load_tenant(args.tenant)
    paths = tenant_paths(args.tenant)
    folder = paths.reports
    path = folder / "items.json"
    ledger = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    repos = {h["host"]: h["local_path"] for h in tenant.raw.get("hosts") or [] if h.get("local_path")}
    added = 0
    for run in runs_by_name("link-audit-*-run*.json", folder):
        data = json.loads(run.read_text(encoding="utf-8"))
        ref = f"link-audit-run{data['run_id']}"
        if ref in (ledger.get("runs") or []):
            continue
        update(ledger, ref, run_date_of(run, "link-audit-"), run_items(data),
               in_repo({h: p for h, p in repos.items() if h in (data.get("hosts") or {})}))
        added += 1
    for run in runs_by_name("repo-audit-*-run*.json", folder):
        data = json.loads(run.read_text(encoding="utf-8"))
        ref = f"repo-audit-run{data['run_id']}"
        if ref in (ledger.get("runs") or []):
            continue
        update(ledger, ref, run_date_of(run, "repo-audit-"), repo_items(data),
               in_repo({h: p for h, p in repos.items() if h in (data.get("hosts") or {})}), source="repo-audit")
        added += 1
    store = InventoryStore(paths.inventory) if paths.inventory.is_file() else None
    for run in runs_by_name("discovery-*-run*.json", folder):
        data = json.loads(run.read_text(encoding="utf-8"))
        ref = f"discovery-run{data['run_id']}"
        if "items" not in data or ref in (ledger.get("runs") or []):
            continue
        hosts = list(data["items"])
        listed = ({u for h in hosts for u in store.sample_urls(data["run_id"], h, None, limit=-1)}
                  if store else None)
        if listed is not None and not listed:
            listed = None  # the inventory no longer has this run
        update(ledger, ref, run_date_of(run, "discovery-"), discovery_items(data), in_sitemaps(hosts, listed),
               source="discovery")
        added += 1
    if not added:
        print(f"Item ledger already has every link-check and discovery run ({path})")
        return 0
    path.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for host in sorted(ledger.get("baseline") or {}):
        c = counts(ledger, host)
        print(f"{host}: since {c['since']}: {c['baseline']} at baseline, {c['new']} new, {c['fixed']} fixed, "
              f"{c['removed']} removed, {c['open']} still open"
              + (f" ({c['fixed_pct']}% fixed)" if c["fixed_pct"] is not None else ""))
    print(f"Item ledger: {added} run(s) added -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
