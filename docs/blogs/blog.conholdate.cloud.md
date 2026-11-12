# blog.conholdate.cloud: log

Scanned and fixed on **11 Nov 2026** (one session): health **86 → 84** (new checks) **→ 94 → 100**, 0 open findings,
14 blog commits, 11 rows in `reports/conholdate.cloud/agent-fixes.json`. Steps: [../playbook.md](../playbook.md);
the reusable fixes from here are the playbook's **fix catalogue**.

## Facts (confirmed 11 Nov 2026)

| Item | Value |
|---|---|
| Source repo | `conholdate-cloud/blog.conholdate.cloud`, branch **main**; clone `/Users/Apple/Work/Aspose/GitHub/blog.conholdate.cloud-PROD/blog.conholdate.cloud` |
| Workflows | In the blog repo: `.github/workflows/production-aws.yml`, `production-ceph.yml` (+ staging). Build: `hugo --config "config.yml,config-production.yml" --minify` |
| Production deploy | cron `0 3 * * 1-5` = 08:00 PKT Mon–Fri (the comment's 10–11 AM is wrong), skipped without new commits; SK runs "Deploy Production - AWS" by hand for same-day fixes |
| Hugo | **0.101.0** extended (`/Users/Apple/Downloads/Softwares/Hugo/hugo_extended_0.101.0_darwin-amd64/hugo`) |
| Redirects.json | **Applies live** (~2 min after a push, no deploy). CloudFront caches redirect answers (query string not in the cache key). 3 entries now: `/tag/`, `/category/`, `/feed/` |
| Redirect behaviour | Keys match exactly; the host forwards no-slash → slash with a **302** only for real folders (should be 301; CDN setting, not changed) |
| Content | 5 English posts in `content/Conholdate.Cloud/total/` (`mainSections: [Conholdate.Cloud]`), 4 translated into 22 languages, the Java merge post (Mar 2026) English only; 93 post files |
| Taxonomies | tag pages `/tag/<name>/` (`permalinks: tags: /tag/:title/`), list `/tags/`; one category "Conholdate.Total Cloud Product Family" |
| Theme | PaperMod (as blog.conholdate.com); custom CSS in `assets/css/extended/custom.css` |
| Traffic | Jul 2025 – Nov 2026: 14 clicks, 1,307 impressions (home 350); 28 days to 8 Nov: 2 clicks, 173 impressions |

## Fixes (all verified live 11 Nov unless noted)

| # | Problem | Fix | Commit(s) |
|---|---|---|---|
| F1 | OG, Twitter, JSON-LD in `<body>` on every page (switcher `<div>` mid-`<head>`) | `extend_head.html` last in `head.html` | d194619 |
| F2 | No x-default | x-default in `head.html` and `sitemap.xml`; `_index.<lang>.md` for the section so its 23 versions link (they were unlinked, titled "Conholdate.Clouds") | d194619, f414aef |
| F3 | 27 single-post tags → 578 thin tag pages competing with posts | tag pages `noindex, follow`; `Disallow: /tags/`, `/tag/` removed from robots.txt | 70cb21f |
| F4 | 4 wrong-language links in 3 Arabic posts (2025-08-12 commit) | → `/ar/…` (SK: fix from here) | bbe3a99 |
| F5 | Redirects.json WordPress-template leftovers; `/category/` 404 | SK's set: `/tag/`, `/category/`, `/feed/` | 9a5a07c |
| F6 | Two categories for one family (4 + 1 posts) | all 92 files → "Conholdate.Total Cloud Product Family" (SK: the real family) | bbe3a99 |
| F7 | Java post in `content/Conholdate.Total/` (outside `mainSections`: never on the home page); empty stray category page | moved into `content/Conholdate.Cloud/total/` (URL unchanged); stray `_index.md` deleted (SK) | 0804d88 |
| F8 | No H1 on the 23 home pages | PaperMod `homeInfoParams` per language: "Conholdate Cloud Blog" + "Articles on Conholdate.Total Cloud REST APIs and SDKs: …" (SK: "Articles", not "Tutorials"; brand without the dot); compact CSS (SK: the theme's hero took too much room); translations by Claude (SK) | a7d6751, 62d8a5b, d0a4811 |
| F9 | `/search/`, `/archives/` indexable (thin; one-word titles/descriptions; "text needs JavaScript") | `noindex, follow`, out of the sitemaps (46 pages) | bc3530d |
| F10 | 19 titles > 70, 26 descriptions > 170; Excel translations stale (English rewritten Jul 2026) | 66 values in 43 files (`scripts/ops/front_matter_set.py` pattern); all posts in range | 16b6a14 |
| F11 | No llms.txt | `static/llms.txt`: summary, 5 articles, 23 languages, sitemap, category (SK reworded "Product Family") | 4cf4ed8, f672a2f, 05b9fb5 |
| F12 | Language menu names wrong (日本 "Japan", 한국인 "a Korean person", 中國傳統的 garbled; id/nl/th in English; he with vowel marks) | native names in `config.yml` | 6217d42 |

Every template/content change was tested before the push: full Hugo 0.101 build with the production config before
and after (`scripts/ops/build_diff.py`), `commit_check.py` PASSED, screenshots desktop + 390 px for layout changes,
`scripts/ops/live_head.py` after each deploy.

## Scans

| When | Runs | Health (crawl / on-page / languages / AI) | Note |
|---|---|---|---|
| 7 Nov | discovery 4, crawl 10 … | 86 | before the 11 Nov checks |
| 11 Nov 16:56 | 5, 16–21 | 84 (98 / 98 / 93 / 95) | new `tag_pages_thin`; snapshot 2026-11-11 |
| 11 Nov 18:39 (after deploy 1) | 6, 22–27 | 94 | thin tags, links, H1 resolved |
| 11 Nov (after deploy 2) | 7, 28–33 | 94 (100 / 99 / 100 / 95) | x-default resolved; snapshot "Fixes live: …" |
| 11 Nov (after deploy 3) | 8, 34–39 | **100** (all 100) | 0 open; snapshot "Health 100: …"; speed not scored (no real-user data) |

## 12 Nov: audit of the auditors, rescan (health 100 → 94, all real)

SK: "audit our auditors and improve them". Every problem found by hand on 11 Nov became a check; the rescan then
found problems nobody had seen.

| New in our audit | Found here |
|---|---|
| Full crawl of hosts with ≤ 500 sitemap URLs (139 of 139 pages, was ~15 sampled) | Text check saw every page → the next row |
| Crawl `title_untranslated` / `description_untranslated` | **22 translated home pages keep the English `<title>` and description** (config sets them once); de section page description; vi post title |
| Repo `post_text_untranslated` (every translation file) | 4 files: vi seoTitle (PDF), vi title (Excel), ar title (HTML), fr description (HTML) |
| Repo `rtl_direction_missing` | ar, fa, he without `languageDirection: rtl` (`dir=auto` live) |
| Repo `slash_redirect_temporary` (live) | no-slash URLs answer 302 (CDN) |
| LLM text check (now on all pages) | he H1 " manipulat גליונות…", it H1 "Manipula" (→ "Manipola") |
| Repo `post_title_length`, `post_description_length`, `post_outside_main_sections`, `translation_stale`, `section_index_untranslated`, `language_name_wrong`, `category_page_unused` | 0 here (fixed 11 Nov: F2, F6, F7, F10, F12) |

Scan 12 Nov: discovery 9, crawl 58, AI 53, speed 54, text 55, links 56, repo 57; snapshot 2026-11-12. Open: 6
issue types, 9 items. The two LLM home-page answers ("a different product") are recorded as reviewed in the tenant
YAML: real, but counted by `title_untranslated`.

### Proposed fixes (need SK's approval per push)

| # | Fix | Where | Deploy |
|---|---|---|---|
| F13 | Home `<title>` + description per language (`languages.<lang>.title`, `.params.description`), 22 languages | config.yml | yes |
| F14 | Translate 4 front-matter values; he and it H1 typos | 6 post files | yes |
| F15 | `languageDirection: rtl` for ar, fa, he; check PaperMod's RTL layout (screenshots) | config.yml | yes |
| F16 | 301 instead of 302 for no-slash URLs | CloudFront (not the repo) | infra |

SK approved F13–F15 (12 Nov); SK pushed and deployed them the same day, **verified live** (agent-fixes rows 12–14): 8b0b5e7 (F14), 5ec2890 (F13: also
`params.siteName` + `layouts/partials/templates/opengraph.html`, because Hugo 0.101 copies a language-level `title`
into `params.title`, which PaperMod uses for og:site_name), 21c9347 (F15). Tested: full build before/after (no English
page changed, sitemaps same URLs/hreflang), commit check PASSED (835 pages), RTL screenshots desktop + 390 px.
Seen while testing, not fixed: English H2s in translated post bodies ("Convert HTML to DOCX" on /ar/), header label
"Home" in English on every language.

Our audit, same day: the untranslated checks follow the translation agent's rules (`core/audit/keep_terms.py`:
product/brand names by shape, formats, abbreviations, platforms, code, URLs, the host's labels do not count);
blog.conholdate.com 239 → 198. The no-slash finding now shows the URL to try (curl -I), not a "file".

Rescan after the deploy (12 Nov): **health 100**, 1 open issue type: no-slash 302 (F16, CDN, 2 items, improvable).
One more LLM false positive recorded as reviewed (/fr/ home title and description = tagline, not "a different
product"). Snapshot 2026-11-12-2. Full-crawl limit raised to 1,000 URLs (SK).

## 12 Nov, later: company menu bar, new translations

| # | Problem | Fix / state |
|---|---|---|
| F17 | **No company bar on /zh-hant/** (SK spotted): `params.dynamicmenuid.zh-hant: conholdatecloud-zh-hant`; the menu script (menucdn.containerize.com/core/engine.min.js) splits the id on `-` and accepts exactly two parts, so it drew nothing. The service has Traditional Chinese as `zht` | `conholdatecloud-zht`; blog commit **39f62ad, pushed and deployed 12 Nov, verified live** (bar in Traditional Chinese); tested with a local Hugo 0.101 build: bar renders in Traditional Chinese; commit check PASSED. New repo check `menu_id_invalid` (51b22b2). he/nl/sv have no menu JSON on the CDN but render through the service's API fallback (fine) |
| F18 | SK's translation agent added the Java post's 22 translations (1244f92, 12 Nov 09:50 UTC): **9 titles and 9 descriptions too long** (": Schritt-für-Schritt-Anleitung" etc.) | SK: fix now and update the agent. Blog commit **98431b5** (18 values), deployed and verified live; translation agent 423a608 (length limits) pushed to GitHub |
| F19 | `static/llms.txt` still says the Java post is "English only" | Blog commit **50ce0eb**, deployed and verified live |

Rescan after the deploy (12 Nov, evening): discovery 11, crawl 72 (161 pages, every sitemap URL; +22 Java
translations), AI 73, speed 74, text 75, links 76 (207 links), repo 78: **health 100**, open only F16 (no-slash 302,
CDN). 17 agent-fix rows, all verified; F17 found by Shoaib Khan (`found_by`). Snapshot 2026-11-12-3.

| F20 | llms.txt hand-made, stale within a day (SK: "LLM.txt update task would be regular") | **Generated at build**: output format `llms` + `layouts/index.llms.txt`, `static/llms.txt` removed; blog commit **7bf0f7b, committed, not pushed**; build before/after: only llms.txt (+22 language files) changed, all links exist; commit check PASSED. Audit guard `llms_txt_outdated` (6f910c0) |

## Decisions by SK (11 Nov)

- Thin tags: an issue only if posts could share better tags; with 5 posts they cannot → noindex (F3); retag later.
- Redirects: keep `/tag/`, `/category/`, `/feed/` ("no-slash may auto-forward": only true for real folders).
- x-default: keep (states the fallback Google would mostly guess).
- Category: "Conholdate.Total Cloud Product Family" is the real family. All posts in one folder.
- Home H1: pilot here; "Articles", "Conholdate Cloud"; compact; translations by Claude.
- Target 100 "in sight of Google as well": real fixes only, no audit rule relaxed for the score.
- llms.txt: list all languages. Language names: fix in config.

## Our audit, changed because of this blog

| Change | Commit |
|---|---|
| New crawl check `social_tags_in_body` (not optimized; score group "head order" with `head_closed_early`; fix guide entry; commit check warns `social_tag_in_body`) | 7694323 |
| `tag_pages_thin` not raised when `/tags/` and 2 tag pages answer noindex (read live, robots.txt respected) | 7694323 |
| `commit_check.py` reports only shortcode damage a range adds (it blamed old `=\"` in commented-out figures of 38 translations) | 66280a2 |
| Helpers: `scripts/ops/live_head.py`, `build_diff.py`, `front_matter_set.py` | this session |

## Open (not done)

- Retag posts to 2–3 broad tags (SK: later; tag pages are noindex meanwhile).
- The Java merge post has no translations (SK's translation agent).
- Arabic, Persian, Hebrew pages render left-to-right: now a check (`rtl_direction_missing`), fix F15 proposed.
- Host forwards no-slash → slash with 302 instead of 301 (CDN).

## Learned here

- Same theme as blog.conholdate.com: F1–F3, F8, F9 carry over (blog.conholdate.com has the F1 bug: OG 5, Twitter 3,
  JSON-LD 1 in `<body>` on its home page; 6,872 titles/descriptions out of range by `front_matter_set.py --scan`).
- Look past the sampled pages: the crawl showed 2 long titles, the repo had 45; the x-default gap hid in
  auto-generated section pages; a post outside `mainSections` never reached the home page.
- Translations drift: an English title rewritten later leaves 22 stale translated titles.
- Utility pages (search, archives) cost more than they bring: noindex and out of the sitemap.
