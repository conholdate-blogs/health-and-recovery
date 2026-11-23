# blog.groupdocs.cloud

Third blog in the fix round (order: blog.conholdate.cloud ✓ → blog.conholdate.com ✓ → **blog.groupdocs.cloud** →
blog.aspose.cloud → blog.aspose.com; blog.groupdocs.com monitor only). Log started 19 Nov 2026, before the first
scan with all checks. Update in the same session as each step.

## Facts (checked 19 Nov 2026)

| What | Value |
|---|---|
| Repo | `/Users/Apple/Work/Aspose/GitHub/blog.groupdocs.cloud-PROD/groupdocs-cloud-blog`, branch **`master`** (not main); 584 English posts |
| Commit identity | repo-local `Shoaib Khan <shoaib.khan@aspose.com>` set 19 Nov (it was missing); check `git config --local user.email` each session |
| Hugo | 0.101.0 (deploy workflow); binary `/Users/Apple/Downloads/Softwares/Hugo/hugo_extended_0.101.0_darwin-amd64/hugo` |
| Deploy | `.github/workflows/deploy-production-aws.yml` (`aws s3 sync ./public/ s3://blog-groupdocs-cloud/`), cron 01:00 and 03:00 UTC Mon–Fri; Ceph production + staging workflows too. SK runs deploys by hand when needed |
| Redirects.json | 506 lines; live or applied at deploy: **to confirm** (blog.conholdate.com: at deploy; blog.aspose.com: live via Lambda@Edge) |
| llms.txt | none (no `static/llms.txt`, no `layouts/index.llms.txt`): fix catalogue row 7 (generate at build) |
| Languages | 18 supported: ar, de, es, fa, fr, id, it, ja, ko, pl, pt, ru, th, tr, uk, vi, zh, zh-hant |
| GA4 / GSC | 252358764 / `https://blog.groupdocs.cloud/` |
| Who edits content (since May 2026) | mustafabutt-dev 58 commits (new posts), shoaibkhan-aspose 42 (translation agent), Blogs Translation Agent 11, Farhan Raza 7 ("Optimized Blog Posts"), igor.zubarev 2 |
| Health | 75 (7 Nov scan, before the new checks); **54** (19 Nov, all checks, before fixes) |

## Known before the scan (docs/identified-issues.md, dry runs 12–13 Nov)

Company menu bar missing on /zh-hant/ (`groupdocscloud-zh-hant`; `-zht` exists), descriptions/titles out of range
3,870 / 2,390, stale translations 234, translations keeping English text 117, junk redirect entries 63, section
`_index.md` English only 18, wrong language names 5, RTL off 2, a redirect target not https, 1 translated URL
mismatch, no-slash 302. Earlier link check (22 Oct): ~490 links to old WordPress `/category/<x>/`, 129 damaged links
from 2023 translations.

## Scan 1: full scan with all checks (19 Nov 2026, before any fix)

Runs: discovery 5, crawl audit 19, AI 20, speed 21, text 22, link + repo checks the same day (clone f13d6515);
8 min. Live page before it archived as 2026-11-19 (downloaded); snapshot 2026-11-19-2 "Full scan 19 Nov, all
checks (before fixes)". **Health 75 → 54** (crawl 88 → 74, on-page 94 → 92, languages 88 → 83, AI 95, UX 100);
issue types 15 → 39 (24 new, almost all from checks added since 7 Nov, not new damage); clicks 752 / impressions
72,476 (28 days to 16 Nov; 7 Nov: 717 / 62,338).

