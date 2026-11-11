# blog.conholdate.cloud: log

Next blog in the "scan and fix" program (SK, 2026-11-11: the smallest site, in a separate session, after
blog.conholdate.com's plan was set). Steps: [../playbook.md](../playbook.md). Updated in the same session as every
finding, decision, fix and check.

## Facts (collected 11 Nov 2026; confirm at the start of the session)

| Item | Value |
|---|---|
| Source repo | `conholdate-cloud/blog.conholdate.cloud`, branch **main**; local clone `/Users/Apple/Work/Aspose/GitHub/blog.conholdate.cloud-PROD/blog.conholdate.cloud` (clean, at `d2bc592` 4 Nov) |
| Workflows | **In the blog repo itself**: `.github/workflows/production-aws.yml`, `production-ceph.yml` (+ staging). So the commit check's push check and deploy gate would both live in this one repo |
| Production deploy | cron `0 3 * * 1-5` = **08:00 PKT** Mon–Fri (comment says 10–11 AM: wrong, as on blog.conholdate.com), skipped without new commits (`check-changes`); manual run from the Actions tab |
| Hugo | **0.101.0** extended (`/Users/Apple/Downloads/Softwares/Hugo/hugo_extended_0.101.0_darwin-amd64/hugo`) |
| Redirects.json | 4 entries (`/tag/`, `/category`, `/feed`, `/feed/`), all 301 live (checked 11 Nov). Live or at deploy: still unknown (needs a change to test; blog.conholdate.com applies at deploy) |
| Taxonomy URLs | term pages `/tag/<name>/` (`permalinks: tags: /tag/:title/`), list `/tags/`; categories `/categories/<x>/` (2) |
| Head order (11 Nov) | Same bug shape as blog.aspose.com: `extend_head.html` (renders the `langswitcher.html` div when translated, i.e. on every page) sits before Open Graph, Twitter and JSON-LD, so those land in `<body>` live (title, canonical, hreflang, robots come before it: fine). blog.conholdate.com has it too (home: OG 5, Twitter 3, JSON-LD 1 in `<body>`) |
| Size (7 Nov) | 5 English posts, 93 post files, 23 languages, 27 tags (all single-post), 186 sitemap URLs, no tag URLs in sitemaps |
| Traffic (28 days to 3 Nov) | 2 clicks, 161 impressions |
| Health (7 Nov) | 86; 7 issue types, 4 open items |
| Theme | PaperMod (like blog.conholdate.com) |

## Open findings at the last scan (7 Nov, before the 11 Nov scan improvements)

| Id | Check | Severity |
|---|---|---|
| intl-0002 | Posts link to another language although a translation exists (4 links, 3 Arabic posts, from a 2025-08-12 commit) | incorrect |
| ai-0001 | Pages show almost no text without JavaScript (listing/category pages) | incorrect |
| intl-0001 | hreflang without x-default | improvable |
| onpage-0001 / 0003 | Description / title length | improvable |
| onpage-0002 | Pages without H1 | improvable |
| ai-0002 | No llms.txt | improvable |

## Plan for the session

1. Confirm the facts above; test whether Redirects.json applies live or at deploy (one harmless check: curl an entry).
2. Full scan with the new checks: `caffeinate -i .venv/bin/python scripts/run_cycle.py conholdate.cloud` (~2 min).
   New checks since the last scan: junk redirect entries, translated URLs, thin tag pages (27 of 27 tags single-post:
   expect a finding), tag pages in sitemaps (none expected).
3. Review, snapshot ("Full scan with the new checks"), update this log.
4. Propose fixes in the playbook order (smallest first), each push approved by SK: the 4 wrong-language links,
   hreflang x-default, tags, then others. Template fixes found here can carry over to blog.conholdate.com (same theme).
5. Verify live, agent-fixes table (`reports/conholdate.cloud/agent-fixes.json`), re-scan, snapshot, push.

## Scan 11 Nov 2026 (full, runs 5, 16–21; snapshot 2026-11-11; our commit 7c42489)

Health 86 → 84 (crawl 100 → 98) from the new `tag_pages_thin` finding (crawl-261111-1: 27 of 27 tags single-post,
555 tag pages in 23 languages, 0 clicks, 30 impressions). Repo file check clean (no junk keys, no translated-URL
mismatches). Open: llms.txt missing, no x-default (186), no H1 (23 home pages), content needs JS (29 listing pages),
thin tags, 4 wrong-language links (unchanged), title/description length. No page 2 (5 posts, paginate 10).

**Audit gap found:** `head_closed_early` checks only tags that come before the div (title, canonical, hreflang …),
so Open Graph / Twitter / JSON-LD in `<body>` went unreported here and on blog.conholdate.com.

**Oddity (not fixed):** `/<lang>/conholdate.cloud/` section pages (22 languages) have no English translation linked,
so they get no `en` hreflang and no x-default.

## Tags and Redirects.json reviewed (SK's questions, 11 Nov)

- **Tags:** 5 English posts (3 PDF, 1 HTML, 1 Excel), 27 tags, each on one post; tags are copied unchanged into
  every translation. Best possible sharing: "PDF" 3 posts, "Conversion" 3, the rest 1, and a tag on all 5 would just
  repeat the home page. Search Console since Jul 2025: tag pages 1 click, ~150 impressions, mostly position 30–110,
  and they compete with the posts (e.g. `/sv/tag/html-to-jpg/` 35 impressions at 15 vs its post 1). Two categories
  mean the same thing: "Conholdate.Total Product Family" (4 posts) and "Conholdate.Total Cloud Product Family" (1).
- **Redirects.json:** all 4 entries came with the initial commit (b6056d6, 2025-07-14), copied from a WordPress-era
  template; this blog has been Hugo since launch. No internal links to `/tag/`, `/category`, `/feed`; no Search
  Console page for them since Jul 2025. `/tag/` has a purpose (term pages live at `/tag/<x>/`, the list at
  `/tags/`); `/category` and `/feed(/)` never existed here (and `/feed` sends a feed reader to an HTML page).
- **SK's decision (11 Nov):** keep `/tag/` → `/tags/`, `/category/` → `/categories/` (key gets the slash),
  `/feed/` → home; drop `/feed`. Live test: keys match exactly; the host forwards no-slash → slash (with a **302**,
  not 301) only for real folders (`/tags`, `/categories`, posts); `/tag` and `/category/` are 404 today. So `/feed`
  and `/category` will answer 404 after the change (never visited: fine). Prepared as F5 (JSON valid, 3 entries).
- Seen: the no-slash → slash forward on real folders is a 302 (temporary); a 301 would be right (host/CDN setting).
- Also seen: `/search/` and `/<lang>/archives/` get impressions (thin utility pages, for later).

## Fixes

| # | Fix | State |
|---|---|---|
| F1 | `head.html`: `extend_head.html` moved to the end of `<head>` (OG, Twitter, JSON-LD back in `<head>`) | pushed `d194619` 11 Nov, waiting for deploy |
| F2 | x-default hreflang (default language) in `head.html` and `sitemap.xml` | pushed `d194619`, waiting for deploy |
| F3 | Tag pages (`/tags/`, `/tag/<x>/`) `noindex, follow`; `Disallow: /tags/` and `/tag/` removed from robots.txt so the noindex is seen | pushed `70cb21f`, waiting for deploy |
| F4 | 4 wrong-language links in 3 Arabic posts → `/ar/…` (SK: fix from here) | pushed `bbe3a99`, waiting for deploy |
| F5 | Redirects.json: `/category` → `/category/`, `/feed` removed (SK's set) | pushed `9a5a07c`; **live 2 min after the push, no deploy** (`/category/` 301 at 17:49); `/category`, `/feed` still served from CloudFront cache (age ~3,200 s) |
| F7 | Java merge post moved from `content/Conholdate.Total/` (not in `mainSections`, so **never listed on the home page**) to `content/Conholdate.Cloud/total/`; URL unchanged; `/conholdate.total/` section page gone. Stray empty category `groupdocs.total-product-family` deleted (SK: yes) | pushed `0804d88`, waiting for deploy |
| F6 | Category: all 92 files → "Conholdate.Total Cloud Product Family" (SK: the real family) | pushed `bbe3a99`, waiting for deploy |

Pushed 11 Nov 17:47 PKT (`d2bc592..bbe3a99`); commit check PASSED (after fixing our check, 66280a2: it blamed old
`=\"` in commented-out figures of 38 translations on the commit). Left alone: `content/categories/groupdocs.total-product-family/_index.md`,
an empty category page titled "Conholdate.Total Cloud Product Family" (live 200), ask SK.

Audit changes from this blog (7694323): `social_tags_in_body` check (not optimized, group "head order" with
`head_closed_early`, commit check warns); `tag_pages_thin` skipped when `/tags/` and 2 tag pages answer noindex.

Test (11 Nov, Hugo 0.101.0, production config, full build before/after): file set identical; no SEO tag left in
`<body>` on any page; 555 tag term pages + 23 `/tags/` pages index → `noindex, follow`, no other robots change;
x-default on 790 pages; sitemaps changed only by 161 x-default lines; robots.txt only the two lines removed.

## Learned here

- Same theme family as blog.conholdate.com: template fixes carry over (head order, x-default, tag noindex).
- Redirects.json applies **live** here (within ~2 min), unlike blog.conholdate.com (at deploy). CloudFront caches
  redirect answers (query string not in the cache key), so a removed entry keeps answering until the cache expires.
- Redirect keys match exactly; the host forwards no-slash → slash (302) only for real folders.
