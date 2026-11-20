# The report site: pages, data and how to update them

Published at https://conholdate-blogs.github.io/health-and-recovery/ (second copy at
https://shoaibkhan-aspose.github.io/health-and-recovery/), built by `.github/workflows/pages.yml` →
`scripts/build_site.py` from committed files only. Every page carries `noindex, nofollow` (no robots.txt block:
a blocked page's noindex is never read). Written 12 Nov 2026 so nothing is lost.

## Pages

| Page | URL | Built by | Data |
|---|---|---|---|
| Home | `/` | `build_site.py` (LANDING) | scores from the Blogs page, alerts |
| Blogs | `/blogs/` | `build_report.collection_report` | each blog prepared as its own page |
| Domain | `/<tenant>/` | `build_report.py` | findings, runs, traffic summary; snapshots in `/<tenant>/archive/` |
| **Subdomain** | `/<host>/` | `build_report.py --host` + `scripts/templates/discovery_report.html` | as domain, filtered; `_issue_log` from `site_pages.issue_rows` |
| **Check sheet** | `/check-sheet/` | `scripts/site_pages.check_sheet_page` | `docs/check-sheet.md` (rendered as is; check names link to the Fix guide, rule ids to Rules) |
| **Issue log** | `/<host>/issues/` | `scripts/site_pages.issue_log_page` | `findings.json`, `agent-fixes.json`, `issue-notes.json` |
| **Rules** | `/rules/` | `scripts/site_pages.rules_page` | `docs/rules.yaml` |
| Fix guide | `/fix-guide/` | `build_site.guide_page` | `core/fix_guide.py`; rows link their rules |
| Method | `/method/` | `scripts/templates/method.html` | |

## Subdomain page (layout agreed with SK, 12 Nov 2026)

1. **Header:** Section switch (only "Blogs", domains hidden) + Subdomain switch (all blog subdomains); breadcrumb.
   No run line (run ids are in the footer).
2. **Overview:** tiles Health score · Search clicks · Impressions · **Issues** (Issue log: open of total, fixed,
   resolved, reviewed, link) · **Items** (pages/links/files: open of total, fixed %). Then five **area cards**
   (Crawl & indexing, On-page, Languages, AI readiness, Speed) with score, bar, issues and a "Show data ▼" button;
   a card opens its data tables underneath: Crawl = robots.txt and sitemaps, submitted sitemaps, site structure;
   On-page = crawl audit; Languages = sections; AI = AI access; Speed = speed. All cards start closed (SK, 16 Nov;
   until then the lowest area below 100 opened by default). Each card says when it was last checked ("checked
   13–16 Nov": oldest to newest date of the scans that feed the area; red when the oldest is over 14 days); hover
   and the opened data panel name each scan with its date. Scans per area (`AREA_SCANS` in the template): Crawl =
   sitemap scan, crawl audit, repo check, link check, site structure; On-page = crawl audit, text check, repo check;
   Languages = sitemap scan, crawl audit, link check, repo check; AI = crawl audit, AI audit; Speed = speed audit.
   Reference panel headers (17 Nov, SK: run lists were unreadable) say what is broken ("broken: 1 page with
   errors") and the scope in words ("180 pages checked in 12 scans, 11–16 Nov 2026"); run numbers and request
   counts are only in the hover text (and the footer).
3. **Fix progress:** agent line ("N fixes by the Health and Recovery Agent" + an "Open the Issue log →" button); **graph**: open, fixed
   (cumulative) and all found (dashed) per day with a recorded run, plus a separate health-score chart (0–100) on the
   same dates: side by side from 760 px, stacked below; hovering a day marks it in both, one tooltip (13 Nov); a day
   with several scans that moved the score draws each at the same x, a vertical jump; health axis from a round step
   below the lowest score to 100; Resolved and Reviewed lines only when > 0, so open + fixed + resolved + reviewed =
   all found (13 Nov); Health card without trend line, Items card fixed % bold green; History 100s bold green;
   subdomain switch order .com (aspose, groupdocs, conholdate) then .cloud (no dual y-axis; colours
   validated for colour-blind readers: light #b42318/#17b26a, dark #c01e1e/#17a865); per-check item table (open rows
   red); "Resolved since the last run"; History (5 rows + Show all; changes on their own line under the value).
4. **Issues and fixes:** open findings ranked by score with evidence; filters hidden under 6 issues.
5. Reference is empty on subdomain pages (its tables are in the cards); domain pages keep it.
6. **Visibility (19–20 Nov, SK: "values like Ahrefs")**: a **Visibility card** in SK's order (DR, keywords, top 3,
   top 10, AI visits; change vs the same 28 days six months ago) on subdomain pages (a tile beside Health; a click
   opens the panel) and as a cell in every subdomain row (domain and Blogs pages). The panel (closed by default, end
   of the Overview): **monthly small multiples**, one square chart per number on its own scale from 0, one dot per
   complete calendar month, 6 / 12 months switch (remembered per viewer), shared hover across the four monthly charts;
   Domain Rating has its own months (recorded from 19 Nov 2026); the table behind "Show table". Monthly data:
   `reports/<tenant>/visibility-monthly.json` (12 months filled in from Search Console and GA4 on 20 Nov; each run adds
   months that ended at least 4 days ago; older months are kept). Earlier (19 Nov) version: Overview tile "Organic keywords" (Search
   Console queries with impressions, 28 days; top 10; vs six months ago; link "AI visits · DR"), a Visibility panel at
   the end of the Overview (keywords, top 10, top 3, with a click, hidden-search share, AI-assistant visits per
   platform from GA4, Domain Rating from Ahrefs; now, six months ago, change, source) and History columns "Organic
   keywords" and "AI visits". Data: `reports/<tenant>/visibility.json` (one entry a day), from `scripts/visibility.py`,
   last step of `run_cycle.py` (full and quick). DR needs `AHREFS_API_KEY`; without it the last value is kept with its
   date and `--dr host=N` records a value read elsewhere.

Words: an **issue** is a kind of problem (one Issue log row); an **item** is one page, link or file it affects.

## Issue log

- Rows: every finding of the subdomain (open and resolved) + agent fixes of issues found by hand.
- Status: Open · Pushed, waiting for deploy · ✓ Verified live (date and commits under it) · Resolved (gone, no fix
  recorded) · Reviewed (false or relabelled) · Won't fix.
- Top: one bar row per status (Total, Open red, Fixed green = verified + waiting, Resolved grey, Reviewed light
  grey); a row filters the table. Columns sort on click; ▸ opens details (ID, check, what it means, what the audit
  saw, issue fixed, result, commits, notes, links).

### How to update it

| To record | Edit |
|---|---|
| A fix by the agent | a row in `reports/<tenant>/agent-fixes.json`: host, found, check, issue, repo, commits, fixed, verified, result; optional `finding` (id), `fixed_by` (default "Health and Recovery Agent"; also "Translation Agent", "Blog Team Platform", "Shoaib Khan") and `found_by` (who found it, for issues found by hand) |
| An issue found by hand and fixed | always an agent-fixes row with `found_by` (rule PROC-3): a scan sees only the current state, so a problem fixed before the next scan would leave no trace; set `verified` after checking it live; make it a check if it can recur |
| A note or decision | `reports/<tenant>/issue-notes.json`: `{"<finding id or check>": {"status": "Reviewed", "notes": [{"date", "by", "text"}]}}`; `by` in full ("Shoaib Khan") |
| A rule | `docs/rules.yaml` (id, rule, why, set_by, date, checks, status); a test checks ids and check names |

Names on the pages: people and agents in full (`site_pages.WHO` maps old short keys); Rules show
"Blogs Team" with "- Shoaib Khan" under it.

## Deploy trap

GitHub Pages of the conholdate-blogs repo twice kept a finished deployment "in progress" and refused the next one
("Please cancel <sha> first", while cancelling says "it's finished"). The workflow retries once after cancelling;
if that fails, SK re-runs the failed job after about 30 minutes (cleared both times on 12 Nov).

## Home page cards (13 Nov 2026, SK)

Each subdomain is a card (`build_site.sub_tile`): health score, a bar and "N% of issues closed" (fixed + resolved +
reviewed of all Issue log rows), "Open issues: X of Y", "N items still affected" (open ledger items); alerts under
it. Order everywhere: blog.aspose.com, blog.groupdocs.com, blog.conholdate.com, then the .cloud ones. Three per
row on desktop, two on tablets, one on phones. Replaces the 6 Nov rule "scores + alerts only".

## Issues chart on the Issue log (13 Nov 2026, SK)

`site_pages.issues_chart` puts the subdomain page's issues chart (open, fixed, all found; tooltip with resolved and
reviewed) on top of `/<host>/issues/`, full width, drawn by the same code: the template's `worm-css` and `worm-js`
blocks are cut out and injected with the same `issue_log_summary` series (`wormGraph(…, {issuesOnly: true})`).
Edit the chart only in the template; keep those blocks self-contained (they need `esc`, `day`, `$`).

## Issues across blogs (13 Nov 2026, SK)

`/blogs/issues/` (`site_pages.matrix_page`, built by `build_site` for each collection): one row per issue type
found on any blog, one column per blog in site order. Cells: ✗ Open (with "% fixed · N open" for item checks),
✓ Fixed / ✓ Resolved, Reviewed, or **NOT FOUND** in green when the audits never saw it there; each opens that blog's
Issue log. Rows grouped by severity (heading row each, worst first), inside a group most blogs open first. Last column: open count and the blogs where it was fixed
(where to copy the fix from). Linked from the home page's Blogs card ("issues across blogs →").

