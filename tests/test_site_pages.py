"""Rules file and issue log (scripts/site_pages.py). Offline."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.fix_guide import GUIDE  # noqa: E402
from scripts import site_pages  # noqa: E402


def test_every_rule_names_real_checks_and_unique_ids():
    data = site_pages.load_rules()
    ids = [r["id"] for r in data["rules"]]
    assert len(ids) == len(set(ids))
    for r in data["rules"]:
        assert r["id"].split("-")[0] in data["areas"], r["id"]
        assert r["status"] in ("active", "proposed", "retired"), r["id"]
        for c in r.get("checks") or []:
            assert c in GUIDE, f"{r['id']}: unknown check {c}"


def test_issue_log_status_and_hand_found_rows(tmp_path, monkeypatch):
    class P:
        reports = tmp_path
        findings_export = tmp_path / "findings.json"

    monkeypatch.setattr(site_pages, "tenant_paths", lambda t: P)
    f = lambda i, check, status: {  # noqa: E731
        "id": i,
        "subdomain": "b.example.com",
        "check": check,
        "status": status,  # noqa: E731
        "source": "crawl-audit",
        "dimension": "intl",
        "type": "incorrect",
        "affected_pages": 3,
        "detected_at": "2026-11-12",
        "title": check,
        "resolved_at": "2026-11-13T00:00:00" if status == "resolved" else None,
    }
    P.findings_export.write_text(
        json.dumps(
            [f("a", "h1_missing", "open"), f("b", "title_untranslated", "resolved"), f("c", "title_length", "resolved")]
        )
    )
    (tmp_path / "agent-fixes.json").write_text(
        json.dumps(
            [
                {
                    "host": "b.example.com",
                    "check": "title_untranslated",
                    "found": "2026-11-12",
                    "commits": ["abc1234def"],
                    "repo": "o/r",
                    "fixed": "2026-11-12",
                    "verified": "2026-11-13",
                    "result": "Live",
                },
                {
                    "host": "b.example.com",
                    "check": "language_names",
                    "found": "2026-11-11",
                    "issue": "Menu names",
                    "commits": ["fff0000"],
                    "repo": "o/r",
                    "fixed": "2026-11-11",
                    "verified": None,
                },
            ]
        )
    )
    (tmp_path / "issue-notes.json").write_text(
        json.dumps({"a": {"notes": [{"date": "2026-11-12", "by": "SK", "text": "later"}]}})
    )
    rows = {r["id"] if r["id"] != "–" else r["check"]: r for r in site_pages.issue_rows("t", "b.example.com")}
    assert rows["a"]["status"] == "Open" and "Shoaib Khan: later" in rows["a"]["notes"][0]
    assert rows["b"]["status"] == "✓ Verified live" and "abc1234" in rows["b"]["commits"]
    assert rows["c"]["status"] == "Resolved" and rows["c"]["by"] == "unknown"
    assert rows["language_names"]["status"] == "Pushed, waiting for deploy"
    assert list(rows)[0] == "a"  # open first


def test_fixer_names_and_verified_date_in_status(tmp_path, monkeypatch):
    class P:
        reports = tmp_path
        findings_export = tmp_path / "findings.json"

    monkeypatch.setattr(site_pages, "tenant_paths", lambda t: P)
    P.findings_export.write_text("[]")
    (tmp_path / "agent-fixes.json").write_text(
        json.dumps(
            [
                {
                    "host": "b.example.com",
                    "check": "x",
                    "found": "2026-11-11",
                    "issue": "a",
                    "fixed": "2026-11-11",
                    "verified": "2026-11-12",
                },
                {
                    "host": "b.example.com",
                    "check": "y",
                    "found": "2026-11-11",
                    "issue": "b",
                    "fixed_by": "Translation Agent",
                    "fixed": "2026-11-11",
                    "verified": "2026-11-12",
                },
            ]
        )
    )
    rows = {r["check"]: r for r in site_pages.issue_rows("t", "b.example.com")}
    assert rows["x"]["by"] == "Health and Recovery Agent" and rows["y"]["by"] == "Translation Agent"
    html_ = site_pages.issue_log_page("t", "b.example.com", "", "", "")
    assert "Verified live<small class=\"\">12 Nov 2026</small>" in html_ and ">Verified live</th>" not in html_
    assert ">Fixed by</th>" in html_ and 'class="tile t-fixed"' in html_
    assert site_pages.who("SK") == "Shoaib Khan"
