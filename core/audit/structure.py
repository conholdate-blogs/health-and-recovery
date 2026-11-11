"""Site structure of a Hugo blog, read from its source repo (read-only): posts per language, tags and categories,
and how many listing pages Hugo builds from them (home, each category and each tag, per language, `paginate` posts
a page). SK, 2026-11-07: most tags hold one or two posts, and every tag is a page in every language, so the tag
pages dwarf the posts; these numbers show it per blog and give the tag clean-up its before/after.

Search numbers (clicks on tag pages and on paginated /page/N/ listings) and sitemap counts are added by the script
from the traffic cache and the discovery inventory.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

_FM = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
_NAME = re.compile(r"^index(?:\.([A-Za-z]{2,3}(?:-[A-Za-z]+)?))?\.md$")
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_PAGINATE = re.compile(r"^paginate:\s*(\d+)\s*$", re.M)
TAG_PATH = re.compile(r"^/(?:[a-z]{2}(?:-[a-z]+)?/)?tags?/[^/]+/")
PAGED_PATH = re.compile(r"/(?:page|p)/(\d+)/?$")
DEEP_PAGE = 50  # SK's proposed cap on paginated listing pages
TOP_TAGS = 10


def paginate_of(repo: Path, default: int = 10) -> int:
    """`paginate` from the repo's config.yml (Hugo's default 10)."""
    cfg = repo / "config.yml"
    m = _PAGINATE.search(cfg.read_text(encoding="utf-8", errors="ignore")) if cfg.is_file() else None
    return int(m.group(1)) if m else default


def _terms(value) -> list[str]:
    if not value:
        return []
    items = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    return sorted({str(v).strip().lower() for v in items if str(v).strip()})


def scan(repo: Path, default_lang: str = "en", paginate: int | None = None) -> dict:
    """Tags, categories and listing pages of one blog repo."""
    paginate = paginate or paginate_of(repo)
    posts = Counter()
    tags: dict[str, Counter] = defaultdict(Counter)
    cats: dict[str, Counter] = defaultdict(Counter)
    tags_per_post: list[int] = []
    for f in repo.glob("content/**/index*.md"):
        m = _NAME.match(f.name)
        if not m:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
        fm = _FM.match(text)
        if not fm:
            continue
        try:
            meta = yaml.load(fm.group(1), Loader=_LOADER) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(meta, dict) or meta.get("draft") is True:
            continue
        lang = m.group(1) or default_lang
        posts[lang] += 1
        post_tags = _terms(meta.get("tags"))
        tags[lang].update(post_tags)
        cats[lang].update(_terms(meta.get("categories")))
        if lang == default_lang:
            tags_per_post.append(len(post_tags))

    def pages(n: int) -> int:
        return max(1, -(-n // paginate))

    listing = tag_listing = deep = 0
    for lang, n in posts.items():
        for count, is_tag in [(n, False)] + [(c, False) for c in cats[lang].values()] + \
                [(c, True) for c in tags[lang].values()]:
            p = pages(count)
            listing += p
            tag_listing += p if is_tag else 0
            deep += max(0, p - DEEP_PAGE)
    own = tags[default_lang]
    return {
        "paginate": paginate,
        "posts": posts[default_lang], "posts_all_languages": sum(posts.values()), "languages": len(posts),
        "tags": len(own),
        "tags_one_post": sum(1 for c in own.values() if c == 1),
        "tags_two_or_less": sum(1 for c in own.values() if c <= 2),
        "tags_per_post": round(sum(tags_per_post) / len(tags_per_post), 1) if tags_per_post else 0,
        "tag_pages_all_languages": sum(len(t) for t in tags.values()),
        "top_tags": own.most_common(TOP_TAGS),
        "categories": len(cats[default_lang]),
        "listing_pages": listing, "tag_listing_pages": tag_listing, "pages_beyond_cap": deep, "cap": DEEP_PAGE,
    }


def search_numbers(gsc_rows: list[dict], host: str) -> dict:
    """Clicks and impressions (28 days) on tag pages and on paginated listing pages of one host."""
    out = Counter()
    for r in gsc_rows:
        url = r.get("page") or ""
        if f"//{host}/" not in url:
            continue
        path = "/" + url.split(f"//{host}/", 1)[1]
        clicks, impr = r.get("clicks", 0), r.get("impressions", 0)
        out["clicks"] += clicks
        if TAG_PATH.match(path):
            out["tag_clicks"] += clicks
            out["tag_impressions"] += impr
            out["tag_pages_with_clicks"] += 1 if clicks else 0
        m = PAGED_PATH.search(path)
        if m:
            out["paged_clicks"] += clicks
            out["paged_impressions"] += impr
            out["paged_pages_seen"] += 1
            out["deep_paged_clicks"] += clicks if int(m.group(1)) > DEEP_PAGE else 0
    return dict(out)


# ---- findings (SK, 2026-11-10: scored tag findings from these numbers) ----

AUDITOR = "structure-audit"
THIN_SHARE = 0.5  # red in the Site structure panel: at least half the tags hold one post
# check -> (dimension, type, title, expected, fix_tier, effort)
CHECKS = {
    "tag_pages_thin": ("crawl", "improvable", "Most tag pages list a single post",
                       "Tags group several posts (at most 20% with one post); weak tag pages are noindex, follow and "
                       "stay out of the sitemap", 3, "M"),
    "sitemap_lists_tag_pages": ("crawl", "not_optimized", "Sitemaps list tag pages",
                                "Sitemaps list posts and real landing pages; tag pages stay out", 3, "S"),
}


TAG_SAMPLE = 2  # tag term pages read live besides the tags list


def _robots_noindex(headers: dict, html: str) -> bool:
    from selectolax.lexbor import LexborHTMLParser

    values = [headers.get("x-robots-tag") or ""]
    values += [m.attributes.get("content") or "" for m in LexborHTMLParser(html).css('meta[name="robots"]')]
    return any("noindex" in v.lower() for v in values)


def tag_robots(get, host: str) -> dict:
    """Do the tag pages tell search engines to stay away? Reads https://<host>/tags/ and up to TAG_SAMPLE tag pages it
    links to. `get(url)` returns (status, headers, html, blocked_by_robots). A page blocked by robots.txt does not count
    as noindex: its noindex is never read (SK, 2026-11-11: thin tags only matter while tag pages are indexable)."""
    from urllib.parse import urljoin, urlsplit

    from selectolax.lexbor import LexborHTMLParser

    pages, list_url = [], f"https://{host}/tags/"
    status, headers, html, blocked = get(list_url)
    pages.append({"url": list_url, "status": status, "blocked": blocked,
                  "noindex": bool(status == 200 and not blocked and _robots_noindex(headers, html))})
    terms = []
    if status == 200 and html:
        for a in LexborHTMLParser(html).css("a[href]"):
            u = urljoin(list_url, a.attributes.get("href") or "")
            path = urlsplit(u).path
            parts = [p for p in path.split("/") if p]
            if urlsplit(u).netloc == host and len(parts) == 2 and parts[0] in ("tag", "tags") and u not in terms:
                terms.append(u)
    for u in terms[:TAG_SAMPLE]:
        status, headers, html, blocked = get(u)
        pages.append({"url": u, "status": status, "blocked": blocked,
                      "noindex": bool(status == 200 and not blocked and _robots_noindex(headers, html))})
    return {"pages": pages, "all_noindex": len(pages) > 1 and all(p["noindex"] for p in pages)}


def findings(tenant: str, host: str, s: dict, fix_channel: str | None = None) -> list[dict]:
    """Findings for one host from its structure numbers (scan + sitemap + search). Scored on the clicks tag pages
    earn (evidence.traffic), not on their share of the host's URLs."""
    from core.findings import FindingIds, make_finding

    ids, out = FindingIds(), []
    search = s.get("search") or {}
    clicks = f"tag pages earned {search.get('tag_clicks', 0):,} of {search.get('clicks', 0):,} clicks (28 days)"
    traffic = {"clicks": search.get("tag_clicks", 0), "impressions": search.get("tag_impressions", 0)}

    def add(check, urls, observed, affected):
        dimension, ftype, title, expected, tier, effort = CHECKS[check]
        f = make_finding(ids=ids, tenant=tenant, subdomain=host, template="tag", dimension=dimension, type=ftype,
                         check=check, title=title, urls=urls, observed=observed, expected=expected,
                         affected_pages=affected, effort=effort, fix_tier=tier, fix_channel=fix_channel)
        f["evidence"]["traffic"] = traffic
        out.append(f)

    tags, one = s.get("tags") or 0, s.get("tags_one_post") or 0
    handled = (s.get("tag_robots") or {}).get("all_noindex")  # thin but out of the index: no search problem
    if tags and one / tags >= THIN_SHARE and not handled:
        pages = s.get("tag_pages_all_languages") or tags
        add("tag_pages_thin", [f"https://{host}/tags/"],
            f"{one:,} of {tags:,} tags ({one / tags:.0%}) have one post; {pages:,} tag pages in "
            f"{s.get('languages', 1)} languages; {s.get('tags_per_post', 0)} tags per post; {clicks}",
            round(pages * one / tags))
    listed = s.get("sitemap_tag_urls") or 0
    if listed:
        total = s.get("sitemap_urls") or 0
        add("sitemap_lists_tag_pages", [f"https://{host}/sitemap.xml"],
            f"{listed:,} of {total:,} sitemap URLs ({listed / total:.0%}) are tag pages; {clicks}" if total else
            f"{listed:,} sitemap URLs are tag pages; {clicks}", listed)
    return out
