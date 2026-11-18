# blog.conholdate.com: log

Pilot blog for "scan and fix" (SK, 2026-11-11): get this blog right first, then repeat the steps on the others.
Updated in the same session as every finding, decision, fix and check. Steps that repeat for every blog live in
[../playbook.md](../playbook.md).

## Facts

| Item | Value |
|---|---|
| Source repo | `conholdate/conholdate-blog`, branch **main**; local clone `/Users/Apple/Work/Aspose/GitHub/blog.conholdate.com-PROD/conholdate-blog` |
| Workflows repo | `conholdate/conholdate-blog-workflows` (local clone next to it) |
| Production deploy | `Deploy Production - AWS` and `- Ceph`, cron `0 3 * * 1-5` = **08:00 PKT** Mon–Fri (the workflow comment says 10–11 AM: wrong), skipped when there are no new commits; manual run from the Actions tab |
| Hugo | **0.101.0** extended (local: `/Users/Apple/Downloads/Softwares/Hugo/hugo_extended_0.101.0_darwin-amd64/hugo`) |
| Redirects.json | Applied **at deploy**, not live from the repo (unlike blog.aspose.com): a removed entry still answered 301 ten minutes after the push and 404 right after the AWS deploy (11 Nov) |
| Size (7 Nov) | 559 English posts, 10,062 post files, 18 languages; 53,700 sitemap URLs, 43,584 of them tag pages |
| Traffic (28 days to 3 Nov) | 2,906 clicks; tag pages 45 |
| Theme | PaperMod; `footer.html` is `partialCached` per layout and kind (a per-page check in `extend_footer.html` does not hold) |
| Gists | `{{< gist user id "file" >}}` shortcode: 2,963 embeds in 1,314 post files (397 English posts) |
| Commits | Translation agent (`shoaib.khan@aspose.com`, "Translate articles for: …") and auto-merges |
| Fix channel | SK's team (Phase 1: every push needs SK's approval) |

## Fixes

| Date | Fix | Commit | Verified |
|---|---|---|---|
| 2026-11-11 | Gist placeholder: `extend_footer.html` removes `.gist template` (same as blog.groupdocs.com) | `065759ab` | Live after the AWS deploy: a post with 4 gists renders all 4 and no `{{ revealButtonHref }}` (headless Chrome) |
| 2026-11-11 | Redirects.json: all 6 `revealButtonHref` entries removed (1465 → 1459) | `9cc26f48` | 404 after the deploy; other redirects still 301 |

Both carry "Fixed by Health and Recovery Agent" and are listed in `reports/conholdate.com/agent-fixes.json`.

## Findings and decisions

| Date | Finding | Decision |
|---|---|---|
| 2026-11-11 | `{{ revealButtonHref }}` URLs: 0 Search Console impressions in 16 months | Fix the source (footer) and remove all redirect entries (SK: none should exist) |
| 2026-11-11 | Junk redirect entry left: 1 `#:~:text=` fragment key (`/total/export-data-to-excel-in-java/%23:~:text=…`); 5 non-ASCII keys | Remove (B1); SK's rule: no redirect for junk URLs |
| 2026-11-11 | 15 translations under their own URL (all French, 2020–2022; e.g. `fr/total/créez-votre-propre-application-google-docs-like`) | Back to `/fr/<English url>/` (B2); redirects or not: **open, see "Waiting for SK"** |
| 2026-11-11 | hreflang without x-default (14,072 pages) | Template fix (B3) |
| 2026-11-11 | 93% of tags have one post; sitemaps list 43,584 tag pages; `Disallow: /tag/` blocks the English ones (crawl-0002) | Tag + pagination pilot (B4) |
| 2026-11-11 | Wrong-language links 374, broken 81, damaged 54, missing translations 20 | Link fixes from the fix lists (B5) |
| 2026-11-11 | Open Graph, Twitter and JSON-LD land in `<body>` (home checked live: OG 5, Twitter 3, JSON-LD 1), found during the blog.conholdate.cloud session: language-switcher div ends `<head>` before them, as on blog.aspose.com; our `head_closed_early` does not cover these tags | Proposed: same head-order fix as blog.conholdate.cloud F1 (fold into B3) |

## Scan 13 Nov (all new checks of 12 Nov)

- Full cycle 8 min, all steps OK; clone at aff5ac2b. Runs: discovery 4, crawl 22, speed 24, AI 23, text 25, links 26,
  repo 27. Crawl: rotating sample (53,736 sitemap URLs; 83 checked over 4 runs, 26 rechecked).
- **Health 65 → 58** (31 open issue types); the drop comes from new checks, not from new damage. Biggest losses: broken links 10,
  untranslated home descriptions 5 (ar/ko/id keep the English one), tag/search pages without text 5, robots-blocked
  sitemap URLs 5, "Conholdate.Totals" H1 typo in ru/de 5, tag pages in sitemaps 4.9.
