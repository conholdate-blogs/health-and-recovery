"""Build the whole GitHub Pages site: one subfolder per tenant, a landing page, and redirects for old links.

    python scripts/build_site.py --out site

Every tenant with a committed findings export (reports/<tenant>/findings.json) gets its latest report at
<out>/<tenant>/ and its archive at <out>/<tenant>/archive/; each of its hosts a page at <out>/<host>/ (the
tenant report filtered to that host). The fix guide (every check: what it means, impact,
fix, verify) is one shared page at <out>/fix-guide/ that the reports link to, and so is the method ("How this
audit works") at <out>/method/. Renders only committed files:
no store, no Google calls.
The site once served the first tenant's report at the root; LEGACY_TENANT keeps those links working
(/#<anchor> and /archive/<date>/ redirect into its subfolder).
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core import brand  # noqa: E402
from core.fix_guide import AREAS, GUIDE, guide_key, mark_terms  # noqa: E402
from core.paths import published_tenants, tenant_paths  # noqa: E402
from core.tenant import load_tenant  # noqa: E402
from scripts import build_archive, build_report  # noqa: E402

LEGACY_TENANT = "aspose.app"  # its report was the site root until 2026-10-20

HEAD = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
""" + brand.FAVICON_LINK + "\n"

LANDING = HEAD + """<title>Site health reports</title>
<style>
:root { --bg: #f6f7f9; --surface: #fff; --fg: #18202b; --muted: #5b6676; --line: #dde2e9; --accent: #1f5f8b }
@media (prefers-color-scheme: dark) { :root { --bg: #11161d; --surface: #182029; --fg: #e4e9f0; --muted: #98a3b3;
  --line: #2a3542; --accent: #6fb0dc; color-scheme: dark } }
* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif }
main { max-width: 760px; margin: 0 auto; padding: 32px 16px 64px; display: grid; gap: 20px }
h1 { margin: 0; font-size: 28px; display: flex; align-items: center; gap: 12px } p { margin: 0; color: var(--muted) }
a { color: var(--accent) }
ol { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px }
li { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px;
  display: grid; gap: 4px }
li b { font-size: 18px } li span { color: var(--muted); font-size: 14px; overflow-wrap: anywhere }
</style>
<script>
// Old links pointed at the first tenant's report on this page (e.g. /#findings): send them there.
if (location.hash.length > 1 && "__LEGACY__") location.replace("__LEGACY__/" + location.hash);
</script>
<main>
  <h1>""" + brand.logo(36) + """Site health reports</h1>
  <p>One report per domain. Read-only audits: nothing on any site is changed.
  How to fix each kind of problem: <a href="fix-guide/">fix guide</a>. How the audits and scores work:
  <a href="method/">method</a>.</p>
  <ol>
__ITEMS__
  </ol>
</main>
</html>
"""


GUIDE_URL = "../fix-guide/"  # from a tenant report at <out>/<tenant>/
SEVERITY = {"broken": "Broken", "incorrect": "Incorrect", "not_optimized": "Not optimized", "improvable": "Improvable"}

