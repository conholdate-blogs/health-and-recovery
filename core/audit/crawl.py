"""Crawl auditor: fetch a sample of pages per template and check status, redirects, indexability, canonical,
hreflang, the basic head tags (title, meta description, H1, html lang, viewport) and, for AI readiness, the
text a crawler sees without JavaScript and the presence of structured data.

All checks are deterministic code. Pages come from a discovery inventory run (see core.audit.sample), plus
each host's homepage and the tenant's `audit.extra_urls`. Findings are grouped like discovery findings: per
host, or per section on hosts with configured sections, so one template fix = one finding. Each finding says
how many sampled pages failed per template; `affected_pages` extrapolates that share to the inventory.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from collections import defaultdict, deque
from datetime import date
from urllib.parse import urlsplit, urlunsplit

from core.audit.keep_terms import looks_untranslated
from core.audit.page import parse_page
from core.audit.sample import FULL_MAX, SampledUrl, group_langs, sample_inventory
from core.discovery.classify import LANG_CODES, classify_url, compile_templates
from core.findings import FindingIds, make_finding

AUDITOR = "crawl-audit"
EXAMPLES = 5
MAX_CANONICAL_TARGETS = 50  # distinct canonical targets fetched per run, to show whether they exist
RECENT_RUNS = 3  # the rotating half avoids pages crawled in this many previous runs
COVERAGE_RUNS = 4  # "N of M pages checked in the last COVERAGE_RUNS runs"
TITLE_LEN = (10, 70)  # display width (CJK characters count 2); outside this range is a finding
DESCRIPTION_LEN = (50, 170)
REFRESH_URL_RE = re.compile(r"url\s*=\s*['\"]?([^'\";]+)", re.I)
HREFLANG_RE = re.compile(r"^(x-default|[a-z]{2,3}(-[a-z]{4})?(-([a-z]{2}|\d{3}))?)$", re.I)
SOFT_404_URL_RE = re.compile(r"(^|[/?&=_.-])([a-z]*404|not-?found|notfound|error)([/?&=_.-]|$)", re.I)  # page404
SOFT_404_TITLE_RE = re.compile(r"\b(404|page not found|not found)\b", re.I)
SOFT_404_H1_RE = re.compile(r"\b(page not found|does not exist|error on this page)\b", re.I)  # error text, own title
NO_ZOOM_RE = re.compile(r"user-scalable\s*=\s*(no|0)\b|maximum-scale\s*=\s*1(\.0*)?\b", re.I)
MIN_TEXT_CHARS = 250  # visible characters (no spaces) in the raw HTML below which a page reads as empty to AI crawlers

# check -> (dimension, type, title, expected, fix_tier, effort)
CHECKS = {
    "fetch_error": ("crawl", "broken", "Pages fail to load (network error or timeout)", "HTTP 200", 1, "S"),
    "http_error": ("crawl", "broken", "Pages listed in sitemaps return an HTTP error", "HTTP 200", 1, "S"),
    "robots_blocked": ("crawl", "incorrect", "Sitemaps list pages that robots.txt blocks",
                       "sitemaps list only crawlable pages", 3, "S"),
    "redirected": ("crawl", "not_optimized", "Sitemaps list URLs that redirect",
                   "sitemaps list final URLs that answer HTTP 200", 1, "S"),
    "meta_refresh": ("crawl", "not_optimized", "Sitemaps list meta-refresh redirect pages",
                     "sitemaps list the target URL; moved pages use an HTTP 301", 1, "S"),
    "redirect_chain": ("crawl", "not_optimized", "Redirect chains (2+ hops)", "a single redirect hop", 2, "S"),
    "redirect_temporary": ("crawl", "not_optimized", "Pages redirect with a temporary status (302/307)",
                           "permanent redirects (301/308) for moved URLs", 2, "S"),
    "soft_404": ("crawl", "broken", "Error page served with HTTP 200 (soft 404)",
                 "HTTP 404/410 for missing pages", 2, "M"),
    "noindex": ("crawl", "incorrect", "Pages listed in sitemaps (or homepages) are noindex",
                "only indexable pages in sitemaps; homepages indexable", 3, "S"),
    "canonical_missing": ("crawl", "improvable", "Pages have no canonical tag",
                          "a self-referencing absolute canonical", 2, "S"),
    "canonical_multiple": ("crawl", "incorrect", "Pages declare more than one canonical URL",
                           "exactly one canonical", 2, "S"),
    "canonical_elsewhere": ("crawl", "incorrect", "Sitemap URLs canonicalize to a different URL",
                            "sitemaps list the canonical URL; canonical points to the page itself", 2, "S"),
    "head_closed_early": ("crawl", "broken", "<head> ends early: title, canonical and hreflang land in <body>",
                          "every head tag inside <head>; no <div> or other body element before them", 1, "S"),
    "social_tags_in_body": ("crawl", "not_optimized",
                            "<head> ends early: Open Graph and Twitter tags (and JSON-LD) land in <body>",
                            "every head tag inside <head>; a <div> (e.g. language switcher) only after them", 1, "S"),
    "title_missing": ("onpage", "broken", "Pages have no <title>", "a unique, descriptive title", 1, "S"),
    "title_multiple": ("onpage", "incorrect", "Pages have more than one <title>", "one <title> in <head>", 1, "S"),
    "title_length": ("onpage", "improvable", "Titles are too long or too short",
                     f"{TITLE_LEN[0]}-{TITLE_LEN[1]} characters (CJK count double)", 1, "S"),
    "title_duplicate": ("onpage", "not_optimized", "Different pages share the same title",
                        "a unique title per page and language", 1, "M"),
    "description_missing": ("onpage", "improvable", "Pages have no meta description",
                            "a unique meta description", 1, "S"),
    "description_length": ("onpage", "improvable", "Meta descriptions are too long or too short",
                           f"{DESCRIPTION_LEN[0]}-{DESCRIPTION_LEN[1]} characters (CJK count double)", 1, "S"),
    "description_duplicate": ("onpage", "not_optimized", "Different pages share the same meta description",
                              "a unique meta description per page and language", 1, "M"),
    "title_untranslated": ("intl", "incorrect", "Translated pages keep the English title",
                           "the title in the page's language", 1, "S"),
    "description_untranslated": ("intl", "incorrect", "Translated pages keep the English meta description",
                                 "the meta description in the page's language", 1, "S"),
    "h1_missing": ("onpage", "improvable", "Pages have no H1", "one H1 that states the page topic", 1, "S"),
    "h1_multiple": ("onpage", "improvable", "Pages have more than one H1", "one H1 per page", 1, "S"),
    "hreflang_missing": ("intl", "not_optimized", "Localized pages have no hreflang tags in page HTML",
                         "hreflang alternates for every language version, incl. a self-reference and x-default",
                         2, "M"),
    "hreflang_no_self": ("intl", "incorrect", "hreflang set does not include the page itself",
                         "a self-referencing hreflang entry", 2, "S"),
    "hreflang_invalid": ("intl", "incorrect", "Invalid hreflang codes",
                         "ISO 639-1 language (+ optional ISO 3166-1 region) or x-default", 2, "S"),
    "hreflang_conflict": ("intl", "incorrect", "hreflang lists one language code with different URLs",
                          "one URL per language code", 2, "S"),
    "head_tags_repeated": ("crawl", "improvable", "Canonical/hreflang tags are emitted more than once",
                           "each head tag emitted once", 2, "S"),
    "hreflang_no_xdefault":("intl", "improvable", "hreflang set has no x-default", "an x-default entry", 2, "S"),
    "html_lang_missing": ("intl", "improvable", "Pages have no <html lang> attribute",
                          "<html lang> matching the page language", 1, "S"),
    "html_lang_mismatch": ("intl", "incorrect", "<html lang> does not match the language in the URL",
                           "<html lang> = the URL's language", 1, "S"),
    "viewport_missing": ("ux", "not_optimized", "Pages have no meta viewport",
                         "<meta name=viewport content='width=device-width, initial-scale=1'>", 1, "S"),
    "viewport_no_zoom": ("ux", "not_optimized", "Viewport disables zoom (user-scalable=no or maximum-scale=1)",
                         "zoom allowed (WCAG 1.4.4)", 1, "S"),
    "content_needs_js": ("ai", "incorrect", "Pages show almost no text without JavaScript",
                         f"the main text in the HTML itself (at least {MIN_TEXT_CHARS} characters); AI crawlers "
                         "do not run JavaScript", 2, "M"),
    "no_structured_data": ("ai", "improvable", "Pages have no structured data (JSON-LD)",
                           "JSON-LD naming what the page is (e.g. WebApplication, Article, FAQPage) and who "
                           "publishes it", 2, "S"),
}


def norm_url(url: str) -> str:
    """Lower-case scheme and host, drop the fragment. Path and query are compared exactly."""
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


def display_len(text: str) -> int:
    """Approximate rendered width: East Asian wide/full-width characters count 2, as SERP pixel limits do."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _is_html(rec: dict) -> bool:
    return "html" in (rec.get("content_type") or "").lower()


