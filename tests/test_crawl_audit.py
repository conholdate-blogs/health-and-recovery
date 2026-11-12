"""Offline tests for the crawl auditor: page parsing, per-page checks, sampling and a full run."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.audit.crawl import audit, import_report, latest_inventory_run, page_issues  # noqa: E402
from core.audit.page import parse_page  # noqa: E402
from core.audit.sample import sample_inventory  # noqa: E402
from core.audit.store import AuditStore  # noqa: E402
from core.discovery.fetch import FetchResult  # noqa: E402
from core.discovery.store import InventoryStore  # noqa: E402
from core.findings import FindingsStore  # noqa: E402
from core.tenant import Tenant  # noqa: E402

DESC = "A meta description that is long enough to pass the length check easily."


def html(title="Convert PDF files online", canonical=None, hreflang=(), lang="en", h1=("Convert PDF",),
         desc="auto", viewport="width=device-width, initial-scale=1", robots=None) -> bytes:
    head = [f"<title>{title}</title>" if title is not None else ""]
    desc = f"{title}: {DESC}" if desc == "auto" else desc
    if desc is not None:
        head.append(f'<meta name="description" content="{desc}">')
    if canonical:
        head.append(f'<link rel="canonical" href="{canonical}">')
    head += [f'<link rel="alternate" hreflang="{c}" href="{h}">' for c, h in hreflang]
    if viewport is not None:
        head.append(f'<meta name="viewport" content="{viewport}">')
    if robots:
        head.append(f'<meta name="robots" content="{robots}">')
    head.append('<script type="application/ld+json">{"@type": "WebApplication"}</script>')
    body = "".join(f"<h1>{h}</h1>" for h in h1) + "<main>" + "Convert your files online for free. " * 10 + "</main>"
    lang_attr = f' lang="{lang}"' if lang else ""
    return f"<!doctype html><html{lang_attr}><head>{''.join(head)}</head><body>{body}</body></html>".encode()


def rec(url, status=200, final_url=None, redirects=(), redirect_statuses=(), source="sitemap", lang=None):
    return {"url": url, "status": status, "final_url": final_url or url, "redirects": list(redirects),
            "redirect_statuses": list(redirect_statuses), "blocked": 0, "error": None, "source": source,
            "lang": lang, "content_type": "text/html"}


def checks(issues):
    return {c for c, _ in issues}


# ---- page parsing ----

def test_parse_page_reads_head_and_headers():
    body = (b'<html lang="FR"><head><title> A  b </title><link rel="Canonical" href="/x">'
            b'<link rel="alternate" hreflang="de" href="/de/x"><meta NAME="Robots" content="NoIndex"></head>'
            b'<body><h1> Hi <b>there</b></h1><link rel="canonical" href="/body-ignored"></body></html>')
    f = parse_page(body, "https://h.example/fr/x", {"link": '<https://h.example/x>; rel="canonical"',
                                                       "x-robots-tag": "noarchive"})
    assert f.titles == ["A b"] and f.html_lang == "FR" and f.h1 == ["Hi there"]
    assert f.canonicals == ["https://h.example/x", "https://h.example/x"]
    assert f.hreflang == [("de", "https://h.example/de/x")]
    assert f.robots == ["noindex", "noarchive"] and f.noindex


# ---- per-page checks ----

def test_clean_page_has_no_issues():
    url = "https://h.example/pdf/merge"
    facts = parse_page(html(canonical=url, hreflang=[("en", url), ("x-default", url)]), url)
    assert page_issues(rec(url), facts, localized=True) == []


def test_redirect_canonical_and_tag_issues():
    url = "https://h.example/pdf/split"
    final = "https://h.example/pdf/splitter"
    facts = parse_page(html(title="x", canonical="https://h.example/pdf/other", desc=None, h1=("A", "B"), lang=None,
                            viewport="width=device-width, user-scalable=no"), final)
    got = checks(page_issues(rec(url, final_url=final, redirects=[url, url + "/"], redirect_statuses=[302, 301]),
                             facts, localized=True))
    assert {"redirected", "redirect_chain", "redirect_temporary", "canonical_elsewhere", "title_length",
            "description_missing", "h1_multiple", "hreflang_missing", "html_lang_missing", "viewport_no_zoom"} <= got


def test_soft_404_errors_and_blocked():
    url = "https://h.example/email/sitemap.xml"
    final = "https://h.example/email/error?code=404"
    facts = parse_page(html(title="Error"), final)
    assert checks(page_issues(rec(url, final_url=final, redirects=[url], redirect_statuses=[302]), facts, False)) == {
        "redirected", "redirect_temporary", "soft_404"}
    assert checks(page_issues(rec(url, status=404), None, False)) == {"http_error"}
    # redirect to an app's own error route ('page404'), generic title, error text only in the H1
    url = "https://h.example/psd/conversion/ai-to-pdf"
    final = "https://h.example/psd/page404?url=/psd/conversion/ai-to-pdf"
    facts = parse_page(html(title="Edit PSD files", h1=("There is an error on this page or it does not exist",)), final)
    got = page_issues(rec(url, final_url=final, redirects=[url], redirect_statuses=[302]), facts, False)
    assert "soft_404" in checks(got) and "does not exist" in dict(got)["soft_404"]
    assert "soft_404" in checks(page_issues(rec(url), facts, False))  # H1 alone, no redirect
    blocked = {**rec(url, status=None), "blocked": 1}
    assert checks(page_issues(blocked, None, False)) == {"robots_blocked"}


def test_hreflang_and_lang_checks():
    url = "https://h.example/fr/pdf/merge"
    facts = parse_page(html(canonical=url, lang="de", hreflang=[("en_US", "https://h.example/pdf/merge")]), url)
    got = checks(page_issues(rec(url, lang="fr"), facts, localized=True))
    assert got == {"hreflang_invalid", "hreflang_no_self", "hreflang_no_xdefault", "html_lang_mismatch"}


# ---- sampling ----

def make_inventory():
    inv = InventoryStore(":memory:")
    run = inv.start_run("example.com", {"hosts": [], "sections": [], "max_sitemaps": None})
    rows = []
    for i in range(50):
        rows.append((run, f"https://app.example.com/pdf/tool{i}", "app.example.com", "pdf", None, "tool", None, "s", 0))
    for lang in ("fr", "de", "es"):
        for i in range(5):
            rows.append((run, f"https://app.example.com/pdf/{lang}/tool{i}", "app.example.com", "pdf", lang, "tool",
                         None, "s", 0))
    rows.append((run, "https://app.example.com/pdf/", "app.example.com", "pdf", None, "family-hub", None, "s", 0))
    rows.append((run, "https://app.example.com/omr/x", "app.example.com", "omr", None, "tool", None, "s", 0))
    rows.append((run, "https://www.example.com/", "www.example.com", "", None, "home", None, "s", 0))
    inv.add_urls(rows)
    inv.finish_run(run, {})
    return inv, run


def test_sample_is_stable_and_bounded():
    inv, run = make_inventory()
    s1 = sample_inventory(inv.db, run, ["app.example.com"], {"app.example.com"}, full_max=0,
                          per_template=2, other_langs=2)
    s2 = sample_inventory(inv.db, run, ["app.example.com"], {"app.example.com"}, full_max=0,
                          per_template=2, other_langs=2)
    assert s1 == s2
    tool = [s for s in s1 if s.section == "pdf" and s.template == "tool"]
    assert len(tool) == 4 and len([s for s in tool if s.lang is None]) == 2
    assert len({s.lang for s in tool if s.lang}) == 2 and tool[0].group_urls == 65
    capped = sample_inventory(inv.db, run, ["app.example.com"], {"app.example.com"}, full_max=0, max_per_host=3)
    assert {(s.section, s.template) for s in capped} == {("pdf", "tool"), ("pdf", "family-hub"), ("omr", "tool")}
    more = sample_inventory(inv.db, run, ["app.example.com"], {"app.example.com"}, full_max=0, other_langs=0,
                            per_template_by_host={"app.example.com": 10})
    assert len([s for s in more if (s.section, s.template) == ("pdf", "tool")]) == 10
    only = sample_inventory(inv.db, run, ["app.example.com"], {"app.example.com"}, full_max=0, sections=["omr"])
    assert [s.url for s in only] == ["https://app.example.com/omr/x"]
    assert latest_inventory_run(inv.db) == run


# ---- full run ----

class FakeFetcher:
    def __init__(self, pages):
        self.pages, self.requests = pages, 0

    def get(self, url):
        self.requests += 1
        if url not in self.pages:
            return FetchResult(url, 404, final_url=url, content_type="text/html", body=b"<html></html>")
        body = self.pages[url]
        return FetchResult(url, 200, final_url=url, content_type="text/html; charset=utf-8", body=body)


def make_tenant(extra_urls=()):
    raw = {
        "property": "example.com", "excluded_host_patterns": ["*-qa.*"],
        "hosts": [{"host": "www.example.com"}, {"host": "app.example.com", "fix_channel": "git-pr"}],
        "discovery": {"section_sitemaps": {"app.example.com": {"sections": ["pdf", "omr"], "paths": []}}},
        "audit": {"extra_urls": list(extra_urls), "full_crawl_max_urls": 0},
    }
    return Tenant(property="example.com", gsc_properties=[], ga4_property_id=None, hosts=raw["hosts"],
                  excluded_host_patterns=raw["excluded_host_patterns"], raw=raw)


class BlockingFetcher(FakeFetcher):
    """robots.txt blocks the default-language tool pages only, as `Disallow: /tag/` does on the .com blogs."""

    def allowed(self, url):
        return "/pdf/tool" not in url

    def get(self, url):
        if not self.allowed(url):
            return FetchResult(url, None, error="disallowed by robots.txt", blocked_by_robots=True)
        return super().get(url)


def test_robots_blocked_counts_the_inventory_not_the_sample():
    inv, run = make_inventory()
    report = audit(make_tenant(), BlockingFetcher({}), inv.db, run, AuditStore(":memory:"), log=None)
    found = [f for f in report["findings"] if f["check"] == "robots_blocked"]
    exact = inv.db.execute("SELECT count(*) FROM urls WHERE run_id = ? AND url LIKE '%/pdf/tool%'", (run,)).fetchone()[0]
    assert len(found) == 1 and found[0]["affected_pages"] == exact
    assert f"Exact count from the sitemaps: {exact}" in found[0]["evidence"]["observed"]


def test_audit_run_findings_and_resolution():
    inv, run = make_inventory()
    pages = {}
    for i in range(50):
        u = f"https://app.example.com/pdf/tool{i}"
        pages[u] = html(title=f"Tool {i} for PDF files", canonical=u)  # no hreflang on a localized section
    for lang in ("fr", "de", "es"):
        for i in range(5):
            u = f"https://app.example.com/pdf/{lang}/tool{i}"
            pages[u] = html(title=f"Tool {i} {lang} for PDF files", canonical=u, lang=lang)
    pages["https://app.example.com/pdf/"] = html(title="Same hub title", canonical="https://app.example.com/pdf/")
    pages["https://app.example.com/omr/"] = html(title="Same hub title", canonical="https://app.example.com/omr/")
    pages["https://www.example.com/"] = html(title="Home page title", canonical="https://www.example.com/")
    pages["https://app.example.com/"] = html(title="App home title", canonical="https://app.example.com/")
    tenant = make_tenant(extra_urls=["https://app.example.com/omr/", "https://x-qa.example.com/"])

    report = audit(tenant, FakeFetcher(pages), inv.db, run, AuditStore(":memory:"), log=None)
    by_check = {(f["check"], f["template"]): f for f in report["findings"]}
    assert set(by_check) == {("hreflang_missing", "page:pdf"), ("http_error", "page:omr"),
                             ("title_duplicate", "page:pdf"), ("title_duplicate", "page:omr"),
                             ("description_duplicate", "page:pdf"), ("description_duplicate", "page:omr")}
    hl = by_check[("hreflang_missing", "page:pdf")]
    assert hl["dimension"] == "intl" and hl["fix_channel"] == "git-pr"
    assert "tool 4/4" in hl["evidence"]["observed"] and hl["affected_pages"] == 66  # 65 tool + 1 hub
    assert not any("x-qa" in p["url"] for p in report["pages"])

    fstore = FindingsStore(":memory:")
    first = import_report(fstore, report)
    assert len(first["new"]) == 6
    for i in range(50):  # the template gains hreflang
        u = f"https://app.example.com/pdf/tool{i}"
        pages[u] = html(title=f"Tool {i} for PDF files", canonical=u, hreflang=[("en", u), ("x-default", u)])
    for lang in ("fr", "de", "es"):
        for i in range(5):
            u = f"https://app.example.com/pdf/{lang}/tool{i}"
            pages[u] = html(title=f"Tool {i} {lang} for PDF files", canonical=u, lang=lang,
                            hreflang=[(lang, u), ("x-default", u)])
    pages["https://app.example.com/pdf/"] = html(title="PDF hub page title", canonical="https://app.example.com/pdf/",
                                                 hreflang=[("en", "https://app.example.com/pdf/"),
                                                           ("x-default", "https://app.example.com/pdf/")])
    second = import_report(fstore, audit(tenant, FakeFetcher(pages), inv.db, run, AuditStore(":memory:"), log=None))
    assert len(second["resolved"]) == 5  # hreflang + duplicate titles/descriptions; the omr 404 stays open


def test_xdefault_is_not_a_self_reference_and_repeated_tags():
    url = "https://h.example/html/conversion/md"
    alts = [("x-default", url), ("de", "https://h.example/html/de/conversion/md")]
    body = html(canonical=url, hreflang=alts + alts).replace(b"</head>", f'<link rel="canonical" href="{url}"></head>'
                                                             .encode())
    facts = parse_page(body, url, {"link": f'<{url}>; rel="canonical"'})
    got = checks(page_issues(rec(url), facts, localized=True))
    assert got == {"hreflang_no_self", "head_tags_repeated"}
    facts = parse_page(html(canonical=url, hreflang=[("de", url), ("de", url + "x"), ("x-default", url)]), url)
    assert "hreflang_conflict" in checks(page_issues(rec(url), facts, localized=True))


def test_section_filter_keeps_other_hosts_and_homepages():
    inv, run = make_inventory()
    tenant = make_tenant(extra_urls=["https://app.example.com/pdf/"])
    tenant.raw["audit"]["section_urls"] = {"app.example.com": ["/{section}/family/"]}
    report = audit(tenant, FakeFetcher({}), inv.db, run, AuditStore(":memory:"), sections=["omr"], log=None)
    urls = {p["url"] for p in report["pages"]}
    assert urls == {"https://app.example.com/omr/x", "https://www.example.com/", "https://app.example.com/",
                    "https://app.example.com/omr/family/"}
    fstore = FindingsStore(":memory:")
    import_report(fstore, report)  # every page 404s: one http_error finding per (host, section)
    keys = {f["key"] for f in fstore.findings()}
    assert "crawl/http_error/www.example.com/page" in keys and "crawl/http_error/app.example.com/page" in keys
    report["findings"] = []
    assert len(import_report(fstore, report)["resolved"]) == 3  # omr section + both unsectioned findings


def test_meta_refresh_stub_and_cjk_width():
    url = "https://h.example/en/"
    body = (b'<html lang=en><head><title>x</title><meta name=robots content="noindex">'
            b'<meta http-equiv=refresh content="0; url=https://h.example/"></head></html>')
    assert checks(page_issues(rec(url), parse_page(body, url), localized=True)) == {"meta_refresh"}
    url = "https://h.example/zh-hant/with-logo"
    facts = parse_page(html(title="線上生成帶標誌", canonical=url, lang="zh-hant",
                            desc="免費產生帶有自訂徽標的二維碼。此外，還可額外付費使用徽標自動調整最大尺寸功能。"), url)
    assert page_issues(rec(url, lang="zh-hant"), facts, localized=False) == []


def test_sections_without_sitemap_urls_use_top_search_pages():
    inv, run = make_inventory()  # omr has 1 sitemap URL, so only a section with none is filled
    tenant = make_tenant()
    tenant.raw["discovery"]["section_sitemaps"]["app.example.com"]["sections"] = ["pdf", "omr", "drawing"]
    search = [{"page": f"https://app.example.com/drawing/tool{i}", "clicks": i} for i in range(10)]
    search.append({"page": "https://app.example.com/omr/other", "clicks": 99})
    report = audit(tenant, FakeFetcher({}), inv.db, run, AuditStore(":memory:"), sections=["omr", "drawing"],
                   search_pages=search, log=None)
    filled = [p for p in report["pages"] if p["source"] == "search"]
    assert [p["url"] for p in filled] == [f"https://app.example.com/drawing/tool{i}" for i in (9, 8, 7, 6)]
    assert filled[0]["group_urls"] == 10 and filled[0]["section"] == "drawing"


def test_ignore_rule_skips_private_pages():
    inv, run = make_inventory()
    tenant = make_tenant()
    tenant.raw["audit"]["ignore_pages"] = [{"host": "app.example.com", "status": 404, "path_prefix": "/omr/",
                                           "reason": "private"}]
    report = audit(tenant, FakeFetcher({}), inv.db, run, AuditStore(":memory:"), sections=["omr"], log=None)
    omr = [p for p in report["pages"] if p["url"] == "https://app.example.com/omr/x"][0]
    assert omr["ignored"] == "private" and omr["issues"] == []
    assert not any(f["template"] == "page:omr" for f in report["findings"])
    assert report["summary"]["app.example.com"]["ignored"] == 1


def test_locations_show_listing_sitemap_and_canonical_target():
    inv, run = make_inventory()
    inv.add_sitemap(run, {"url": "s", "host": "app.example.com", "parent": "https://app.example.com/index.xml"})
    pages = {f"https://app.example.com/pdf/tool{i}": html(title=f"Tool {i} for PDF files",
                                                       canonical="https://app.example.com/conversion")
             for i in range(50)}
    tenant = make_tenant()
    report = audit(tenant, FakeFetcher(pages), inv.db, run, AuditStore(":memory:"), sections=["pdf"], log=None)
    f = next(x for x in report["findings"] if x["check"] == "canonical_elsewhere")
    roles = {(loc["role"], loc["url"]) for loc in f["evidence"]["locations"]}
    assert ("listed in", "s") in roles and ("sitemap index", "https://app.example.com/index.xml") in roles
    target = next(loc for loc in f["evidence"]["locations"] if loc["role"] == "canonical target")
    assert target["url"] == "https://app.example.com/conversion" and target["note"] == "HTTP 404"
    assert report["canonical_targets"] == {"https://app.example.com/conversion": "HTTP 404"}
    assert "(HTTP 404)" in f["evidence"]["observed"]


def test_head_closed_early_by_a_div_is_one_finding_not_missing_tags():
    """blog.aspose.com, 3 Nov 2026: a language-switcher <div> written first into <head> ends it; the title,
    canonical and hreflang after it land in <body>. One head_closed_early, not title/canonical missing. A <title>
    inside an inline SVG is fine."""
    url = "https://h.example/de/pdf/merge"
    page = ("<!doctype html><html lang=de><head><meta charset=utf-8><div id=locale>DE</div>"
            f"<title>Merge PDF online</title><link rel=canonical href='{url}'>"
            f"<link rel=alternate hreflang=de href='{url}'></head><body><h1>Merge</h1></body></html>")
    facts = parse_page(page, url)
    assert facts.body_head_tags == ["title", "canonical", "hreflang"]
    got = dict(page_issues(rec(url), facts, localized=True))
    assert "canonical" in got["head_closed_early"]
    assert not {"title_missing", "canonical_missing", "description_missing", "hreflang_missing",
                "viewport_missing"} & set(got)  # head checks skipped
    assert "h1_missing" not in got and "no_structured_data" in got  # body checks still run
    no_h1 = parse_page(page.replace("<h1>Merge</h1>", ""), url)
    assert "h1_missing" in dict(page_issues(rec(url), no_h1, localized=True))
    svg = parse_page(html(canonical=url).replace(b"<h1>", b"<svg><title>icon</title></svg><h1>"), url)
    assert svg.body_head_tags == []


def test_social_tags_after_the_div_are_their_own_finding():
    """blog.conholdate.cloud, 11 Nov 2026: the switcher <div> comes after title, canonical and hreflang but before
    Open Graph, Twitter and JSON-LD. Search tags are fine, so not head_closed_early: social_tags_in_body."""
    url = "https://h.example/de/pdf/merge"
    page = ("<!doctype html><html lang=de><head><meta charset=utf-8><title>Merge PDF online</title>"
            f"<link rel=canonical href='{url}'><link rel=alternate hreflang=de href='{url}'>"
            "<div id=locale>DE</div><meta property='og:title' content='Merge'><meta name='twitter:card' content='s'>"
            "<script type='application/ld+json'>{}</script></head><body><h1>Merge</h1></body></html>")
    facts = parse_page(page, url)
    assert facts.body_head_tags == [] and facts.body_social_tags == ["Open Graph", "Twitter card", "JSON-LD"]
    got = dict(page_issues(rec(url), facts, localized=True))
    assert "social_tags_in_body" in got and "head_closed_early" not in got
    ok = parse_page(page.replace("<div id=locale>DE</div>", ""), url)  # JSON-LD in <body> alone is valid: no finding
    assert ok.body_social_tags == []
    only_ld = parse_page("<html><head><title>t</title></head><body><script type='application/ld+json'>{}</script>"
                         "</body></html>", url)
    assert only_ld.body_social_tags == []


def test_small_host_is_crawled_in_full():
    inv, run = make_inventory()
    total = inv.db.execute("SELECT COUNT(*) FROM urls WHERE run_id = ? AND host = ?",
                           (run, "app.example.com")).fetchone()[0]
    full = sample_inventory(inv.db, run, ["app.example.com"], {"app.example.com"})
    assert len(full) == total and len({s.url for s in full}) == total
    assert len(sample_inventory(inv.db, run, ["app.example.com"], {"app.example.com"}, full_max=0)) < total


def test_translated_page_with_the_english_title_is_found():
    from core.audit.crawl import untranslated_issues

    def page(url, lang, title, refs):
        return {"url": url, "host": "b.example.com", "final_url": url, "status": 200, "lang": lang, "issues": [],
                "facts": {"titles": [title], "descriptions": [], "robots": [], "hreflang": refs}}

    refs = [["en", "https://b.example.com/"], ["ja", "https://b.example.com/ja/"], ["de", "https://b.example.com/de/"]]
    en = page("https://b.example.com/", "en", "File Format APIs | Brand Cloud", refs)
    ja = page("https://b.example.com/ja/", "ja", "File Format APIs | Brand Cloud", refs)
    de = page("https://b.example.com/de/", "de", "Dateiformat-APIs | Brand Cloud", refs)
    brand = page("https://b.example.com/ko/", "ko", "Brand", refs + [["ko", "https://b.example.com/ko/"]])
    en2 = page("https://b.example.com/s/", "en", "Example Blog News", [["en", "https://b.example.com/s/"]])
    de2 = page("https://b.example.com/de/s/", "de", "Example Blog News", [["en", "https://b.example.com/s/"]])
    untranslated_issues([en, ja, de, brand, en2, de2], "titles", "title_untranslated")
    assert not de2["issues"]  # one word besides the host's labels (b, example, com)
    assert [c for c, _ in ja["issues"]] == ["title_untranslated"]
    assert not en["issues"] and not de["issues"] and not brand["issues"]
