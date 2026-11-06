"""Per-tenant layout: data/<tenant>/, reports/<tenant>/, and the Pages site with one subfolder per tenant."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.paths import published_tenants, tenant_paths  # noqa: E402
from core.tenant import load_tenant  # noqa: E402


def test_tenant_paths(tmp_path):
    p = tenant_paths("example.org", tmp_path / "data", tmp_path / "reports")
    assert p.findings_store == tmp_path / "data" / "example.org" / "findings.sqlite"
    assert p.findings_export == tmp_path / "reports" / "example.org" / "findings.json"
    assert p.archive == tmp_path / "reports" / "example.org" / "archive"
    for bad in ("", "../x", "a/b", ".hidden"):
        with pytest.raises(ValueError):
            tenant_paths(bad)


def test_published_tenants(tmp_path):
    for t in ("b.org", "a.org"):
        (tmp_path / t).mkdir()
        (tmp_path / t / "findings.json").write_text("[]")
    (tmp_path / "no-report.org").mkdir()
    assert published_tenants(tmp_path) == ["a.org", "b.org"]


def test_unpublished_tenant_is_left_off_the_site(monkeypatch):
    from scripts import build_site

    monkeypatch.setattr(build_site, "published_tenants", lambda: ["aspose.app", "aspose.com"])
    assert build_site.site_tenants() == ["aspose.com"]  # tenants/aspose.app.yaml: published: false


def test_home_page_pairs_subdomains_by_brand():
    from scripts.build_site import collection_block

    members = [("conholdate.cloud", "blog.conholdate.cloud"), ("aspose.cloud", "blog.aspose.cloud"),
               ("aspose.com", "blog.aspose.com"), ("conholdate.com", "blog.conholdate.com")]
    block = collection_block("blogs", members, {"blog.aspose.com": (55, "F"), "blog.aspose.cloud": (67, "C")})
    rows = [r for r in block.splitlines() if 'class="pairs"' in r]
    assert [[h for h in ("aspose.com", "aspose.cloud", "conholdate.com", "conholdate.cloud") if f"blog.{h}/" in r]
            for r in rows] == [["aspose.com", "aspose.cloud"], ["conholdate.com", "conholdate.cloud"]]
    assert '<a class="sub g-F" href="blog.aspose.com/"><code>blog.aspose.com</code><b>55</b></a>' in block
    assert '<a href="blogs/"><b>Blogs</b></a>' in block


def test_property_must_match_file_name(tmp_path):
    (tmp_path / "x.org.yaml").write_text("property: y.org\nhosts: []\n")
    with pytest.raises(ValueError, match="must match"):
        load_tenant("x.org", tmp_path)


def test_redirect_keeps_anchor():
    from scripts.build_site import redirect_page

    page = redirect_page("../aspose.app/archive/")
    assert 'location.replace("../aspose.app/archive/" + location.hash)' in page
    assert page.index("<script>") < page.index('http-equiv="refresh"')  # the script runs first, keeping #anchor
    assert "noindex, nofollow" in page


def test_report_without_family_hosts(tmp_path):
    """A tenant whose traffic summary has no sectioned hosts gets no family cards (and no crash)."""
    from scripts.build_report import add_families, add_views

    summary = tmp_path / "traffic-summary.json"
    summary.write_text(json.dumps({"windows": {"current": ["2026-01-01", "2026-01-28"]}, "hosts": {}}))
    report = {"run_id": 1, "findings": [], "sections": {}}
    add_families(report, summary)
    assert "_families" not in report
    add_views(report, [], tmp_path / "health-history.json")
    assert "_run_changes" in report


def test_host_cards(tmp_path):
    """Hosts without family cards get a health card scored like a family, with their search traffic."""
    from scripts.build_report import add_hosts

    summary = tmp_path / "traffic-summary.json"
    summary.write_text(json.dumps({"windows": {}, "hosts": {}, "host_totals": {
        "blog.example.org": {"source": "gsc", "current": {"clicks": 5, "impressions": 50, "pages": 3}}}}))
    finding = {"id": "onpage-0001", "status": "open", "type": "incorrect", "check": "title_missing",
               "subdomain": "blog.example.org", "template": "page", "title": "No title",
               "evidence": {"urls": ["https://blog.example.org/"], "sample": {"post": [1, 4]}}}
    report = {"hosts": {"blog.example.org": {"urls": 40}, "www.example.org": {"urls": 1}}, "findings": [finding],
              "_families": {"hosts": {"www.example.org": []}}}
    add_hosts(report, summary)
    card, www = report["_hosts"]  # www has a family host entry but no cards: plain host score, no rollup
    assert card["host"] == "blog.example.org" and card["urls"] == 40 and "rollup" not in www
    assert card["health"] == 95 and card["grade"] == "A"  # incorrect 20 x share 0.25
    assert card["traffic"]["current"]["clicks"] == 5


def test_fix_guide_page(tmp_path, monkeypatch):
    """One shared guide page with an anchor per check; reports link to it instead of embedding the table."""
    from core.fix_guide import GUIDE
    from scripts import build_site
    from scripts.build_report import build

    monkeypatch.setattr(build_site, "open_by_check", lambda tenants: {"title_missing": {"a.org": 2}})
    page = build_site.guide_page(["a.org"])
    assert page.count('<tr id="g-') == len(GUIDE)
    assert '<a href="../a.org/">a.org</a> 2' in page
    report = {"tenant": "a.org", "findings": [{"_guide": "title_missing"}],
              "_guide": {"areas": [], "rows": {"title_missing": {}, "h1_missing": {}}}}
    html = build(report, [], None, guide_url="../fix-guide/")
    assert '"_guide_url": "../fix-guide/"' in html and "h1_missing" not in html  # only rows the report uses
    # a counted check keeps its row (name, severity in Fix progress) after its finding is resolved
    report["_hosts"] = [{"items": {"by_check": {"h1_missing": {}}}}]
    assert "h1_missing" in build(report, [], None, guide_url="../fix-guide/")


def test_method_page(tmp_path):
    """"How this audit works" is one shared page; published reports link to it, local pages keep the section."""
    from scripts import build_site
    from scripts.build_report import build

    page = build_site.method_page()
    assert 'id="method-health"' in page and 'id="method-score"' in page and "Glossary" in page
    assert 'id="method-areas" hidden' not in page and "__METHOD__" not in page
    report = {"tenant": "a.org", "findings": []}
    published = build(report, [], None, method_url="../method/")
    assert 'id="method-health"' not in published and '"_method_url": "../method/"' in published
    local = build(report, [], None)
    assert 'id="method-health"' in local and "__METHOD__" not in local


def test_family_host_rollup():
    """A host with families: click-weighted family health minus host-wide findings; the lowest family is named."""
    from scripts.build_report import family_rollup

    cards = [{"family": "a", "health": 90, "grade": "A", "traffic": {"current": {"clicks": 300}}},
             {"family": "b", "health": 50, "grade": "D", "traffic": {"current": {"clicks": 100}}}]
    host_wide = {"id": "crawl-0001", "status": "open", "type": "broken", "check": "robots_unreachable",
                 "subdomain": "p.example.org", "template": "host", "title": "robots.txt cannot be reached",
                 "evidence": {"urls": ["https://p.example.org/robots.txt"]}}
    r = family_rollup("p.example.org", cards, [host_wide], 1000)
    assert r["rollup"]["weighted"] == 80 and r["rollup"]["host_wide"] == 40  # (90*300 + 50*100) / 400; broken x 1.0
    assert r["health"] == 40 and r["grade"] == "D" and r["rollup"]["lowest"]["family"] == "b"


def test_report_template_ids_are_unique():
    """Two elements with one id break the report: $("x") finds only the first (a "hosts" section once emptied
    the Reference tables)."""
    import re
    from collections import Counter

    html = "".join((ROOT / "scripts" / "templates" / name).read_text(encoding="utf-8")
                   for name in ("discovery_report.html", "method.html"))  # the method section is inlined locally
    ids = Counter(re.findall(r'\bid="([^"$]+)"', html))
    assert [k for k, n in ids.items() if n > 1] == []


def test_property_switch_only_on_the_site():
    """Published reports list the site's tenants for the header switch; local pages and snapshots do not."""
    from scripts.build_report import build

    report = {"tenant": "a.org", "findings": []}
    assert '"_tenants": ["a.org", "b.org"]' in build(report, [], None, site_tenants=["a.org", "b.org"])
    assert '"_tenants": []' in build(report, [], None)