def page_issues(rec: dict, facts, localized: bool) -> list[tuple[str, str]]:
    """Per-page checks -> [(check, note)]. Duplicate titles/descriptions are checked across pages later."""
    issues: list[tuple[str, str]] = []
    listed = rec["source"] == "sitemap"
    if rec["blocked"]:
        return [("robots_blocked", "disallowed by robots.txt")] if listed else []
    if rec["status"] is None:
        return [("fetch_error", rec["error"] or "no response")]

    hops = list(zip(rec["redirect_statuses"], rec["redirects"], strict=False))
    if hops:
        chain = " -> ".join(f"{s}" for s, _ in hops) + f" -> {rec['final_url']}"
        if listed:
            issues.append(("redirected", f"redirects {chain}"))
        if len(hops) >= 2:
            issues.append(("redirect_chain", f"{len(hops)} hops: {chain}"))
        temporary = [s for s in rec["redirect_statuses"] if s in (302, 303, 307)]
        if temporary:
            issues.append(("redirect_temporary", f"HTTP {temporary[0]} -> {rec['final_url']}"))
    if rec["status"] >= 400:
        return [*issues, ("http_error", f"HTTP {rec['status']}" + (f" at {rec['final_url']}" if hops else ""))]
    if rec["status"] != 200 or facts is None:
        return issues

    title = facts.titles[0] if facts.titles else ""
    h1 = facts.h1[0] if facts.h1 else ""
    final_path = urlsplit(rec["final_url"] or rec["url"])
    if ((hops and SOFT_404_URL_RE.search(final_path.path + "?" + final_path.query))
            or SOFT_404_TITLE_RE.search(title) or SOFT_404_H1_RE.search(h1)):
        issues.append(("soft_404", f"HTTP 200 at {rec['final_url']}, title '{title[:80]}'"
                                   + (f", H1 '{h1[:80]}'" if SOFT_404_H1_RE.search(h1) else "")))
        return issues  # an error page's other tags say nothing about the template

    if facts.refresh and REFRESH_URL_RE.search(facts.refresh):
        target = REFRESH_URL_RE.search(facts.refresh).group(1).strip()
        if listed:
            issues.append(("meta_refresh", f"meta refresh to {target}"))
        return issues  # a redirect stub's own tags say nothing about the template
    # <head> ended early: one root cause. The head checks (title, description, robots, canonical, hreflang,
    # viewport) would fire falsely, so they are skipped on this page; body checks (H1, text, JSON-LD) still run.
    head = not facts.body_head_tags
    if not head:
        issues.append(("head_closed_early", "in <body>: " + ", ".join(facts.body_head_tags + facts.body_social_tags)))
    elif facts.body_social_tags:  # same cause, later in <head>: search tags fine, link previews and template at risk
        issues.append(("social_tags_in_body", "in <body>: " + ", ".join(facts.body_social_tags)))
    # as the check says: only a page a sitemap lists, or a homepage, must be indexable (13 Nov: listing pages 2+,
    # tag and utility pages are noindex on purpose and are sampled through extra_urls or rechecks)
    if head and facts.noindex and (listed or rec["source"] == "homepage"):
        issues.append(("noindex", f"robots: {'; '.join(facts.robots)}"))
    here = norm_url(rec["final_url"] or rec["url"])
    canon = list(dict.fromkeys(norm_url(c) for c in facts.canonicals))
    if not head:
        pass
    elif not canon:
        issues.append(("canonical_missing", "no <link rel=canonical> and no Link header"))
    elif len(canon) > 1:
        issues.append(("canonical_multiple", ", ".join(canon[:3])))
    elif canon[0] != here and not facts.noindex:
        issues.append(("canonical_elsewhere", f"canonical {canon[0]}"))

    if not head:
        pass
    elif not facts.titles:
        issues.append(("title_missing", "no <title> in <head>"))
    else:
        if len(facts.titles) > 1:
            issues.append(("title_multiple", " | ".join(facts.titles[:3])))
        if not TITLE_LEN[0] <= display_len(title) <= TITLE_LEN[1]:
            issues.append(("title_length", f"width {display_len(title)}: '{title[:90]}'"))
    desc = facts.descriptions[0] if facts.descriptions else ""
    if not head:
        pass
    elif not desc:
        issues.append(("description_missing", "no meta description" if not facts.descriptions else "empty"))
    elif not DESCRIPTION_LEN[0] <= display_len(desc) <= DESCRIPTION_LEN[1]:
        issues.append(("description_length", f"width {display_len(desc)}: '{desc[:90]}'"))
    h1 = [h for h in facts.h1 if h]
    if not h1:
        issues.append(("h1_missing", "no non-empty <h1>"))
    elif len(h1) > 1:
        issues.append(("h1_multiple", f"{len(h1)} H1s: " + " | ".join(h[:40] for h in h1[:3])))

    # search engines ignore hreflang on a noindex page (13 Nov 2026: listing pages 2+ repeat page 1's set)
    if facts.hreflang and not facts.noindex:
        codes = [c for c, _ in facts.hreflang]
        bad = sorted({c for c in codes if not HREFLANG_RE.match(c)})
        if bad:
            issues.append(("hreflang_invalid", ", ".join(bad[:5])))
        # x-default does not count as the self-reference: the page needs an entry for its own language
        targets = {norm_url(h) for c, h in facts.hreflang if c.lower() != "x-default"}
        if here not in targets and not (canon and canon[0] in targets):
            own = sorted({c for c in set(codes) if c.lower() != "x-default"})
            issues.append(("hreflang_no_self", f"{len(own)} languages ({', '.join(own[:8])}"
                                               f"{', ...' if len(own) > 8 else ''}), none points to {here}"))
        by_code: dict = defaultdict(set)
        for c, h in facts.hreflang:
            by_code[c.lower()].add(norm_url(h))
        conflicts = sorted(c for c, hs in by_code.items() if len(hs) > 1)
        if conflicts:
            issues.append(("hreflang_conflict", f"codes with 2+ URLs: {', '.join(conflicts[:5])}"))
    if facts.head_canonicals > 1 or len(facts.hreflang) > len(set(facts.hreflang)):
        issues.append(("head_tags_repeated", f"{facts.head_canonicals} canonical tags, {len(facts.hreflang)} "
                                             f"hreflang tags for {len(set(facts.hreflang))} distinct"))
    if facts.hreflang and not facts.noindex:
        if not any(c.lower() == "x-default" for c in codes):
            issues.append(("hreflang_no_xdefault", f"{len(codes)} entries: {', '.join(codes[:6])}"))
    elif head and localized and not facts.noindex:
        issues.append(("hreflang_missing", "no <link rel=alternate hreflang> in <head>"))

    if not facts.html_lang:
        issues.append(("html_lang_missing", "no lang attribute on <html>"))
    elif rec["lang"] and facts.html_lang.lower().split("-")[0] != rec["lang"].split("-")[0]:
        issues.append(("html_lang_mismatch", f"URL language {rec['lang']}, <html lang='{facts.html_lang}'>"))

    if not head:
        pass
    elif facts.viewport is None:
        issues.append(("viewport_missing", "no meta viewport"))
    elif NO_ZOOM_RE.search(facts.viewport):
        issues.append(("viewport_no_zoom", facts.viewport))

    if not facts.noindex:  # AI readiness: what an answer engine can read and attribute
        if facts.text_chars is not None and facts.text_chars < MIN_TEXT_CHARS:
            issues.append(("content_needs_js", f"{facts.text_chars} characters of main text in the HTML"))
        if not facts.jsonld_types:
            issues.append(("no_structured_data", f"{facts.jsonld_invalid} JSON-LD blocks, none valid"
                           if facts.jsonld_invalid else "no JSON-LD"))
    return issues


