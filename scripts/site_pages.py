"""Issue log (one page per subdomain, /<subdomain>/issues/) and Rules (one shared page, /rules/) for the Pages site.
SK, 2026-11-12: keep the list of issues we identify and fix, with notes, and our rules, structurally on the website.

Issue log rows come from the committed files only:
- reports/<tenant>/findings.json: every finding of the subdomain, open and resolved (found, severity, scope);
- reports/<tenant>/agent-fixes.json: fixes by the agent (commit, fixed, verified, result); a row is matched to its
  finding by `finding` id, else by check; a fix without a finding (found by hand) is a row of its own;
- reports/<tenant>/issue-notes.json (optional): {"<finding id or check>": {"status": "...", "notes": [{"date",
  "by", "text"}]}}: decisions and notes; `status` overrides the computed one (e.g. "Reviewed", "Won't fix").
Rules come from docs/rules.yaml.
"""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

import yaml

from core.fix_guide import GUIDE, guide_key
from core.paths import tenant_paths

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = REPO_ROOT / "docs" / "rules.yaml"
SEVERITY = {"broken": "Broken", "incorrect": "Incorrect", "not_optimized": "Not optimized", "improvable": "Improvable"}
AREA_NAMES = {"crawl": "Crawl", "onpage": "On-page", "intl": "Languages", "ai": "AI", "perf": "Speed", "ux": "UX"}
# Who fixed an issue or set a rule, as shown on the pages (SK, 2026-11-12). Data files may use the short keys.
FIXERS = ["Health and Recovery Agent", "Translation Agent", "Blog Team Platform", "Shoaib Khan"]
WHO = {
    "SK": "Shoaib Khan",
    "Agent": "Health and Recovery Agent",
    "Translation agent": "Translation Agent",
    "translation agent": "Translation Agent",
    "Platform": "Blog Team Platform",
}
TEAM = {"Shoaib Khan": "Blogs Team"}  # shown under the name on the Rules page
DEFAULT_FIXER = "Health and Recovery Agent"  # agent-fixes.json rows without `fixed_by`


def who(name) -> str:
    return WHO.get(str(name or "").strip(), str(name or "").strip())


STATUS_ORDER = ["Open", "Pushed, waiting for deploy", "✓ Verified live", "Resolved", "Reviewed", "Won't fix"]
ITEM_SOURCES = {"repo-audit": "items", "link-audit": "links", "discovery": "URLs"}

