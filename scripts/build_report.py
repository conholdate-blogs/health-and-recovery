"""Render the site health report (discovery, crawl audits, latest speed, AI and text checks) as one HTML page.

    python scripts/build_report.py                     # TENANT (default aspose.app): newest runs in reports/<tenant>/
    python scripts/build_report.py --tenant conholdate.cloud --out reports/conholdate.cloud/discovery-latest.html
    python scripts/build_report.py --findings reports/aspose.app/findings.json  # without the store (GitHub Actions)

The page embeds the run's data as JSON and renders it in the browser (no external requests except
Google Fonts). Findings come from the findings store (open + unverified, discovery and manual review,
with notes and what is new or resolved in this run); without a store, from the run JSON.
Optional --notes / --audit-notes: plain-text files, one key takeaway per line, shown at the top and in the
crawl audit section. --audit '' leaves the crawl audit out.
Output: reports/<tenant>/<input name>.html, or --out. GitHub Pages serves site/<tenant>/index.html (--standalone).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core import brand  # noqa: E402
from core.findings import FindingsStore  # noqa: E402
from core.fix_guide import AREAS, GUIDE, TERMS, guide_key  # noqa: E402
from core.items import counts as item_counts  # noqa: E402
from core.paths import TenantPaths, tenant_paths  # noqa: E402
from core.report_view import (  # noqa: E402
    confidence,
    grade_summary,
    health_trend,
    merge_root_causes,
    run_changes,
    systemic_issues,
    top_risks,
)
from core.scorecard import (SCORE_METHOD, area_scores, family_of, family_scorecards, grade, half_up,  # noqa: E402
                            scorecard)
from core.tenant import load_tenant  # noqa: E402

TEMPLATE = REPO_ROOT / "scripts" / "templates" / "discovery_report.html"
METHOD = REPO_ROOT / "scripts" / "templates" / "method.html"  # "How this audit works", shared with build_site


# For hosting the file on its own (GitHub Pages): the artifact host adds this skeleton itself.
STANDALONE_HEAD = (
    '<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '<meta name="robots" content="noindex, nofollow">\n'
)


# The Pages site has one shared fix guide page and one method page (scripts/build_site.py); a snapshot is served
# three levels below the site root (/<tenant>/archive/<date>/).
SNAPSHOT_GUIDE_URL = "../../../fix-guide/"
SNAPSHOT_METHOD_URL = "../../../method/"


def method_html() -> str:
    """The method fragment with its glossary rows for the terms marked in check names (core.fix_guide.TERMS)."""
    rows = "".join(f"\n          <tr><td><b>{html.escape(k)}</b></td><td>{html.escape(v)}</td></tr>" for k, v in TERMS.items())
    return METHOD.read_text(encoding="utf-8").replace("__TERMS__", rows)


def method_section() -> str:
    return ('  <section aria-labelledby="s-method" id="method">\n    <h2 id="s-method">How this audit works</h2>\n'
            + method_html() + "  </section>\n")


def build(report: dict, notes: list[str], run_date: str | None, standalone: bool = False,
          guide_url: str | None = None, site_tenants: list[str] | None = None,
          site_hosts: list[str] | None = None, method_url: str | None = None,
          collections: list[dict] | None = None) -> str:
    """The report page. With guide_url, "How to fix" links go to that shared fix guide page instead of a full
    guide table inside the report (the table stays for local pages); with method_url, "How this audit works"
    links go to that shared page instead of a section at the end. With site_tenants (the published site),
    the header offers a switch to the other tenants' reports, and with site_hosts to the tenant's host pages
    (published at the site root next to the tenant reports)."""
    data = dict(report, _notes=notes, _run_date=run_date, _guide_url=guide_url, _tenants=site_tenants or [],
                _site_hosts=site_hosts or [], _method_url=method_url, _collections=collections or [])
    if guide_url and report.get("_guide"):  # only the rows this report's findings and Fix progress table use
        used = {f.get("_guide") for f in report["findings"]}
        used |= {k for h in report.get("_hosts") or [] for k in (h.get("items") or {}).get("by_check", {})}
        data["_guide"] = dict(report["_guide"], rows={k: v for k, v in report["_guide"]["rows"].items() if k in used})
    payload = json.dumps(data, default=str).replace("</", "<\\/")
    template = TEMPLATE.read_text(encoding="utf-8")
    title = f"{report.get('_page_host') or report['tenant']} Site Health"
    page = (template.replace("__TITLE__", title).replace("__FAVICON__", brand.FAVICON_LINK)
            .replace("__LOGO__", brand.logo(22)).replace("__METHOD__\n", "" if method_url else method_section())
            .replace("__DATA__", payload))
    return STANDALONE_HEAD + page if standalone else page


def read_notes(path: str | None) -> list[str]:
    if not path:
        return []
    lines = [ln.strip().lstrip("-• ").strip() for ln in Path(path).read_text(encoding="utf-8").splitlines()]
    return [n for n in lines if n]


def run_date_of(path: Path, prefix: str) -> str | None:
    return path.stem.split("-run")[0].removeprefix(prefix) if "-run" in path.stem else None


def runs_by_name(pattern: str, folder: Path) -> list[Path]:
    """Report files in `folder` ordered by the date and run number in their names (file times are meaningless
    after a git checkout)."""
    def key(p: Path):
        m = re.search(r"(\d{4}-\d{2}-\d{2})-run(\d+)", p.name)
        return (m.group(1), int(m.group(2))) if m else ("", 0)
    return sorted(folder.glob(pattern), key=key)


def newest(pattern: str, folder: Path) -> Path | None:
    found = runs_by_name(pattern, folder)
    return found[-1] if found else None


def from_export(rows: list[dict], run_ref: str) -> tuple[list[dict], dict]:
    """Open findings and what `run_ref` changed, from reports/<tenant>/findings.json (for CI, where the store is
    absent).
    Same shape as FindingsStore.findings() and .changes()."""
    findings = sorted((f for f in rows if f["status"] in ("open", "unverified")), key=lambda f: f["id"])
    def seq(ref: str | None) -> int:  # discovery-run7 -> 7
        m = re.search(r"(\d+)$", ref or "")
        return int(m.group(1)) if m else 0

    prefix = run_ref.rstrip("0123456789")
    first_run = not any((f.get("first_seen_run") or "").startswith(prefix) and seq(f["first_seen_run"]) < seq(run_ref)
                        for f in rows)
    new = [f["id"] for f in findings if f.get("first_seen_run") == run_ref]
    resolved = [f for f in rows if f["status"] == "resolved" and f.get("resolved_run") == run_ref]
    return findings, {"run": run_ref, "new": [] if first_run else new, "resolved": resolved, "first_run": first_run}


def audit_summary(paths: list[Path], notes: list[str]) -> dict:
    """Merge crawl-audit runs (oldest first): the newest result wins for a page checked more than once, so
    section-scoped batches add up to one picture. Only what the page shows (not per-page facts)."""
    from core.audit.crawl import summarize_pages

    pages: dict = {}
    runs = []
    for path in paths:
        a = json.loads(path.read_text(encoding="utf-8"))
        runs.append({"run_id": a["run_id"], "date": run_date_of(path, "crawl-audit-"), "pages": len(a["pages"]),
                     "sections": a["params"].get("sections"), "requests": a["requests"],
                     "duration_s": a["duration_s"], "stopped_early": a["stopped_early"]})
        for p in a["pages"]:
            pages[p["url"]] = p
    last = json.loads(paths[-1].read_text(encoding="utf-8"))
    sections: dict = {}
    for p in pages.values():
        if p["section"]:
            sections.setdefault(p["host"], set()).add(p["section"])
    return {"run_id": runs[-1]["run_id"], "date": runs[-1]["date"], "runs": runs, "params": last["params"],
            "summary": summarize_pages(list(pages.values())), "pages": len(pages),
            "requests": sum(r["requests"] for r in runs), "duration_s": sum(r["duration_s"] for r in runs),
            "stopped_early": any(r["stopped_early"] for r in runs),
            "sections": {h: sorted(v) for h, v in sections.items()}, "notes": notes}


def add_families(report: dict, summary_path: Path) -> None:
    """Family scorecards per sectioned host (from reports/<tenant>/traffic-summary.json, written by prioritize.py), and
    each finding's family for the report's Family filter. A host page (_page_host) keeps only its own host."""
    if not summary_path.is_file():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    report["_families"] = {"windows": summary["windows"], "hosts": {}}
    for host, traffic in summary["hosts"].items():
        if report.get("_page_host") and host != report["_page_host"]:
            continue
        families = list(traffic)
        cards = report["_families"]["hosts"][host] = family_scorecards(
            report["findings"], host, families, (report.get("sections") or {}).get(host) or {}, traffic)
        for f in report["findings"]:
            fam = family_of(f, host, set(families))
            if fam:
                f["_family"] = fam
        if report.get("_area_scores"):  # family rows show health by area like subdomain rows (SK, 2026-10-27)
            for c in cards:
                c["areas"] = [{**a, "state": "scored"} for a in area_scores(
                    [f for f in report["findings"] if f.get("_family") == c["family"] and f["subdomain"] == host],
                    c["urls"] or ((c["traffic"].get("current") or {}).get("pages") or 0))]
    if not report["_families"]["hosts"]:  # a tenant without sectioned hosts has no family cards
        del report["_families"]


def family_rollup(host: str, cards: list[dict], findings: list[dict], urls: int) -> dict:
    """Health of a host with family cards: its families' health weighted by search clicks (equal weights without
    traffic), minus the points of host-wide findings that belong to no family (root sitemap, robots.txt, ...).
    The lowest family is named, because an average hides a failing one."""
    clicks = {c["family"]: ((c.get("traffic") or {}).get("current") or {}).get("clicks") or 0 for c in cards}
    total = sum(clicks.values())
    weighted = (sum(c["health"] * clicks[c["family"]] for c in cards) / total if total
                else sum(c["health"] for c in cards) / len(cards))
    families = {c["family"] for c in cards}
    host_wide = scorecard(host, [f for f in findings if not family_of(f, host, families)], urls)
    health = max(0, half_up(weighted - (100 - host_wide["health"])))
    low = min(cards, key=lambda c: c["health"])
    return {"health": health, "grade": grade(health), "penalties": host_wide["penalties"],
            "cosmetic_capped": host_wide["cosmetic_capped"],
            "rollup": {"families": len(cards), "weighted": half_up(weighted), "host_wide": 100 - host_wide["health"],
                       "by_clicks": bool(total), "lowest": {"family": low["family"], "grade": low["grade"],
                                                           "health": low["health"]}}}


def add_hosts(report: dict, summary_path: Path) -> None:
    """A health row per host (same score as families, whole host as the scope), with the host's search traffic
    from reports/<tenant>/traffic-summary.json. A host with family cards rolls its families up (family_rollup)."""
    family_cards = (report.get("_families") or {}).get("hosts") or {}
    totals = {}
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        totals = summary.get("host_totals") or {}
        report["_traffic_window"] = (summary.get("windows") or {}).get("current")
    items_path = summary_path.parent / "items.json"
    ledger = json.loads(items_path.read_text(encoding="utf-8")) if items_path.is_file() else None
    cards = []
    for host, stats in sorted((report.get("hosts") or {}).items()):
        mine = [f for f in report["findings"] if f["subdomain"] == host]
        card = scorecard(host, mine, stats.get("urls") or 0)
        if family_cards.get(host):
            card.update(family_rollup(host, family_cards[host], mine, stats.get("urls") or 0))
        card.update(host=card.pop("family"), urls=stats.get("urls") or 0, traffic=totals.get(host) or {})
        if report.get("_area_scores"):
            card["areas"] = host_areas(report, host, mine, stats.get("urls") or 0)
        if ledger and host in (ledger.get("baseline") or {}):  # fixed / new / still open of the exact checks
            card["items"] = item_counts(ledger, host)
        cards.append(card)
    if cards:
        report["_hosts"] = cards


def host_areas(report: dict, host: str, findings: list[dict], urls: int) -> list[dict]:
    """Health by area for one host, each marked as checked or not by the runs in this report. Speed without
    real-user data and without findings says so instead of scoring 100 from lab runs alone."""
    ran = {"crawl": True, "onpage": bool(report.get("_audit")),
           "intl": bool(report.get("_audit") or report.get("_links")),
           "ai": bool(report.get("_ai") or report.get("_audit")), "perf": bool(report.get("_perf"))}
    perf = ((report.get("_perf") or {}).get("summary") or {}).get(host) or {}
    areas = area_scores(findings, urls)
    for a in areas:
        a["state"] = "scored" if ran.get(a["dimension"], True) else "not checked"
        if a["dimension"] == "perf" and a["state"] == "scored":
            a["pages"], a["lab_median"] = perf.get("pages") or 0, perf.get("median_score")
            if not perf.get("field") and not a["penalties"]:
                a["state"] = "no data"
    return areas


def focus_host(report: dict, host: str, all_rows: list[dict] | None, tenant) -> None:
    """Turn the tenant report into one host's page: only that host's findings, changes, reference rows and (for a
    host with families) family cards. Scores are the same as on the tenant page."""
    drop_hosts(report, {host})
    report["_page_host"] = host
    audit = report.get("_audit")
    if audit:  # pages audited on this host, not across the tenant
        audit["pages"] = ((audit.get("summary") or {}).get(host) or {}).get("pages") or 0
    report["findings"] = [f for f in report["findings"] if f["subdomain"] == host]
    if all_rows is not None:
        all_rows[:] = [f for f in all_rows if f["subdomain"] == host]
    for key in ("sections", "sitemaps"):
        if isinstance(report.get(key), dict):
            report[key] = {h: v for h, v in report[key].items() if h == host}
    snapshot = (tenant.raw.get("gsc_sitemaps_snapshot") or {}).get("property") or ""
    if urlsplit(snapshot).netloc != host:
        report["gsc_comparison"] = []
    changes = report.get("_changes")
    if isinstance(changes, dict):
        ids = {f["id"] for f in report["findings"]}
        changes["new"] = [i for i in changes.get("new") or [] if i in ids]
        changes["resolved"] = [f for f in changes.get("resolved") or [] if f.get("subdomain") == host]


def gsc_comparison(report: dict, snap: dict) -> list[dict]:
    """Submitted sitemaps (tenant gsc_sitemaps_snapshot) next to the live ones from the run's sitemap list, for
    runs made before the snapshot was added (discovery writes the same rows itself when it has one)."""
    base = (snap.get("property") or "").rstrip("/")
    live = {s["url"]: s for sections in (report.get("sitemaps") or {}).values() for rows in sections.values()
            for s in rows}
    rows = []
    for s in snap.get("sitemaps") or []:
        r = live.get(base + s["path"])
        if r is not None:
            rows.append({"path": s["path"], "url": r["url"], "gsc_status": s.get("status"),
                         "gsc_discovered": s.get("discovered"), "live_status": r["status"] or r["error"],
                         "live_kind": r["kind"], "live_urls": r["urls"]})
    return rows


def drop_hosts(report: dict, keep: set) -> list[str]:
    """Leave out hosts the tenant no longer audits (dropped from its YAML after a run): run files are never
    edited, so their per-host data is filtered here. Returns the hosts left out."""
    audit, ai, perf, text = (report.get(k) or {} for k in ("_audit", "_ai", "_perf", "_text"))
    tables = [report.get("hosts"), audit.get("summary"), ai.get("summary"), perf.get("summary"),
              perf.get("origins"), text.get("summary")]
    dropped: set = set()
    for table in tables:
        if isinstance(table, dict):
            for h in [h for h in table if h not in keep]:
                dropped.add(h)
                del table[h]
    return sorted(dropped)


def runs_label(report: dict) -> str:
    runs = f"discovery run {report['run_id']}"
    if report.get("_audit"):
        runs += f", crawl audit run {report['_audit']['run_id']}"
    if report.get("_perf"):
        runs += f", speed audit run {report['_perf']['run_id']}"
    if report.get("_ai"):
        runs += f", AI audit run {report['_ai']['run_id']}"
    if report.get("_text"):
        runs += f", text check run {report['_text']['run_id']}"
    if report.get("_links"):
        runs += f", link check run {report['_links']['run_id']}"
    if report.get("_repo"):
        runs += f", repo file check run {report['_repo']['run_id']}"
    return runs


def perf_summary(path: Path) -> dict:
    """What the page shows of a speed-audit run: run id, date, scope, per-host summary, whole-host field data."""
    a = json.loads(path.read_text(encoding="utf-8"))
    return {"run_id": a["run_id"], "date": run_date_of(path, "perf-audit-"), "params": a["params"],
            "pages": len(a["pages"]), "summary": a["summary"], "origins": a["origins"],
            "stopped_early": a["stopped_early"], "incomplete": a.get("incomplete", False)}


def ai_summary(path: Path) -> dict:
    """What the page shows of an AI-audit run: run id, date, per-host access and llms.txt summary."""
    a = json.loads(path.read_text(encoding="utf-8"))
    return {"run_id": a["run_id"], "date": run_date_of(path, "ai-audit-"), "summary": a["summary"]}


def text_summary(path: Path) -> dict:
    """What the page shows of a text-check run: run id, date, model, pages checked, per-host summary."""
    a = json.loads(path.read_text(encoding="utf-8"))
    return {"run_id": a["run_id"], "date": run_date_of(path, "text-audit-"), "model": a["params"]["model"],
            "pages_checked": a["pages_checked"], "unchecked": len(a["unchecked"]), "summary": a["summary"]}


def link_summary(path: Path) -> dict:
    """What the page shows of a link-audit run: run id, date, per-host posts, links and issues."""
    a = json.loads(path.read_text(encoding="utf-8"))
    return {"run_id": a["run_id"], "date": run_date_of(path, "link-audit-"), "summary": a["summary"]}


def repo_summary(folder: Path) -> dict | None:
    """What the page uses of the repo file runs: the newest, and every run of its day, so a fix and the re-checks
    after it on one day all show as resolved."""
    runs = runs_by_name("repo-audit-*-run*.json", folder)
    if not runs:
        return None
    a = json.loads(runs[-1].read_text(encoding="utf-8"))
    day = run_date_of(runs[-1], "repo-audit-")
    ids = [int(p.stem.rpartition("run")[2]) for p in runs if run_date_of(p, "repo-audit-") == day]
    return {"run_id": a["run_id"], "run_ids": ids, "date": day, "summary": a["summary"]}


def add_views(report: dict, all_rows: list[dict] | None = None, history_path: Path | None = None) -> None:
    """Fix guide, confidence, merged root causes, systemic issues, top risks, grade summary, changes since the
    last run and the family health trend (see core/report_view.py)."""
    findings = report["findings"]
    report["_guide"] = {"areas": AREAS, "rows": GUIDE, "terms": TERMS}
    for f in findings:
        f["_guide"] = guide_key(f.get("check"), f.get("source"))
        f["_confidence"] = confidence(f)
    refs = [f"discovery-run{report['run_id']}"]
    if report.get("_audit"):
        refs.append(f"crawl-audit-run{report['_audit']['run_id']}")
    if report.get("_perf"):
        refs.append(f"perf-audit-run{report['_perf']['run_id']}")
    if report.get("_ai"):
        refs.append(f"ai-audit-run{report['_ai']['run_id']}")
    if report.get("_text"):
        refs.append(f"text-audit-run{report['_text']['run_id']}")
    if report.get("_links"):
        refs.append(f"link-audit-run{report['_links']['run_id']}")
    if report.get("_repo"):
        refs += [f"repo-audit-run{i}" for i in report["_repo"]["run_ids"]]
    changes = run_changes(all_rows or findings, refs)
    titles = {f["id"]: f for f in (all_rows or findings)}
    changes["resolved"] = [{"id": i, "title": titles[i]["title"], "subdomain": titles[i]["subdomain"]}
                           for i in changes["resolved"]]
    report["_run_changes"] = changes
    fam = report.get("_families")
    if not fam:
        return
    host = next(iter(fam["hosts"]))
    cards = fam["hosts"][host]
    families = {c["family"] for c in cards}
    merge_root_causes(findings, host, families)
    report["_systemic"] = systemic_issues(findings, host, families)
    report["_risks"] = top_risks(findings, host, families)
    report["_summary"] = grade_summary(cards)
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path and history_path.is_file() else []
    report["_trend"] = health_trend(cards, history, runs_label(report))


def record_health(report: dict, history_path: Path) -> None:
    """Append this run's family, host and area health to reports/<tenant>/health-history.json (once per set of
    runs and score method). Hosts are recorded from 2026-10-26 on; older entries have families only. The entry of
    the same runs scored by an older method is rescored, keeping its old scores."""
    from datetime import date

    fam = report.get("_families")
    hosts = report.get("_hosts") or []
    if not fam and not hosts:
        return
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.is_file() else []
    runs = runs_label(report)
    same = [h for h in history if h["runs"] == runs]
    if current := next((h for h in same if h.get("method", 1) == SCORE_METHOD), None):
        # entries from before 2026-11-06 have no stats: the newest gets today's, so the History table starts
        # with it (SK chose to start fresh, no backfill)
        if current is history[-1] and not any("stats" in v for v in current["hosts"].values()):
            for c in hosts:
                if c["host"] in current["hosts"]:
                    current["hosts"][c["host"]]["stats"] = host_stats(report, c)
            history_path.write_text(json.dumps(history, indent=1) + "\n", encoding="utf-8")
        return
    entry: dict = {"date": date.today().isoformat(), "runs": runs, "method": SCORE_METHOD}
    if same:
        old = same[-1]
        history.remove(old)
        entry["date"] = old["date"]
        entry["rescored"] = {"on": date.today().isoformat(), "method": old.get("method", 1),
                             **{k: old[k] for k in ("families", "hosts", "note") if k in old}}
    if fam:
        entry["families"] = {c["family"]: c["health"] for c in fam["hosts"][next(iter(fam["hosts"]))]}
    entry["hosts"] = {c["host"]: {"health": c["health"], **({"areas": {a["dimension"]: a["health"] for a in c["areas"]
                                                                       if a["state"] == "scored"}}
                                                            if c.get("areas") else {}),
                                  "stats": host_stats(report, c)} for c in hosts}
    history.append(entry)
    history_path.write_text(json.dumps(history, indent=1) + "\n", encoding="utf-8")


def host_stats(report: dict, card: dict) -> dict:
    """The Overview tiles of one host, kept per run for the History table (SK, 2026-11-06): search clicks and
    impressions of the 28 days ending `traffic_to`, issue types (findings), open issues (link and sitemap items)."""
    cur = (card.get("traffic") or {}).get("current") or {}
    return {"clicks": cur.get("clicks"), "impressions": cur.get("impressions"),
            "traffic_to": (report.get("_traffic_window") or [None, None])[1],
            "issue_types": sum(1 for f in report.get("findings") or [] if f["subdomain"] == card["host"] and not f.get("_merged_into")),
            "open_issues": (card.get("items") or {}).get("open")}


def run_changes_note(runs: str, before: str | None) -> list[str]:
    """What ran since the previous entry, from the two runs labels: a check's first run, or a newer run of it."""
    parse = lambda s: dict((m[1], int(m[2])) for m in re.finditer(r"([A-Za-z][\w ]*?) run (\d+)", s or ""))  # noqa: E731
    now, prev = parse(runs), parse(before)
    if before is None:
        return ["first run"]
    return [f"{name[0].upper()}{name[1:]} added" if name not in prev else f"new {name} (run {n})"
            for name, n in now.items() if prev.get(name) != n]


