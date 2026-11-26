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
| Redirects.json | **applies live** (confirmed 26 Nov: `/tag/.net-html-to-xps-conversion/` answers its entry's 301) |
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

## Scan 3: full scan before batch 2 (26 Nov 2026, SK: "better to perform before fixes")

Clone 01fe452d (= live: batch 1 deployed and verified, 9 more retranslation commits, 3568e0a3 removed the duplicate
posts); batch 2 parked on branch `batch2-split` so the repo checks see only what is live. Runs: discovery 7, crawl 27,
AI 28, speed 29, text 30, links 31, repo 32. Snapshot **2026-11-26** "Full scan 26 Nov, before batch 2 (template
fixes)" (live page = 2026-11-23-2, already archived).

| | 19 Nov | 23 Nov | 26 Nov |
|---|---|---|---|
| Health | 54 | 54 | **55** (crawl 74 → 75) |
| Issue types | 39 | 39 | **37** |
| Open items | 9,950 | 9,512 | **9,116** |
| Clicks / impressions (28 days) | 752 / 72,476 | 794 / 79,794 | 834 / 83,487 |

Fixed since 23 Nov: 341 items, 0 new: `translation_stale` 126, `post_title_length` 61, `post_description_length` 41
(retranslations), `post_url_duplicate` 38 + `dup_in_file` 38 (duplicate posts removed by the blog developer; findings
crawl-261119-3 and crawl-0001 resolved), `post_cover_lost` 18, `post_front_matter_markup` 17, `link_broken` 1 (batch
1), `post_text_untranslated` 1.

## Fix batch 2: template and config fixes, one commit per fix (SK, 26 Nov)

**Pushed 26 Nov (01fe452d..8fc184e4), waits for deploy.** SK: one commit per fix type, easier to review (and to revert, and one agent-fixes row each). First built as one
commit 7d317afe (local), split into 12 by a script; final tree byte-identical to 7d317afe; each commit builds alone
with Hugo 0.101 (100,281 pages each).

| Commit | Fix (catalogue row) |
|---|---|
| f8990763 | head order: language switcher last, OG/Twitter/JSON-LD in `<head>` (1) |
| fd626511 | x-default in head and sitemaps (2) |
| 934d5bf5 | tag pages `noindex, follow` (3) |
| b7e81cac | /search/, /archives/ `noindex, follow`, out of sitemaps (4) |
| cf61fe76 | /GroupDocs.Cloud/ section page `noindex, follow`, out of sitemaps (16) |
| be79bc86 | 18 section `_index.<lang>.md` |
| acebd752 | listing pages 2+ `noindex, follow` + self canonical (25) |
| cc974a5d | llms.txt at build (7) |
| cc9ca113 | language names ja, ko, zh-hant, id, th (11) |
| f042fb05 | RTL ar, fa (14) |
| fce32e65 | zh-hant menu id `groupdocscloud-zht` (15) |
| 8fc184e4 | home description per language, English 353 → 148 characters (12) |

Build diff (whole batch vs 01fe452d): only robots of tag pages, /tags/, /search/, /archives/, the section page and
page 2+ (5,915 rows, all expected kinds); 19 llms.txt files added; sitemaps change by x-default lines and the dropped
utility/section URLs; **SEO tags in `<body>` 56,079 → none**; x-default on 55,955 pages (the 44,345 without have no
hreflang at all, except 765 tag/category pages whose term exists only in translations: no English page to point to).
Seen in passing: tag slugs with backslashes (`/tag/\add-image-to-word\/`, from `\"…\"` in tag lists) on 1 language
each: candidate check.

### Batch 2 live (26 Nov): verified, rescan

SK deployed 26 Nov. Live check (scratch `live_b2.py`): **28 of 28 pass** (head order, x-default in pages and
sitemaps, robots of tag/search/archives/section/page 2+, self canonical on page 2+, home/posts still `index, follow`,
fr section title, llms.txt en/de text/plain, language names, `dir=rtl` ar/fa, zh-hant `-zht`, home descriptions);
screenshots of /zh-hant/ (company bar in Traditional Chinese) and /ar/ (right to left). 12 agent-fixes rows.

