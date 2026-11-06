"""Item ledger: the individual issues of the exact checks, tracked across runs, so a blog's report can say how many
were fixed, how many are new and how many are still open (SK, 2026-10-27).

An item is one thing to fix: one link (link check), one missing language of one post, one unsupported language;
from discovery (blog subdomains, 2026-10-30), one URL a sitemap lists wrongly (twice, in two sitemaps, without
hreflang, ...) or one sitemap with a file-level problem (no lastmod, cannot be fetched, ...).
Only exhaustive checks have items; sampled checks (crawl audit, text check, speed) stay at finding level, because a
page leaving the sample is not a fix. An item that is gone counts as fixed when its place still exists, and as
removed when it is gone (a deleted post is not a fix): link check, the file in the blog's repo; discovery, the URL
in the run's sitemaps (sitemap-level items always count as fixed: dropping a broken sitemap is a fix). Each run
closes only items of its own source.

Ledger (reports/<tenant>/items.json): {"runs": [run refs], "baseline": {host: {"run", "date"}},
"items": {key: {"source", "check", "host", "page", "file", "link", "first_seen", "last_seen", "fixed", "removed"}}}
(items without "source" are link-check items).
Shown as issues = fixed + open, fixed, open and the latest scan date (SK, 2026-10-27: no "new", no baseline on
the pages; new issues show as a growing issue count). Fixed % = fixed / issues; removed items count neither way.

A gone link item whose link is still in the same file under another check is "changed" (field `became`), not fixed
(SK, 2026-11-06: a 404 link that redirects again after Redirects.json was repaired still holds the old URL). It
counts neither as fixed nor as open: its successor item (e.g. link_redirected) counts as open in its own row.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path


def run_items(link_run: dict) -> dict[str, dict]:
    """key -> item for one link-check run. A link that appears twice in one file is two items."""
    items: dict[str, dict] = {}
    for host, h in (link_run.get("hosts") or {}).items():
        seen: Counter = Counter()
        for i in h.get("issues") or []:
            base = f"{i['check']}|{host}|{i['file']}|{i['link']}"
            seen[base] += 1
            items[f"{base}|{seen[base]}"] = {"check": i["check"], "host": host, "page": i.get("page"),
                                             "file": i["file"], "link": i["link"]}
        for p in h.get("partial") or []:
            for lang in p.get("missing") or []:
                items[f"translation_partial|{host}|{p['folder']}|{lang}"] = {
                    "check": "translation_partial", "host": host, "page": p.get("page"), "file": p["folder"],
                    "link": lang}
        for lang in h.get("unsupported") or {}:
            items[f"language_unsupported|{host}|{lang}"] = {"check": "language_unsupported", "host": host,
                                                           "page": None, "file": None, "link": lang}
    return items


def discovery_items(discovery_run: dict) -> dict[str, dict]:
    """key -> item for one discovery run's `items` (blog subdomains only). A URL listed three times in one sitemap
    is two items, as the finding counts it."""
    items: dict[str, dict] = {}
    for host, issues in (discovery_run.get("items") or {}).items():
        seen: Counter = Counter()
        for i in issues:
            base = f"{i['check']}|{host}|{i['sitemap'] or ''}|{i['url'] or ''}"
            seen[base] += 1
            items[f"{base}|{seen[base]}"] = {"source": "discovery", "check": i["check"], "host": host,
                                             "page": i["url"], "file": i["sitemap"], "link": None}
    return items


def repo_items(repo_run: dict) -> dict[str, dict]:
    """key -> item for one repo file run (core/audit/repo.py): one entry or post file. An invalid file is one item."""
    items: dict[str, dict] = {}
    for host, h in (repo_run.get("hosts") or {}).items():
        seen: Counter = Counter()
        for i in h.get("issues") or []:
            base = f"{i['check']}|{host}|{i['file']}|{i['link'] or ''}"
            seen[base] += 1
            items[f"{base}|{seen[base]}"] = {"source": "repo-audit", "check": i["check"], "host": host,
                                             "page": i.get("page"), "file": i["file"], "link": i["link"]}
    return items


def in_repo(repos: dict[str, str]) -> dict:
    """Link check: host -> does a gone item's post still exist in the host's clone (pulled to the run's commit)."""
    return {host: lambda rec, root=Path(path): not rec["file"] or (root / rec["file"]).exists()
            for host, path in repos.items()}


def in_sitemaps(hosts, listed: set[str] | None) -> dict:
    """Discovery: host -> is a gone item's URL still in the run's sitemaps (listed = every URL of the run; None
    when the inventory is not at hand, then every gone item counts as fixed)."""
    return {host: lambda rec: not rec["page"] or listed is None or rec["page"] in listed for host in hosts}


def update(ledger: dict, run_ref: str, run_date: str, items: dict[str, dict], exists: dict,
           source: str = "link-audit") -> dict:
    """Add one run (once). New keys open; open keys of the same source and a host the run covered (exists: host ->
    check) that are missing from the run are fixed if exists(item) says their place is still there, else removed;
    a key that comes back reopens."""
    if run_ref in ledger.setdefault("runs", []):
        return ledger
    known = ledger.setdefault("items", {})
    for host in {it["host"] for it in items.values()} | set(exists):
        ledger.setdefault("baseline", {}).setdefault(host, {"run": run_ref, "date": run_date})
    for key, it in items.items():
        rec = known.get(key)
        if rec is None:
            known[key] = {**it, "first_seen": run_date, "last_seen": run_date, "fixed": None, "removed": None}
        else:
            rec.update(last_seen=run_date, fixed=None, removed=None)
            rec.pop("changed", None)
            rec.pop("became", None)
    # the same link in the same file, now reported by another check (a 404 link that redirects again)
    still = {(it["host"], it["file"], it["link"]): it["check"] for it in items.values()
             if it.get("source", "link-audit") == "link-audit" and it.get("link")}
    for key, rec in known.items():
        if (key in items or rec["fixed"] or rec["removed"] or rec.get("changed") or rec["host"] not in exists
                or rec.get("source", "link-audit") != source):
            continue
        became = still.get((rec["host"], rec["file"], rec["link"])) if source == "link-audit" else None
        if became and became != rec["check"]:
            rec["changed"], rec["became"] = run_date, became
        else:
            rec["fixed" if exists[rec["host"]](rec) else "removed"] = run_date
    ledger["runs"].append(run_ref)
    return ledger


def counts(ledger: dict, host: str) -> dict:
    """Since the host's baseline: items found at the baseline, new since, fixed, removed, still open, fixed %;
    the same per check."""
    base = (ledger.get("baseline") or {}).get(host)
    if not base:
        return {}

    def tally(recs: list[dict]) -> dict:
        fixed = sum(1 for r in recs if r["fixed"])
        still = sum(1 for r in recs if not r["fixed"] and not r["removed"] and not r.get("changed"))
        return {"issues": fixed + still, "fixed": fixed, "open": still,
                "removed": sum(1 for r in recs if r["removed"]),
                # changed: the link is still in the post, now under another check (counted there, as open)
                "changed": sum(1 for r in recs if r.get("changed")),
                "redirects": sum(1 for r in recs if r.get("became") == "link_redirected"),
                "baseline": sum(1 for r in recs if r["first_seen"] == base["date"]),
                "new": sum(1 for r in recs if r["first_seen"] > base["date"]),
                "fixed_pct": round(100 * fixed / (fixed + still)) if fixed + still else None}

    mine = [r for r in (ledger.get("items") or {}).values() if r["host"] == host]
    by_check: dict = {}
    for r in mine:
        by_check.setdefault(r["check"], []).append(r)
    scanned = max((d for r in mine for d in (r["last_seen"], r["fixed"], r["removed"], r.get("changed")) if d),
                  default=base["date"])
    return {**tally(mine), "since": base["date"], "scanned": scanned, "runs": len(ledger.get("runs") or []),
            "by_check": {c: tally(rs) for c, rs in sorted(by_check.items())}}
