"""Read-only check before long scans (2026-11-06): .env keys (names only, never values), Python packages, step scripts,
free disk, per blog tenant its data files and clone state (clean, branch, ahead/behind after a fetch), Mac sleep
settings; with --live also one LLM call and one PageSpeed call.

    .venv/bin/python scripts/ops/preflight.py [--live]

Run long scans under `caffeinate -i` (the Mac sleeps after 1 minute idle; keep the lid open and on power).
"""
import importlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from core.paths import tenant_paths  # noqa: E402
from core.tenant import load_tenant  # noqa: E402
from scripts.run_cycle import STEPS, dotenv  # noqa: E402

BLOGS = ["conholdate.cloud", "conholdate.com", "aspose.cloud", "groupdocs.cloud", "aspose.com", "groupdocs.com"]


def ok(flag: bool) -> str:
    return "OK " if flag else "XX "


def main() -> int:
    env = dotenv(REPO / ".env")
    print("== .env ==")
    for k in ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CREDENTIALS_HEALTH_AND_RECOVERY", "PROFESSIONALIZE_API_KEY",
              "PROFESSIONALIZE_BASE_URL", "PROFESSIONALIZE_LLM_MODEL", "PAGESPEED_API_KEY"]:
        v = env.get(k)
        extra = (" (key file exists)" if Path(v).is_file() else " (KEY FILE MISSING)") if v and "GOOGLE" in k else ""
        print(f"  {ok(bool(v) or k == 'PAGESPEED_API_KEY')}{k} {'set' if v else 'not set'}{extra}")
    print("== packages ==")
    for m in ["httpx", "yaml", "selectolax", "openai", "google.oauth2", "googleapiclient"]:
        try:
            importlib.import_module(m)
            print(f"  OK {m}")
        except Exception as e:  # noqa: BLE001
            print(f"  XX {m}: {type(e).__name__}")
    print("== step scripts ==")
    for s in STEPS:
        print(f"  {ok((REPO / 'scripts' / f'{s}.py').is_file())}{s}.py")
    free = shutil.disk_usage(REPO).free / 1e9
    print(f"== disk ==\n  {ok(free > 5)}{free:.0f} GB free")
    print("== blogs ==")
    for t in BLOGS:
        ten, p = load_tenant(t), tenant_paths(t)
        print(f"-- {t}")
        for name in ["inventory.sqlite", "findings.sqlite", "audit.sqlite"]:
            print(f"   {ok((p.data / name).is_file())}data/{t}/{name}")
        for h in ten.raw.get("hosts") or []:
            if not h.get("local_path"):
                continue
            g = ["git", "-C", h["local_path"]]
            dirty = subprocess.run(g + ["status", "--porcelain"], capture_output=True, text=True).stdout.strip()
            subprocess.run(g + ["fetch", "-q"], capture_output=True, text=True, timeout=300)
            ab = subprocess.run(g + ["rev-list", "--left-right", "--count", "HEAD...@{u}"], capture_output=True,
                                text=True).stdout.split() or ["?", "?"]
            print(f"   {ok(not dirty and ab[0] == '0')}{h['host']}: ahead {ab[0]}, behind {ab[1]}"
                  f"{', LOCAL CHANGES' if dirty else ''} (the cycle pulls --ff-only)")
    pm = subprocess.run(["pmset", "-g"], capture_output=True, text=True).stdout
    sleep = next((ln.strip() for ln in pm.splitlines() if ln.strip().startswith("sleep")), "?")
    print(f"== Mac ==\n  {sleep}  -> run scans under caffeinate -i")
    if "--live" in sys.argv:
        import os
        os.environ.update(env)
        from core.llm import LLM
        from core.pagespeed import PageSpeedClient, make_session
        t0 = time.time()
        try:
            LLM.from_env().complete("Reply with the single word OK.", "ping")
            print(f"  OK LLM ({time.time() - t0:.1f}s)")
        except Exception as e:  # noqa: BLE001
            print(f"  XX LLM: {type(e).__name__}")
        t0 = time.time()
        try:
            PageSpeedClient(make_session(), retries=1).run("https://blog.conholdate.cloud/")
            print(f"  OK PageSpeed ({time.time() - t0:.0f}s)")
        except Exception as e:  # noqa: BLE001
            print(f"  XX PageSpeed: {type(e).__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
