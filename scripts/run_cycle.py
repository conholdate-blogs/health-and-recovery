"""Run a tenant's full audit cycle in order, as CLAUDE.md "Full cycle" describes, and stop at the first failure.

    .venv/bin/python scripts/run_cycle.py aspose.app
    .venv/bin/python scripts/run_cycle.py aspose.cloud --from audit_text
    .venv/bin/python scripts/run_cycle.py aspose.cloud --quick     # discovery, link check, prioritize

Before the link check, each blog's local clone is fast-forwarded (git pull --ff-only); a clone with local
changes or a diverged history stops the cycle untouched. Loads .env itself (the same keys `set -a; source .env`
would export). Steps (STEPS below): discover, audit_crawl, audit_ai, audit_perf, audit_text, then for blogs with a
source repo (`audit.links` in the YAML) audit_links and audit_repo, track_items, prioritize, audit_structure and
rescore (prioritize --offline, scoring the structure findings). Each step gets --tenant; output goes to
data/<tenant>/cycle-<date>.log. Building, snapshotting and pushing the report stay manual: the results are reviewed
by hand first (LLM findings in particular).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.paths import tenant_paths  # noqa: E402
from core.tenant import load_tenant  # noqa: E402

# audit_structure after prioritize: its search numbers come from the traffic cache that prioritize has just
# refreshed; rescore (prioritize --offline, no Google calls) then scores the structure findings it adds
STEPS = ["discover", "audit_crawl", "audit_ai", "audit_perf", "audit_text", "audit_links", "audit_repo", "track_items",
         "prioritize", "audit_structure", "rescore"]
# the exact (non-sampled) checks only: weekly and after a translation batch; no LLM, about 35 min for the blogs
QUICK = ["discover", "audit_links", "audit_repo", "track_items", "prioritize", "audit_structure", "rescore"]


def pull_clones(tenant) -> str | None:
    """Fast-forward each blog's local clone before the link check (SK, 2026-10-27). Returns an error, or None.
    Never touches a clone with local changes or one that has diverged: that is SK's working copy."""
    for h in tenant.raw.get("hosts") or []:
        path = h.get("local_path")
        if not path:
            continue
        git = ["git", "-C", path]
        if subprocess.run(git + ["status", "--porcelain"], capture_output=True, text=True).stdout.strip():
            return f"{path} has local changes; not pulled"
        r = subprocess.run(git + ["pull", "--ff-only", "-q"], capture_output=True, text=True)
        if r.returncode:
            return f"{path}: git pull --ff-only failed: {r.stderr.strip()}"
        head = subprocess.run(git + ["log", "-1", "--format=%h %cs"], capture_output=True, text=True).stdout.strip()
        print(f"  {h['host']}: clone at {head}", flush=True)
    return None


def dotenv(path: Path) -> dict[str, str]:
    """KEY=value lines of a .env file (comments, blank lines and surrounding quotes ignored)."""
    env = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.removeprefix("export ").split("=", 1)
                env[key.strip()] = value.strip().strip("'\"")
    return env


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tenant")
    ap.add_argument("--from", dest="start", choices=STEPS, help="resume at this step")
    ap.add_argument("--quick", action="store_true", help="exact checks only: " + ", ".join(QUICK))
    args = ap.parse_args(argv)
    tenant = load_tenant(args.tenant)
    steps = QUICK if args.quick else STEPS
    steps = steps[steps.index(args.start):] if args.start in steps else steps
    if not (tenant.raw.get("audit") or {}).get("links"):
        # blog source repos only
        steps = [s for s in steps if s not in ("audit_links", "audit_repo", "audit_structure", "rescore")]
    if not (tenant.raw.get("audit") or {}).get("links") and not (tenant.raw.get("collections") or {}).get("blogs"):
        steps = [s for s in steps if s != "track_items"]  # items come from the link check and blog sitemaps
    env = {**os.environ, **dotenv(REPO_ROOT / ".env"), "TENANT": args.tenant}
    log_path = tenant_paths(args.tenant).data / f"cycle-{date.today().isoformat()}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        for step in steps:
            if step == "audit_links":
                error = pull_clones(tenant)
                if error:
                    print(f"Stopped before the link check: {error}", file=sys.stderr)
                    return 1
            script = "prioritize" if step == "rescore" else step
            cmd = [sys.executable, str(REPO_ROOT / "scripts" / f"{script}.py"), "--tenant", args.tenant]
            if step == "rescore":
                cmd.append("--offline")
            elif step != "prioritize":
                cmd.append("--quiet")
            started = time.time()
            print(f"[{time.strftime('%H:%M')}] {step} ...", flush=True)
            log.write(f"\n=== {step} {time.strftime('%Y-%m-%d %H:%M')} ===\n")
            log.flush()
            code = subprocess.run(cmd, cwd=REPO_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
            print(f"[{time.strftime('%H:%M')}] {step} {'ok' if code == 0 else f'FAILED ({code})'} "
                  f"in {(time.time() - started) / 60:.0f} min", flush=True)
            if code:
                print(f"Stopped. Log: {log_path}. Resume with --from {step}", file=sys.stderr)
                return code
    print(f"Cycle done for {args.tenant}. Log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
