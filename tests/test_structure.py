"""Offline tests for the site structure step: tags, categories, listing pages, search numbers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.audit.structure import scan, search_numbers  # noqa: E402


def post(repo: Path, folder: str, name: str, tags, cats=("pdf",), draft=False):
    d = repo / "content" / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(f"---\ntitle: x\ntags: {list(tags)}\ncategories: {list(cats)}\ndraft: {str(draft).lower()}"
                          "\n---\nbody\n", encoding="utf-8")


def test_tags_categories_and_listing_pages(tmp_path):
    (tmp_path / "config.yml").write_text("baseURL: /\npaginate: 2\n")
    post(tmp_path, "a", "index.md", ["PDF", "merge"])
    post(tmp_path, "a", "index.de.md", ["pdf", "merge"])
    post(tmp_path, "b", "index.md", ["pdf"])
    post(tmp_path, "c", "index.md", ["pdf", "split"])
    post(tmp_path, "d", "index.md", ["secret"], draft=True)
    s = scan(tmp_path)
    assert (s["paginate"], s["posts"], s["posts_all_languages"], s["languages"]) == (2, 3, 4, 2)
    assert (s["tags"], s["tags_one_post"], s["tags_two_or_less"]) == (3, 2, 2)  # pdf 3, merge 1, split 1; draft out
    assert s["tags_per_post"] == round(5 / 3, 1) and s["top_tags"][0] == ("pdf", 3)
    # en: home 2 pages + category 2 + tags 2+1+1 = 8; de: home 1 + category 1 + tags 1+1 = 4
    assert (s["listing_pages"], s["tag_listing_pages"], s["tag_pages_all_languages"]) == (12, 6, 5)
    assert s["pages_beyond_cap"] == 0


def test_search_numbers_tag_and_paginated_pages():
    rows = [{"page": "https://b.example/tag/pdf/", "clicks": 3, "impressions": 40},
            {"page": "https://b.example/de/tags/merge/", "clicks": 0, "impressions": 5},
            {"page": "https://b.example/page/3/", "clicks": 1, "impressions": 9},
            {"page": "https://b.example/p/60/", "clicks": 2, "impressions": 2},
            {"page": "https://b.example/pdf/a-post/", "clicks": 10, "impressions": 100},
            {"page": "https://other.example/tag/x/", "clicks": 99, "impressions": 99}]
    q = search_numbers(rows, "b.example")
    assert (q["clicks"], q["tag_clicks"], q["tag_impressions"], q["tag_pages_with_clicks"]) == (16, 3, 45, 1)
    assert (q["paged_clicks"], q["paged_pages_seen"], q["deep_paged_clicks"]) == (3, 2, 2)


TAGS_LIST = '<html><head><meta name="robots" content="{r}"></head><body>' \
            '<a href="/tag/a/">a</a><a href="https://blog.example.com/tag/b/">b</a><a href="/tag/c/">c</a>' \
            '<a href="/post/">p</a><a href="https://other.example.com/tag/x/">x</a></body></html>'


def fake_get(robots="noindex, follow", blocked=(), header=None):
    seen = []

    def get(url):
        seen.append(url)
        if url in blocked:
            return None, {}, "", True
        return 200, ({"x-robots-tag": header} if header else {}), TAGS_LIST.format(r=robots), False
    return get, seen


def test_tag_robots_all_noindex_skips_thin_finding():
    from core.audit.structure import findings, tag_robots

    get, seen = fake_get()
    tr = tag_robots(get, "blog.example.com")
    assert seen == ["https://blog.example.com/tags/", "https://blog.example.com/tag/a/",
                    "https://blog.example.com/tag/b/"]
    assert tr["all_noindex"]
    s = {"tags": 10, "tags_one_post": 9, "tag_pages_all_languages": 200, "languages": 20, "tag_robots": tr}
    assert findings("t", "blog.example.com", s) == []
    s["tag_robots"] = tag_robots(fake_get(robots="index, follow")[0], "blog.example.com")
    assert not s["tag_robots"]["all_noindex"]
    assert [f["check"] for f in findings("t", "blog.example.com", s)] == ["tag_pages_thin"]


def test_tag_robots_blocked_page_is_not_noindex_and_header_counts():
    from core.audit.structure import tag_robots

    tr = tag_robots(fake_get(blocked={"https://blog.example.com/tag/a/"})[0], "blog.example.com")
    assert not tr["all_noindex"] and tr["pages"][1]["blocked"]
    assert tag_robots(fake_get(robots="index", header="noindex")[0], "blog.example.com")["all_noindex"]


def test_tag_robots_skips_tag_pages_that_do_not_answer_200():
    # blog.groupdocs.cloud 26 Nov: /tag/.net-…/ slugs 404 live; they must not decide whether tag pages are noindex
    from core.audit.structure import tag_robots

    base, seen = fake_get()

    def get(url):
        if url.endswith("/tag/a/"):
            seen.append(url)
            return 404, {}, '<html><head><meta name="robots" content="index, follow"></head></html>', False
        return base(url)
    tr = tag_robots(get, "blog.example.com")
    assert seen[-1] == "https://blog.example.com/tag/c/"  # read on to get two pages that answer 200
    assert tr["all_noindex"]


def test_single_main_section_page_must_be_noindex(tmp_path):
    # 13 Nov 2026: with one main section the section page repeats the home page's list
    from core.audit.structure import findings, section_robots

    (tmp_path / "config.yml").write_text("params:\n  mainSections:\n  - Conholdate.Total\n", encoding="utf-8")
    seen = []

    def get(robots):
        def g(url):
            seen.append(url)
            return 200, {}, f'<html><head><meta name="robots" content="{robots}"></head></html>', False
        return g
    sec = section_robots(get("index, follow"), "blog.example.com", tmp_path)
    assert seen == ["https://blog.example.com/conholdate.total/"] and not sec["noindex"]
    assert [f["check"] for f in findings("t", "blog.example.com", {"section_robots": sec, "languages": 18})] == [
        "section_lists_home_posts"]
    sec = section_robots(get("noindex, follow"), "blog.example.com", tmp_path)
    assert findings("t", "blog.example.com", {"section_robots": sec}) == []
    (tmp_path / "config.yml").write_text("params:\n  mainSections: [a, b]\n", encoding="utf-8")
    assert "url" not in section_robots(get("index, follow"), "blog.example.com", tmp_path)  # two sections: no read


def test_taxonomy_feeds_from_config_outputs(tmp_path):
    from core.audit.structure import taxonomy_feeds

    (tmp_path / "config.yml").write_text("outputs:\n  home: [HTML, RSS]\n", encoding="utf-8")
    assert taxonomy_feeds(tmp_path) == {"config": "config.yml", "taxonomy": True, "term": True}  # Hugo default
    (tmp_path / "config.yml").write_text("outputs:\n  home: [HTML, RSS]\n  taxonomy: [HTML]\n  term: [HTML]\n",
                                         encoding="utf-8")
    assert taxonomy_feeds(tmp_path)["term"] is False and taxonomy_feeds(tmp_path)["taxonomy"] is False
    (tmp_path / "config-production.yml").write_text("outputs:\n  term: [HTML, RSS]\n", encoding="utf-8")
    assert taxonomy_feeds(tmp_path) == {"config": "config-production.yml", "taxonomy": True, "term": True}


def test_junk_kind():
    from core.audit.structure import junk_kind

    h = "https://blog.example.com"
    assert junk_kind(f"{h}/fa/tag/%5C%D8%AD%D8%B0%D9%81%5C/") == "escaped"
    assert junk_kind(f"{h}/ar/tag/%D8%A7%D8%B3%D8%AA%D8%AE%D8%B1%D8%A7%D8%AC-xml/index.xml") == "non_english"
    assert junk_kind(f"{h}/x/%7B%7B%20revealButtonHref%20%7D%7D") == "placeholder"
    assert junk_kind(f"{h}//total/post/") == "double_slash"
    assert junk_kind(f"{h}/tag/merge-pdf/index.xml") is None  # feeds still built: taxonomy_feeds_built covers them
    assert junk_kind(f"{h}/tag/merge-pdf/index.xml", feeds_built=False) == "taxonomy_feed"
    assert junk_kind(f"{h}/index.xml", feeds_built=False) is None
    assert junk_kind(f"{h}/conversion/merge-pdf/") is None
    assert junk_kind(f"{h}/category/a%20b/") is None  # an encoded space is not non-English


def test_junk_live_and_findings():
    from core.audit.structure import findings, junk_live

    h = "https://blog.example.com"
    rows = [{"page": f"{h}/fa/tag/%5Cx%5C/", "clicks": 5, "impressions": 50},
            {"page": f"{h}/ar/tag/%D8%A7/", "clicks": 1, "impressions": 90},
            {"page": f"{h}/conversion/ok/", "clicks": 9, "impressions": 900}]
    status = {rows[0]["page"]: 404, rows[1]["page"]: 200}
    junk = junk_live(lambda u: (status[u], {}, "", False), rows)
    assert junk["urls"] == 2 and junk["checked"] == 2
    assert junk["served"] == [{"page": rows[1]["page"], "kind": "non_english", "clicks": 1, "impressions": 90}]
    assert junk["by_kind"]["escaped"]["live"] == {"404": 1}
    s = {"languages": 19, "tag_pages_all_languages": 1000, "categories": 10,
         "taxonomy_feeds": {"config": "config.yml", "term": True, "taxonomy": False},
         "known_junk": {**junk, "window": ["2025-08-01", "2026-11-25"]}}
    got = {f["check"]: f for f in findings("t", "blog.example.com", s)}
    assert got["taxonomy_feeds_built"]["affected_pages"] == 1000 + 10 * 19
    assert got["url_junk_served"]["affected_pages"] == 1
    assert got["url_junk_served"]["evidence"]["traffic"] == {"clicks": 1, "impressions": 90}
    s["taxonomy_feeds"] = {"term": False, "taxonomy": False}
    s["known_junk"]["served"] = []
    assert not findings("t", "blog.example.com", s)
    # a URL the sitemaps list is a real page (en dash in a 2017 slug), never junk
    real = junk_live(lambda u: (200, {}, "", False), [{"page": f"{h}/total/news-%E2%80%93-2017/", "clicks": 1,
                                                      "impressions": 9}], sitemap_urls={f"{h}/total/news-–-2017/"})
    assert real["urls"] == 0 and not real["served"]