Rescan (runs: crawl, AI, speed, text, links, repo, structure on 8fc184e4), snapshot **2026-11-26-2** "After batch 2":

| | Before (26 Nov) | After (26 Nov) |
|---|---|---|
| Health | 55 | **82** (crawl 75 → 90, languages 83 → 90, AI 95 → 100) |
| Issue types | 37 | **26** |
| Open items | 9,116 | 9,091 |

Resolved: social tags in body, x-default, canonical to page 1, section page list, section `_index` English only,
language names, RTL, company menu, description untranslated, text needs JavaScript (/search/), llms.txt missing,
tag pages thin. New: `llms_txt_charset` (llms.txt served as `text/plain` without `charset=utf-8`: same as F22 on
blog.conholdate.cloud; `hugo deploy` matcher `*.txt` → `text/plain; charset=utf-8` in `deployment.matchers`).

**Our audit corrected (26 Nov):** the structure step read the first tag pages alphabetically: `/tag/.net-…/` (404, and
a Redirects.json 301 to a post) and kept `tag_pages_thin` open. Now it reads on until two tag pages answer 200 and
treats a redirected URL as not the page (`core/audit/structure.py tag_robots`, `scripts/audit_structure.py get`,
test added). The first snapshot of this rescan carried the false finding; dropped before publishing, redone.

**Found by Shoaib Khan and the agent (26 Nov): tag URLs starting with a dot 404 live.** 3 tags (`.NET rewriter SDK`,
`.NET HTML to XPS conversion`, `.NET HTML to PDF converter`, 1 post × 19 files each) → 57 tag pages in the Hugo
build answer 404 (`/tag/.net-html-to-xps-conversion/` has a Redirects.json entry to the post); 64 post pages link to
them. Likely cause: the deploy upload skips folders whose name starts with a dot (to confirm on the bucket). Also
confirms **Redirects.json applies live on this blog** (Facts table "to confirm" settled).

## Fix batch 3a: tags, categories, small fixes (26 Nov 2026; pushed 8fc184e4..bb1da4d8, waits for deploy)

Shoaib Khan: merge dot tags into existing tags where possible ("dotnet" otherwise); then found `c#` tags
(`/tag/c#-ai-summarization/` cut at `#`) and asked to check other characters; tags are never translated (confirmed:
translation agent `translatable_fields`). One commit per fix type; each English change ships with all its
translations (checked per commit: no English file changed without all its translations, so nothing is queued).

| Commit | Fix | Files |
|---|---|---|
| 4fca7cac | `.NET rewriter SDK` → existing `document rewriting` (shared with the other rewriter post) | 19 |
| 2ce59c6d | `.NET HTML to XPS conversion` removed (the post already has `html to xps conversion`) | 19 |
| 8864154b | `.NET html to pdf converter` → existing `html to pdf converter` | 19 |
| bef704c7 | llms.txt / robots.txt served `text/plain; charset=utf-8` (`deployment.matchers`, as F22 on blog.conholdate.cloud) | config |
| bd47f594 | "Home" label in each language (`params.label.text`, words as blog.conholdate.com + uk, zh-hant) | config |
| 385873d2 | translated keys → `tags` / `categories` (`теги`, `категории`, `etiketler`, `برچسب‌ها`, `دسته‌ها`, `catégories :`, `categorias`) | 25 |
| f8649f45 | escaped `\"…\"` in tags and categories (also mismatched `\"x"`, curly `\"x\”`, run-together `x\" - \"y` split) | 162 |
| 8b0ec070 | `c#` → `csharp` in tags (59 tags, 17 posts; no existing `csharp`/`c-sharp` tag to merge into) | 323 |
| 93ea772d | translation tags = English tags (29 posts: translated or partly translated by the 2025 pipeline) | 485 |
| bb1da4d8 | translation categories = English (translated or missing) | 93 |

