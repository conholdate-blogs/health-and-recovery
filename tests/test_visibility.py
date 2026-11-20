from datetime import date

from core.visibility import ai_platform, ai_referrals, complete_months, keyword_counts, monthly_dr, upsert_entry


def test_complete_months():
    m = complete_months(date(2026, 11, 20), 3)
    assert m == [("2026-08", "2026-08-01", "2026-08-31"), ("2026-09", "2026-09-01", "2026-09-30"),
                 ("2026-10", "2026-10-01", "2026-10-31")]
    assert complete_months(date(2026, 11, 3), 1) == [("2026-09", "2026-09-01", "2026-09-30")]  # Oct not final yet
    assert complete_months(date(2026, 11, 4), 1) == [("2026-10", "2026-10-01", "2026-10-31")]
    assert complete_months(date(2026, 1, 10), 2)[0][0] == "2025-11"


def test_monthly_dr():
    h = [{"date": "2026-11-19", "hosts": {"b": {"dr": 28, "dr_date": "2026-11-19"}}},
         {"date": "2026-11-26", "hosts": {"b": {"dr": 29, "dr_date": "2026-11-26"}}},
         {"date": "2026-12-03", "hosts": {"b": {"dr": 29, "dr_date": "2026-11-26"}}},
         {"date": "2026-12-10", "hosts": {"b": {}}}]
    assert monthly_dr(h, "b") == {"2026-11": 29}


def test_ai_platform():
    assert ai_platform("chatgpt.com") == "ChatGPT"
    assert ai_platform("chat.openai.com") == "ChatGPT"
    assert ai_platform("www.perplexity.ai") == "Perplexity"
    assert ai_platform("gemini.google.com") == "Gemini"
    assert ai_platform("copilot.microsoft.com") == "Copilot"
    assert ai_platform("claude.ai") == "Claude"
    assert ai_platform("google") is None
    assert ai_platform("(direct)") is None
    assert ai_platform(None) is None


def test_ai_referrals_one_host():
    rows = [{"hostName": "blog.x.com", "sessionSource": "chatgpt.com", "sessions": 3.0},
            {"hostName": "blog.x.com", "sessionSource": "perplexity.ai", "sessions": 5.0},
            {"hostName": "blog.x.com", "sessionSource": "google", "sessions": 99.0},
            {"hostName": "www.x.com", "sessionSource": "chatgpt.com", "sessions": 7.0}]
    out = ai_referrals(rows, "blog.x.com")
    assert out == {"sessions": 8, "by_platform": {"Perplexity": 5, "ChatGPT": 3}}


def test_keyword_counts():
    rows = [{"keys": ["a"], "impressions": 10, "position": 2.0, "clicks": 1},
            {"keys": ["b"], "impressions": 20, "position": 8.5, "clicks": 0},
            {"keys": ["c"], "impressions": 10, "position": 30.0, "clicks": 0}]
    out = keyword_counts(rows, 100)
    assert out["queries"] == 3 and out["top10"] == 2 and out["top3"] == 1 and out["with_clicks"] == 1
    assert out["hidden_share"] == 0.6
    assert "capped" not in out
    assert keyword_counts([], 0, capped=True) == {"queries": 0, "top10": 0, "top3": 0, "with_clicks": 0,
                                                   "impressions": 0, "hidden_share": None, "capped": True}


def test_upsert_replaces_same_day_and_carries_dr():
    h = upsert_entry([], {"date": "2026-11-19", "hosts": {"b": {"dr": 28, "dr_date": "2026-11-19"}}})
    h = upsert_entry(h, {"date": "2026-11-19", "hosts": {"b": {"dr": 29, "dr_date": "2026-11-19"}}})
    assert len(h) == 1 and h[0]["hosts"]["b"]["dr"] == 29
    h = upsert_entry(h, {"date": "2026-11-26", "hosts": {"b": {"keywords": {"queries": 5}}}})
    assert [e["date"] for e in h] == ["2026-11-19", "2026-11-26"]
    assert h[-1]["hosts"]["b"]["dr"] == 29 and h[-1]["hosts"]["b"]["dr_date"] == "2026-11-19"
