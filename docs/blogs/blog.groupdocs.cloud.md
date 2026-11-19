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
| Health | 75 (7 Nov scan, before the new checks) |

## Known before the scan (docs/identified-issues.md, dry runs 12–13 Nov)

Company menu bar missing on /zh-hant/ (`groupdocscloud-zh-hant`; `-zht` exists), descriptions/titles out of range
3,870 / 2,390, stale translations 234, translations keeping English text 117, junk redirect entries 63, section
`_index.md` English only 18, wrong language names 5, RTL off 2, a redirect target not https, 1 translated URL
mismatch, no-slash 302. Earlier link check (22 Oct): ~490 links to old WordPress `/category/<x>/`, 129 damaged links
from 2023 translations.

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
   current translations only otherwise (TR-9), ISSUE rows where a fix drops a needed retranslation.
4. Carry over the proven fixes: playbook "Fix catalogue" rows 1–24 (template: head order, x-default, tag/search/
   archives noindex, section page noindex, llms.txt at build, menu ids, language names, RTL; content: links,
   front matter, titles, covers, cut posts). Check sheet: `docs/check-sheet.md` (also `/check-sheet/` on the site).
5. Each blog push needs SK's approval; build-diff template changes with Hugo 0.101; verify live after SK's deploy;
   agent-fixes rows; rescan and snapshot.
