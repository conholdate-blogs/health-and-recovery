"""Write a blog's most-read posts per language for llms.txt (data/llms_popular.json in the blog repo).

    set -a; source .env; set +a
    .venv/bin/python scripts/ops/llms_popular.py --tenant groupdocs.cloud [--months 3] [--top 50] [--write]

Why (Shoaib Khan, 26 Nov 2026): llms.txt listed only the 100 newest posts; on blog.groupdocs.cloud none of the 30
most-clicked pages (52% of all clicks) was among them. Hugo cannot read Search Console at build time, so this script
writes the ranking to a data file that layouts/index.llms.txt reads ("Most read" first, then the newest posts not
listed yet). Refresh monthly as an approved commit; if the file is missing the template lists only the newest.

Ranking per language: that language's Search Console clicks over the last N months (pages of its own posts only),
posts with at least --min-clicks; if fewer than --top, filled from the blog-wide ranking (sum over all languages)
with posts that have a translation in that language. Values are the posts' url paths without the trailing slash.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from core.tenant import load_tenant  # noqa: E402

FM = re.compile(r"^﻿?---\r?\n(.*?)\r?\n---", re.S)


def norm(path: str) -> str:
    return "/" + path.strip().strip("/") if path.strip("/") else "/"


def posts_by_url(repo: Path, default_lang: str) -> tuple[dict, dict]:
    """url path -> (lang, folder); folder -> set of languages."""
    by_url, langs = {}, defaultdict(set)
    for f in repo.glob("content/**/index*.md"):
        m = FM.match(f.read_text(encoding="utf-8", errors="replace"))
        try:
            d = yaml.safe_load(m.group(1)) if m else None
        except yaml.YAMLError:
            continue
        if not isinstance(d, dict) or d.get("draft") or not d.get("url"):
            continue
        lang = f.name[len("index."):-len(".md")] if f.name != "index.md" else default_lang
        folder = str(f.parent.relative_to(repo))
        by_url[norm(str(d["url"]))] = (lang, folder)
        langs[folder].add(lang)
    return by_url, langs


def fetch_pages(tenant, site: str, start: str, end: str) -> list[dict]:
    from core.google_auth import get_credentials
    from core.gsc import API_MAX_ROWS, GSCClient

    credentials, _ = get_credentials(key_env=tenant.credentials_env)
    gsc, rows, start_row = GSCClient(credentials), [], 0
    while True:
        batch = gsc.search_analytics(site, start, end, ["page"], row_limit=API_MAX_ROWS, start_row=start_row)
        rows += batch
        if len(batch) < API_MAX_ROWS:
            return rows
        start_row += API_MAX_ROWS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--months", type=int, default=3)
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--min-clicks", type=int, default=1)
    ap.add_argument("--write", action="store_true", help="write <blog repo>/data/llms_popular.json")
    a = ap.parse_args()
    tenant = load_tenant(a.tenant)
    host = next(h for h in tenant.raw["hosts"] if h.get("local_path"))
    repo, site = Path(host["local_path"]), next(s for s in tenant.gsc_properties if host["host"] in s)
    default_lang = (tenant.raw.get("audit") or {}).get("default_lang") or "en"
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=30 * a.months)
    rows = fetch_pages(tenant, site, start.isoformat(), end.isoformat())
    by_url, langs = posts_by_url(repo, default_lang)

    per_lang, blog_wide, unmatched = defaultdict(Counter), Counter(), 0
    for r in rows:
        path = norm(re.sub(r"^https?://[^/]+", "", r["keys"][0]).split("#")[0].split("?")[0])
        hit = by_url.get(path)
        if not hit:
            unmatched += r["clicks"]
            continue
        lang, folder = hit
        per_lang[lang][folder] += r["clicks"]
        blog_wide[folder] += r["clicks"]

    url_of = {(lang, folder): url for url, (lang, folder) in by_url.items()}
    out, report = {}, []
    for lang in sorted({lang for lang, _ in by_url.values()}):
        own = [f for f, c in per_lang[lang].most_common() if c >= a.min_clicks]
        chosen = own[: a.top]
        for f, _ in blog_wide.most_common():
            if len(chosen) >= a.top:
                break
            if f not in chosen and lang in langs[f]:
                chosen.append(f)
        out[lang] = [url_of[(lang, f)] for f in chosen if (lang, f) in url_of]
        report.append((lang, len(own), sum(1 for c in per_lang[lang].values() if c >= 3), sum(per_lang[lang].values())))

    print(f"{site} {start}..{end}: {sum(r['clicks'] for r in rows):,} clicks, {unmatched:,} not on a post page")
    print(f"{'lang':8} {'posts >=1 click':>16} {'>=3 clicks':>11} {'clicks':>7}")
    for lang, n1, n3, clicks in sorted(report, key=lambda x: -x[3]):
        print(f"{lang:8} {n1:>16} {n3:>11} {clicks:>7}")
    if a.write:
        p = repo / "data" / "llms_popular.json"
        p.parent.mkdir(exist_ok=True)
        meta = {"_about": f"Most-read posts per language for layouts/index.llms.txt: Search Console clicks "
                          f"{start}..{end}, top {a.top}; written by the Health and Recovery Agent "
                          f"(scripts/ops/llms_popular.py), refreshed monthly"}
        meta["_updated"] = date.today().isoformat()  # llms.txt "Last updated" when later than the newest post
        p.write_text(json.dumps({**meta, **out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("written", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