def test_host_page_keeps_only_its_host(tmp_path):
    """A host page shows one host's findings, reference rows and crawl count; the scores stay as on the tenant
    page."""
    from types import SimpleNamespace

    from scripts.build_report import focus_host

    f = lambda i, h: {"id": i, "subdomain": h, "status": "open"}  # noqa: E731
    report = {"hosts": {"a.org": {}, "b.org": {}}, "findings": [f("x-1", "a.org"), f("x-2", "b.org")],
              "sections": {"a.org": {}, "b.org": {}}, "sitemaps": {"b.org": {}}, "gsc_comparison": [{"path": "/s"}],
              "_audit": {"pages": 30, "summary": {"a.org": {"pages": 21}, "b.org": {"pages": 9}}},
              "_changes": {"new": ["x-1", "x-2"], "resolved": [f("x-3", "b.org")]}}
    rows = list(report["findings"])
    tenant = SimpleNamespace(raw={"gsc_sitemaps_snapshot": {"property": "https://b.org/"}})
    focus_host(report, "a.org", rows, tenant)
    assert [x["id"] for x in report["findings"]] == ["x-1"] and [x["id"] for x in rows] == ["x-1"]
    assert list(report["hosts"]) == ["a.org"] and report["sitemaps"] == {} and report["gsc_comparison"] == []
    assert report["_audit"]["pages"] == 21 and report["_changes"] == {"new": ["x-1"], "resolved": []}
    assert report["_page_host"] == "a.org"


