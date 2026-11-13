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
   On-page = crawl audit; Languages = sections; AI = AI access; Speed = speed. The lowest area below 100 opens by
   default.
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
Issue log. Rows: most blogs open first, then severity. Last column: open count and the blogs where it was fixed
(where to copy the fix from). Linked from the home page's Blogs card ("issues across blogs →").