def untranslated_issues(pages: list[dict], field: str, check: str, default_lang: str = "en",
                        keep_terms: list[str] | None = None) -> None:
    """Add `check` to translated pages whose title/description is the English page's, word for word (2026-11-12:
    blog.conholdate.cloud's 22 translated home pages kept the English <title>; the LLM text check noticed 2). The
    English page is the page's own hreflang entry for the default language (or x-default), when it was crawled.
    Words a translation keeps in English (product and brand names, formats, platforms, the host's labels:
    core/audit/keep_terms.py) do not count; fewer than 3 others and the value may rightly stay the same."""
    by_url = {norm_url(p["final_url"] or p["url"]): p for p in pages if p.get("facts") and p["status"] == 200}
    for p in pages:
        f = p.get("facts")
        if not f or p["status"] != 200 or not p["lang"] or p["lang"] == default_lang \
                or any("noindex" in r for r in f.get("robots") or []):
            continue
        refs = {c.lower(): h for c, h in f.get("hreflang") or []}
        en_url = refs.get(default_lang) or refs.get("x-default")
        en = by_url.get(norm_url(en_url)) if en_url else None
        if not en or en is p or not f[field] or not en["facts"][field]:
            continue
        value = f[field][0]
        if value == en["facts"][field][0] and looks_untranslated(value, p["host"], keep_terms):
            p["issues"].append((check, f"same as {en['url']}: '{value[:70]}'"))