def test_site_hosts_must_not_clash(monkeypatch):
    """Flat URLs: a host may not share its name with a tenant or a site folder."""
    from types import SimpleNamespace

    from scripts import build_site

    monkeypatch.setattr(build_site, "load_tenant", lambda t: SimpleNamespace(host_names=["fix-guide"]))
    with pytest.raises(SystemExit, match="clashes"):
        build_site.site_hosts(["a.org"])


def test_area_scores_and_speed_without_real_user_data():
    """Opted-in tenants get health by area on each host card; speed with no field data and no findings is not 100."""
    from scripts.build_report import add_hosts

    finding = {"id": "intl-0001", "status": "open", "type": "broken", "check": "link_missing_translation",
               "dimension": "intl", "subdomain": "blog.example.org", "template": "post", "title": "Links",
               "evidence": {"urls": ["https://blog.example.org/"]}, "affected_pages": 10}
    report = {"hosts": {"blog.example.org": {"urls": 40}}, "findings": [finding], "_area_scores": True,
              "_audit": {}, "_links": {"run_id": 1},
              "_perf": {"summary": {"blog.example.org": {"pages": 12, "field": 0, "median_score": 74}}}}
    add_hosts(report, Path("missing.json"))
    areas = {a["dimension"]: a for a in report["_hosts"][0]["areas"]}
    assert areas["intl"]["state"] == "scored" and areas["intl"]["health"] == 90  # 40 x share 10/40
    assert areas["onpage"]["state"] == "not checked"  # no crawl audit in this report
    assert areas["perf"]["state"] == "no data" and areas["perf"]["lab_median"] == 74
    report.pop("_area_scores")
    add_hosts(report, Path("missing.json"))
    assert "areas" not in report["_hosts"][0]