EXTRA_CSS = """
td.id { white-space: nowrap; font-size: 13px } td.id small { display: block; color: var(--muted) }
td.st { white-space: nowrap; font-weight: 600 } .st-open { color: var(--broken) } .st-ok { color: #067647 }
@media (prefers-color-scheme: dark) { .st-ok { color: #47cd89 } }
td.st small { display: block; font-weight: 400; color: var(--muted) }
td.fix, td.notes { font-size: 13px } td.notes ul { margin: 0; padding-left: 16px } td.notes li + li { margin-top: 4px }
td.notes small, td.fix small { color: var(--muted) } td.num { white-space: nowrap }
.rule { font-weight: 600; min-width: 260px } code { font-size: 13px }
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def day(iso: str | None) -> str:
    if not iso:
        return "–"
    d = date.fromisoformat(str(iso)[:10])
    return f"{d.day} {d.strftime('%b %Y')}"


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _commit_links(row: dict) -> str:
    repo = row.get("repo") or ""
    out = []
    for sha in row.get("commits") or []:
        short = esc(sha[:7])
        out.append(f'<a href="https://github.com/{esc(repo)}/commit/{esc(sha)}">{short}</a>' if repo else short)
    return ", ".join(out)


def issue_rows(tenant: str, host: str) -> list[dict]:
    paths = tenant_paths(tenant)
    findings = [f for f in _load(paths.findings_export, []) if f.get("subdomain") == host]
    fixes = [r for r in _load(paths.reports / "agent-fixes.json", []) if r.get("host") == host]
    notes = _load(paths.reports / "issue-notes.json", {})
    by_id = {f["id"]: f for f in findings}
    matched: dict[str, list[dict]] = {}
    loose = []
    for r in fixes:
        fid = r.get("finding")
        if not fid or fid not in by_id:
            same = sorted(
                (f for f in findings if f.get("check") == r.get("check")), key=lambda f: f.get("detected_at") or ""
            )
            fid = same[-1]["id"] if same else None
        if fid:
            matched.setdefault(fid, []).append(r)
        else:
            loose.append(r)

    rows = []
    for f in findings:
        fx = matched.get(f["id"], [])
        verified = max((r.get("verified") or "" for r in fx), default="")
        if f["status"] in ("open", "unverified"):
            status = "Pushed, waiting for deploy" if fx and not verified else "Open"
        else:
            status = "✓ Verified live" if verified else "Resolved"
        g = GUIDE.get(guide_key(f.get("check"), f.get("source")) or "", {})
        unit = ITEM_SOURCES.get(f.get("source"), "pages")
        note = notes.get(f["id"]) or notes.get(f.get("check") or "") or {}
        rows.append(
            {
                "id": f["id"],
                "area": AREA_NAMES.get(f.get("dimension"), f.get("dimension") or ""),
                "found": f.get("detected_at"),
                "issue": g.get("name") or f.get("title"),
                "check": f.get("check"),
                "guide": guide_key(f.get("check"), f.get("source")),
                "severity": f.get("type"),
                "scope": f"{f.get('affected_pages') or 0:,} {unit}",
                "status": note.get("status") or status,
                "fixed": max((r.get("fixed") or "" for r in fx), default="")
                or (f.get("resolved_at") or "")[:10]
                or None,
                "by": ", ".join(dict.fromkeys(who(r.get("fixed_by") or DEFAULT_FIXER) for r in fx))
                if fx
                else ("unknown" if f["status"] == "resolved" else ""),
                "commits": "; ".join(_commit_links(r) for r in fx),
                "verified": verified or None,
                "notes": [r.get("result") for r in fx if r.get("result")]
                + [f"{day(n.get('date'))} · {who(n.get('by'))}: {n.get('text', '')}" for n in note.get("notes") or []],
                "open": f["status"] in ("open", "unverified"),
            }
        )
    for r in loose:  # fixes of issues found by hand (no finding)
        note = notes.get(r.get("check") or "") or {}
        rows.append(
            {
                "id": "–",
                "area": "found by hand",
                "found": r.get("found"),
                "issue": r.get("issue"),
                "check": r.get("check"),
                "guide": None,
                "severity": None,
                "scope": "–",
                "status": note.get("status")
                or ("✓ Verified live" if r.get("verified") else "Pushed, waiting for deploy"),
                "fixed": r.get("fixed"),
                "by": who(r.get("fixed_by") or DEFAULT_FIXER),
                "commits": _commit_links(r),
                "verified": r.get("verified"),
                "notes": ([r["result"]] if r.get("result") else [])
                + [f"{day(n.get('date'))} · {who(n.get('by'))}: {n.get('text', '')}" for n in note.get("notes") or []],
                "open": False,
            }
        )
    rows.sort(
        key=lambda x: (
            STATUS_ORDER.index(x["status"]) if x["status"] in STATUS_ORDER else 9,
            "".join(chr(255 - ord(c)) for c in (x["found"] or "")),
        )
    )
    return rows


def _status_cls(status: str) -> str:
    return "st-open" if status == "Open" else "st-ok" if status.startswith("✓") else ""


def issue_log_page(tenant: str, host: str, css: str, head: str, logo: str) -> str:
    """The page at /<host>/issues/ (two levels below the site root)."""
    rows = issue_rows(tenant, host)
    cols = (
        "ID · Area",
        "Found",
        "Issue",
        "Severity",
        "Scope",
        "Status",
        "Fixed · by · commit",
        "Notes",
    )
    trs = []
    for r in rows:
        issue = esc(r["issue"])
        if r["guide"]:
            issue = f'<a href="../../fix-guide/#g-{esc(r["guide"])}">{issue}</a>'
        if r["open"] and r["id"] != "–":
            issue += f' <small>(<a href="../#f-{esc(r["id"])}">evidence</a>)</small>'
        sev = r["severity"]
        fixed = " · ".join(x for x in (day(r["fixed"]) if r["fixed"] else "", r["by"], r["commits"]) if x) or "–"
        notes = "".join(f"<li>{esc(n)}</li>" for n in r["notes"])
        trs.append(
            f'<tr data-status="{esc(r["status"])}" data-area="{esc(r["area"])}">'
            f'<td class="id">{esc(r["id"])}<small>{esc(r["area"])}</small></td>'
            f'<td class="num">{day(r["found"])}</td><td class="name">{issue}</td>'
            + (
                f'<td class="sev sev-{esc(sev)}"><span class="dot"></span>{SEVERITY.get(sev, sev)}</td>'
                if sev
                else "<td>–</td>"
            )
            + f'<td class="num">{esc(r["scope"])}</td>'
            f'<td class="st {_status_cls(r["status"])}">{esc(r["status"])}'
            + (f"<small>{day(r['verified'])}</small>" if r["status"].startswith("✓") and r["verified"] else "")
            + f'</td><td class="fix">{fixed}</td>'
            f'<td class="notes">{f"<ul>{notes}</ul>" if notes else "–"}</td></tr>'
        )
    statuses = [s for s in STATUS_ORDER if any(r["status"] == s for r in rows)]
    areas = sorted({r["area"] for r in rows})
    counts = " · ".join(f"{sum(r['status'] == s for r in rows)} {s.lower()}" for s in statuses)
    opts = lambda vals: "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in vals)  # noqa: E731
    return (
        head + f"<title>Issue log: {esc(host)}</title>\n<style>{css}{EXTRA_CSS}</style>\n<main>\n"
        f'  <nav class="crumbs" aria-label="Breadcrumb"><a href="../../">All domains</a> › '
        f'<a href="../../{esc(tenant)}/">{esc(tenant)}</a> › <a href="../">{esc(host)}</a> › <b>Issue log</b></nav>\n'
        f"  <h1>{logo}Issue log</h1>\n"
        f"  <p>Every issue the audits identified on {esc(host)}, open and closed, with who fixed it, the commit, "
        f"when the fix was verified live, and notes and decisions. Open issues first, then newest. Issues found by "
        f"hand and fixed by the agent are listed too.</p>\n"
        f'  <div class="filters"><label for="st">Status</label><select id="st"><option value="">All</option>'
        f'{opts(statuses)}</select><label for="ar">Area</label><select id="ar"><option value="">All</option>'
        f"{opts(areas)}</select><span>{len(rows)} issues · {counts}</span></div>\n"
        f'  <div class="tablewrap"><table>\n    <thead><tr>{"".join(f"<th>{c}</th>" for c in cols)}</tr></thead>\n'
        f"    <tbody>{''.join(trs)}</tbody>\n  </table></div>\n</main>\n"
        "<script>\nconst f = () => { const s = st.value, a = ar.value;\n"
        "  for (const tr of document.querySelectorAll('tbody tr')) tr.hidden = (s && tr.dataset.status !== s) || "
        "(a && tr.dataset.area !== a); };\nst.addEventListener('change', f); ar.addEventListener('change', f);\n"
        "</script>\n</html>\n"
    )


def load_rules() -> dict:
    return (
        yaml.safe_load(RULES_FILE.read_text(encoding="utf-8")) if RULES_FILE.is_file() else {"areas": {}, "rules": []}
    )


def rules_by_check() -> dict[str, list[str]]:
    """check -> rule ids, for links from the Fix guide."""
    out: dict[str, list[str]] = {}
    for r in load_rules().get("rules") or []:
        for c in r.get("checks") or []:
            out.setdefault(c, []).append(r["id"])
    return out


def rules_page(css: str, head: str, logo: str) -> str:
    data = load_rules()
    areas = data.get("areas") or {}
    cols = ("ID", "Rule", "Why", "Set by", "Enforced by", "Status")
    body = []
    for prefix, name in areas.items():
        rules = [r for r in data.get("rules") or [] if str(r["id"]).split("-")[0] == prefix]
        if not rules:
            continue
        trs = []
        for r in rules:
            checks = (
                ", ".join(
                    f'<a href="../fix-guide/#g-{esc(c)}"><code>{esc(c)}</code></a>'
                    if c in GUIDE
                    else f"<code>{esc(c)}</code>"
                    for c in r.get("checks") or []
                )
                or "process"
            )
            trs.append(
                f'<tr id="{esc(r["id"])}"><td class="id">{esc(r["id"])}</td><td class="rule">{esc(r["rule"])}</td>'
                f'<td>{esc(r.get("why"))}</td><td class="num">{esc(who(r.get("set_by")))}'
                + (f"<br><small>({esc(TEAM[who(r.get('set_by'))])})</small>" if who(r.get("set_by")) in TEAM else "")
                + f"<br><small>"
                f'{day(r.get("date"))}</small></td><td class="fix">{checks}</td>'
                f'<td class="st {"st-ok" if r.get("status") == "active" else ""}">{esc(r.get("status"))}</td></tr>'
            )
        body.append(
            f'<tbody><tr class="area"><th colspan="6" scope="colgroup">{esc(name)}'
            f"<small>{len(rules)} rule{'s' if len(rules) != 1 else ''}"
            f"</small></th></tr>{''.join(trs)}</tbody>"
        )
    n = len(data.get("rules") or [])
    return (
        head + "<title>Rules</title>\n" + f"<style>{css}{EXTRA_CSS}</style>\n<main>\n"
        '  <nav class="crumbs" aria-label="Breadcrumb"><a href="../">All domains</a> › <b>Rules</b></nav>\n'
        f"  <h1>{logo}Rules</h1>\n"
        "  <p>The rules the audits check and the fixes follow: who set each one and when, and the checks that "
        "enforce it (each links to its Fix guide entry). Rules are revised here; a changed rule keeps its ID.</p>\n"
        f'  <div class="filters"><span>{n} rules</span></div>\n'
        f'  <div class="tablewrap"><table>\n    <thead><tr>{"".join(f"<th>{c}</th>" for c in cols)}</tr></thead>\n'
        f"    {''.join(body)}\n  </table></div>\n</main>\n</html>\n"
    )
