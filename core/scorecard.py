"""Family scorecards: a health grade per section that ignores traffic, so a small family's team sees how
broken its own pages are, next to the traffic numbers that say how much it matters to the business.

health = 100 - severe - min(COSMETIC_CAP, cosmetic), floored at 0, where each open finding costs
WEIGHT[type] x share of the family's pages it affects (at least MIN_SHARE). Findings that share a root cause
(GROUPS) count once: only the worst in a group. A canonical that points at a 4xx/5xx page counts as broken.
Grades: A >= 90, B >= 75, C >= 60, D >= 40, F below.
"""

from __future__ import annotations

import math
import re
from urllib.parse import urlsplit

from core.findings import template_section

WEIGHT = {"broken": 40.0, "incorrect": 20.0, "not_optimized": 6.0, "improvable": 2.0}
SEVERE = ("broken", "incorrect")
COSMETIC_CAP = 20.0
MIN_SHARE = 0.25
# exact checks that count every file or entry they cover weigh their real share, with this small floor
# (SK, 2026-11-06: one bad post file of 13k cost as much as a quarter of the site under MIN_SHARE)
MIN_SHARE_EXACT = 0.01
EXACT_SHARE_SOURCES = {"repo-audit"}
# raised whenever the formula changes, so trends compare only scores computed the same way (health-history.json
# entries without "method" are 1; 2 = sampled findings weigh their estimated pages, 2026-10-27; 3 = repo file
# checks weigh their real share, floor MIN_SHARE_EXACT, 2026-11-06)
SCORE_METHOD = 3
_LIVE_OBSERVED = re.compile(r"^(\d+) of (\d+) sampled")
GRADES = ((90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F"))
TYPE_ORDER = ("broken", "incorrect", "not_optimized", "improvable")

# check -> root-cause group; checks not listed form their own group
GROUPS = {
    **dict.fromkeys(("fetch_failed", "parse_error", "empty", "over_limit", "section_no_sitemap", "host_no_sitemap",
                     "malformed_child", "foreign_child"), "sitemap"),
    **dict.fromkeys(("lastmod_bulk", "lastmod_missing", "lastmod_invalid", "dup_in_file", "cross_sitemap_dups",
                     "off_host", "http_urls", "excluded_host"), "sitemap content"),
    **dict.fromkeys(("http_error", "fetch_error", "soft_404", "robots_blocked"), "page errors"),
    **dict.fromkeys(("canonical_missing", "canonical_multiple", "canonical_elsewhere", "canonical_broken"),
                    "canonical"),
    **dict.fromkeys(("hreflang_none", "hreflang_partial", "hreflang_missing", "hreflang_no_self", "hreflang_invalid",
                     "hreflang_conflict", "hreflang_no_xdefault", "html_lang_missing", "html_lang_mismatch"),
                    "hreflang"),
    **dict.fromkeys(("redirected", "redirect_chain", "redirect_temporary", "meta_refresh"), "redirects"),
    **dict.fromkeys(("title_missing", "title_multiple", "title_length", "title_duplicate"), "titles"),
    **dict.fromkeys(("description_missing", "description_length", "description_duplicate"), "descriptions"),
    **dict.fromkeys(("h1_missing", "h1_multiple"), "headings"),
    **dict.fromkeys(("viewport_missing", "viewport_no_zoom"), "viewport"),
    **dict.fromkeys(("lcp_poor", "lcp_needs_work", "inp_poor", "inp_needs_work", "cls_poor", "cls_needs_work",
                     "ttfb_poor", "lab_no_paint", "origin_cwv_poor", "origin_cwv_needs_work"),
                    "speed"),
    **dict.fromkeys(("lab_load_failed",), "page errors"),  # same root cause as HTTP errors
    **dict.fromkeys(("content_needs_js", "no_structured_data", "llms_txt_missing", "llms_txt_invalid",
                     "ai_bot_blocked", "ai_bot_firewalled"), "ai"),
    **dict.fromkeys(("text_typo", "text_leftover", "text_topic_mismatch"), "wording"),
    **dict.fromkeys(("link_missing_translation", "link_damaged", "link_wrong_language", "link_broken"),
                    "internal links"),
    **dict.fromkeys(("translation_partial", "language_unsupported"), "translations"),
    **dict.fromkeys(("redirect_file_invalid", "redirect_not_working", "redirect_key_malformed", "redirect_self_loop",
                     "redirect_target_bad"), "redirect file"),
    **dict.fromkeys(("post_front_matter_broken", "post_url_relative"), "post files"),
}
# the one-glance status line on a card: label -> groups it summarizes
STATUS = {"Sitemap": ("sitemap",), "Pages": ("page errors",), "Canonical": ("canonical",), "hreflang": ("hreflang",)}
# health by area at the top of a host's report (SK, 2026-10-26; tenant opt-in report.area_scores): finding
# dimension -> area name. Always shown in this order; other dimensions follow when they have findings.
AREAS = {"crawl": "Crawl & indexing", "onpage": "On-page content", "intl": "Languages", "ai": "AI readiness",
         "perf": "Speed"}


def half_up(x: float) -> int:
    """Round halves up (65.5 -> 66, 65.4 -> 65), as people expect (SK, 2026-10-27); round() sends halves to even."""
    return math.floor(x + 0.5 + 1e-9)


# names for dimensions that only manual findings use; shown after the five areas when they have findings
OTHER_AREAS = {"ux": "User experience", "content": "Content", "cross": "Cross-site", "platform": "Platform"}


def grade(health: float) -> str:
    return next(g for floor, g in GRADES if health >= floor)


def family_of(f: dict, host: str, families: set) -> str | None:
    """The section a finding belongs to on a sectioned host: from its template, or for manual findings from
    the first path segment of its evidence URLs."""
    if f["subdomain"] != host:
        return None
    sec = template_section(f["template"])
    if sec is not None:
        return sec if sec in families else None
    for u in f["evidence"]["urls"]:
        seg = [s for s in urlsplit(u).path.split("/") if s]
        if seg and seg[0] in families:
            return seg[0]
    return None


def effective_type(f: dict) -> str:
    """A canonical whose target answers 4xx/5xx removes the page from search: count it as broken."""
    if f.get("check") == "canonical_elsewhere":
        for loc in (f["evidence"].get("locations") or []):
            note = loc.get("note") or ""
            if loc.get("role") == "canonical target" and note.startswith(("HTTP 4", "HTTP 5")):
                return "broken"
    return f["type"]


def group_of(f: dict) -> str:
    check = f.get("check")
    if not check:
        return f"manual:{f['id']}"
    if check == "http_error" and all("//" in urlsplit(u).path for u in f["evidence"]["urls"]):
        return "sitemap"  # pages listed with a malformed URL: the sitemap is the root cause
    return GROUPS.get(check, check)


def live_sample(f: dict) -> tuple[int, int] | None:
    """(failing, sampled) of a redirect_not_working finding: from evidence.live_sample, else from its observed text
    ("1 of 40 sampled sources ...", findings recorded before the field existed)."""
    ev = f.get("evidence") or {}
    if ev.get("live_sample"):
        failed, sampled = ev["live_sample"]
        return int(failed), int(sampled)
    m = _LIVE_OBSERVED.match(ev.get("observed") or "")
    return (int(m[1]), int(m[2])) if m else None


def share_of(f: dict, family_urls: int) -> float:
    """How much of the family a finding covers. A sampled finding: its estimated pages (each failing template's
    share x that template's URLs) / the family's URLs, so a one-page template weighs as one page, not as the
    whole family (SK, 2026-10-27); the failing share of the sample when the URL counts are missing. Else the
    Prioritizer's share for discovery findings, else affected pages / family URLs.

    Repo file checks (SK, 2026-11-06) are exact, so they weigh what they really cover, floored at MIN_SHARE_EXACT
    instead of MIN_SHARE: an invalid Redirects.json breaks every redirect (all of it); redirects that do not work
    weigh the failing share of the live sample; the other checks their files or entries / the subdomain's URLs."""
    if f.get("source") in EXACT_SHARE_SOURCES:
        check = f.get("check")
        if check == "redirect_file_invalid":
            share = 1.0
        elif check == "redirect_not_working" and live_sample(f):
            failed, sampled = live_sample(f)
            share = failed / sampled if sampled else 1.0
        elif f.get("affected_pages") and family_urls:
            share = f["affected_pages"] / family_urls
        else:
            share = 1.0
        return max(MIN_SHARE_EXACT, min(1.0, share))
    sample = (f["evidence"] or {}).get("sample")
    if sample and f.get("affected_pages") and family_urls:
        share = f["affected_pages"] / family_urls
    elif sample:
        failed, sampled = sum(v[0] for v in sample.values()), sum(v[1] for v in sample.values())
        share = failed / sampled if sampled else 1.0
    elif (f.get("impact") or {}).get("share") is not None:
        share = f["impact"]["share"]
    elif f.get("affected_pages") and family_urls:
        share = f["affected_pages"] / family_urls
    else:
        share = 1.0 if f.get("check") else MIN_SHARE
    return max(MIN_SHARE, min(1.0, share))


def scorecard(family: str, findings: list[dict], family_urls: int) -> dict:
    groups: dict = {}  # group -> (penalty, type, finding id)
    for f in findings:
        if f["status"] != "open":
            continue
        t = effective_type(f)
        penalty = WEIGHT.get(t, 2.0) * share_of(f, family_urls)
        g = group_of(f)
        if g not in groups or penalty > groups[g][0]:
            groups[g] = (penalty, t, f["id"])
    severe = sum(p for p, t, _ in groups.values() if t in SEVERE)
    cosmetic = sum(p for p, t, _ in groups.values() if t not in SEVERE)
    health = max(0, half_up(100 - severe - min(COSMETIC_CAP, cosmetic)))

    open_f = [f for f in findings if f["status"] == "open"]
    top = sorted(open_f, key=lambda f: (TYPE_ORDER.index(effective_type(f)),
                                        -((f.get("impact") or {}).get("clicks_28d") or 0), f["id"]))
    status = {}
    for label, gs in STATUS.items():
        worst = [t for g, (_, t, _) in groups.items() if g in gs]
        status[label] = "bad" if any(t in SEVERE for t in worst) else "warn" if worst else "ok"
    return {
        "family": family,
        "health": health,
        "grade": grade(health),
        "penalties": sorted(({"group": g, "points": round(p, 1), "type": t, "id": fid}
                             for g, (p, t, fid) in groups.items()), key=lambda x: -x["points"]),
        "cosmetic_capped": cosmetic > COSMETIC_CAP,
        "counts": {t: sum(1 for f in open_f if effective_type(f) == t) for t in TYPE_ORDER},
        "unverified": sum(1 for f in findings if f["status"] == "unverified"),
        "top": [{"id": f["id"], "title": f["title"], "type": effective_type(f),
                 "blocker": effective_type(f) == "broken"} for f in top[:3]],
        "status": status,
    }


def area_scores(findings: list[dict], urls: int) -> list[dict]:
    """Health per area: the scorecard formula over one dimension's findings only. The overall health spends the
    points of every area (and the cosmetic cap across all of them), so it is never above an area's score."""
    dims = list(AREAS) + sorted({f["dimension"] for f in findings if f["status"] == "open"} - set(AREAS))
    areas = []
    for dim in dims:
        c = scorecard(dim, [f for f in findings if f.get("dimension") == dim], urls)
        areas.append({"dimension": dim, "name": AREAS.get(dim) or OTHER_AREAS.get(dim, dim), "health": c["health"],
                      "grade": c["grade"], "penalties": c["penalties"], "counts": c["counts"]})
    return areas


def family_scorecards(findings: list[dict], host: str, families: list[str], section_stats: dict,
                      traffic: dict | None = None) -> list[dict]:
    """One card per family of `host`, worst health first. section_stats: {family: {'urls', 'langs'}} from the
    discovery report; traffic: {family: {window: {'clicks', 'impressions', 'pages'}}} from traffic-summary."""
    fams = set(families)
    by_family: dict = {f: [] for f in families}
    for f in findings:
        fam = family_of(f, host, fams)
        if fam:
            by_family[fam].append(f)
    cards = []
    for fam in families:
        stats = section_stats.get(fam) or {}
        tr = (traffic or {}).get(fam) or {}
        urls = stats.get("urls") or 0
        card = scorecard(fam, by_family[fam], urls or (tr.get("current") or {}).get("pages") or 0)
        card.update(urls=urls, langs=len(stats.get("langs") or {}), traffic=tr)
        cards.append(card)
    return sorted(cards, key=lambda c: (c["health"], -((c["traffic"].get("current") or {}).get("clicks") or 0)))