def host_history(host: str, history_path: Path) -> list[dict]:
    """One row per recorded run with stats for a host, newest first, each with a note of what changed since the
    entry before it (so a score jump from a new check reads as that, not as the site getting worse)."""
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.is_file() else []
    rows, before = [], None
    for h in history:
        entry = (h.get("hosts") or {}).get(host)
        if not entry:
            continue
        if "stats" in entry:
            note = run_changes_note(h["runs"], before["runs"] if before else None)
            if before and before.get("method", 1) != h.get("method", 1):
                note.append(f"score method {h.get('method', 1)}")
            rows.append({"date": h["date"], "health": entry["health"], "areas": entry.get("areas") or {},
                         **entry["stats"], "note": note})
        before = h
    return rows[::-1]


def host_trends(report: dict, history_path: Path) -> dict[str, list[dict]]:
    """Health of each host per recorded set of runs, ending with this report (for the Overview and host cards)."""
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.is_file() else []
    runs = runs_label(report)
    trends = {}
    for card in report.get("_hosts") or []:
        host = card["host"]
        points = [{"date": h["date"], "runs": h["runs"], "health": h["hosts"][host]["health"]}
                  for h in history if host in (h.get("hosts") or {}) and h.get("method", 1) == SCORE_METHOD]
        if not points or points[-1]["runs"] != runs:
            points.append({"date": None, "runs": runs, "health": card["health"]})
        trends[host] = points
    return trends


