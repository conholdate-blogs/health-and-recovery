# blog.aspose.cloud

Fourth blog in the fix round (order: blog.conholdate.cloud ✓ → blog.conholdate.com ✓ → blog.groupdocs.cloud →
**blog.aspose.cloud** → blog.aspose.com; blog.groupdocs.com monitor only). Log started 19 Nov 2026 with the first
scan with all checks. Update in the same session as each step.

## Facts (checked 19 Nov 2026)

| What | Value |
|---|---|
| Repo | `/Users/Apple/Work/Aspose/GitHub/blog.aspose.cloud-PROD/aspose-cloud-blog`, branch **`master`**; 1,257 English posts (`index.md`) |
| Commit identity | repo-local `Shoaib Khan <shoaib.khan@aspose.com>` set 19 Nov (it was missing); check `git config --local user.email` each session |
| Hugo | 0.101.0 (deploy workflow); binary `/Users/Apple/Downloads/Softwares/Hugo/hugo_extended_0.101.0_darwin-amd64/hugo` |
| Deploy | `.github/workflows/deploy-production-aws.yml`, cron 01:00 and 03:00 UTC Mon–Fri; Ceph production + staging workflows too |
| Redirects.json | 1,184 lines; live or applied at deploy: **to confirm** |
| llms.txt | none (no `static/llms.txt`, no `layouts/index.llms.txt`): fix catalogue row 7 (generate at build) |
| Languages | 21 supported: ar, da, de, el, es, fa, fr, he, hu, it, ja, ka, ko, pt, ru, th, tr, uk, vi, zh, zh-tw (config/sitemaps also publish cs, id: `language_unsupported`) |
| GA4 / GSC | 252280807 / `https://blog.aspose.cloud/` |
| Health | 67 (7 Nov), 66 (11 Nov repo check correction); **49** (19 Nov, all checks, before fixes) |

## Scan 1: full scan with all checks (19 Nov 2026, before any fix)

Runs: discovery 5, crawl audit 20, AI 21, speed 22, text 23, link check 25, repo check 26 (clone 6d325bb759). The
first attempt stopped in the link check when the session ended (run 24, no file); resumed with `--from
audit_links`; link check 30 min. Live page before it archived as 2026-11-19 (downloaded); snapshot 2026-11-19-2
"Full scan 19 Nov, all checks (before fixes)". **Health 66 → 49** (crawl 86 → 75, on-page 92 → 90, languages
83 → 78, AI 95, UX 100); issue types 22 → 44; open items 1,966 → 14,780 (almost all from checks added since 7 Nov,
not new damage; 1 item fixed: a missing-translation link); clicks 626 / impressions 59,079 (28 days to 16 Nov;
7 Nov: 659 / 58,659).