def duplicate_issues(pages: list[dict], field: str, check: str) -> None:
    """Add `check` to pages that share a title/description with another page of the same host and language.
    Pages that canonicalize to the same URL are not duplicates of each other, and a noindex page is in no search
    index, so it competes with nothing (13 Nov 2026: blog.conholdate.com's tag pages, noindex, reuse the home
    description)."""
    seen: dict = defaultdict(list)
    for p in pages:
        f = p.get("facts")
        if not f or p["status"] != 200 or any(c == "soft_404" for c, _ in p["issues"]) or not f[field] \
                or any("noindex" in r for r in f.get("robots") or []):
            continue
        value = f[field][0]
        target = norm_url(f["canonicals"][0]) if f["canonicals"] else norm_url(p["final_url"] or p["url"])
        seen[(p["host"], p["lang"] or "", value)].append((p, target))
    for (_, _, value), items in seen.items():
        if len({t for _, t in items}) < 2:
            continue
        for p, target in items:
            others = [q["url"] for q, t in items if t != target][:2]
            if others:
                p["issues"].append((check, f"'{value[:60]}' also on {', '.join(others)}"))


class CrawlAudit:
    def __init__(self, tenant, fetcher, inventory_db, inventory_run: int, store, hosts=None, sections=None,
                 per_template=2, other_langs=2, max_per_host=None, max_pages=None, search_pages=None, log=print):
        self.tenant = tenant
        self.fetcher = fetcher
        self.inventory_db = inventory_db
        self.inventory_run = inventory_run
        self.store = store
        self.hosts = [h for h in tenant.host_names if not hosts or h in hosts]
        self.sections = sections
        self.per_template, self.other_langs, self.max_per_host = per_template, other_langs, max_per_host
        self.max_pages = max_pages
        self.search_pages = search_pages or []  # [{'page', 'clicks'}]: fills sections that no sitemap covers
        self.log = log or (lambda *_: None)
        raw = tenant.raw
        self.sectioned = set((raw.get("discovery") or {}).get("section_sitemaps") or {})
        self.templates = {h: compile_templates(specs) for h, specs in (raw.get("url_templates") or {}).items()}
        self.lang_codes = frozenset(raw["languages"]) if raw.get("languages") else LANG_CODES
        self.fix_channels = {h["host"]: h.get("fix_channel") for h in tenant.hosts}
        self.audit_cfg = raw.get("audit") or {}
        self.pages: list[dict] = []
        self.run_id: int | None = None
        self.stopped_early = False
        self.target_status: dict = {}  # canonical target -> 'HTTP 404' / 'HTTP 200' / error
        self._parents: dict = {}

    def _section(self, host: str, section: str) -> str:
        return section if host in self.sectioned else ""

    def _sections_for(self, host: str) -> list[str]:
        cfg = ((self.tenant.raw.get("discovery") or {}).get("section_sitemaps") or {}).get(host) or {}
        src = cfg.get("sections") or []
        return [str(x) for x in (self.tenant.raw.get(src, []) if isinstance(src, str) else src)]

    def _classified(self, url: str, source: str) -> SampledUrl:
        host = urlsplit(url).netloc.lower()
        c = classify_url(url, self.templates.get(host, ()), self.lang_codes)
        return SampledUrl(url, host, self._section(host, c.section), c.lang, c.template, 1, source)

    def targets(self) -> list[SampledUrl]:
        sample = sample_inventory(self.inventory_db, self.inventory_run, self.hosts, self.sectioned, self.sections,
                                  self.per_template, self.other_langs, self.audit_cfg.get("default_lang", "en"),
                                  self.max_per_host, self.audit_cfg.get("per_template_by_host"),
                                  self.audit_cfg.get("full_crawl_max_urls", FULL_MAX),
                                  salt=date.today().isoformat(), seen=self.recent_urls(), dates=self.post_dates())
        seen = {s.url for s in sample}
        for url in self.recheck_urls():  # pages that failed last run: verify each fix page by page
            if url not in seen:
                seen.add(url)
                c = self._classified(url, "recheck")
                if self.sections is None or not c.section or c.section in self.sections:
                    sample.append(c)
        extra = [f"https://{h}/" for h in self.hosts]  # homepages always, also with a section filter
        for host, paths in (self.audit_cfg.get("section_urls") or {}).items():
            if host in self.hosts:  # pages per section that no sitemap lists (e.g. hub pages)
                extra += [f"https://{host}{path.format(section=sec)}" for sec in self._sections_for(host)
                          for path in paths]
        extra += [u for u in self.audit_cfg.get("extra_urls") or []
                  if urlsplit(u).netloc.lower() in self.hosts and not self.tenant.is_excluded(urlsplit(u).netloc)]
        for url in extra:
            if url not in seen:
                seen.add(url)
                c = self._classified(url, "homepage" if urlsplit(url).path in ("", "/") else "extra")
                if self.sections is None or not c.section or c.section in self.sections:
                    sample.append(c)
        for t in self._search_fill({(s.host, s.section) for s in sample if s.source == "sitemap"}):
            if t.url not in seen:
                seen.add(t.url)
                sample.append(t)
        return sample

    def _previous_runs(self, n: int) -> list[int]:
        rows = self.store.db.execute("SELECT id FROM runs WHERE tenant = ? AND auditor = ? AND finished_at IS NOT NULL "
                                     "ORDER BY id DESC LIMIT ?", (self.tenant.property, AUDITOR, n)).fetchall()
        return [r[0] for r in rows]

    def recent_urls(self) -> set:
        """URLs crawled in the last RECENT_RUNS runs: the rotating half of the sample looks elsewhere first."""
        runs = self._previous_runs(RECENT_RUNS)
        if not runs:
            return set()
        q = f"SELECT DISTINCT url FROM pages WHERE run_id IN ({', '.join('?' * len(runs))})"
        return {r[0] for r in self.store.db.execute(q, runs)}

    def recheck_urls(self) -> list[str]:
        """Pages of this run's hosts that had an issue in the previous run (crawled again, not counted in the sample
        share: a page picked because it failed would inflate the estimate)."""
        runs = self._previous_runs(1)
        if not runs:
            return []
        rows = self.store.db.execute("SELECT url, host FROM pages WHERE run_id = ? AND issues NOT IN ('[]', 'null') "
                                     "AND (ignored IS NULL OR ignored = '')", runs).fetchall()
        return sorted(u for u, h in rows if h in self.hosts)

    def post_dates(self) -> dict[str, str]:
        from pathlib import Path

        from core.audit.postdates import post_dates

        out: dict = {}
        for h in self.tenant.hosts:
            if h["host"] in self.hosts and h.get("local_path") and Path(h["local_path"]).is_dir():
                out.update(post_dates(Path(h["local_path"]), h["host"]))
        return out

    def coverage(self) -> dict:
        """Per host: distinct inventory URLs crawled in this run and the previous COVERAGE_RUNS - 1 runs."""
        runs = [self.run_id, *[r for r in self._previous_runs(COVERAGE_RUNS) if r != self.run_id]][:COVERAGE_RUNS]
        q = (f"SELECT p.host, COUNT(DISTINCT p.url) FROM pages p JOIN urls_now u ON u.url = p.url "
             f"WHERE p.run_id IN ({', '.join('?' * len(runs))}) GROUP BY p.host")
        inv = self.inventory_db.execute("SELECT url, host FROM urls WHERE run_id = ?", (self.inventory_run,)).fetchall()
        totals: dict = defaultdict(int)
        for _, h in inv:
            totals[h] += 1
        self.store.db.execute("CREATE TEMP TABLE IF NOT EXISTS urls_now (url TEXT PRIMARY KEY)")
        self.store.db.execute("DELETE FROM urls_now")
        self.store.db.executemany("INSERT OR IGNORE INTO urls_now VALUES (?)", [(u,) for u, _ in inv])
        checked = dict(self.store.db.execute(q, runs).fetchall())
        return {h: {"checked": checked.get(h, 0), "urls": totals.get(h, 0), "runs": len(runs)}
                for h in self.hosts if totals.get(h)}

    def _search_fill(self, covered: set) -> list[SampledUrl]:
        """Sections with no sitemap URLs: sample their top search pages per template instead (source 'search')."""
        missing = {(h, sec) for h in self.hosts if h in self.sectioned for sec in self._sections_for(h)
                   if (self.sections is None or sec in self.sections) and (h, sec) not in covered}
        if not missing or not self.search_pages:
            return []
        groups: dict = defaultdict(list)
        for r in self.search_pages:
            c = self._classified(r["page"], "search")
            if (c.host, c.section) in missing:
                groups[(c.host, c.section, c.template)].append((r.get("clicks", 0), c))
        out = []
        for (_host, _sec, _tmpl), items in sorted(groups.items()):
            items.sort(key=lambda x: (-x[0], x[1].url))
            out += [SampledUrl(c.url, c.host, c.section, c.lang, c.template, len(items), "search")
                    for _, c in items[: self.per_template + self.other_langs]]
        return out

    def _fetch(self, t: SampledUrl) -> dict:
        res = self.fetcher.get(t.url)
        rec = {
            "url": t.url, "host": t.host, "section": t.section, "lang": t.lang, "template": t.template,
            "source": t.source, "group_urls": t.group_urls, "listed_in": t.sitemap,
            "status": res.status, "final_url": res.final_url,
            "redirects": res.redirects, "redirect_statuses": res.redirect_statuses, "content_type": res.content_type,
            "bytes": len(res.body), "truncated": int(res.truncated), "blocked": int(res.blocked_by_robots),
            "error": res.error, "elapsed_ms": res.elapsed_ms, "facts": None,
        }
        facts = None
        if res.status == 200 and _is_html(rec):
            facts = parse_page(res.body, res.final_url or t.url, res.headers)
            rec["facts"] = facts.to_dict()
        rec["ignored"] = self._ignored(rec)
        rec["issues"] = [] if rec["ignored"] else page_issues(rec, facts, self._localized(t.host, t.section))
        return rec

    def _ignored(self, rec: dict) -> str | None:
        """Reason if the page matches a tenant `audit.ignore_pages` rule (host, status, path_prefix), else None."""
        path = urlsplit(rec["url"]).path
        for rule in self.audit_cfg.get("ignore_pages") or []:
            if (rule.get("host") in (None, rec["host"]) and rule.get("status") in (None, rec["status"])
                    and path.startswith(rule.get("path_prefix", "/"))):
                return rule.get("reason") or "ignored by tenant rule"
        return None

    def _check_canonical_targets(self) -> None:
        """Fetch each distinct foreign canonical target once and add its status to the issue notes."""
        targets = []
        for p in self.pages:
            if any(c == "canonical_elsewhere" for c, _ in p["issues"]):
                t = norm_url(p["facts"]["canonicals"][0])
                if t not in targets:
                    targets.append(t)
        for t in targets[:MAX_CANONICAL_TARGETS]:
            res = self.fetcher.get(t)
            status = f"HTTP {res.status}" if res.status else (res.error or "no response")
            if res.redirects and res.final_url:
                status += f" via redirect to {res.final_url}"
            self.target_status[t] = status
        for p in self.pages:
            p["issues"] = [(c, f"{n} ({self.target_status[norm_url(p['facts']['canonicals'][0])]})")
                           if c == "canonical_elsewhere" and norm_url(p["facts"]["canonicals"][0]) in self.target_status
                           else (c, n) for c, n in p["issues"]]

    def _parent(self, sitemap: str) -> str | None:
        """The sitemap index that lists `sitemap`, from the inventory."""
        if sitemap not in self._parents:
            row = self.inventory_db.execute("SELECT parent FROM sitemaps WHERE run_id = ? AND url = ?",
                                            (self.inventory_run, sitemap)).fetchone()
            self._parents[sitemap] = row[0] if row else None
        return self._parents[sitemap]

    def locations(self, check: str, items: list) -> list[dict]:
        """Clickable evidence: the pages, the sitemap files that list them and the index above those, and
        for a foreign canonical the target URL with its status."""
        locs: list[dict] = []
        seen: set = set()

        def add(role, url, note=None):
            if url and (role, url) not in seen:
                seen.add((role, url))
                locs.append({"role": role, "url": url, **({"note": note} if note else {})})

        examples = items[:EXAMPLES]
        for p, note in examples:
            add("page", p["url"], note[:200])
        for p, _ in examples:
            if p.get("listed_in"):
                add("listed in", p["listed_in"])
                add("sitemap index", self._parent(p["listed_in"]))
        if check == "canonical_elsewhere":
            for p, _ in examples:
                t = norm_url(p["facts"]["canonicals"][0])
                add("canonical target", t, self.target_status.get(t))
        return locs

    def _localized(self, host: str, section: str) -> bool:
        return len(self.langs.get((host, section), set())) > 1

    def run(self) -> dict:
        started = time.monotonic()
        params = {"hosts": self.hosts, "sections": self.sections, "inventory_run": self.inventory_run,
                  "per_template": self.per_template, "other_langs": self.other_langs,
                  "max_per_host": self.max_per_host, "max_pages": self.max_pages}
        self.run_id = self.store.start_run(self.tenant.property, AUDITOR, params)
        self.langs = group_langs(self.inventory_db, self.inventory_run, self.sectioned)
        targets = self.targets()
        self.log(f"{len(targets)} pages to fetch on {len({t.host for t in targets})} hosts")

        # Round-robin across hosts: the per-host rate limit then overlaps instead of adding up.
        queues: dict = defaultdict(deque)
        for t in targets:
            queues[t.host].append(t)
        while any(queues.values()):
            for host in list(queues):
                if not queues[host]:
                    continue
                if self.max_pages is not None and len(self.pages) >= self.max_pages:
                    self.stopped_early = True
                    break
                rec = self._fetch(queues[host].popleft())
                self.pages.append(rec)
                self.log(f"[{len(self.pages)}/{len(targets)}] {rec['status'] or rec['error']}  {rec['url']}  "
                         f"issues={len(rec['issues'])}")
            if self.stopped_early:
                break

        self._check_canonical_targets()
        duplicate_issues(self.pages, "titles", "title_duplicate")
        duplicate_issues(self.pages, "descriptions", "description_duplicate")
        default_lang = self.audit_cfg.get("default_lang", "en")
        keep = (self.audit_cfg.get("translation") or {}).get("keep_terms")
        untranslated_issues(self.pages, "titles", "title_untranslated", default_lang, keep)
        untranslated_issues(self.pages, "descriptions", "description_untranslated", default_lang, keep)
        for rec in self.pages:
            self.store.add_page(self.run_id, rec)

        report = {"tenant": self.tenant.property, "auditor": AUDITOR, "run_id": self.run_id, "params": params,
                  "canonical_targets": self.target_status,
                  "requests": self.fetcher.requests, "duration_s": round(time.monotonic() - started, 1),
                  "pages_planned": len(targets), "stopped_early": self.stopped_early, "summary": self.summary(),
                  "recheck": sum(p.get("source") == "recheck" for p in self.pages), "coverage": self.coverage()}
        report["findings"] = self.findings()
        self.store.finish_run(self.run_id, {k: v for k, v in report.items() if k != "findings"})
        report["pages"] = self.pages
        return report

    def summary(self) -> dict:
        return summarize_pages(self.pages)

    def blocked_in_inventory(self, host: str, section: str) -> int:
        """Sitemap URLs robots.txt blocks, counted exactly: the sample favours the default language, so scaling it
        up misleads when a rule hits one language (one blog's /tag/: 2,523 URLs, not the sample's 39,579)."""
        sql, args = "SELECT url FROM urls WHERE run_id = ? AND host = ?", [self.inventory_run, host]
        if section:
            sql, args = sql + " AND section = ?", args + [section]
        return sum(not self.fetcher.allowed(u) for (u,) in self.inventory_db.execute(sql, args))

    def findings(self) -> list[dict]:
        ids = FindingIds()
        sampled: dict = defaultdict(int)  # (host, section, template) -> sampled pages
        group_size: dict = {}
        for p in self.pages:
            if p.get("ignored") or p.get("source") == "recheck":
                continue  # excluded from the sample: neither a failure nor a pass (a recheck is not a random pick)
            g = (p["host"], p["section"], p["template"])
            sampled[g] += 1
            group_size[g] = max(group_size.get(g, 0), p["group_urls"])

        hits: dict = defaultdict(list)  # (check, host, section) -> [(page, note)]
        for p in self.pages:
            for check, note in p["issues"]:
                hits[(check, p["host"], p["section"])].append((p, note))

        out = []
        for (check, host, section), items in sorted(hits.items()):
            dimension, ftype, title, expected, tier, effort = CHECKS[check]
            per_template: dict = defaultdict(int)
            rechecked = 0
            for p, _ in items:
                if p.get("source") == "recheck" or (p["host"], p["section"], p["template"]) not in sampled:
                    rechecked += 1
                else:
                    per_template[p["template"]] += 1
            in_scope = sum(n for (h, s, _), n in sampled.items() if h == host and s == section)
            estimate = max(len(items), sum(round(group_size[(host, section, t)] * n / sampled[(host, section, t)])
                                           for t, n in per_template.items()))
            tmpl = ", ".join(f"{t} {n}/{sampled[(host, section, t)]}" for t, n in sorted(per_template.items()))
            examples = "; ".join(f"{p['url']}: {note}" for p, note in items[:EXAMPLES])
            full = all(n >= group_size[g] for g, n in sampled.items() if g[0] == host and g[1] == section)
            kind = "pages (every sitemap URL crawled)" if full else "sampled pages"
            observed = (f"{len(items) - rechecked} of {in_scope} {kind} (by template: {tmpl or '-'})"
                        + (f"; {rechecked} more among pages rechecked because they failed last run" if rechecked
                           else "") + f". e.g. {examples}")
            if check == "robots_blocked":
                estimate = self.blocked_in_inventory(host, section)
                observed += f". Exact count from the sitemaps: {estimate}"
            where = f" (/{section}/)" if section else ""
            finding = make_finding(
                ids=ids, tenant=self.tenant.property, subdomain=host, template=f"page:{section}" if section else "page",
                dimension=dimension, type=ftype, check=check, title=title + where,
                urls=[p["url"] for p, _ in items[:10]], observed=observed, expected=expected,
                affected_pages=estimate, effort=effort, fix_tier=tier, fix_channel=self.fix_channels.get(host))
            # structured sample per template, used by the Prioritizer: {template: [failed, sampled]}
            finding["evidence"]["locations"] = self.locations(check, items)
            finding["evidence"]["sample"] = {t: [n, sampled[(host, section, t)]]
                                             for t, n in sorted(per_template.items())}
            out.append(finding)
        return out