def snapshot(page: str, label: str, report: dict, archive: Path) -> Path:
    """Freeze a standalone report page into reports/<tenant>/archive/<date>[-n].html and list it in index.json.
    Snapshots are never rebuilt (older reports stay as they were)."""
    from datetime import date

    archive.mkdir(parents=True, exist_ok=True)
    day = date.today().isoformat()
    name, n = f"{day}.html", 1
    while (archive / name).exists():
        n += 1
        name = f"{day}-{n}.html"
    (archive / name).write_text(page, encoding="utf-8")
    index_path = archive / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else []
    runs = runs_label(report)
    index.append({"file": name, "date": day if n == 1 else f"{day} ({n})", "label": label, "runs": runs})
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return archive / name


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", nargs="?", help="discovery JSON (default: newest in reports/<tenant>/)")
    ap.add_argument("--tenant", default=os.environ.get("TENANT", "aspose.app"))
    ap.add_argument("--notes", help="text file, one key takeaway per line")
    ap.add_argument("--audit", help="comma-separated crawl-audit JSONs, merged oldest first "
                    "(default: every crawl-audit run in reports/<tenant>/; '' to leave out)")
    ap.add_argument("--audit-notes", help="text file, one crawl-audit takeaway per line")
    ap.add_argument("--perf", help="speed-audit JSON (default: newest perf-audit run in reports/<tenant>/; "
                    "'' to leave out)")
    ap.add_argument("--ai", help="AI-audit JSON (default: newest ai-audit run in reports/<tenant>/; '' to leave out)")
    ap.add_argument("--text", help="text-check JSON (default: newest text-audit run in reports/<tenant>/; "
                    "'' to leave out)")
    ap.add_argument("--links", help="link-audit JSON (default: newest link-audit run in reports/<tenant>/; "
                    "'' to leave out)")
    ap.add_argument("--out", help="output HTML path")
    ap.add_argument("--host", help="one host's page: only that host's findings and rows (scores as on the "
                    "tenant page)")
    ap.add_argument("--site-hosts", help="comma-separated hosts with their own page on the published site: adds a "
                    "host switch to the header (build_site.py passes it)")
    ap.add_argument("--site-tenants", help="comma-separated tenants on the published site: adds a property "
                    "switch to the header (build_site.py passes it)")
    ap.add_argument("--guide-url", help="link to the shared fix guide page instead of including the guide table "
                    "(build_site.py passes ../fix-guide/)")
    ap.add_argument("--method-url", help="link to the shared method page instead of including the section "
                    "(build_site.py passes ../method/)")
    ap.add_argument("--standalone", action="store_true",
                    help="add doctype, charset, viewport and noindex (for GitHub Pages: --out docs/index.html)")
    ap.add_argument("--store", help="findings store (default: data/<tenant>/findings.sqlite)")
    ap.add_argument("--findings", help="read findings from this export (reports/<tenant>/findings.json) instead of "
                    "the store")
    ap.add_argument("--snapshot", metavar="LABEL",
                    help="also freeze this report (standalone) into reports/<tenant>/archive/ with this label, and "
                    "record the family health in reports/<tenant>/health-history.json (do this after every full run)")
    ap.add_argument("--areas", action="store_true",
                    help="health by area even when the tenant does not opt in (the Blogs page passes it)")
    ap.add_argument("--site-collections", help="comma-separated slug:Name of the site's cross-domain pages (e.g. "
                    "blogs:Blogs): adds them to the domain switch (build_site.py passes it)")
    return ap