| Severity | Check | Items / pages | Note |
|---|---|---|---|
| broken | `link_broken` | 511 links, 509 pages | 42 targets; mostly old WordPress `/category/<x>/`; 476 copied from the English post |
| broken | `post_url_duplicate` **new** | 76 files | 2 English pairs × 19 files: compare-excel-files-via-rest-in-csharp (2026-09-21 / 2026-10-09), extract-text-from-pdf-in-nodejs (2025-06-18 / 2026-09-21) |
| broken | `post_body_cut_off` **new** | 4 posts | 3 unclosed code blocks (2026-07-08 json-to-html php, 2026-08-24 csv-to-jpg python, +1), 1 2015 maintenance post |
| broken | `link_damaged` / `link_missing_translation` | 5 / 2 pages | |
| incorrect | `canonical_elsewhere` **new** | sample 2/34 | `/page/2/` canonical → home (as blog.conholdate.com before B4); estimate 922 inflated (page 2 classed as post template; tenant fixed 19 Nov, `paginated` template, correct from the next crawl); fix = playbook row 25 |
| incorrect | `description_untranslated` **new** | sample 4 | translated home pages keep the English description (F13 on blog.conholdate.cloud) |
| incorrect | `post_front_matter_escaped` **new** | 544 files | `\"…\"` in cover alt/caption |
| incorrect | `post_cover_lost` **new** | 423 translations | English post has a cover |
| incorrect | `link_wrong_language` | 72 links, 18 pages | 4 targets |
| incorrect | `link_differs_from_original` **new** | 36 links | |
| incorrect | `section_index_untranslated` 18, `language_name_wrong` 5, `translated_url_mismatch` 1, `post_text_untranslated` 110, `menu_id_invalid` 1 (zh-hant), `content_needs_js` (/search/), `text_topic_mismatch` 5 | | all known from the dry runs |
| not optimized | `social_tags_in_body` **new** | 33/34 sampled | head order bug (fix catalogue row 1) |
| not optimized | `section_lists_home_posts` **new**, `dup_in_file` 38 | | |
| improvable | `hreflang_no_xdefault`, `llms_txt_missing`, `h1_missing` (sample), `h1_multiple`, `post_body_h1` 1,308, `title_length`/`description_length` (crawl), `post_title_length` 2,382, `post_description_length` 3,855, `translation_stale` 198, `tag_pages_thin`, `link_redirected` 157, `redirect_key_malformed` 74, `redirect_target_bad` 1, `slash_redirect_temporary`, `rtl_direction_missing` 2, `post_front_matter_markup` 39, `text_typo` 1 | | |

**Queue report** (`reports/groupdocs.cloud/queue-report-2026-11-19.md`): 552 queued translations in 31 posts
(354 after other English edits, 198 after the optimizer); 21 posts are fix-here candidates (TR-9); English issues
of fully queued posts 2 (a broken link; the duplicate URL above); optimizer cuts 0; by-hand items: half-translated
titles 68, extra keys 527, missing cover files 71, tag lists differ 531. English body check not run yet.

## Scan 2: quick scan after the retranslation batch (23 Nov 2026)

Clone f13d6515 → 580e4ba7: 30 commits (23 translation agent "Retranslate articles", 288 files in 17 posts; 2 new
viewer posts; 1 optimizer commit on 2023-08-28-zip-to-jpg-online). Quick cycle (links + repo, 8 min): link run 25,
repo run 26. **Open items 9,512; fixed since 19 Nov 456, all in retranslated posts; new 18** (all
`translation_stale` of zip-to-jpg after the optimizer edit).

| Check | Fixed by the retranslation |
|---|---|
| `post_cover_lost` | 199 (424 → 224 open) |
| `post_description_length` / `post_title_length` | 122 / 36 |
| `post_front_matter_escaped` | 64 |
| `link_differs_from_original` | 18 (36 → 18) |
| `post_text_untranslated` | 16 |
| `post_front_matter_markup` | 1 |

- **Retranslated files compared with their English post** (scratch script, code fences, code lines, headings,
  links, images, shortcodes, front matter keys, url, title/description = English): **288 of 288 match, no new item
  in any retranslated file**; YAML valid. The old versions had extra code blocks (e.g. pdf-to-jpg de: 12 fences / 58
  code lines vs English 10 / 29). Items still open in those posts are in files not retranslated yet.
- Not fixed by retranslation (English-side): `post_url_duplicate` extract-text-from-pdf-in-nodejs (19 files).
- **Optimizer 580e4ba7:** `seoTitle` "ZIP to JPG | Transform ZIP files to JPEG Images" → "ZIP to JPG Online Converter
  – Fast, Free, Secure" (fine; first read of the word-diff wrongly said the topic was dropped, SK corrected it 23
  Nov: read the full before/after line, never only the word-diff); writes U+2011 non-breaking hyphens ("picture‑perfect"): in 85 English
  posts and 1,148 translations repo-wide.
- **Queue report** (`queue-report-2026-11-23.md`): 282 queued translations in 16 posts (was 552 in 31); 216 after the
  optimizer; 8 fix-here candidates; 1 English issue in fully queued posts (`/category/conversion/` 404 in
  2022-11-05-convert-csv-to-json…); by-hand: half-translated titles 65, extra keys 493, missing cover files 71, tag
  lists differ 485.