GUIDE_PAGE = HEAD + """<title>Fix guide</title>
<style>
:root { --bg: #f6f7f9; --surface: #fff; --fg: #18202b; --muted: #5b6676; --line: #dde2e9; --accent: #1f5f8b;
  --tint: #eef2f6; --hit: #fff4d6; --broken: #b42318; --incorrect: #b54708; --notopt: #a15c07; --improvable: #475467 }
@media (prefers-color-scheme: dark) { :root { --bg: #11161d; --surface: #182029; --fg: #e4e9f0; --muted: #98a3b3;
  --line: #2a3542; --accent: #6fb0dc; --tint: #1e2935; --hit: #3a3218; --broken: #f97066; --incorrect: #fd853a;
  --notopt: #fdb022; --improvable: #98a2b3; color-scheme: dark } }
* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif }
main { max-width: 1180px; margin: 0 auto; padding: 32px 16px 64px; display: grid; gap: 18px }
h1 { margin: 0; font-size: 28px; display: flex; align-items: center; gap: 12px }
p { margin: 0; color: var(--muted); max-width: 80ch }
a { color: var(--accent) }
.filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 14px }
select { font: inherit; padding: 4px 8px }
.tablewrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 8px }
table { border-collapse: collapse; width: 100%; min-width: 860px; font-size: 14px }
th, td { text-align: left; vertical-align: top; padding: 9px 12px; border-bottom: 1px solid var(--line) }
thead th { font-size: 12px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted);
  background: var(--tint) }
tr.area th { background: var(--tint); font-size: 15px; border-top: 2px solid var(--accent) }
tr.area small { color: var(--muted); font-weight: 400; margin-left: 8px }
td.name { font-weight: 600; min-width: 160px }
td.sev { white-space: nowrap; font-weight: 600; color: var(--sev) }
.sev-broken { --sev: var(--broken) } .sev-incorrect { --sev: var(--incorrect) }
.sev-not_optimized { --sev: var(--notopt) } .sev-improvable { --sev: var(--improvable) }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--sev); margin-right: 6px }
td.open { font-size: 13px; color: var(--muted); min-width: 120px }
tr:target td { background: var(--hit) }
tr[id] { scroll-margin-top: 80px }
.crumbs { font-size: 14px; color: var(--muted) } .crumbs b { color: var(--fg) }
abbr.term { text-decoration: underline dotted; cursor: help }
</style>
<main>
  <nav class="crumbs" aria-label="Breadcrumb"><a href="../">All domains</a> › <b>Fix guide</b></nav>
  <h1>""" + brand.logo(36) + """Fix guide</h1>
  <p>One row per check the audits run: what a finding means, why it matters, how to fix it and how to verify the
  fix. Every site health report links here. "Open findings" counts the open findings per report today.</p>
  <div class="filters"><label for="area">Area</label>
    <select id="area"><option value="">All areas</option>__OPTIONS__</select>
    <span>__COUNT__</span></div>
  <div class="tablewrap"><table>
    <thead><tr><th>Check</th><th>Severity</th><th>What it means</th><th>Impact</th><th>How to fix</th>
      <th>How to verify</th>
      <th>Open findings</th></tr></thead>
__BODY__
  </table></div>
</main>
<script>
document.getElementById("area").addEventListener("change", e => {
  const area = e.target.value;
  for (const tb of document.querySelectorAll("tbody[data-area]")) tb.hidden = !!area && tb.dataset.area !== area;
});
</script>
</html>
"""


def open_by_check(tenants: list[str]) -> dict:
    """guide key -> {tenant: open findings} from the committed exports."""
    out: dict = {}
    for t in tenants:
        for f in json.loads(tenant_paths(t).findings_export.read_text(encoding="utf-8")):
            k = guide_key(f.get("check"), f.get("source")) if f["status"] in ("open", "unverified") else None
            if k:
                out.setdefault(k, {}).setdefault(t, 0)
                out[k][t] += 1
    return out


def guide_page(tenants: list[str]) -> str:
    """The shared fix guide: rows grouped by area, worst severity first; anchors #g-<check> as in the reports."""
    used = open_by_check(tenants)
    order = list(SEVERITY)
    body = []
    for area in AREAS:
        rows = sorted(((k, g) for k, g in GUIDE.items() if g["area"] == area),
                      key=lambda kg: (order.index(kg[1]["severity"]) if kg[1]["severity"] in order else 9,
                                      kg[1]["name"]))
        if not rows:
            continue
        n_used = sum(1 for k, _ in rows if k in used)
        head = (f'<tr class="area"><th colspan="7" scope="colgroup">{html.escape(area)}<small>{len(rows)} checks'
                f'{f" · {n_used} with open findings" if n_used else ""}</small></th></tr>')
        trs = []
        for k, g in rows:
            sev = g["severity"]
            opened = ", ".join(f'<a href="../{html.escape(t)}/">{html.escape(t)}</a> {n}'
                               for t, n in sorted(used.get(k, {}).items()))
            trs.append(f'<tr id="g-{html.escape(k)}"><td class="name">{mark_terms(html.escape(g["name"]))}</td>'
                       f'<td class="sev sev-{html.escape(sev)}"><span class="dot"></span>{SEVERITY.get(sev, sev)}</td>'
                       + "".join(f"<td>{html.escape(g[c])}</td>" for c in ("means", "impact", "fix", "verify"))
                       + f'<td class="open">{opened or "–"}</td></tr>')
        body.append(f'  <tbody data-area="{html.escape(area)}">{head}{"".join(trs)}</tbody>')
    options = "".join(f'<option value="{html.escape(a)}">{html.escape(a)}</option>' for a in AREAS)
    count = f"{len(GUIDE)} checks · {len(used)} with open findings"
    return GUIDE_PAGE.replace("__OPTIONS__", options).replace("__COUNT__", count).replace("__BODY__", "\n".join(body))


