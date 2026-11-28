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
    "section_lists_home_posts": ("crawl", "not_optimized", "Section page repeats the home page's post list",
                                 "With one main section, its section page is noindex, follow and out of the sitemap",
                                 3, "S"),
    "taxonomy_feeds_built": ("crawl", "improvable", "Tag and category pages build RSS feeds",
                             "Tag and category pages are HTML only (config outputs: taxonomy and term [HTML]); the "
                             "home and section feeds stay", 3, "S"),
    "url_junk_served": ("crawl", "not_optimized", "Junk URLs Google knows still answer 200",
                        "URLs left by old translations and broken generators (translated or escaped tag names, "
                        "placeholders, double slashes, dropped feeds) answer 404, or 301 to the right page", 3, "M"),
}


# ---- feeds of taxonomy pages (Shoaib Khan, 28 Nov 2026: a feed per tag and language is junk) ----

FEED_KINDS = ("taxonomy", "term")  # taxonomy = /tags/, /categories/; term = /tag/<name>/, /categories/<name>/


def taxonomy_feeds(repo: Path) -> dict:
    """Which taxonomy page kinds build an RSS feed, from `outputs` in config.yml (a config-production.yml, when it
    sets outputs, wins). Hugo's default for both kinds is HTML + RSS, so a kind missing from `outputs` builds one."""
    import yaml

    outputs, source = None, None
    for name in ("config-production.yml", "config.yml"):
        try:
            cfg = yaml.safe_load((repo / name).read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(cfg.get("outputs"), dict):
            outputs, source = {str(k).lower(): v for k, v in cfg["outputs"].items()}, name
            break
    out = {"config": source or "config.yml"}
    outputs = dict(outputs or {})
    if "taxonomyterm" in outputs:  # pre-0.73 names: Hugo reads the whole block the old way (blog.conholdate.cloud
        # 28 Nov, build-checked): "taxonomy" = term pages, "taxonomyTerm" = the /tags/ list
        legacy_term = outputs.pop("taxonomy", None)
        outputs["taxonomy"] = outputs.pop("taxonomyterm")
        if legacy_term is not None:
            outputs.setdefault("term", legacy_term)
    for kind in FEED_KINDS:
        value = outputs.get(kind)
        formats = [str(v).lower() for v in value] if isinstance(value, list) else None
        out[kind] = formats is None or "rss" in formats
    return out


# ---- junk URLs Google knows (Shoaib Khan, 28 Nov 2026: "cover such dumb urls from earlier translations") ----

# Search Console regex (RE2) for candidates; junk_kind() decides. Encoded as Search Console reports them.
JUNK_GSC_REGEX = r"%5[Cc]|%22|%[89A-Fa-f][0-9A-Fa-f]|%7[Bb]%7[Bb]|[^:]//|/(tags?|categor(y|ies))/[^/]+/index\.xml"
_NON_ASCII = re.compile(r"%[89A-Fa-f][0-9A-Fa-f]")
_TAX_FEED = re.compile(r"/(tags?|categor(?:y|ies))/[^/]+/index\.xml$")
JUNK_LIVE_CAP = 400  # URLs fetched per run, most impressions first
JUNK_KINDS = {"escaped": "escaped name (\\ or \")", "non_english": "non-English characters",
              "placeholder": "template placeholder", "double_slash": "double slash", "taxonomy_feed": "tag feed"}


def junk_kind(url: str, feeds_built: bool = True) -> str | None:
    """Why a URL is junk, or None. Every post, tag and category URL is English (rule URL-1), so any non-ASCII
    character is junk; a tag or category feed counts only once the blog stopped building them."""
    from urllib.parse import urlsplit

    path = urlsplit(url).path
    up = path.upper()
    if "%5C" in up or "%22" in up or "\\" in path or '"' in path:
        return "escaped"
    if "%7B%7B" in up or "{{" in path:
        return "placeholder"
    if _NON_ASCII.search(path) or any(ord(c) > 127 for c in path):
        return "non_english"
    if "//" in path:
        return "double_slash"
    if not feeds_built and _TAX_FEED.search(path):
        return "taxonomy_feed"
    return None


def _norm(url: str) -> str:
    from urllib.parse import unquote

    return unquote(url).rstrip("/").lower()


def junk_live(get, rows: list[dict], feeds_built: bool = True, cap: int = JUNK_LIVE_CAP,
              sitemap_urls: set[str] | None = None) -> dict:
    """Fetch the junk URLs among Search Console page rows ({page, clicks, impressions}), most impressions first.
    `get(url)` returns (status, headers, html, blocked); a redirect counts as 301. A URL the sitemaps list is a real
    page, not junk (blog.groupdocs.cloud 28 Nov: 2017 newsletter posts with an en dash in the slug)."""
    real = {_norm(u) for u in sitemap_urls or ()}
    junk = [dict(r, kind=k) for r in rows if (k := junk_kind(r["page"], feeds_built)) and _norm(r["page"]) not in real]
    junk.sort(key=lambda r: (-r.get("impressions", 0), r["page"]))
    by_kind: dict = {}
    served = []
    for i, r in enumerate(junk):
        k = by_kind.setdefault(r["kind"], {"urls": 0, "clicks": 0, "impressions": 0, "live": {}})
        k["urls"] += 1
        k["clicks"] += r.get("clicks", 0)
        k["impressions"] += r.get("impressions", 0)
        if i >= cap:
            continue
        status = get(r["page"])[0]
        k["live"][str(status)] = k["live"].get(str(status), 0) + 1
        if status == 200:
            served.append({"page": r["page"], "kind": r["kind"], "clicks": r.get("clicks", 0),
                           "impressions": r.get("impressions", 0)})
    return {"urls": len(junk), "checked": min(len(junk), cap), "by_kind": by_kind, "served": served}


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
    # A tag page that does not answer 200 (blog.groupdocs.cloud 26 Nov: slugs starting with a dot, `/tag/.net-…/`,
    # 404 or 301 live) says nothing about the robots of the others: read on until TAG_SAMPLE pages answer 200.
    read = 0
    for u in terms[:TAG_SAMPLE * 5]:
        status, headers, html, blocked = get(u)
        pages.append({"url": u, "status": status, "blocked": blocked,
                      "noindex": bool(status == 200 and not blocked and _robots_noindex(headers, html))})
        read += status == 200 or blocked
        if read >= TAG_SAMPLE:
            break
    answered = [p for p in pages if p["status"] == 200 or p["blocked"]]  # blocked: its noindex is never read
    return {"pages": pages, "all_noindex": len(answered) > 1 and all(p["noindex"] for p in answered)}


def main_sections(repo: Path) -> list[str]:
    """params.mainSections from the repo's config.yml."""
    import yaml

    try:
        cfg = yaml.safe_load((repo / "config.yml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    return [str(x) for x in ((cfg.get("params") or {}).get("mainSections") or [])]


def section_robots(get, host: str, repo: Path) -> dict:
    """With one main section the section page lists exactly the home page's posts (13 Nov 2026, blog.conholdate.com
    and blog.conholdate.cloud): read it live and say whether it tells search engines to stay away."""
    sections = main_sections(repo)
    if len(sections) != 1:
        return {"sections": sections}
    url = f"https://{host}/{sections[0].lower()}/"
    status, headers, html, blocked = get(url)
    return {"sections": sections, "url": url, "status": status,
            "noindex": bool(status == 200 and not blocked and _robots_noindex(headers, html))}


def findings(tenant: str, host: str, s: dict, fix_channel: str | None = None) -> list[dict]:
    """Findings for one host from its structure numbers (scan + sitemap + search). Scored on the clicks tag pages
    earn (evidence.traffic), not on their share of the host's URLs."""
    from core.findings import FindingIds, make_finding

    ids, out = FindingIds(), []
    search = s.get("search") or {}
    clicks = f"tag pages earned {search.get('tag_clicks', 0):,} of {search.get('clicks', 0):,} clicks (28 days)"
    traffic = {"clicks": search.get("tag_clicks", 0), "impressions": search.get("tag_impressions", 0)}

    def add(check, urls, observed, affected, template="tag", traffic=traffic):
        dimension, ftype, title, expected, tier, effort = CHECKS[check]
        f = make_finding(ids=ids, tenant=tenant, subdomain=host, template=template, dimension=dimension, type=ftype,
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
    sec = s.get("section_robots") or {}
    if sec.get("url") and sec.get("status") == 200 and not sec.get("noindex"):
        add("section_lists_home_posts", [sec["url"]],
            f"one main section ({sec['sections'][0]}): {sec['url']} lists the same posts as the home page and is "
            f"indexable, in {s.get('languages', 1)} languages", s.get("languages", 1))
    feeds = s.get("taxonomy_feeds") or {}
    if feeds.get("term") or feeds.get("taxonomy"):
        langs = s.get("languages", 1)
        files = ((s.get("tag_pages_all_languages") or 0) + (s.get("categories") or 0) * langs) if feeds.get("term") \
            else 0
        files += 2 * langs if feeds.get("taxonomy") else 0
        kinds = " and ".join(k for k in ("term", "taxonomy") if feeds.get(k))
        add("taxonomy_feeds_built", [f"https://{host}/tags/index.xml"],
            f"{feeds.get('config')} outputs build an RSS feed for {kinds} pages: about {files:,} feed files "
            f"(each tag and category in {langs} languages), linked from every tag page", files, template="feed")
    junk = s.get("known_junk") or {}
    served = junk.get("served") or []
    if served:
        kinds = ", ".join(f"{JUNK_KINDS.get(k, k)} {sum(1 for x in served if x['kind'] == k)}"
                          for k in sorted({x["kind"] for x in served}))
        add("url_junk_served", [x["page"] for x in served[:20]],
            f"{len(served):,} of {junk.get('checked', 0):,} junk URLs Search Console knows ({junk.get('window')}) "
            f"answer 200: {kinds}", len(served), template="junk",
            traffic={"clicks": sum(x["clicks"] for x in served),
                     "impressions": sum(x["impressions"] for x in served)})
    return out
