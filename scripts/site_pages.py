"""Issue log (one page per subdomain, /<subdomain>/issues/) and Rules (one shared page, /rules/) for the Pages site.
SK, 2026-11-12: keep the list of issues we identify and fix, with notes, and our rules, structurally on the website.

Issue log rows come from the committed files only:
- reports/<tenant>/findings.json: every finding of the subdomain, open and resolved (found, severity, scope);
- reports/<tenant>/agent-fixes.json: fixes by the agent (commit, fixed, verified, result); a row is matched to its
  finding by `finding` id, else by check; a fix without a finding (found by hand) is a row of its own, and
  `found_by` says who found it (e.g. "Shoaib Khan"; SK, 2026-11-12: issues he finds and we fix are logged);
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
                "notes": [
                    f"{day(n.get('date'))} · {who(n.get('by'))}: {n.get('text', '')}" for n in note.get("notes") or []
                ],
                "results": [r.get("result") for r in fx if r.get("result")],
                "fix_issues": [r.get("issue") for r in fx if r.get("issue")],
                "observed": (f.get("evidence") or {}).get("observed") or "",
                "means": g.get("means") or "",
                "open": f["status"] in ("open", "unverified"),
            }
        )
    for r in loose:  # fixes of issues found by hand (no finding)
        note = notes.get(r.get("check") or "") or {}
        rows.append(
            {
                "id": "–",
                "area": "found by " + who(r.get("found_by") or "hand"),
                "found_by": who(r.get("found_by") or ""),
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
                "notes": [
                    f"{day(n.get('date'))} · {who(n.get('by'))}: {n.get('text', '')}" for n in note.get("notes") or []
                ],
                "results": [r["result"]] if r.get("result") else [],
                "fix_issues": [],
                "observed": "",
                "means": "",
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


SEV_RANK = {"broken": 0, "incorrect": 1, "not_optimized": 2, "improvable": 3}
# status rows (count, bar, share): (label, statuses, css class); "Fixed" = verified live + pushed (SK, 2026-11-12)
TILES = [
    ("Open", ["Open"], "t-open"),
    ("Fixed", ["✓ Verified live", "Pushed, waiting for deploy"], "t-fixed"),
    ("Resolved", ["Resolved"], "t-res"),
    ("Reviewed", ["Reviewed", "Won't fix"], "t-rev"),
]

LOG_CSS = """
.switch { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: flex-end; font-size: 13px;
  color: var(--muted) } .switch select { font: inherit; padding: 3px 6px; max-width: 100% }
/* one row per status: count, name, bar, share (SK, 2026-11-12); a row filters the table */
.sbars { display: grid; gap: 4px; max-width: 900px }
.srow { display: grid; grid-template-columns: 44px 230px 1fr 48px; align-items: center; gap: 12px; padding: 4px 8px;
  background: none; border: 1px solid transparent; border-radius: 6px; font: inherit; color: inherit; text-align: left;
  cursor: pointer }
.srow:hover { background: var(--surface) } .srow[aria-pressed="true"] { border-color: var(--accent);
  background: var(--surface) }