def prepare(args: argparse.Namespace) -> tuple[dict, list[str], str | None, str, Path] | int:
    """The report data for one tenant (or one of its hosts), ready for build(): runs, findings, scores, views.
    Returns (report, notes, run date, a one-line note of the sources, the discovery run file) or an exit code."""
    paths: TenantPaths = tenant_paths(args.tenant)
    folder = paths.reports

    if args.report:
        src = Path(args.report)
    else:
        src = newest("discovery-*-run*.json", folder)
        if src is None:
            print(f"No discovery-*.json in {folder}. Run scripts/discover.py first.", file=sys.stderr)
            return 1

    report = json.loads(src.read_text(encoding="utf-8"))
    notes = read_notes(args.notes)
    all_rows: list[dict] | None = None
    audit_srcs: list[Path] = []
    if args.audit:
        audit_srcs = [Path(a) for a in args.audit.split(",")]
    elif args.audit is None:
        audit_srcs = runs_by_name("crawl-audit-*-run*.json", folder)
    audit_src = audit_srcs[-1] if audit_srcs else None
    if audit_srcs:
        report["_audit"] = audit_summary(audit_srcs, read_notes(args.audit_notes))
    perf_src = Path(args.perf) if args.perf else newest("perf-audit-*-run*.json", folder) if args.perf is None else None
    if perf_src:
        report["_perf"] = perf_summary(perf_src)
    ai_src = Path(args.ai) if args.ai else newest("ai-audit-*-run*.json", folder) if args.ai is None else None
    if ai_src:
        report["_ai"] = ai_summary(ai_src)
    text_src = Path(args.text) if args.text else newest("text-audit-*-run*.json", folder) if args.text is None else None
    if text_src:
        report["_text"] = text_summary(text_src)
    link_src = (Path(args.links) if args.links else newest("link-audit-*-run*.json", folder)
                if args.links is None else None)
    if link_src:
        report["_links"] = link_summary(link_src)
    if repo_runs := repo_summary(folder):
        report["_repo"] = repo_runs
    # fixes the agent made on a site repo, with SK's approval (reports/<tenant>/agent-fixes.json; SK, 2026-11-07:
    # the report shows that the Health & Recovery Agent found and fixed them)
    if (fixes := folder / "agent-fixes.json").is_file():
        report["_agent_fixes"] = json.loads(fixes.read_text(encoding="utf-8"))
    if args.findings:
        rows = json.loads(Path(args.findings).read_text(encoding="utf-8"))
        all_rows = rows
        report["findings"], report["_changes"] = from_export(rows, f"discovery-run{report['run_id']}")
        if not audit_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "crawl-audit"]
        if not perf_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "perf-audit"]
        if not ai_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "ai-audit"]
        if not text_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "text-audit"]
        if not link_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "link-audit"]
    elif Path(store_path := args.store or str(paths.findings_store)).is_file():
        store = FindingsStore(store_path)
        run_ref = f"discovery-run{report['run_id']}"
        if not store.db.execute("SELECT 1 FROM runs WHERE ref = ?", (run_ref,)).fetchone():
            print(f"{run_ref} is not in the findings store; run scripts/findings.py import-discovery {src}",
                  file=sys.stderr)
            return 1
        report["findings"] = store.findings()
        all_rows = store.findings(("open", "unverified", "resolved", "superseded"))
        report["_changes"] = store.changes(run_ref)
        if not audit_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "crawl-audit"]
        if not perf_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "perf-audit"]
        if not ai_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "ai-audit"]
        if not text_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "text-audit"]
        if not link_src:
            report["findings"] = [f for f in report["findings"] if f["source"] != "link-audit"]
    else:
        print(f"No findings store at {store_path}; using the run's own findings.", file=sys.stderr)
    try:
        tenant = load_tenant(args.tenant)
    except FileNotFoundError:
        tenant = None
    dropped = drop_hosts(report, set(tenant.host_names)) if tenant else []
    if dropped:
        print(f"Left out hosts no longer in tenants/{args.tenant}.yaml: {', '.join(dropped)}", file=sys.stderr)
    if tenant and not report.get("gsc_comparison") and tenant.raw.get("gsc_sitemaps_snapshot"):
        report["gsc_comparison"] = gsc_comparison(report, tenant.raw["gsc_sitemaps_snapshot"])
    if args.host:
        if not tenant or args.host not in tenant.host_names:
            print(f"{args.host} is not a host of tenant {args.tenant}", file=sys.stderr)
            return 2
        focus_host(report, args.host, all_rows, tenant)
    report["_area_scores"] = bool(args.areas or (tenant and (tenant.raw.get("report") or {}).get("area_scores")))
    report["_manager_view"] = bool(tenant and (tenant.raw.get("report") or {}).get("manager_view"))
    add_families(report, paths.traffic_summary)
    add_hosts(report, paths.traffic_summary)
    add_views(report, all_rows, paths.health_history)
    if report["_manager_view"] or args.areas:
        report["_host_trends"] = host_trends(report, paths.health_history)
    if report.get("_page_host"):
        report["_history"] = host_history(report["_page_host"], paths.health_history)
    run_date = run_date_of(src, "discovery-")
    sources = (f"{src.name}" + (f" and {len(audit_srcs)} crawl-audit runs (newest {audit_src.name})" if audit_src else "")
               + (f" and {perf_src.name}" if perf_src else "") + (f" and {ai_src.name}" if ai_src else "")
               + (f" and {text_src.name}" if text_src else ""))
    return report, notes, run_date, sources, src


