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

## SK's decisions (13 Nov)

| # | Decision |
|---|---|
| B2 | **No redirects** for the 15 old French URLs |
| B1 + B2 | Prepare and test both commits, **show first**; push decided after review |
| B5 | Show the link fixes, fix together; **change the translation agent** where it caused them so it does not repeat; find an efficient approval flow (one review table per batch) |

## B1 + B2 prepared (13 Nov; local branch `hra/b1-b2` in conholdate-blog, NOT pushed, waiting for SK's review)

| Commit | What | Redirects.json |
|---|---|---|
| 2993d49c | B1a: 15 junk keys our check flagged (non-English slug, double slash, # fragment) | 1459 → 1444 |
| 940695cf | B1b (SK, 13 Nov, after selecting lines in the file): 6 upper-case copies of one URL + 43 keys that send to the home page (other sites' shop pages, scanners `/wp-admin`, `/login`, `*.iso`, `*.exe`, `/notify-one_deny?…`, removed 2019 WordPress posts, `/page/18/`); `/feed`, `/feed/`, `/feed.json` → `/index.xml` (live RSS, 200) | 1444 → 1395 |
| 24babc50 | B2: `url:` of 15 French files → `/fr/<English url>/`; 10 dated `/fr/YYYY/MM/DD/` keys retargeted to the new URLs (their old targets would 404). No redirects for the old French-slug URLs (SK) | 1395 |

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
