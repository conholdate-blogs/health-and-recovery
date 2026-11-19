"""Visibility numbers per host, the free counterparts of a backlink tool's dashboard (SK, 2026-11-19):

- keywords: Search Console queries with impressions in a window, how many rank in the top 10 / top 3 (average
  position), and the share of impressions Google hides (anonymized queries), so the count is read as a floor;
- AI referrals: GA4 sessions whose source is an AI assistant (ChatGPT, Perplexity, Gemini, Copilot, ...);
- Domain Rating: a backlink tool's score, per registered domain (every subdomain shares it).

Pure functions only; the fetching lives in scripts/visibility.py. No query text is kept, only counts.
"""

from __future__ import annotations

# GA4 sessionSource substring -> platform (lower-case match; the first hit wins, so specific names come first)
AI_SOURCES: list[tuple[str, str]] = [
    ("chatgpt", "ChatGPT"), ("chat.openai", "ChatGPT"), ("openai", "ChatGPT"),
    ("perplexity", "Perplexity"),
    ("gemini.google", "Gemini"), ("bard.google", "Gemini"),
    ("copilot", "Copilot"),
    ("claude.ai", "Claude"), ("anthropic", "Claude"),
    ("deepseek", "DeepSeek"),
    ("grok", "Grok"), ("x.ai", "Grok"),
    ("meta.ai", "Meta AI"),
    ("you.com", "You.com"),
    ("mistral", "Mistral"),
    ("poe.com", "Poe"),
]


def ai_platform(source: str | None) -> str | None:
    """The AI platform a GA4 session source belongs to, or None."""
    s = (source or "").lower()
    for key, name in AI_SOURCES:
        if key in s:
            return name
    return None


def ai_referrals(rows: list[dict], host: str) -> dict:
    """GA4 rows {hostName, sessionSource, sessions} -> {"sessions": n, "by_platform": {name: n}} for one host."""
    by: dict[str, int] = {}
    for r in rows:
        if (r.get("hostName") or "").lower() != host.lower():
            continue
        name = ai_platform(r.get("sessionSource"))
        if name:
            by[name] = by.get(name, 0) + round(r.get("sessions") or 0)
    by = dict(sorted(by.items(), key=lambda kv: -kv[1]))
    return {"sessions": sum(by.values()), "by_platform": by}


def keyword_counts(rows: list[dict], total_impressions: int | None, capped: bool = False) -> dict:
    """GSC query rows {keys: [query], impressions, position, clicks} -> counts.

    hidden_share: impressions not covered by any query row (Google's anonymized queries) / all impressions.
    capped: the fetch stopped at its row limit, so `queries` is a floor."""
    queries = [r for r in rows if (r.get("impressions") or 0) > 0]
    shown = sum(r.get("impressions") or 0 for r in queries)
    out = {
        "queries": len(queries),
        "top10": sum(1 for r in queries if (r.get("position") or 999) <= 10),
        "top3": sum(1 for r in queries if (r.get("position") or 999) <= 3),
        "with_clicks": sum(1 for r in queries if (r.get("clicks") or 0) > 0),
        "impressions": total_impressions,
        "hidden_share": None,
    }
    if total_impressions:
        out["hidden_share"] = round(max(0.0, 1 - shown / total_impressions), 3)
    if capped:
        out["capped"] = True
    return out


def upsert_entry(history: list[dict], entry: dict) -> list[dict]:
    """Keep one entry per date (a re-run the same day replaces it), oldest first. Per-host values the new entry
    lacks (e.g. Domain Rating without an API key) are carried over from the newest earlier entry, with their own
    date, so the latest entry always holds the latest known value."""
    rest = [e for e in history if e["date"] != entry["date"]]
    earlier = [e for e in rest if e["date"] < entry["date"]]
    if earlier:
        last = earlier[-1]
        for host, vals in entry["hosts"].items():
            prev = last["hosts"].get(host) or {}
            if vals.get("dr") is None and prev.get("dr") is not None:
                vals["dr"], vals["dr_date"] = prev["dr"], prev.get("dr_date") or last["date"]
    return sorted(rest + [entry], key=lambda e: e["date"])