.srow b { font-size: 18px; text-align: right } .srow span small { color: var(--muted); margin-left: 6px }
.srow em { font-style: normal; color: var(--muted); font-size: 13px; text-align: right }
.track { display: flex; height: 12px; border-radius: 6px; overflow: hidden; background: var(--line) }
.track i { display: block } i.t-all { background: var(--accent) } i.t-open { background: var(--broken) }
i.t-fixed { background: #12b76a } i.t-pushed { background: #a6f4c5 } i.t-res { background: #98a2b3 }
i.t-rev { background: #d0d5dd }
.t-open b { color: var(--broken) } .t-fixed b { color: #067647 } .t-res b { color: var(--muted) }
@media (prefers-color-scheme: dark) { .t-fixed b { color: #47cd89 } }
@media (max-width: 640px) { .srow { grid-template-columns: 36px 1fr 44px } .srow .track { grid-column: 1 / -1 } }
th.sort { cursor: pointer; user-select: none; white-space: nowrap }
th.sort::after { content: " ↕"; opacity: .4 } th[aria-sort="ascending"]::after { content: " ↑"; opacity: 1 }
th[aria-sort="descending"]::after { content: " ↓"; opacity: 1 }
td.st .commits { font-weight: 400; font-size: 13px }
td.small, th.small { font-size: 12px; color: var(--muted) } td.small small { font-size: 11px }
td.sev.small { color: var(--sev) } td.name { min-width: 300px }
td.name .sum { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  font-weight: 400; font-size: 13px; color: var(--muted); margin-top: 2px }
td.tog { width: 28px; padding-right: 0 } td.tog button { border: 0; background: none; cursor: pointer; font-size: 14px;
  color: var(--accent); padding: 2px 4px }
tr.det td { background: var(--tint); font-size: 13px }
tr.det dl { display: grid; grid-template-columns: 130px 1fr; gap: 6px 14px; margin: 4px 0 }
tr.det dt { color: var(--muted); font-weight: 600 } tr.det dd { margin: 0 } tr.det ul { margin: 0; padding-left: 16px }
@media (max-width: 700px) { tr.det dl { grid-template-columns: 1fr } }
tbody + tbody tr.main td { border-top: 1px solid var(--line) }
"""


def _status_detail(r: dict) -> str:
    """Date and commits under the status (SK, 2026-11-12: commits here, only the name in Fixed by)."""
    st, commits = r["status"], r["commits"]
    if st.startswith("✓"):
        lines = [day(r["verified"]) if r["verified"] else "", commits]
    elif st.startswith("Pushed"):
        lines = [f"pushed {day(r['fixed'])}" if r["fixed"] else "", commits]
    elif st == "Resolved":
        lines = [f"gone {day(r['fixed'])}" if r["fixed"] else ""]
    else:
        lines = []
    return "".join(f'<small class="{"commits" if x == commits else ""}">{x}</small>' for x in lines if x)


def section_switch(host: str, hosts: list[str], tail: str) -> str:
    """Section (Blogs only, SK 2026-11-12) and Subdomain selects, as on the report pages; `tail` keeps the page kind."""
    if not hosts:
        return ""
    opts = "".join(f'<option value="{esc(h)}"{" selected" if h == host else ""}>{esc(h)}</option>' for h in hosts)
    return (
        '<div class="switch"><label for="sec-sw">Section</label><select id="sec-sw"><option selected>Blogs</option>'
        f'</select><label for="sub-sw">Subdomain</label><select id="sub-sw"><option value="">All blogs</option>{opts}'
        "</select></div>\n<script>"
        "document.getElementById('sec-sw').onchange = () => { location.href = '../../blogs/'; };"
        "document.getElementById('sub-sw').onchange = e => { location.href = e.target.value ? "
        f"`../../${{e.target.value}}/{tail}` : '../../blogs/'; }};</script>\n"
    )


def issue_log_page(
    tenant: str, host: str, css: str, head: str, logo: str, section_hosts: list[str] | None = None
) -> str:
    """The page at /<host>/issues/ (two levels below the site root): tiles and a bar on top, then a sortable table."""
    rows = issue_rows(tenant, host)
    cols = [
        ("", None),
        ("ID · Area", "s"),
        ("Found", "s"),
        ("Issue", "s"),
        ("Severity", "n"),
        ("Scope", "n"),
        ("Status", "n"),
        ("Fixed by", "s"),
    ]
    trs = []
    for i, r in enumerate(rows):
        issue = esc(r["issue"])
        if r["guide"]:
            issue = f'<a href="../../fix-guide/#g-{esc(r["guide"])}">{issue}</a>'
        if r["id"] != "–":
            summary = (r["fix_issues"] or [r["observed"]])[0]
        else:
            summary = (r["results"] or [""])[0]
        sev = r["severity"]
        rank = STATUS_ORDER.index(r["status"]) if r["status"] in STATUS_ORDER else 9
        scope_n = int("".join(c for c in r["scope"].split(" ")[0] if c.isdigit()) or 0)
        det = []  # the expanded row: everything we know about the issue
        if r["id"] != "–":
            det.append(("ID · check", f"{esc(r['id'])} · <code>{esc(r['check'])}</code> · {esc(r['area'])}"))
        else:
            who_found = f"by {esc(r['found_by'])}" if r.get("found_by") else "by hand (no audit check at the time)"
            det.append(("Found", who_found))
        if r["means"]:
            det.append(("What it means", esc(r["means"])))
        if r["observed"]:
            det.append(("Audit saw", esc(r["observed"])))
        det += [("Issue fixed", esc(x)) for x in r["fix_issues"]]
        det += [("Result", esc(x)) for x in r["results"]]
        if r["commits"]:
            det.append(("Commits", r["commits"]))
        if r["notes"]:
            det.append(("Notes", "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in r["notes"]) + "</ul>"))
        links = []
        if r["open"] and r["id"] != "–":
            links.append(f'<a href="../#f-{esc(r["id"])}">Evidence on the report</a>')
        if r["guide"]:
            links.append(f'<a href="../../fix-guide/#g-{esc(r["guide"])}">How to fix</a>')
        if links:
            det.append(("Links", " · ".join(links)))
        dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in det)
        sev_td = (
            f'<td class="sev small sev-{esc(sev)}" data-v="{SEV_RANK.get(sev, 9)}"><span class="dot"></span>'
            f"{SEVERITY.get(sev, sev)}</td>"
            if sev
            else '<td class="small" data-v="9">–</td>'
        )
        trs.append(
            f'<tbody data-status="{esc(r["status"])}" data-area="{esc(r["area"])}">'
            f'<tr class="main"><td class="tog"><button type="button" aria-expanded="false" aria-controls="d{i}" '
            f'aria-label="Details">▸</button></td>'
            f'<td class="id small" data-v="{esc(r["id"])}">{esc(r["id"])}<small>{esc(r["area"])}</small></td>'
            f'<td class="num small" data-v="{esc(r["found"] or "")}">{day(r["found"])}</td>'
            f'<td class="name" data-v="{esc(r["issue"])}">{issue}'
            + (f'<span class="sum">{esc(summary)}</span>' if summary else "")
            + "</td>"
            + sev_td
            + f'<td class="num small" data-v="{scope_n}">{esc(r["scope"])}</td>'
            f'<td class="st {_status_cls(r["status"])}" data-v="{rank}">{esc(r["status"])}{_status_detail(r)}</td>'
            f'<td class="fix" data-v="{esc(r["by"])}">{esc(r["by"]) or "–"}</td></tr>'
            f'<tr class="det" id="d{i}" hidden><td></td><td colspan="7"><dl>{dl}</dl></td></tr></tbody>'
        )
    n = {s: sum(r["status"] == s for r in rows) for s in STATUS_ORDER}
    verified, pushed = n["✓ Verified live"], n["Pushed, waiting for deploy"]
    total = max(len(rows), 1)
    sub = {
        "Open": "to fix",
        "Fixed": f"{verified} verified live" + (f" · {pushed} waiting for deploy" if pushed else ""),
        "Resolved": "gone, no fix recorded",
        "Reviewed": "false or relabelled",
    }

    def srow(label, k, fill, f, cls="", pressed=False, note=""):
        return (
            f'<button type="button" class="srow {cls}" data-f="{esc(f)}" aria-pressed="{str(pressed).lower()}">'
            f'<b>{k}</b><span>{label}<small>{esc(note)}</small></span><span class="track">{fill}</span>'
            f"<em>{100 * k / total:.0f}%</em></button>"
        )

    def seg(cls, k):
        return f'<i class="{cls}" style="width:{100 * k / total:.2f}%"></i>' if k else ""

    srows = [srow("Total", len(rows), seg("t-all", len(rows)), "", pressed=True, note="issues found")]
    fills = {"Fixed": seg("t-fixed", verified) + seg("t-pushed", pushed)}
    for label, sts, cls in TILES:
        k = sum(n[s] for s in sts)
        srows.append(srow(label, k, fills.get(label) or seg(cls, k), "|".join(sts), cls, note=sub[label]))
    areas = sorted({r["area"] for r in rows})
    opts = "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in areas)
    heads = "".join(f'<th class="sort" data-t="{t}" tabindex="0">{c}</th>' if t else f"<th>{c}</th>" for c, t in cols)
    return (
        head
        + f"<title>Issue log: {esc(host)}</title>\n<style>{css}{EXTRA_CSS}{LOG_CSS}</style>\n<main>\n"
        + section_switch(host, section_hosts or [], "issues/")
        + f'  <nav class="crumbs" aria-label="Breadcrumb"><a href="../../">All domains</a> › '
        f'<a href="../../{esc(tenant)}/">{esc(tenant)}</a> › <a href="../">{esc(host)}</a> › <b>Issue log</b></nav>\n'
        f"  <h1>{logo}Issue log</h1>\n"
        f"  <p>Every issue the audits identified on {esc(host)}, open and closed: status with the date and commits, "
        f"who fixed it, and notes and decisions. Issues found by hand and fixed are listed too. Click a status row "
        f"to filter, a column header to sort.</p>\n"
        + issues_chart(tenant, host)
        + f'  <div class="sbars">{"".join(srows)}</div>\n'
        f'  <div class="filters"><label for="ar">Area</label><select id="ar"><option value="">All</option>{opts}'
        f'</select><span id="shown"></span></div>\n'
        f'  <div class="tablewrap"><table>\n    <thead><tr>{heads}</tr></thead>\n'
        f"    {''.join(trs)}\n  </table></div>\n</main>\n" + LOG_JS
    )


def issues_chart(tenant: str, host: str) -> str:
    """The subdomain page's issues chart (open, fixed, all found per run day) on top of the Issue log (SK, 2026-11-13),
    drawn by the same code: the template's worm-css and worm-js blocks, with the same series."""
    import json as _json

    try:
        from scripts import build_report
    except ImportError:  # run as scripts/site_pages.py
        import build_report
    from core.paths import tenant_paths

    series = build_report.issue_log_summary(tenant, host, tenant_paths(tenant).health_history)["series"]
    if len(series) < 2:
        return ""
    tpl = (Path(__file__).parent / "templates" / "discovery_report.html").read_text(encoding="utf-8")
    cut = lambda a, b: tpl.split(a, 1)[1].split(b, 1)[0]  # noqa: E731
    css = cut("/* worm-css:start", "/* worm-css:end */").split("*/", 1)[1]
    js = cut("// worm-js:start", "// worm-js:end").split("\n", 1)[1]
    data = _json.dumps(series).replace("</", "<\\/")
    return (
        f"<style>{css}\n:root {{ --w-open: #b42318; --w-fixed: #17b26a }}\n"
        "@media (prefers-color-scheme: dark) { :root { --w-open: #c01e1e; --w-fixed: #17a865 } }</style>\n"
        '  <div id="chart-wrap"></div>\n<script>\n(() => {\n'
        "  const $ = id => document.getElementById(id);\n"
        '  const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", \'"\': "&quot;" }[c]));\n'
        '  const MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");\n'
        "  const day = d => { const m = /^(\\d{4})-(\\d{2})-(\\d{2})/.exec(d || \"\"); return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : d || \"\"; };\n"
        f"{js}\n  const S = {data}, wrap = $(\"chart-wrap\");\n"
        "  const draw = () => { wrap.innerHTML = wormGraph(S, wrap.clientWidth, { issuesOnly: true }); wireWorm(S); };\n"
        "  draw(); let last = wrap.clientWidth, t = 0;\n"
        "  window.addEventListener(\"resize\", () => { clearTimeout(t); t = setTimeout(() => {\n"
        "    if (Math.abs(wrap.clientWidth - last) < 8) return; last = wrap.clientWidth; draw(); }, 150); });\n"
        "})();\n</script>\n"
    )


LOG_JS = """<script>
const table = document.querySelector("table"), groups = () => [...table.tBodies];
const tiles = [...document.querySelectorAll(".srow")];
let want = "";
function filter() {
  const a = ar.value, sts = want ? want.split("|") : null;
  let k = 0;
  for (const g of groups()) {
    g.hidden = (sts && !sts.includes(g.dataset.status)) || (a && g.dataset.area !== a);
    k += !g.hidden;
  }
  shown.textContent = `${k} of ${groups().length} shown`;
}
tiles.forEach(t => t.addEventListener("click", () => {
  want = t.dataset.f; tiles.forEach(x => x.setAttribute("aria-pressed", x === t)); filter();
}));
ar.addEventListener("change", filter);
table.addEventListener("click", e => {
  const b = e.target.closest("td.tog button");
  if (!b) return;
  const open = b.getAttribute("aria-expanded") !== "true";
  b.setAttribute("aria-expanded", open); b.textContent = open ? "▾" : "▸";
  document.getElementById(b.getAttribute("aria-controls")).hidden = !open;
});
document.querySelectorAll("th.sort").forEach(th => {
  const i = th.cellIndex;
  const go = () => {
    const asc = th.getAttribute("aria-sort") !== "ascending", num = th.dataset.t === "n";
    document.querySelectorAll("th.sort").forEach(x => x.removeAttribute("aria-sort"));
    th.setAttribute("aria-sort", asc ? "ascending" : "descending");
    const v = g => g.rows[0].cells[i].dataset.v || "";
    groups().sort((x, y) => {
      const c = num ? Number(v(x)) - Number(v(y)) : v(x).localeCompare(v(y));
      return asc ? c : -c;
    }).forEach(g => table.appendChild(g));
  };
  th.addEventListener("click", go);
  th.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
});
filter();
</script>
</html>
"""


MATRIX_CSS = """
table.mx { min-width: 980px } table.mx td, table.mx th { text-align: center } table.mx td.name, table.mx th:first-child { text-align: left }
table.mx td.name small { display: block; color: var(--muted); font-weight: 400; font-size: 12px }
table.mx tr.area th { text-align: left; color: var(--sev) } table.mx tr.area th small { color: var(--muted) }
.mx .c-open { color: var(--broken); font-weight: 700 } .mx .c-ok { color: #067647; font-weight: 700 }
.mx .c-nf { color: #067647; font-weight: 700; letter-spacing: .03em; font-size: 12px } .mx .c-rev { color: var(--muted) }
.mx td a { text-decoration: none; color: inherit } .mx td small { display: block; font-weight: 400; color: var(--muted) }
@media (prefers-color-scheme: dark) { .mx .c-ok, .mx .c-nf { color: #47cd89 } }
"""


def matrix_page(members: list[tuple[str, str]], items: dict[str, dict], css: str, head: str, logo: str) -> str:
    """/blogs/issues/: every issue type down, every blog across (SK, 2026-11-13): where a fix proven on one blog
    still waits on another. A blog that never had the issue shows NOT FOUND in green."""
    hosts = [h for _, h in members]
    cells: dict = {}  # guide key -> host -> rows
    meta: dict = {}
    for t, h in members:
        for r in issue_rows(t, h):
            k = r["guide"] or r["check"]
            cells.setdefault(k, {}).setdefault(h, []).append(r)
            meta.setdefault(k, r)
    order = {s: i for i, s in enumerate(["broken", "incorrect", "not_optimized", "improvable"])}

    def state(k, h):
        rows = cells[k].get(h)
        if not rows:
            return "nf"
        st = {r["status"] for r in rows}
        if "Open" in st:
            return "open"
        if st & {"✓ Verified live", "Pushed, waiting for deploy", "Resolved"}:
            return "ok"
        return "rev"

    def cell(k, h):
        s, href = state(k, h), f"../../{esc(h)}/issues/"
        if s == "nf":
            return '<td class="c-nf" title="never found on this blog">NOT FOUND</td>'
        if s == "ok":
            fixed = any(r["status"] in ("✓ Verified live", "Pushed, waiting for deploy") for r in cells[k][h])
            return f'<td class="c-ok"><a href="{href}">✓ {"Fixed" if fixed else "Resolved"}</a></td>'
        if s == "rev":
            return f'<td class="c-rev"><a href="{href}">Reviewed</a></td>'
        c = ((items.get(h) or {}).get(k) or {})
        detail = f'<small>{c.get("fixed_pct", 0)}% fixed · {c["open"]:,} open</small>' if c.get("issues") else ""
        return f'<td class="c-open"><a href="{href}">✗ Open{detail}</a></td>'

    # grouped by severity, worst first (SK, 2026-11-13); inside a group, open on the most blogs first
    keys = sorted(cells, key=lambda k: (order.get(meta[k]["severity"], 9), -sum(state(k, h) == "open" for h in hosts),
                                        meta[k]["issue"]))
    head_row = "".join(f"<th>{esc(h).replace('.', '.<wbr>')}</th>" for h in hosts)
    body, group = [], None
    for k in keys:
        m = meta[k]
        if m["severity"] != group:  # a heading row per severity, with how many issue types are still open somewhere
            group = m["severity"]
            ks = [x for x in keys if meta[x]["severity"] == group]
            n_any = sum(any(state(x, h) == "open" for h in hosts) for x in ks)
            body.append(f'<tr class="area sev-{esc(group)}"><th colspan="{len(hosts) + 2}"><span class="dot"></span>'
                        f'{esc(SEVERITY.get(group, group))}<small>{len(ks)} issue type{"" if len(ks) == 1 else "s"} · '
                        f'{n_any} still open on some blog</small></th></tr>')
        name = f'<a href="../../fix-guide/#g-{esc(k)}">{esc(m["issue"])}</a>' if m.get("guide") else esc(m["issue"])
        n_open = sum(state(k, h) == "open" for h in hosts)
        fixed_on = [h for h in hosts if state(k, h) == "ok"]
        body.append(f'<tr><td class="name">{name}<small>{esc(m["area"])}</small></td>'
                    + "".join(cell(k, h) for h in hosts)
                    + f'<td>{"<b class=c-ok>✓ none open</b>" if not n_open else f"{n_open} open"}'
                    + (f'<small>fixed on {", ".join(esc(h.replace("blog.", "")) for h in fixed_on)}</small>' if fixed_on else "") + "</td></tr>")
    return (
        head
        + f"<title>Issues across blogs</title>\n<style>{css}{EXTRA_CSS}{MATRIX_CSS}</style>\n<main>\n"
        + '  <nav class="crumbs" aria-label="Breadcrumb"><a href="../../">All domains</a> › <a href="../">Blogs</a> › <b>Issues across blogs</b></nav>\n'
        + f"  <h1>{logo}Issues across blogs</h1>\n"
        + "  <p>Every issue type found on any blog, and its state on each blog: open (with the share of its items fixed), "
        "fixed, resolved, or NOT FOUND when the audits never saw it there. Grouped by severity, worst first; inside a "
        "group, issues open on the most blogs come first; "
        "a fix proven on one blog shows where to copy it from. Each cell opens that blog's Issue log.</p>\n"
        + f'  <div class="tablewrap"><table class="mx">\n    <thead><tr><th>Issue</th>{head_row}<th>All blogs</th></tr></thead>\n'
        + f"    <tbody>{''.join(body)}</tbody>\n  </table></div>\n</main>\n</html>\n"
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
                f'<td>{esc(r.get("why"))}</td><td class="num">'
                + (  # a person under their team (SK, 2026-11-12): "Blogs Team" / "- Shoaib Khan"
                    f"{esc(TEAM[who(r.get('set_by'))])}<br>- {esc(who(r.get('set_by')))}"
                    if who(r.get("set_by")) in TEAM
                    else esc(who(r.get("set_by")))
                )
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