METHOD_URL = "../method/"  # from a tenant report at <out>/<tenant>/

METHOD_PAGE = HEAD + """<title>How this audit works</title>
<style>
:root { --bg: #f6f7f9; --surface: #fff; --fg: #18202b; --muted: #5b6676; --line: #dde2e9; --accent: #1f5f8b;
  --tint: #eef3f8 }
@media (prefers-color-scheme: dark) { :root { --bg: #11161d; --surface: #182029; --fg: #e4e9f0; --muted: #98a3b3;
  --line: #2a3542; --accent: #6fb0dc; --tint: #1d2834; color-scheme: dark } }
* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif }
main { max-width: 1100px; margin: 0 auto; padding: 32px 16px 64px; display: grid; gap: 18px }
h1 { margin: 0; font-size: 28px; display: flex; align-items: center; gap: 12px }
p { margin: 0; color: var(--muted); max-width: 80ch }
a { color: var(--accent) }
.crumbs { font-size: 14px; color: var(--muted) } .crumbs b { color: var(--fg) }
</style>
<main id="method">
  <nav class="crumbs" aria-label="Breadcrumb"><a href="../">All domains</a> › <b>How this audit works</b></nav>
  <h1>""" + brand.logo(36) + """How this audit works</h1>
  <p>What each audit checks, how health and the priority score are calculated, and the terms the reports use.
  Every site health report links here. See also the <a href="../fix-guide/">fix guide</a>.</p>
__METHOD__</main>
</html>
"""


def method_page() -> str:
    """The shared "How this audit works" page; the area-scores note is shown here because a report uses it."""
    body = build_report.method_html().replace(' id="method-areas" hidden', "")
    return METHOD_PAGE.replace("__METHOD__", body)


def redirect_page(target: str) -> str:
    """A page that forwards to `target` (relative), keeping the #anchor."""
    t = html.escape(target, quote=True)
    return (HEAD + f"<title>Moved</title>\n<script>location.replace({json.dumps(target)} + location.hash);</script>\n"
            f'<meta http-equiv="refresh" content="0; url={t}">\n'
            f'<p>This page moved to <a href="{t}">{t}</a>.</p>\n</html>\n')


def tenant_item(tenant: str) -> str:
    rows = json.loads(tenant_paths(tenant).findings_export.read_text(encoding="utf-8"))
    open_n = sum(1 for f in rows if f["status"] in ("open", "unverified"))
    hosts = load_tenant(tenant).host_names
    name = html.escape(tenant)
    links = " · ".join(f'<a href="{html.escape(h)}/">{html.escape(h)}</a>' for h in hosts)
    return (f'    <li><a href="{name}/"><b>{name}</b></a><span>{open_n:,} open findings · '
            f'<a href="{name}/archive/">previous versions</a></span><span>Subdomains: {links}</span></li>')


# pages across domains: slug -> name; members come from each tenant's YAML `collections` (SK, 2026-10-27)
COLLECTIONS = {"blogs": "Blogs"}
RESERVED = {"fix-guide", "method", "archive", *COLLECTIONS}  # site folders that are neither tenants nor hosts


def collection_members(tenants: list[str]) -> dict[str, list[tuple[str, str]]]:
    """slug -> [(tenant, host)] from the tenants' `collections`, in site order; a host must belong to its tenant."""
    out: dict = {slug: [] for slug in COLLECTIONS}
    for t in tenants:
        tenant = load_tenant(t)
        for slug, hosts in (tenant.raw.get("collections") or {}).items():
            if slug not in COLLECTIONS:
                raise SystemExit(f"tenants/{t}.yaml: unknown collection {slug!r} (known: {', '.join(COLLECTIONS)})")
            for h in hosts:
                if h not in tenant.host_names:
                    raise SystemExit(f"tenants/{t}.yaml: collection {slug} lists {h}, which is not one of its hosts")
                out[slug].append((t, h))
    return {slug: members for slug, members in out.items() if members}


def collection_item(slug: str, members: list[tuple[str, str]]) -> str:
    links = " · ".join(f'<a href="{html.escape(h)}/">{html.escape(h)}</a>' for _, h in members)
    return (f'    <li><a href="{slug}/"><b>{html.escape(COLLECTIONS[slug])}</b></a><span>{len(members)} subdomains across '
            f'{len({t for t, _ in members})} domains</span><span>{links}</span></li>')