def test_gsc_comparison_from_the_run_sitemap_list():
    from scripts.build_report import gsc_comparison

    report = {"sitemaps": {"blog.example.org": {"": [
        {"url": "https://blog.example.org/sitemap.xml", "status": 200, "error": None, "kind": "index", "urls": 90}]}}}
    snap = {"property": "https://blog.example.org/", "sitemaps": [
        {"path": "/sitemap.xml", "status": "Success", "discovered": 95}, {"path": "/gone.xml", "status": "Success"}]}
    assert gsc_comparison(report, snap) == [{"path": "/sitemap.xml", "url": "https://blog.example.org/sitemap.xml",
                                             "gsc_status": "Success", "gsc_discovered": 95, "live_status": 200,
                                             "live_kind": "index", "live_urls": 90}]


def test_history_records_hosts_and_the_trend_ends_with_this_report(tmp_path):
    """Hosts and areas are recorded once per set of runs; the Overview trend lists them and ends with this report."""
    from scripts.build_report import host_trends, record_health

    history = tmp_path / "health-history.json"
    card = {"host": "blog.example.org", "health": 66, "areas": [{"dimension": "intl", "health": 83, "state": "scored"},
                                                                 {"dimension": "perf", "health": 100, "state": "no data"}]}
    report = {"run_id": 1, "_hosts": [card]}
    assert host_trends(report, history) == {"blog.example.org": [{"date": None, "runs": "discovery run 1", "health": 66}]}
    record_health(report, history)
    record_health(report, history)  # same runs: no second entry
    saved = json.loads(history.read_text())
    assert len(saved) == 1 and saved[0]["hosts"] == {"blog.example.org": {"health": 66, "areas": {"intl": 83}}}
    later = {"run_id": 2, "_hosts": [dict(card, health=70)]}
    assert [p["health"] for p in host_trends(later, history)["blog.example.org"]] == [66, 70]


def test_a_new_score_method_rescores_the_same_runs_and_restarts_the_trend(tmp_path):
    from scripts.build_report import host_trends, record_health

    history = tmp_path / "health-history.json"
    old = [{"date": "2026-10-20", "runs": "discovery run 1", "hosts": {"blog.example.org": {"health": 50}}},
           {"date": "2026-10-27", "runs": "discovery run 2", "hosts": {"blog.example.org": {"health": 55}}}]
    history.write_text(json.dumps(old))
    report = {"run_id": 2, "_hosts": [{"host": "blog.example.org", "health": 63}]}
    record_health(report, history)
    saved = json.loads(history.read_text())
    assert len(saved) == 2 and saved[-1]["date"] == "2026-10-27" and saved[-1]["hosts"]["blog.example.org"]["health"] == 63
    assert saved[-1]["rescored"]["method"] == 1 and saved[-1]["rescored"]["hosts"]["blog.example.org"]["health"] == 55
    assert [p["health"] for p in host_trends(report, history)["blog.example.org"]] == [63]  # not 50 -> 63



def test_blogs_page_members_and_ids():
    """/blogs/ lists the hosts the tenants tag, each prepared as on its own page; ids are prefixed by host because
    they repeat across tenants, and the original id is kept for links to the subdomain page."""
    from scripts import build_site
    from scripts.build_report import collection_report, parse_collections

    assert parse_collections("blogs:Blogs,x") == [{"slug": "blogs", "name": "Blogs"}]
    members = build_site.collection_members(["aspose.cloud", "groupdocs.cloud"])
    assert members["blogs"] == [("aspose.cloud", "blog.aspose.cloud"), ("groupdocs.cloud", "blog.groupdocs.cloud")]
    R = collection_report("Blogs", "blogs", members["blogs"])
    ids = [f["id"] for f in R["findings"]]
    assert len(ids) == len(set(ids)) and all("/" in i and f["_orig_id"] == i.split("/", 1)[1]
                                              for i, f in zip(ids, R["findings"]))
    assert [c["host"] for c in R["_hosts"]] == ["blog.aspose.cloud", "blog.groupdocs.cloud"]
    assert all(c["areas"] and c["domain"] for c in R["_hosts"]) and "overall" not in R