def parse_collections(spec: str | None) -> list[dict]:
    """'blogs:Blogs,forums:Forums' -> [{'slug': 'blogs', 'name': 'Blogs'}, ...]"""
    return [dict(zip(("slug", "name"), item.split(":", 1))) for item in (spec or "").split(",") if ":" in item]


def collection_report(name: str, slug: str, members: list[tuple[str, str]]) -> dict:
    """One page across domains (SK, 2026-10-27: Blogs): each member subdomain prepared exactly as its own page, so
    its numbers match; no overall score. Finding ids repeat across tenants, so they get the host as prefix here
    (_orig_id keeps the id the subdomain page uses)."""
    R: dict = {"tenant": name, "run_id": "–", "hosts": {}, "findings": [], "_hosts": [], "_host_trends": {},
               "_collection": slug, "_manager_view": True, "sections": {}, "sitemaps": {}, "gsc_comparison": [],
               "requests": 0, "sitemaps_fetched": 0, "duration_s": 0, "_dates": [],
               "_run_changes": {"new": [], "resolved": [], "runs": []}}
    for tenant, host in members:
        prepared = prepare(parser().parse_args(["--tenant", tenant, "--findings",
                                                str(tenant_paths(tenant).findings_export), "--host", host, "--areas"]))
        if isinstance(prepared, int):
            raise SystemExit(f"{name}: {host} of {tenant} could not be prepared")
        report, _, run_date, _, _ = prepared
        pid = lambda i: f"{host}/{i}"  # noqa: E731
        for f in report["findings"]:
            f["_orig_id"], f["id"] = f["id"], pid(f["id"])
            if f.get("_merged_into"):
                f["_merged_into"] = pid(f["_merged_into"])
            f["_merged"] = [pid(i) for i in f.get("_merged") or []]
        card = report["_hosts"][0]
        card["domain"] = tenant
        for x in card["penalties"] + [p for a in card.get("areas") or [] for p in a["penalties"]] + card["top"]:
            x["id"] = pid(x["id"])
        ch = report["_run_changes"]
        R["_run_changes"]["new"] += [pid(i) for i in ch.get("new") or []]
        R["_run_changes"]["resolved"] += [dict(r, id=pid(r["id"])) for r in ch.get("resolved") or []]
        R["hosts"].update(report["hosts"])
        R["findings"] += report["findings"]
        R["_hosts"].append(card)
        R["_host_trends"].update(report.get("_host_trends") or {})
        R["_guide"] = report["_guide"]
        R["_dates"] += [d for d in (run_date, *((report.get(k) or {}).get("date") for k in
                                                ("_audit", "_perf", "_ai", "_text", "_links", "_repo"))) if d]
    return R


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.host and args.snapshot:
        print("Snapshots are per tenant; build the tenant report with --snapshot, not a host page.", file=sys.stderr)
        return 2
    prepared = prepare(args)
    if isinstance(prepared, int):
        return prepared
    report, notes, run_date, sources, src = prepared
    paths = tenant_paths(args.tenant)
    out = Path(args.out) if args.out else src.with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    site_tenants = args.site_tenants.split(",") if args.site_tenants else None
    site_hosts = args.site_hosts.split(",") if args.site_hosts else None
    collections = parse_collections(args.site_collections)
    out.write_text(build(report, notes, run_date, args.standalone, args.guide_url, site_tenants, site_hosts,
                         args.method_url, collections), encoding="utf-8")
    if args.snapshot:
        page = build(report, notes, run_date, standalone=True, guide_url=SNAPSHOT_GUIDE_URL,
                     method_url=SNAPSHOT_METHOD_URL)
        print(f"Snapshot: {snapshot(page, args.snapshot, report, paths.archive)}")
        record_health(report, paths.health_history)
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB) from {sources}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