def site_hosts(tenants: list[str]) -> dict[str, list[str]]:
    """Each tenant's hosts. Host pages sit at the site root next to the tenant reports (SK chose flat URLs), so a
    host may not share its name with a tenant or a site folder."""
    hosts = {t: load_tenant(t).host_names for t in tenants}
    taken = set(tenants) | RESERVED
    for t, hs in hosts.items():
        for h in hs:
            if h in taken:
                raise SystemExit(f"Host {h} of {t} clashes with a tenant or site folder of the same name")
            taken.add(h)
    return hosts


def build(out: Path, tenants: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    hosts = site_hosts(tenants)
    members = collection_members(tenants)
    site_collections = ",".join(f"{slug}:{COLLECTIONS[slug]}" for slug in members)
    for t in tenants:
        paths = tenant_paths(t)
        common = ["--tenant", t, "--findings", str(paths.findings_export), "--standalone", "--guide-url", GUIDE_URL,
                  "--method-url", METHOD_URL, "--site-tenants", ",".join(tenants), "--site-hosts", ",".join(hosts[t]),
                  "--site-collections", site_collections]
        if build_report.main(common + ["--out", str(out / t / "index.html")]):
            raise SystemExit(f"Report for {t} failed")
        for h in hosts[t]:  # one page per host: the tenant report filtered to that host
            if build_report.main(common + ["--host", h, "--out", str(out / h / "index.html")]):
                raise SystemExit(f"Host page {h} failed")
        n = build_archive.build(out / t / "archive", paths.archive, t)
        print(f"Archive: {n} snapshots for {t}")
    for slug, mem in members.items():  # pages across domains, e.g. /blogs/
        page = build_report.build(build_report.collection_report(COLLECTIONS[slug], slug, mem), [], None,
                                  standalone=True, guide_url=GUIDE_URL, site_tenants=tenants,
                                  site_hosts=[h for _, h in mem], method_url=METHOD_URL,
                                  collections=build_report.parse_collections(site_collections))
        (out / slug).mkdir(exist_ok=True)
        (out / slug / "index.html").write_text(page, encoding="utf-8")
        print(f"{COLLECTIONS[slug]}: {len(mem)} subdomains")
    (out / "fix-guide").mkdir(exist_ok=True)
    (out / "fix-guide" / "index.html").write_text(guide_page(tenants), encoding="utf-8")
    (out / "method").mkdir(exist_ok=True)
    (out / "method" / "index.html").write_text(method_page(), encoding="utf-8")
    legacy = LEGACY_TENANT if LEGACY_TENANT in tenants else ""  # its old links lead nowhere while it is not published
    items = "\n".join([tenant_item(t) for t in tenants] + [collection_item(s, m) for s, m in members.items()])
    (out / "index.html").write_text(LANDING.replace("__LEGACY__", legacy).replace("__ITEMS__", items),
                                    encoding="utf-8")
    if legacy:  # /archive/ and /archive/<date>/ from before the subfolders
        (out / "archive").mkdir(exist_ok=True)
        (out / "archive" / "index.html").write_text(redirect_page(f"../{legacy}/archive/"), encoding="utf-8")
        for e in build_archive.entries(tenant_paths(legacy).archive):
            slug = Path(e["file"]).stem
            (out / "archive" / slug).mkdir(exist_ok=True)
            (out / "archive" / slug / "index.html").write_text(
                redirect_page(f"../../{legacy}/archive/{slug}/"), encoding="utf-8")


def site_tenants() -> list[str]:
    """Tenants with a report, less those whose YAML says `published: false` (SK, 2026-11-06: only the blogs)."""
    return [t for t in published_tenants() if load_tenant(t).raw.get("published", True) is not False]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="site", help="Pages output folder")
    ap.add_argument("--tenants", help="comma-separated tenants "
                    "(default: every tenant with reports/<tenant>/findings.json, except `published: false`)")
    args = ap.parse_args(argv)
    tenants = args.tenants.split(",") if args.tenants else site_tenants()
    if not tenants:
        print("No reports/<tenant>/findings.json found.", file=sys.stderr)
        return 1
    build(Path(args.out), tenants)
    print(f"Site: {', '.join(tenants)} in {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