def summarize_pages(pages: list[dict]) -> dict:
    """Per-host counts (pages, HTML 200, errors, redirected, blocked, ignored) and issue counts per check."""
    out: dict = {}
    for p in pages:
        h = out.setdefault(p["host"], {"pages": 0, "ok_html": 0, "errors": 0, "redirected": 0, "blocked": 0,
                                       "ignored": 0, "issues": defaultdict(int)})
        h["pages"] += 1
        if p.get("ignored"):
            h["ignored"] += 1
            continue
        h["ok_html"] += int(p["facts"] is not None)
        h["errors"] += int(p["status"] is None and not p["blocked"] or (p["status"] or 0) >= 400)
        h["redirected"] += int(bool(p["redirects"]))
        h["blocked"] += p["blocked"]
        for check, _ in p["issues"]:
            h["issues"][check] += 1
    return {host: {**h, "issues": dict(sorted(h["issues"].items()))} for host, h in out.items()}


def latest_inventory_run(db) -> int | None:
    """Latest finished full discovery run: no section filter and not stopped early."""
    for run_id, params in db.execute("SELECT id, params FROM runs WHERE finished_at IS NOT NULL ORDER BY id DESC"):
        p = json.loads(params or "{}")
        if not p.get("sections") and p.get("max_sitemaps") is None:
            return run_id
    return None


def audit(tenant, fetcher, inventory_db, inventory_run, store, **kw) -> dict:
    return CrawlAudit(tenant, fetcher, inventory_db, inventory_run, store, **kw).run()


def import_report(findings_store, report: dict) -> dict:
    """Record a crawl-audit report in the findings store. A run stopped early resolves nothing."""
    params = report["params"]
    hosts = [] if report.get("stopped_early") else params["hosts"]
    # A section filter narrows only sectioned hosts: findings without a section (other hosts, homepages)
    # were fully re-checked, so they may resolve too.
    return findings_store.import_run(report["findings"], f"{AUDITOR}-run{report['run_id']}", AUDITOR,
                                     hosts=hosts, sections=params.get("sections"), resolve_unsectioned=True)
