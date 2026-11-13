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
