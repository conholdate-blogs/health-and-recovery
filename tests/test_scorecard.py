"""Offline tests for family scorecards: traffic-free health, root-cause groups, cosmetic cap, grades."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.scorecard import area_scores, family_scorecards, grade, scorecard  # noqa: E402

HOST = "app.example.com"


def f(fid, check, ftype, template="page:pdf", sample=None, share=None, status="open", urls=None, locations=None,
      clicks=0):
    ev = {"urls": urls or [f"https://{HOST}/pdf/x"], "observed": "o", "expected": "e"}
    if sample:
        ev["sample"] = sample
    if locations:
        ev["locations"] = locations
    return {"id": fid, "check": check, "type": ftype, "template": template, "subdomain": HOST, "status": status,
            "title": f"{check} title", "affected_pages": 0, "evidence": ev,
            "impact": {"share": share, "clicks_28d": clicks}}


def card(findings, families=("pdf", "omr"), stats=None, traffic=None):
    cards = family_scorecards(findings, HOST, list(families), stats or {"pdf": {"urls": 100, "langs": {"en": 1}}},
                              traffic or {})
    return {c["family"]: c for c in cards}


def test_same_breakage_same_grade_whatever_the_traffic():
    traffic = {"pdf": {"current": {"clicks": 100000}}, "omr": {"current": {"clicks": 10}}}
    cards = card([f("a", "section_no_sitemap", "broken", "sitemap:pdf"),
                  f("b", "section_no_sitemap", "broken", "sitemap:omr")], traffic=traffic)
    assert cards["pdf"]["health"] == cards["omr"]["health"] == 60
    assert cards["pdf"]["grade"] == "C" and cards["pdf"]["status"]["Sitemap"] == "bad"


def test_root_cause_groups_count_once_and_malformed_page_urls_join_the_sitemap():
    c = card([f("a", "fetch_failed", "broken", "sitemap:pdf", share=1.0),
              f("b", "section_no_sitemap", "broken", "sitemap:pdf"),
              f("c", "http_error", "broken", sample={"tool": [4, 4]}, urls=[f"https://{HOST}//pdf/x"])])["pdf"]
    assert c["health"] == 60 and [p["group"] for p in c["penalties"]] == ["sitemap"]


def test_share_cosmetic_cap_and_canonical_to_404_is_broken():
    c = card([f("a", "hreflang_no_self", "incorrect", sample={"tool": [2, 4]}),  # 20 x 0.5
              *[f(f"t{i}", f"cosmetic_{i}", "not_optimized") for i in range(10)]])["pdf"]  # 60, capped at 20
    assert c["health"] == 70 and c["cosmetic_capped"]
    bad = f("x", "canonical_elsewhere", "incorrect", sample={"tool": [4, 4]},
            locations=[{"role": "canonical target", "url": "u", "note": "HTTP 404"}])
    c = card([bad])["pdf"]
    assert c["health"] == 60 and c["top"][0]["blocker"] and c["counts"]["broken"] == 1


def test_manual_findings_map_by_url_and_unverified_do_not_count():
    seed = {**f("seed-onpage-01", None, "incorrect", template="family-hub", urls=[f"https://{HOST}/pdf/"]),
            "check": None}
    c = card([seed, f("u", "title_length", "improvable", status="unverified")])["pdf"]
    assert c["health"] == 95 and c["unverified"] == 1  # 20 x MIN_SHARE 0.25
    assert grade(90) == "A" and grade(39) == "F"


def test_cards_sorted_worst_first_and_top_issues_blockers_first():
    cards = family_scorecards([f("a", "title_length", "improvable", clicks=999), f("b", "http_error", "broken"),
                               f("c", "hreflang_no_self", "incorrect", template="page:omr")],
                              HOST, ["pdf", "omr"], {}, {})
    assert [c["family"] for c in cards] == ["pdf", "omr"]
    assert [t["id"] for t in cards[0]["top"]] == ["b", "a"]


def test_area_scores_split_by_dimension_and_never_above_the_overall():
    found = [{**f("a", "link_broken", "broken"), "dimension": "crawl"},
             {**f("b", "hreflang_no_self", "incorrect"), "dimension": "intl"},
             *[{**f(f"t{i}", f"cosmetic_{i}", "not_optimized"), "dimension": "onpage"} for i in range(5)],
             {**f("u", "ux_thing", "improvable"), "dimension": "ux"}]
    areas = {a["dimension"]: a for a in area_scores(found, 100)}
    assert list(areas)[:5] == ["crawl", "onpage", "intl", "ai", "perf"] and "ux" in areas
    assert areas["crawl"]["health"] == 60 and areas["intl"]["health"] == 80 and areas["ai"]["health"] == 100
    assert areas["onpage"]["health"] == 80  # 5 x 6, capped at 20 within the area
    overall = scorecard("host", found, 100)["health"]
    assert overall == 20 and all(overall <= a["health"] for a in areas.values())


def test_one_page_template_weighs_as_its_pages_not_the_whole_family():
    """status.aspose.app, 2026-10-27: 1 of 1 sampled page of a one-page template cost 40 points."""
    lone = {**f("a", "http_error", "broken", sample={"generic:/{section}": [1, 1]}), "affected_pages": 1}
    assert card([lone])["pdf"]["health"] == 90  # 1 of 100 pages: 40 x MIN_SHARE 0.25
    wide = {**f("b", "http_error", "broken", sample={"tool": [1, 4]}), "affected_pages": 60}
    assert card([wide])["pdf"]["health"] == 76  # 60 of 100 pages: 40 x 0.6, not 40 x 1/4
    assert card([{**lone, "affected_pages": 0}])["pdf"]["health"] == 60  # no page estimate: the sample's share


def test_scores_round_halves_up():
    from core.scorecard import half_up

    assert half_up(65.5) == 66 and half_up(65.4) == 65 and half_up(66.5) == 67 and half_up(0.5) == 1


def test_repo_checks_weigh_their_real_share_with_a_small_floor():
    """SK, 2026-11-06: exact repo checks are not floored at 25%; an invalid Redirects.json counts all of it and
    redirects that do not work count the failing share of the live sample."""
    from core.scorecard import MIN_SHARE_EXACT, share_of

    def repo(check, pages=0, observed="o", live=None):
        r = {**f("r", check, "broken", template="post"), "source": "repo-audit", "affected_pages": pages,
             "impact": {}}
        r["evidence"]["observed"] = observed
        if live:
            r["evidence"]["live_sample"] = live
        return r

    assert share_of(repo("post_front_matter_broken", pages=1), 13000) == MIN_SHARE_EXACT
    assert share_of(repo("post_url_relative", pages=500), 1000) == 0.5
    assert share_of(repo("redirect_file_invalid", pages=10), 100000) == 1.0
    assert share_of(repo("redirect_not_working", live=[39, 40]), 100000) == 39 / 40
    assert share_of(repo("redirect_not_working", observed="10 of 40 sampled sources return 404"), 9) == 0.25
    assert scorecard("h", [repo("post_front_matter_broken", pages=1)], 13000)["health"] == 100  # 40 x 1% = 0.4
