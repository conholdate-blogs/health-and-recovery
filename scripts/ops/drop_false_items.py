"""Delete false items from a tenant's item ledger (reports/<tenant>/items.json), so a corrected check does not count
them as "fixed" (rule: a false positive that was published is deleted, never resolved).

    .venv/bin/python scripts/ops/drop_false_items.py <tenant> <check> [--go]

Which items are false is decided by the current check code. Supported:
- redirect_key_malformed: items whose key core.audit.repo.key_problem() no longer flags (2026-11-11: a double slash
  was wrongly counted as malformed; such keys answer 301 on every blog).
Dry run without --go. The ledger is in git, so the old version stays recoverable.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from core.audit.repo import key_problem  # noqa: E402

FALSE = {"redirect_key_malformed": lambda item: key_problem(item.get("link") or "") is None}


def main() -> int:
    tenant, check = sys.argv[1], sys.argv[2]
    go = "--go" in sys.argv
    path = REPO / "reports" / tenant / "items.json"
    ledger = json.loads(path.read_text())
    false = [k for k, v in ledger["items"].items() if v.get("check") == check and FALSE[check](v)]
    for k in false[:5]:
        print("  ", k)
    print(f"{tenant}: {len(false)} false {check} items{'' if go else ' (dry run)'}")
    if go and false:
        for k in false:
            del ledger["items"][k]
        path.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