| Severity | Check | Items / pages | Note |
|---|---|---|---|
| broken | `link_missing_translation` | 1,220 links, 863 pages | translation agent prefixes links to untranslated posts (known since 22 Oct; was 1,389) |
| broken | `post_url_duplicate` **new** | 264 files | 6 URL pairs × 22 / 44 files: `cells/convert-excel-to-csv-in-csharp` (2023-02-10 / 2024-01-25), `convert-excel-to-html-in-csharp` (2023-02-09 / 2024-01-18), `convert-excel-to-html-in-java` (2022-09-08 / 2024-01-19), `html/complete-html-to-jpg-conversion-tutorial-in-python` (same post in `barcode/` and `html/`), `docx-to-html-conversion-in-php-high-fidelity-tutorial` (2026-07-24, also copied) |
| broken | `link_broken` | 71 links | |
| broken | `link_damaged` | 26 links, 16 pages | |
| broken | `post_body_cut_off` **new** | 7 posts | 5 unclosed code blocks (2024-10-09 glb-to-fbx java, 2026-06-05 barcode healthcare .NET, 2026-08-12 csv-to-xlsx nodejs, 2026-09-09 pdf header C#, 2015 imaging SDK release), 2 cut mid-sentence (2020-08-04 wordpress exporter, 2014-05-16 mail merge ruby) |
| broken | `post_front_matter_broken` | 1 file | `cells/2025-07-15-spreadsheet-cleaning-api-…/index.tr.md` (quoted scalar) |
| incorrect | `canonical_elsewhere` **new** | sample, est. 1,125 | `/page/2/` canonical → home (as blog.conholdate.com before B4); estimate inflated as on groupdocs |
| incorrect | `post_front_matter_escaped` **new** | 747 files | `\"…\"` in front matter |
| incorrect | `post_cover_lost` **new** | 669 translations | English post has a cover |
| incorrect | `description_untranslated` **new** | sample, est. 578 | translated home pages keep the English description |
| incorrect | `post_text_untranslated` | 304 | |
| incorrect | `link_wrong_language` | 64 links, 32 pages | |
| incorrect | `translated_url_mismatch` 22, `section_index_untranslated` 21, `text_topic_mismatch` (sample 17), `content_needs_js` (/search/ etc.), `language_name_wrong` 7 (ja 日本, ko 한국인, zh-tw 中國傳統的, vi/id English, tr Türk, he vowelled), `redirect_self_loop` 4, `translation_partial` 4, `translation_text_garbled` 1 (th dwg-to-png seoTitle has the English title + Thai), `menu_id_invalid` 1 (`asposecloud-zh-tw`) | | |
| not optimized | `social_tags_in_body` **new** | est. 9,126 | head order bug (fix catalogue row 1) |
| not optimized | `description_duplicate`, `title_duplicate` (crawl samples), `dup_in_file` 132, `section_lists_home_posts` **new** 22, `cross_sitemap_dups` 1 | | |
| improvable | `post_description_length` 5,993, `post_title_length` 2,923, `post_body_h1` 1,059, `translation_stale` 651, `link_redirected` 438, `redirect_key_malformed` 136, `tag_pages_thin`, `hreflang_no_xdefault`, `h1_missing` / `title_length` / `description_length` (samples), `post_front_matter_markup` 5, `rtl_direction_missing` 3, `slash_redirect_temporary` 2, `language_unsupported` 2, `lastmod_missing` 2, `llms_txt_missing` | | |

**Queue report** (`reports/aspose.cloud/queue-report-2026-11-19.md`): 1,509 queued translations in 74 posts (front
matter only 561, body 1–5 lines 360, 6–20 210, >20 357, no base 21; changed by others 879, optimizer 546, both 84);
46 posts are fix-here candidates (TR-9); English issues of fully queued posts 5; optimizer cuts 3 (2 still short);
by-hand items: half-translated titles 38, extra keys 566, missing cover files 185, tag lists differ 834. English
body check not run yet.

## Plan (same order as blog.conholdate.com; SK's rules apply)

1. ~~Full scan with all checks~~ done (Scan 1). ~~Queue report~~ done.
2. **English body check** on posts with queued translations (`scripts/ops/english_body_check.py --tenant
   aspose.cloud`), review every finding in context (CSV `review` column).
3. Show SK the findings by type with samples; propose fixes per batch, **English first** for queued posts (TR-10),
   current translations only otherwise (TR-9), ISSUE rows where a fix drops a needed retranslation; items left to
   retranslation go to `reports/aspose.cloud/after-retranslation.csv` (TR-11). The 6 duplicate URLs need the blog
   developer's call (which post stays), as on blog.conholdate.com.
4. Carry over the proven fixes: playbook "Fix catalogue" rows 1–24 (head order, x-default, tag/search/archives
   noindex, section page noindex, llms.txt at build, menu ids, language names, RTL; links, front matter, titles,
   covers, cut posts). Check sheet: `docs/check-sheet.md`.
5. Each blog push needs SK's approval; build-diff template changes with Hugo 0.101; verify live after SK's deploy;
   agent-fixes rows; rescan and snapshot.