- New: OG/Twitter/JSON-LD in `<body>` (crawl-261113-1, ~14k pages), duplicate descriptions (tag pages reuse the home
  description), 198 untranslated, 1,802 + 5,078 post lengths, 3,638 stale, 17 section indexes, 5 language names,
  2 RTL, 3 menu ids, slash 302. All spot-checked: real.
- Snapshot: live page archived first as 2026-11-13, new one 2026-11-13-2.
- Our audit gap: `slash_redirect_temporary` has no scorecard group (shows its check name as group); fix later.

## 18 Nov (evening): fix here, not retranslate (SK)

SK: fix here what can be fixed here; only articles that surely need it go to retranslation. The queue is being
rebuilt by SK (translation agent reset), so these fixes touch only translations that are up to date with their
English post (never a queued one: our commit would drop it from the queue).

| Commit (conholdate-blog) | What | State |
|---|---|---|
| 777e7263 | Batch 4: 493 links in 255 current translations to the translated post instead of the English one (14 posts Aug–Oct 2025 × 2 "See also" links × 17 languages, + convert-pptx-to-docx-java); live sample of new targets 40/40 200 | local, waits for SK's push + deploy |
| 1f806a91 | 7 values that were an LLM answer / garbage (ko dwf, html-to-bmp; tr stl, mpp + its seoTitle, xps; pl merge-pdf; nl 3mf description) replaced by a real translation (own commit, SK) | local, waits for SK's push + deploy |
| c49b7358 | 151 values left in English in 125 current translations (title 65, seoTitle 66, description 20) translated by hand in each language's style. Each file re-parsed: only those fields changed, lengths within 70/170 | local, waits for SK's push + deploy |

- Rescan before (repo + link runs 103/104): resolved `link_damaged`, `link_redirected`, `post_url_duplicate`. Left
  broken: 17 `link_broken` = view-stl-files-online translations (`find-synonym-in-java`), which are behind a real
  optimizer rewrite (seoTitle, description, summary, headings, Jun/Sep 2026); decide after the queue reset (fix the
  link + an ISSUE row).
- Outdated translations here: 3,767; English changes since: body > 20 lines 168 posts / 2,849 translations, 6–20
  lines 28 / 476, 1–5 lines or front matter only 26 / 442 (candidates to fix here), our fixes only 2 / 34.
- Not a defect: 5,855 translations in 395 posts carry the gist code inline (translated comments) instead of
  `{{< gist >}}`; the older pipeline's convention. The commit check's code-fence warning on such files is expected.
