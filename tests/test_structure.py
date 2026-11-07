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