- **English body check** (16 queued posts, `english-body-check-2026-11-23.csv`): 18 findings, reviewed in context:
  **11 real** (typos "Cloud EST API", "wildly used", "supper-efficient", "where as"; sentence copied from a PDF post
  in mpp-to-excel-in-csharp 2024 ("export MS Project file to PDF format" in an Excel post); "editable DOC document" in
  html-to-word; broken "Swagger UI lets you…" in zip-to-jpg; 4 anchor ids from other posts: msg-to-pdf-in-ruby
  `#…-in-python`, csv-json 2× `#PDF-to-HTML-Online-Conversion-Tool` (also a duplicate id), word-in-php
  `#Excel-to-HTML-Viewer-…-Node-js-SDK`), **7 false** ("CSharp" in anchor ids, `[][6]` figure link, colon before a
  code block, `npm install MODULE_NAME` generic phrase, "instructions at [link]").

## Fix batch 1: English fixes in queued posts (TR-10), 23 Nov

- **1b509e71** (pushed to `master` 23 Nov with SK's approval; live after the next deploy, cron 01:00/03:00 UTC Mon–Fri): the 11 real English-body-check findings + the `/category/conversion/`
  404 in 8 posts, 12 lines (commit message lists each). All 8 posts have queued translations, so nothing extra is
  retranslated; the 72 h wait restarts for these 8 (trap).
- Build check (Hugo 0.101, `build_pair.sh` + `build_diff.py`): exactly the 8 English pages, their feeds/tag feeds and
  `index.json` changed. Also 9 translations of comparison/compare-excel-files-via-rest-in-csharp differ between
  two builds of the **same content**: the duplicate URL (`post_url_duplicate`) makes Hugo pick either post at random
  per build. Evidence for the blog developer (SK asked him 23 Nov which post keeps each URL).
- **Found by hand, not fixed (SK to decide):** one GroupDocs Cloud client_id + client_secret written out in a cURL
  example in 2 English posts (merger/2024-06-14-combine-pdf-files-using-pdf-file-merger,
  merger/2025-08-19-merge-pdf-files-using-csharp) and 36 translations. Proposed: rotate the key in the dashboard,
  replace with `{CLIENT_ID}` / `{CLIENT_SECRET}`; candidate check `post_secret_literal`.
- After deploy: live check of the 8 pages, agent-fixes row, rescan.

## Plan (same order as blog.conholdate.com; SK's rules apply)

1. **Full scan with all checks** (`caffeinate -i .venv/bin/python scripts/run_cycle.py groupdocs.cloud`, ~8 min; it
   pulls the clone first): first run of the 18–19 Nov checks here (`post_front_matter_markup`,
   `translation_text_garbled`, `post_cover_lost`, `post_front_matter_escaped`, `post_body_cut_off`,
   `post_raw_html_dropped`, `link_differs_from_original`, shortcodes). Archive the live report page before the
   snapshot. Record every number here.
2. **Queue report** (`scripts/ops/translation_queue_report.py --tenant groupdocs.cloud`, 15 s): queued
   translations by English change size and author, English issues of fully queued posts, optimizer cuts mid-post,
   check-sheet by-hand items (half-translated titles, translated keys, missing cover files, tag lists).
   **English body check** on posts with queued translations (`scripts/ops/english_body_check.py --tenant
   groupdocs.cloud`), review every finding in context (CSV `review` column).
3. Show SK the findings by type with samples; propose fixes per batch, **English first** for queued posts (TR-10),
   current translations only otherwise (TR-9), ISSUE rows where a fix drops a needed retranslation; every item a
   fix leaves to retranslation goes to `reports/groupdocs.cloud/after-retranslation.csv` (TR-11).
4. Carry over the proven fixes: playbook "Fix catalogue" rows 1–24 (template: head order, x-default, tag/search/
   archives noindex, section page noindex, llms.txt at build, menu ids, language names, RTL; content: links,
   front matter, titles, covers, cut posts). Check sheet: `docs/check-sheet.md` (also `/check-sheet/` on the site).
5. Each blog push needs SK's approval; build-diff template changes with Hugo 0.101; verify live after SK's deploy;
   agent-fixes rows; rescan and snapshot.