- Next found, not fixed: many translated titles are half English ("Convert LaTeX zu PDF in Java", id "Convert PUB
  ke Word…", pl "Convert LaTeX do PDF"); `post_text_untranslated` sees only exact English. Candidate check + fix.
- Retranslation candidates CSV: the 7 garbled rows are fixed here and no longer needed as ISSUE rows; the 4 queued
  garbled files and the 2 posts wait for the new queue.

## 18 Nov (later): queue model, Markdown in front matter, garbled translations

- **Queue model (SK):** the sheet holds only missing translations, optimizer-changed posts, our `AUDIT` records and
  the quality agent's; the scanner updates rows instead of rewriting; SK changes the translation agent himself.
  Everything else we fix in place (playbook, scan-sheet rules).
- **New check `post_front_matter_markup`** (rule TD-4): `**`, `__`, backticks, `[x](url)` in title, seoTitle,
  description, and summary **only when the post has no description**. Corrected the same day (SK asked for samples):
  the theme (PaperMod head.html, rss.xml) uses `description` for meta, Open Graph, JSON-LD and RSS and falls back to
  `.Summary` only without one; list cards render the summary as Markdown (blog.conholdate.cloud: `` `/cells` `` showed
  as `<code>`). First count 1,013 files / 230 posts (here) and 24 (blog.conholdate.cloud) was mostly harmless summaries;
  corrected: here 927 files, 206 posts, 78 English (all `description`); blog.conholdate.cloud 0. Live proof:
  `/id/total/how-to-convert-visio-to-pdf-in-java/` meta, og and JSON-LD description start with `**Ubah Visio…**`.
- d7387d38 (43 files, pushed by SK before the correction): 41 of its changes are such summaries (no visible effect,
  harmless), 2 descriptions real.
- **Fix 82e16439 (local, waits for SK's push; needs a deploy):** `**` out of the descriptions of 77 current
  translations whose English post is clean (nothing queued). YAML re-parsed per file, commit check PASSED.
  **Left: 78 English posts with `**` in the description**: the scanner (new version 9ce1431/b6b85e7) still counts
  every English commit as OUTDATED, so an English-only fix would queue their 961 clean current translations. Options
  for SK: English + all current translations in one commit (fix only where they have it, the rest stays untouched and
  becomes OUTDATED), or wait for an optimizer-only OUTDATED rule. Root cause in translations: 484 have `**` the English
  lacks (the LLM keeps or adds it; the translator has no front-matter markup guard).
- **New check `translation_text_garbled`** (rule TR-7): translated title/seoTitle/description with a line break the
  English lacks, a run of zero-width characters, or ≥ 6× the English width (real translations stay under 4×). Here 10
  files (7 Korean/Turkish/Polish titles that are the LLM's answer with steps or code, 1 one-sentence answer, 1 Dutch
  description of zero-width characters); found by hand: 1 more (tr XPS title, a one-line answer at 3×).
  blog.conholdate.cloud 0. Made 2025 by the older pipeline (farhan "translations"), 1 by the translation agent (Jan 2026).
  4 are already OUTDATED; all 11 + the 2 posts above are in `reports/conholdate.com/retranslate-candidates.csv`.
  The new agent (b6b85e7) takes them as `ISSUE` rows via `tools/translation_agent/queue_add.py --source "Health and
  Recovery Agent"` (dry run tested); 7 still need a row (column `queued_now` = no), SK runs it (write key).
  The translator (current version) has no guard for this: `_fit_length` would shorten such a title, not reject it.

## 18 Nov: batch 3 verified; new check link_differs_from_original finds 2 posts

| Step | Commit (conholdate-blog) | State |
|---|---|---|
| Batch 3: th/tr/vi of extract-text-and-images-from-pdf, [27]/[28] as English (first draft duplicated jpg-text-scanner, corrected after SK's review) | f6ec92b6 | **live, verified 18 Nov** (agent-fixes row) |
| Both posts: retranslation instead of link patches (see below). English-only fixes: extract-text description/summary showed literal `**` in the live meta description; convert-webp-to-jpg 8 unused reference definitions (left from the QR code post it was copied from) | 3f942379 | **pushed** (on origin before the agent's 763d3601, 7e347952); today's scanner marks 17 + 17 translations OUTDATED; also in `retranslate-candidates.csv` in case the new scanner rule drops them |

- Found by the new link check (health-and-recovery 222e8c2): unused reference definitions skipped (4,082 here, 23 on
  blog.conholdate.cloud); `link_differs_from_original` (rule TR-6) = 34 links in these 2 posts, 0 on blog.conholdate.cloud.
- **Why the references differ (SK asked: English 28 references, 12 translations 27):** the translations are older
  copies. extract-text: ar, de, es, fr, id, it, ja, ko, nl, pt, ru, zh were made 2022 (de 6 Jul 2022); the English
  changed afterwards (15 May 2023 seoTitle, alt, 2 headings; 17 May 2023 second "See also" line [28]; Dec 2023 link
  fixes). th/tr/vi (Oct 2023) and fa/pl are current. convert-webp-to-jpg: 11 translations made 22 Jun 2023 10:15, the
  English fixed 48 min later (intro links, "See also", the copied "C# QR Code Detector library" sentence).
- First attempt patched only links (batch 3b and a webp link fix, local commits 2e0c77b5, 8c559c1e); SK: not a proper
  fix, the translations stay incomplete. Dropped unpushed; replaced by 3f942379 so the agent retranslates.
- The scanner missed both: the bulk commits (restructure Feb 2025, link prefixes May 2024) gave the translations newer
  dates than the English rewrites (gap SK accepted 17 Nov). `link_differs_from_original` catches some of these cases.
- Learned: an extra or missing reference in a translation usually means an outdated translation, not a link bug:
  compare the English history with the translation's creation date before patching (playbook).

## 17 Nov: B5 batches 1–2 pushed; shortcodes shown as text (found and fixed)

| Commit (conholdate-blog) | What | State |
|---|---|---|
| f7e49738 | Batch 1: 54 double-slash links (3 posts, English + 17) | pushed; deploy run by SK |
| 3e221884 | Batch 2: 64 links to wrong slugs (view-stl-files-online English only: its translations are queued) | pushed; needs a deploy |
| 5707bb85 | 11 shortcodes restored in 4 English posts (view-stl-files-online, convert-svg-to-jpg-png-csharp, convert-eml-to-pst-java, convert-image-to-html-csharp) | pushed; needs a deploy |

- Every link target checked before the push: file in the repo, 200 live, canonical = the link (SK asked).
- Shortcodes: the optimizer escaped `{{< >}}` to `{{&lt; &gt;}}` (261f41ee, 775963f0, Jun 2026); a hand fix
  (cd798646, 10 Jun) dropped `&lt;`/`&gt;`, so the pages printed `{{ gist … }}`: no cover image, no code examples.
  All 4 posts were queued for retranslation, which would have copied the damage into 68 pages. Restored lines are
  identical to the versions before the optimizer; Hugo 0.101 build: 0 raw shortcodes, images and gists render.
- New check `post_shortcode_as_text` (repo audit, rule TD-3) and `shortcode_as_text` (commit check, warn; only what
  a range adds). Commit check on cd798646 warns on all 11; dry run on blog.conholdate.com and blog.conholdate.cloud:
  0 after the fix. Tell the optimizer agent's owner: it escapes < and > inside shortcodes.
- The blog developer resolved both duplicate URLs (52d70c5a + f0826572, 947c4056).

## 17 Nov: B5 checked against the translation agent's queue

- The translation agent's scanner now queues **OUTDATED → Retranslate** (English `index.md` committed after the
  translation). Scan sheet tab blog.conholdate.com (read 17 Nov): 222 rows, all OUTDATED, 17 languages each,
  none started; mostly English "Optimized Blog Posts" edits of 2 Nov.
- Of the open B5 link issues, these are in translations queued for retranslation, so **we leave them alone**:
  238 wrong-language links (7 posts of Aug–Sep 2025: merge-docx-to-pdf-java, convert-pdf-to-grayscale-in-csharp,
  convert-xbrl-to-pdf-online, convert-txt-to-json-in-java, convert-xbrl-to-excel-in-csharp,
  convert-markdown-to-word-in-csharp, convert-pub-to-pptx-in-csharp) and 17 broken links in view-stl-files-online.
  view-stl-files-online's English post has the broken link (find-synonym-in-java): fix the English post only, before
  the retranslation runs, so the new translations copy the fixed link. Check after the retranslation that the links
  are localized.
- English posts with bad links that are not queued (damaged: 3, broken: 3): fix the English post and its
  translations in one commit, so the scanner does not queue a full retranslation.
- The extract-text-and-images-from-pdf post is not queued (bulk commits reset the dates; SK: accept that gap), so
  B5 batch 3 stays a link fix in th/tr/vi.
- Rule written to the playbook (Rules for every change on a blog repo).

## 17 Nov: link check shows origin and fixes (before B5)

- Report: a link the English post has and its translations copied is one entry ("The English post has this link;
  17 translations copied it"); a link only translations share is one entry too (SK).
- Broken links get a **suggested fix** when certain: one existing post with the same content words in order
  (filler words, plurals ignored), or, in a translation, the page the English post links; localized when the
  translation exists, else the English page with the missing translation named (SK's rule). All 81 here match the
  hand-made B5 table. Word order matters: the first version matched convert-pdf-to-word for convert-word-to-pdf.
- An old English slug in a translation follows its redirect: the 3 th/tr/vi links are now `link_redirected`
  (crawl-261117-1) with `/<lang>/total/jpg-text-scanner/`; intl-0002 shows resolved, noted as reclassified.
- **History for links only translations have** (SK): when did the English post get its current link (`git log -S`,
  following renames) vs when was the translation made? "The translation introduced this link" or "the English post
  got its link later: the translation is out of date". git blame was tried first and was wrong: an optimizer commit
  re-wrote identical lines, so blame dated the English link 2026 (8 false "out of date"). Results here: th/tr/vi old
  slug out of date (English fixed 2023-12-13, translated 2023-10-18); create-ms-PDF and all 40 English-link entries
  introduced by the translations. My earlier note blaming the 2024 prefix commit for create-ms-PDF was wrong
  (corrected in the Issue log).

## 16 Nov: S1–S3 verified live (SK deployed the same evening)

- Live: both posts 1 H1 (en, de, ja); Arabic heading `تثبيت C#:`; `/tag/image-extraction-api/` 200, old tag 404;
  header/menu translated (ja ホーム 検索 アーカイブ, ar الرئيسية بحث, fr Accueil Rechercher Archives, zh 首页 归档).
  3 agent-fix rows verified.
- Rescan: h1_multiple and text_typo resolved; post_url_duplicate open (2 URLs, waiting for the blog developer).
  **14 open issue types, health 85**; snapshot 2026-11-16 "Small fixes S1-S3 live; duplicate-URL and body-H1 checks".
- **Our audit fixed on the way** (both from the renamed tag): (1) the text check reads the newest crawl of each page,
  so a page that left the sample kept its typo finding forever: the crawl now rechecks the pages the last text
  check flagged (`text_issue_urls`; the text run stores `flagged`); (2) a rechecked page that no sitemap lists any
  more and answers 404 is no `http_error` (it was renamed or removed on purpose). The false http_error finding
  (crawl-261116-2) was never published and was deleted from the store (rule AUD-4; backup in the session scratchpad).

## 16 Nov: rescan + small fixes S1–S3 (pushed to `main` 16 Nov, f34e3da0)

- **Rescan** (full cycle 8 min, runs 8 and 59–64; clone still at dae84823, no blog commits since 13 Nov): same 15
  open issue types, health 85. Not snapshotted yet (nothing changed; snapshot after the fixes are live).
- **Fixes prepared** (3 commits on dae84823, each with the agent credit line):

| Step | Commit | What | Files |
|---|---|---|---|
| S1 One H1 per page | `002a0dcd` | `# Title` line repeating the title removed from 2 English posts (create-visio-diagram-in-csharp, insert-table-in-onenote-using-java; written that way in English, the translations copied it); Arabic `# التثبيت #:` (English "### C# Installation:", C# lost in translation) back to `### تثبيت C#:` | 37 |
| S2 Tag typo | `15837896` | "Image Extration API" → "Image Extraction API" (one post, 18 languages); tag pages are noindex, so no redirect | 18 |
| S3 Theme labels | `f34e3da0` | Header label "Home" per language (`languages.<lang>.params.label.text`); wrong menu names: ja 探す→検索, 記録→アーカイブ; fr Chercher→Rechercher, Archiver→Archives; pt Procurar→Pesquisar; nl Zoekopdracht→Zoeken; id Mencari→Cari; ar يبحث→بحث; fa جستجو کردن→جستجو; vi lưu trữ/thẻ capitalised; th คลังเก็บเอกสารสำคัญ→คลังบทความ; zh 档案→归档 | config.yml |

- **Tested:** full builds before/after with Hugo 0.101 + production config (both OK). Repo scan: no other body `# `
  headings. Every changed page differs only in header/menu, except: tag lists (renamed tag), reading time
  4 → 3 min on listings (OneNote post shorter), and the duplicate-URL pages below (not from these commits). Fixed
  posts have 1 H1 in all languages; header shows ホーム / الرئيسية / Accueil …; post links `/tag/image-extraction-api/`.
- **Disk:** two full builds need ~9 GB (4.6 GB each, tag pages 1.5 GB); the first attempt filled the disk. Trim
  `*/tag/*` from the old build before building the new one.
- **New finding (by hand): two URLs claimed by two posts each**, all 18 languages; Hugo publishes one of each pair,
  and which one can differ by language and build:

| URL | Posts | Live (English, 16 Nov) | Proposed |
|---|---|---|---|
| `/total/add-barcode-to-pdf-in-java/` | 2026-04-22 and 2026-05-08 (auto-merge 7afc0803), two different articles, same title | 05-08 | keep 05-08, delete 04-22 (SK decides: content removal) |
| `/total/convert-html-to-image-java/` | 2023-06-03 and 2024-06-03 (added fb943ef0 "Restructured category", 2025-02-11); English identical, translations from different runs | identical | delete the 2024 copy |

  **SK (16 Nov):** the blog developer checks both pairs (proposal: keep 05-08, delete 04-22; delete the 2024 copy);
  else we do it later as proposed.
- **New repo checks (rule AUD-3, built 16 Nov):** `post_url_duplicate` (broken; item per file, rule URL-3) and
  `post_body_h1` (improvable; `# ` or `<h1>` outside code, rule TD-2). Dry run: here 72 items (2 URLs × 18 languages
  × 2 posts) and 0 body H1s (S1); blog.conholdate.cloud 0 and 0. Only the current and already-fixed blogs are dry-run
  (SK, 16 Nov: waiting blogs get every check on their turn).
- **Also noted, not fixed:** Categories and Tags menu items link to the English `/categories/` and `/tags/` from
  every language.

## SK's decisions (13 Nov)

| # | Decision |
|---|---|
| B2 | ~~No redirects~~ → **redirects** old → new (SK, 13 Nov, after the agent flagged that a 404 loses the indexed URLs' signals; Google standard over our junk rule) |
| B1 + B2 | Prepare and test both commits, **show first**; push decided after review |
| B5 | Show the link fixes, fix together; **change the translation agent** where it caused them so it does not repeat; find an efficient approval flow (one review table per batch) |

## B7 + B8 + B9 + CB3 verified live (13 Nov evening)

- Deploys seen 17:39 (B7–B9) and ~21:15 (CB3, dae84823). Live: vi/th/tr menus; native language names; `dir=rtl`
  on ar/fa (styled Arabic page checked); home descriptions per language; section pages translated, x-default,
  then `noindex, follow` and out of the sitemaps (CB3); llms.txt per language as UTF-8. 7 agent-fix rows.
- Rescan: **health 72 → 85** (crawl 88, on-page 97, languages 89, AI 100; 15 open issue types; snapshot
  2026-11-13-5). A false `llms_txt_outdated` (our check cut RFC dates like "Thu, 25 Jan 2024" to "Thu, 25 Ja"
  and sorted them as newest) was fixed in `core/audit/repo.iso_date` and deleted from the store (backup in the
  session scratchpad), never published.
- New, real: 2 posts repeat their title as a `#` heading (h1_multiple); tag "image-extration-api" typo.
- Left: links (B5: 81 broken, 54 damaged, 374 wrong-language, 3 missing translation); lengths and stale or
  untranslated text (B10); sitemap duplicates (36); no-slash 302 (CDN); theme "Home" label in English.

## B7 + B8 + B9 prepared (13 Nov; local `main` of conholdate-blog, 5 commits, NOT pushed)

| Commit | Step | What |
|---|---|---|
| 2dfc443c | B7 | company menu ids vi, th, tr (CDN JSON exists for all three) |
| b4165b88 | B8 | native language names (日本語, 한국어, Nederlands, ไทย, Polski, Bahasa Indonesia, العربية); `rtl` for ar, fa |
| 2868d66e | B9 | home description per language (17 translations), English one 190 → 152 characters |
| 2fb622ec | B9 | `_index.<lang>.md` for 17 languages: section title "Conholdate.Total Articles" + translations (was "Conholdate.Totals" / the home title), own description |
| 23831516 | B9 | llms.txt generated at build (newest 100 of 561 posts per language), `*.txt` as UTF-8 (production + staging) |

Build before/after (Hugo 0.101): only llms.txt files added (18); no SEO tag in `<body>`; x-default 55,405 → 56,374
pages (section pages now linked); vi menu `conholdate-en` → `conholdate-vi`, de unchanged (language params merge);
`dir=rtl` on ar/fa; all llms.txt links exist; commit check PASSED. Arabic styled layout to check live after deploy.
Gotchas: the config edit kept LF; a shell `printf` doubled the regex backslashes (fixed; pattern verified).
Carry-back items for blog.conholdate.cloud are in its log (CB1–CB5).

## B3 + B4 verified live (13 Nov, deploy seen 15:53)

- Live: OG/Twitter/JSON-LD in `<head>`, 0 SEO tags in `<body>`; x-default on translated pages (562 in the English
  sitemap); tags, `/search/`, `/archives/`, listing pages 2+ `noindex, follow` (page 2+ canonical to itself);
  posts and home unchanged; robots.txt no longer blocks tags; English sitemap 563 URLs, 0 tag URLs. 4 agent-fix rows.
- Rescan: resolved social_tags_in_body, sitemap_lists_tag_pages, tag_pages_thin, robots_blocked,
  content_needs_js, description_duplicate. **Health 58 → 72** (snapshot 2026-11-13-4; areas: crawl 88, on-page 92,
  languages 84, AI 98).
- Our audit (AUD-3): listing page 2 sampled per blog (`audit.extra_urls`; same problem on aspose.com,
  groupdocs.com, aspose.cloud, groupdocs.cloud); `noindex` check only on sitemap pages and homepages; duplicates
  and hreflang checks skip noindex pages (Google ignores them). A false `hreflang_no_self` on page 2 was deleted
  from the store (backup in the session scratchpad), never published.
- Still open: x-default on 17 English-only section pages (`_index.<lang>.md` needed); `/conholdate.total/` titled
  "Conholdate Blog" like the home; home description English on ar/ko/id; broken links (−10); the rest of B5–B10.

## B3 + B4 prepared (13 Nov; local `main` of conholdate-blog, 4 commits ahead of origin, NOT pushed)

| Commit | What |
|---|---|
| 8a19c164 | B3: `extend_head` last in `head.html` (OG/Twitter/JSON-LD were in `<body>` on 56,721 pages) |
| b0f37c45 | B3: x-default hreflang in `head.html` and the sitemap template (English as fallback) |
| 70c32c62 | B4: tag pages, `/search/`, `/archives/` `noindex, follow`; sitemap filter `/tag/` (was `/tags`, so 43,602 tag URLs were listed), search/archives out; `Disallow: /tag/`, `/tags/` removed from robots.txt |
| 0cb83582 | B4: listing pages 2+ (home, section) `noindex, follow`, canonical to themselves (was page 1); same `.Paginate` input as `list.html` |

Full build before/after (Hugo 0.101, production config, 100,616 pages): robots changed only on 43,728 tag pages, 36
search/archives, 2,016 listing pages 2+; SEO tags in `<body>` 56,721 → 0; x-default 0 → 55,405 pages (every
translated page); sitemaps per language ~3,000 → 563 URLs, tag URLs 45,595 → 0; home canonical unchanged; page 2
canonical `/page/2/`, `/fr/page/2/`. Gotcha: `head.html` has CRLF line endings; a Python text-mode edit rewrote
all 341 lines (undone; edits now keep line endings).

## B1 + B2 verified live (13 Nov, after SK's deploy)

- Pushed by the agent on SK's "push" (e0e0fe53 on `main`), deployed by SK (Deploy Production - AWS).
- Live: 15 French posts 200 at `/fr/<English url>/` (French sitemap lists only the new URLs); 15 old French-slug
  keys + 12 retargeted keys (10 dated, 2 restored dated) 301 to the new URLs; `/feed/` → `/index.xml`; 60 of 62
  removed keys 404. The other 2, `/page/18/` and `/page/19/`, are real Hugo listing pages that the old redirects
  hid; they now answer 200 (`index, follow`), and B4 makes page 2+ `noindex, follow`.
- Check script: urllib needs certifi's CA bundle on this Mac (SSL verify error otherwise); curl works.
- 2 agent-fixes rows (redirect_key_malformed, translated_url_mismatch), verified 13 Nov.

## B1 + B2 prepared (13 Nov; local branch `hra/b1-b2` in conholdate-blog, NOT pushed, waiting for SK's review)

| Commit | What | Redirects.json |
|---|---|---|
| 2993d49c | B1a: 15 junk keys our check flagged (non-English slug, double slash, # fragment) | 1459 → 1444 |
| 940695cf | B1b (SK, 13 Nov, after selecting lines in the file): 6 upper-case copies of one URL + 43 keys that send to the home page (other sites' shop pages, scanners `/wp-admin`, `/login`, `*.iso`, `*.exe`, `/notify-one_deny?…`, removed 2019 WordPress posts, `/page/18/`); `/feed`, `/feed/`, `/feed.json` → `/index.xml` (live RSS, 200) | 1444 → 1395 |
| 24babc50 | B2: `url:` of 15 French files → `/fr/<English url>/`; 10 dated `/fr/YYYY/MM/DD/` keys retargeted to the new URLs (their old targets would 404). No redirects for the old French-slug URLs (SK) | 1395 |

| e0e0fe53 | 15 old `/fr/total/<French slug>/` URLs + 2 old dated French URLs of the same posts (removed in 2993d49c although they answered 301; flagged by the agent) → new URLs, keys percent-encoded (tested live: encoded non-ASCII keys answer 301 here); `Redirects.md` documents rules and groups (JSON has no comments; a "comment" key would be read as a redirect) | 1395 → 1412 |

SK reviews and pushes himself (13 Nov). Our audit: reviewed keep-list `audit.repo.redirect_keep` in the tenant YAML
(17 keys) so these are not junk; rule RED-1 exception.

Tests: commit check with Hugo 0.101 PASSED (only the known OG/Twitter-in-body warning, B3); full builds before/after
(100,533 pages): only the 15 French post folders moved (73 files), sitemaps change only in `/fr/total/` lines (the
French alternate), canonical and hreflang of the moved pages and the German alternate point at the new URLs. Kept:
`/about` → `about.conholdate.com` (another site, a real redirect). After deploy: new URLs 200, old French URLs 404,
removed keys 404, `/feed/` → `/index.xml`.

Our audit (9c5565a): junk rule RED-1 widened (query string, upper-case copy, redirect to the blog's own home page);
branch has 0 junk. blog.conholdate.cloud's `/feed/` → home is now flagged too (retarget to `/index.xml`, small fix).

**B5 attribution (SK, 13 Nov):** of 77 broken links in translations, 34 already exist in the English original
(inherited; fix English first), 43 are translation-only; 51 damaged links are translation-only. Many translation-only
ones come from a 2024 bulk commit "Internal links prefixes updated", not the translation agent. Wrong-language links
now count 731 (links; 374 on 11 Nov was pages; check in B5).

## Waiting for SK (paused 11 Nov; answered 13 Nov, see above)

| # | Decision | Recommendation given |
|---|---|---|
| 1 | B2: redirect the 15 old French URLs to the corrected ones? | **No redirects**: the 15 pages earned 8 clicks / 1,838 impressions in 16 months; redirects would add 15 non-English keys, which SK's rule calls junk (our check would flag them) |
| 2 | Make B1 (15 junk entries out, 1,459 → 1,444) and B2 (one `url:` line in 15 French files) in two commits, push to `main`, then SK runs Deploy Production - AWS | Yes, both in one go, one deploy |
| 3 | B5 link fixes (374 wrong-language, 81 broken, 54 damaged, 20 missing translations): by the agent directly, or by SK's translation agent? | Agent for the mechanical ones (wrong-language, damaged), each batch approved; translation agent for anything needing translation |

Before pushing B1/B2: commit check with Hugo 0.101 (`--base 9cc26f48`), a sample build showing a French page at its new
URL; after the deploy: new URLs 200, old ones 404; the link check then lists internal links to the old French URLs (B5).

## Next session (SK, 12 Nov: continue here on 13 Nov)

1. **Full scan first** with everything built on 12 Nov (new repo checks, crawl checks for untranslated titles,
   rotating sample + recheck + coverage line): `caffeinate -i .venv/bin/python scripts/run_cycle.py conholdate.com`
   (~6 min on 11 Nov; more now: the repo check reads 10,000+ files), review, snapshot. Expect health to drop: the
   12 Nov dry run found 5,070 + 1,802 lengths, 3,638 stale, 198 untranslated, 17 section indexes, 5 language names,
   2 RTL, 3 menu ids.
2. **Decisions to ask SK first:** B2 redirects (recommended: no); B5 who fixes links (recommended: the agent for
   wrong-language and damaged links, the translation agent for anything needing translation).
3. **Order proposed:** B1 + B2 (one deploy; note: Redirects.json applies only at deploy here) → B3 + B7–B9
   (config/templates, one deploy) → B4 → B6 → B5 and B10 in batches → C.
4. Carry over from blog.conholdate.cloud (playbook fix catalogue rows 1–15; commits there F1–F22): head order,
   x-default, tag noindex, utility pages noindex, home title/description per language (+ `params.siteName` and the
   opengraph override), RTL, language names, company menu ids, llms.txt generated at build + `.txt` as UTF-8
   (deployment matcher; hugo deploy re-uploads only changed files), README for new developers.

## Plan (agreed 11 Nov; B7–B10 added 12 Nov)

| Step | What | State |
|---|---|---|
| A1–A5 | Scan improvements: ids with dates, junk redirect warning, translated-URL check, tag findings, Hugo version per blog | Done 11 Nov |
| A6 | Full scan as the new starting point | Done 11 Nov 14:50–14:56 (runs 3, 16–21); health 70 → 65 from the new checks (19 issue types, 952 open items); snapshot 2026-11-11-2 |
| B1 | Junk redirect entries out | Waiting (approval) |
| B2 | 15 translated URLs back + redirects | Waiting |
| B3 | hreflang x-default | Waiting |
| B4 | Tag + pagination pilot | Waiting |
| B5 | Link fixes | Waiting (SK: agent directly or translation agent) |
| B6 | Commit check on conholdate-blog + workflows | Waiting |
| B7 | Company menu ids for vi, th, tr (English bar today; `menu_id_missing`) | New 12 Nov |
| B8 | Language names (ja 日本, ko 한국인, nl "Dutch", …) and RTL for ar, fa | New 12 Nov |
| B9 | Home title/description per language; llms.txt generated at build; `.txt` served as UTF-8; README | New 12 Nov |
| B10 | Titles/descriptions out of range (6,872), stale translations (3,638), English text in translations (198) | New 12 Nov; batches, partly the translation agent (which now keeps lengths itself) |
| C | Re-scan, fix progress, snapshot | After B |

## Carry over from blog.conholdate.cloud (same theme; fixed there 11 Nov, 84 → 100)

Playbook fix catalogue rows; check each here before B3/B4. Facts seen from the blog.conholdate.cloud session:

| Catalogue row | Here | Suggested step |
|---|---|---|
| 1 head order | **Present**: home page OG 5, Twitter 3, JSON-LD 1 in `<body>` (11 Nov) | B3 (same file as x-default) |
| 2 x-default | Missing (14,072 pages); also check sections with `_index.md` in English only | B3 |
| 3 thin tags | 93% single-post tags, 43,584 tag URLs in sitemaps, `Disallow: /tag/` | B4 (noindex, follow + robots + sitemap) |
| 4 search/archives | Not checked yet: `live_head.py https://blog.conholdate.com/search/` | B3/B4 |
| 5 title/description length | **6,872 values out of range** (`front_matter_set.py <repo> --scan`, 11 Nov) | Own step after B; big, by template where possible |
| 6 home H1 | Not checked yet | After SK sees blog.conholdate.cloud's result |
| 7 llms.txt | Not checked yet | Small |
| 9 mainSections / stray categories | Not checked yet | With B4 |
| 11 language names | **5 wrong** (ja 日本, ko 한국인, nl "Dutch", …; repo check 12 Nov, dry run) | Small |
| 15 company menu id | **vi, th, tr have no `dynamicmenuid`**: the English company bar shows on those pages (repo check `menu_id_missing`, 12 Nov) | Small config fix (check the menu service has conholdate/vi, th, tr) |
| new 12 Nov | Dry run of the new repo checks: **3,638 stale translations** (English titles rewritten by the Blog Optimization Agent, Mar 2026), 239 translations with English text, 17 section `_index` missing per language, 1,802 titles + 5,070 descriptions out of range, ar/fa without RTL, no-slash 302 | Next full scan records them |

## Scan 11 Nov (after A1–A5)

| Check | Result |
|---|---|
| Junk redirect entries | 15: 11 non-English slugs (old French/Japanese/Chinese URLs, an Arabic Amazon path, an en dash), 3 double slashes, 1 fragment |
| Translated URLs (intl-261111-1) | 15, all **French** posts from 2020–2022 with a French slug (e.g. `/fr/total/rechercher-un-mot-dans-pdf-en-utilisant-java/`); these 15 URLs earned 8 clicks, 1,838 impressions in 16 months |
| Tag findings | crawl-261111-1 Thin tag pages (93% single-post tags), crawl-261111-2 Sitemaps list tag pages (43,584; score 16) |
| Live redirect sample | 40 of 40 redirect |

## Learned here

- A first search for gists with `\s` in `git grep -E` found none: git grep's regex has no `\s`. Use a plain string (`-F '{{< gist'`).
- Test template changes with the deploy's Hugo version (0.101.0 here), not the local 0.120.
- The double-slash rule in our repo check was wrong (such keys redirect): found by testing the "dead" entries live before proposing to remove them.
