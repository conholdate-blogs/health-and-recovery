"""Offline tests for the item ledger: fixed / new / removed / still open across link-check runs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.items import counts, discovery_items, in_repo, in_sitemaps, run_items, update  # noqa: E402

HOST = "blog.example.org"


def run(links, partial=None):
    """A link-check run with one broken link per (file, link) pair."""
    return {"hosts": {HOST: {"issues": [{"check": "link_broken", "page": f"https://{HOST}/{f}/", "file": f, "link": lk}
                                        for f, lk in links],
                             "partial": partial or [], "unsupported": {}}}}


def test_sk_example_fixed_share_falls_when_new_issues_arrive(tmp_path):
    """1,000 issues, 200 fixed: 20%. Then 1,000 new: 200 of 2,000, 10% (SK, 2026-10-27)."""
    for i in range(1000):
        (tmp_path / f"p{i}.md").write_text("x")
    repos = in_repo({HOST: str(tmp_path)})
    first = [(f"p{i}.md", "/gone/") for i in range(1000)]
    ledger = update({}, "link-audit-run1", "2026-10-22", run_items(run(first)), repos)
    ledger = update(ledger, "link-audit-run2", "2026-10-29", run_items(run(first[200:])), repos)
    c = counts(ledger, HOST)
    assert (c["baseline"], c["fixed"], c["open"], c["fixed_pct"]) == (1000, 200, 800, 20)
    more = first[200:] + [(f"p{i}.md", "/also-gone/") for i in range(1000)]
    ledger = update(ledger, "link-audit-run3", "2026-11-05", run_items(run(more)), repos)
    c = counts(ledger, HOST)
    assert (c["new"], c["fixed"], c["open"], c["fixed_pct"]) == (1000, 200, 1800, 10)
    assert (c["issues"], c["scanned"], c["since"]) == (2000, "2026-11-05", "2026-10-22")  # what the pages show
    assert update(ledger, "link-audit-run3", "2026-11-05", {}, repos) is ledger  # a run counts once


def test_deleted_post_is_removed_not_fixed_and_items_can_come_back(tmp_path):
    (tmp_path / "kept.md").write_text("x")
    repos = in_repo({HOST: str(tmp_path)})
    items = run_items(run([("kept.md", "/a/"), ("kept.md", "/a/"), ("deleted.md", "/b/")],
                          partial=[{"page": "p", "folder": "kept.md", "missing": ["fr", "de"]}]))
    assert len(items) == 5  # the same link twice in one file is two items; each missing language is one
    ledger = update({}, "r1", "2026-10-22", items, repos)
    ledger = update(ledger, "r2", "2026-10-29", {}, repos)
    c = counts(ledger, HOST)
    assert (c["fixed"], c["removed"], c["open"]) == (4, 1, 0)
    ledger = update(ledger, "r3", "2026-11-05", items, repos)  # all come back: reopened, deleted.md too
    c = counts(ledger, HOST)
    assert (c["fixed"], c["removed"], c["open"], c["new"]) == (0, 0, 5, 0)
    assert c["by_check"]["translation_partial"]["open"] == 2


def test_sitemap_items_fixed_removed_and_sources_kept_apart(tmp_path):
    """A duplicate that is gone while its URL is still listed is fixed; gone with its URL, removed; a sitemap-level
    item gone is fixed. A link-check run never closes discovery items, nor the other way round."""
    sm = f"https://{HOST}/sitemap.xml"
    first = {"items": {HOST: [{"check": "dup_in_file", "sitemap": sm, "url": f"https://{HOST}/a/"},
                              {"check": "dup_in_file", "sitemap": sm, "url": f"https://{HOST}/a/"},
                              {"check": "dup_in_file", "sitemap": sm, "url": f"https://{HOST}/gone/"},
                              {"check": "lastmod_missing", "sitemap": sm, "url": None}]}}
    items = discovery_items(first)
    assert len(items) == 4  # a URL listed three times is two items
    (tmp_path / "p.md").write_text("x")
    ledger = update({}, "link-audit-run1", "2026-10-22", run_items(run([("p.md", "/x/")])),
                    in_repo({HOST: str(tmp_path)}))
    ledger = update(ledger, "discovery-run2", "2026-10-30", items, in_sitemaps([HOST], None), source="discovery")
    ledger = update(ledger, "link-audit-run3", "2026-11-06", run_items(run([("p.md", "/x/")])),
                    in_repo({HOST: str(tmp_path)}))
    assert counts(ledger, HOST)["open"] == 5  # the link check left the sitemap items alone
    later = {"items": {HOST: [{"check": "dup_in_file", "sitemap": sm, "url": f"https://{HOST}/a/"}]}}
    ledger = update(ledger, "discovery-run4", "2026-11-06", discovery_items(later),
                    in_sitemaps([HOST], {f"https://{HOST}/a/"}), source="discovery")
    c = counts(ledger, HOST)
    assert (c["fixed"], c["removed"], c["open"]) == (2, 1, 2)  # 2nd /a/ and lastmod fixed; /gone/ removed
    assert c["by_check"]["dup_in_file"] == {**c["by_check"]["dup_in_file"], "fixed": 1, "open": 1}


def test_broken_link_that_redirects_again_is_changed_not_fixed(tmp_path):
    """SK, 2026-11-06: after Redirects.json was repaired, a 404 link redirects again; the old URL is still in the
    post, so it is not fixed: it moves to link_redirected, which counts as open."""
    (tmp_path / "p.md").write_text("x")
    repos = in_repo({HOST: str(tmp_path)})
    ledger = update({}, "r1", "2026-11-03", run_items(run([("p.md", "/2021/12/16/old/"), ("p.md", "/gone/")])), repos)
    later = run([("p.md", "/2021/12/16/old/")])
    later["hosts"][HOST]["issues"][0]["check"] = "link_redirected"
    ledger = update(ledger, "r2", "2026-11-07", run_items(later), repos)
    c = counts(ledger, HOST)
    assert (c["fixed"], c["open"], c["changed"], c["redirects"], c["issues"]) == (1, 1, 1, 1, 2)
    assert c["by_check"]["link_broken"] == {**c["by_check"]["link_broken"], "fixed": 1, "open": 0, "redirects": 1}
    assert c["by_check"]["link_redirected"]["open"] == 1
    ledger = update(ledger, "r3", "2026-11-10", run_items(run([("p.md", "/2021/12/16/old/")])), repos)
    c = counts(ledger, HOST)  # back to 404: the broken item reopens, the old-URL item moves back (not fixed)
    assert c["by_check"]["link_broken"]["open"] == 1 and c["by_check"]["link_redirected"]["fixed"] == 0
    assert c["by_check"]["link_redirected"]["changed"] == 1 and c["redirects"] == 0