Tool: `scripts/ops/taxonomy_fix.py` (modes `--keys`, `--escaped`, `--hash`, `--tags`, `--categories`; dry run by
default; only the tags/categories lines change, each file re-parsed and compared; queued translations skipped and
listed). Its first runs had three bugs, all caught by its own re-parse checks or by Shoaib Khan before any push:
block-list detection ran into the next key (refused 58 files), mismatched/curly escapes left `"\"word to html
csharp\""` (seen by Shoaib Khan), a translated-only `categorias:` got a second `categories:` key (now renamed first;
French `catégories :` has a space before the colon). Commits rebuilt from bd47f594 each time (all local).

**New checks (AUD-3), so every blog is scanned for these:** `url_part_unsafe` (tag, category or post url with a leading
dot, `#`, backslash or quotes) and `translation_taxonomy_differs` (translation tags/categories not the English ones,
translated key names); structure step fixed to skip tag pages that 404 or redirect. Dry run: blog.groupdocs.cloud 0
after the commits; blog.conholdate.cloud 0; **blog.conholdate.com 3,691** (2,821 `#` tags, 837 tag lists, 33 escaped;
register, not fixed now). The waiting blogs get them at their scans. Check sheet F15 updated, F16 added; playbook
rows 26, 27.

Build check before the push (Hugo 0.101, 8fc184e4 vs bb1da4d8): each of the 10 commits builds; post pages 11,155 before and after; removed only tag (3,732) and category (108) pages with broken or translated slugs; added 4,392 tag pages (each language's version of the English tags, noindex); no tag slug with a leading dot, # or backslash. Pushed with Shoaib Khan's approval 26 Nov. After deploy: live check (dot/# tag links gone, /tag/document-rewriting/, llms.txt charset, Home label), agent-fixes rows, rescan.

**Deployed and verified live 26 Nov:** 15 of 16 checks pass (scratch `live_b3.py`): no `.net-` tag link on the posts (en, fr, ja), /tag/document-rewriting/ lists both rewriter posts, /tag/csharp-ai-summarization/ 200 and no tag link with `#`, no tag/category link with a backslash or quote on ru/id/fr/zh-hant translations, zh-hant Parser category page lists its posts, Home label ホーム/Accueil/Головна/首頁. **Open:** llms.txt still `text/plain` without charset: `hugo deploy` re-uploads only changed files and llms.txt did not change; it takes the header with the next post (or one `hugo deploy --force`). 8 agent-fixes rows. Quick rescan (links, repo, structure): new checks 0, health 82, 26 issue types; snapshot 2026-11-26-3.

## llms.txt: most read first (26 Nov 2026, suggested by Shoaib Khan)

Search Console: the 30 most-clicked pages earn 52% of clicks and none was among the newest 100 that llms.txt listed. 3 months (25 Aug - 23 Nov, 2,129 clicks): blog-wide post #10 34 clicks, #30 9, #50 5, #100 3; posts with >= 3 clicks per language fa 29, ru 20, en 13, others 0-11. Shoaib Khan chose **30 most read + 70 newest** (50/50 considered: slots 31-50 would be 1-2 click posts). Blog commit 7a311dc1 (deployed and verified live 26 Nov: 30 + 70 on en, ru, fa; llms.txt now `text/plain; charset=utf-8`): `data/llms_popular.json` (scripts/ops/llms_popular.py --top 30) + template. Build check: 30 + 70 in every language, no URL twice, fallback to 100 newest without the data file, no other file changes. **Monthly refresh as an approved commit (Shoaib Khan).** Next refresh: around 26 Dec 2026.

## Fix batch 3: content in current translations (26 Nov 2026; local, waits for approval)

One commit per fix type; queued translations skipped (they get the fix with their retranslation); every English change
ships with all its current translations.

| Commit | Fix | Files |
|---|---|---|
| 56f7f115 | llms.txt "Last updated" = later of newest post and most-read list (`_updated` in the data file; asked by Shoaib Khan) | 2 |
| adf8ba24 | `\"…\"` values unwrapped (title, seoTitle, description, summary, cover alt/caption; `capa:` blocks too) | 488 |
| ece18216 | cover image restored (flat cover block indented; `capa:` → `cover:`; キャプション, légende, legenda → caption) | 220 |
| 2fec2a06 | `/category/conversion/` (404; /ja/ via a Redirects.json entry) → `/categories/groupdocs.conversion-cloud-product-family/` | 494 links |
| b5d1269a | dated `/2023/02/10/convert-html-to-markdown-…` → current URL | 19 links |
| 26bf6994 | damaged, mistyped (`-in-Java-`, `-USE-rest-api-`), doubled-language (`/ar/ar/`) links | 16 links |
| dbad1988 | wrong-language links in extract-images-from-word-using-csharp translations | 72 links |
| 57e7080f | broken-off URL remainders after links (` -API/)`, ` -파이썬/)`, `/)`; found by Shoaib Khan in review of 26bf6994) | 13 lines |
| 42747fa4 | generator's stray fence before `<!--[CODE_SNIPPET_END]-->` (json-to-html-php, csv-to-jpg-python, ods-to-xlsx translations) | 32 |
| 0ffba0cb | 2018 Viewer Cloud release post: closing fence glued to a caption + a stray fence | 19 |
| 720532a3 | closing fences that swallowed the next sentence (``` Bitte befolgen…) | 20 |
| 1f27615d | empty extra code block in convert-excel-to-csv-in-csharp translations | 18 |

Findings while fixing (all now checks or rules):
- **Snippet markers** `<!--[CODE_SNIPPET_START/END]-->` (post generator; another generator writes `COMPLETE_CODE_SNIPPET`)
  are HTML comments, invisible on the page; they stay. The generator also writes a bare ``` before the END marker, which
  opened a new block: live, the marker and the explanation after every snippet showed inside a code block (csv-to-jpg:
  5 times). Report to the generator's developer. The translation agent knows the markers and keeps fence counts on purpose
  (`_code_fence_count_mismatched`), so it copies the stray fence into every language.
- **Old translation pipeline damage:** fences added or merged in translations: closing fence joined to the next sentence (78),
  empty extra blocks (18), extra fences that put a real ```` ```python ```` in closing position. Gist embeds inlined as code
  are a separate, harmless convention (6,424 translations with more fences than English for that reason only).
- **Split URLs:** an older translation run split links; the tail landed after the sentence (some tails translated: -파이썬, -piton).
- **Our mistakes, caught:** the damaged-link fix left the remainders (Shoaib Khan); the first remainder clean-up swallowed
  sentence endings (caught before commit); `fm_cover_repair.py` false alarms (leading spaces, `legenda`, `capa:` in escaped
  mode) fixed in the tool; the cut-off check flagged a 2015 letter ending "Kind regards, The GroupDocs Team" (sign-offs now ok).
- **Not fixed here:** French link to convert-jpg-to-pdf (waits for that post's own-slug URL, `translated_url_mismatch`);
  Turkish caption `C#"da` (should be an apostrophe, minor); the API secret (waits for key rotation).

**Retranslation (Shoaib Khan offered):** `reports/groupdocs.cloud/retranslate-candidates.csv`: 32 current translations in 6 posts
ISSUE rows added by Shoaib Khan 26 Nov (code blocks damaged: csv-to-pdf-java 11, csv-to-jpg-python 14, ods-to-xlsx-php 4, three Korean files);
7 more (json-to-html-php fa/id/zh-hant, csv-to-jpg-python fa/it/ja/ru) are queued by the 42747fa4 English change.

**New checks:** `code_fence_misplaced` (stray / glued / empty-block fences, unclosed block in a translation),
`link_split_remainder`; `post_body_cut_off` accepts sign-offs. Dry run: blog.groupdocs.cloud 0 left except the 39 translations
for retranslation; blog.conholdate.cloud 0; blog.conholdate.com 23 (22 translations with an unclosed block, 1 stray).

## Post generator review (24 Nov 2026, SK: suggestions for the generator's developer)

63 English posts added by the post generator in 2026 (58 still present at 58f52465; 5 removed: 3 copies in a
`barcode/` folder, and the 2 duplicate-URL copies, removed 24 Nov by 3568e0a3 "removed duplicate posts"). Most
are "Auto-merge" commits (no human review). Scratch scripts: `gen_items.py`, `gen_content.py`, `overlap.py`.

| Finding | Posts |
|---|---|
| Unclosed code block cuts the post off (`post_body_cut_off`) | 2 (2026-07-08 json-to-html php, 2026-08-24 csv-to-jpg python; the second also has an H1 in the body) |
| Same topic and language as an older post (cannibalization) | word/docx-to-html python ×3 (2022, 2026-07-15, 2026-10-30); compare-excel C# (2025-09-19 / 2026-09-21); extract-images-from-pdf C# (2025-09-24 / 2026-10-12) and Java (2023 / 2026-10-02) |
| `seoTitle` = `title` (no separate search title) | 58 of 58 |
| One-post tags (thin tag pages ×19 languages) | 122 of 172 tags |
| U+2011 hyphens | 57 of 58 posts, 558 chars (70 in front matter, 19 in code comments): the generator writes them too, not only the optimizer |
| Template fill bug "learn how to perform how to convert…" | 1 (2026-11-23 powerpoint-to-images) |
| "pricing page" link goes to the temporary-license page | 4 |
| Squashed slug words (`stepbystep`, `groupdocsrewriter`, `groupdocseditor`, `aspnet`); titles 65/72 chars | 2 (2026-11-11 posts) |
| Boilerplate note paragraph identical in 56 posts | 56 |
| `faqs` / `steps` front matter not used by the theme (no FAQPage/HowTo JSON-LD; FAQs render as body text) | all |

Fine: descriptions 120–160 in all, cover files present, 600–1,200 words, URL = `/<section>/<slug>/`, no literal keys.

## Traffic decline analysis (24 Nov 2026, SK: "check the June drop first", "check bulk changes")

Search Console, both .cloud blogs (blog.aspose.cloud in brackets):

| Question | Answer |
|---|---|
| When was the June drop? | **27 May 2026**, the same day on both blogs: daily clicks ~85 → ~30 (≈50 → ~22), impressions about flat. blog.groupdocs.com did not drop (holiday dip, back on 1 June) |
| Cause | **Iran**: 838 of 1,285 clicks (65%) in 13–26 May came from Iran (aspose.cloud 367 of 647, 57%), mostly Persian "free online" posts. Iran clicks 1,501 (May) → 352 (June) → ~100/month since; also 2 clicks in March 2026. External (likely Iranian internet restrictions), not a site change |
| Repo changes 15–30 May | groupdocs.cloud: **none**; aspose.cloud: only generated posts added/removed |
| Long decline (Sep 2025 → Jan 2026) | non-Iran clicks 3,378 → 1,306 (−61%), all countries. English pages Sep 2025 819 clicks / 73,036 impr → Oct 2026 84 / 16,916. Top page `/conversion/zip-to-jpg-online/` 486 → 45 clicks (Sep → Jan), position 4.9 → 8.8, CTR halved at the same position: gradual, no single event |
| Bulk changes since Jul 2025 | hi + cs removed from config (72ef0aea, 10 Oct 2025): 7 clicks in Sep 2025, not the cause; aspose.cloud `env: staging` in config.yml (d3ab50758b, 13 Feb 2026) reverted next commit, live robots `index, follow`; Redirects.json invalid 31 Oct 2025 – 6 Jan 2026 (85091a17 fixed): overlaps the decline, **unproven** (whether this blog reads Redirects.json live is still to confirm); no bulk English edits (max 31 files/month, Nayyer link fixes, Farhan optimizer Oct–Nov 2026) |
| Generated posts | 58 posts × ~19 languages: **31 clicks, 2,803 impressions** (1 Aug – 20 Nov 2026) |

Strategy given to SK for the generator's developer: slow generation, refresh what earned traffic (online-tool intent, translated pages), check indexing of generated posts, measure per batch.

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
