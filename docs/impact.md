# Impact record: what the Health and Recovery Agent changed on the blogs

For announcing the agent (Shoaib Khan, 28 Nov 2026: "record such data/figures … to show what you have done and how we
have improved our blogs"). Every figure has a date and a source; fixes have commits (rows in
`reports/<tenant>/agent-fixes.json`, shown on each blog page as "Fixed by Health & Recovery Agent").

**How to read it**
- **Health** (0–100) and **open items** come from our own scans (`reports/<tenant>/health-history.json`,
  `items.json`). An item = one broken link, one bad file, one wrong page.
- **Search figures** come from Search Console / GA4 (`reports/<tenant>/visibility.json`, `traffic-summary.json`).
  They are a **baseline**, not a result: most fixes went live 24–28 Nov 2026, and search engines need weeks to
  re-crawl. Compare the monthly figures (section 4) from January 2027 on; never credit a change in the same month.
- Keep this file current: add a row in the same session as each verified fix round (rule in CLAUDE.md).

## 1. Per blog, before → after (scans)

| Blog | Fix round | Health | Issue types | Open items | Items fixed | Agent fixes (commits verified live) |
|---|---|---|---|---|---|---|
| blog.conholdate.cloud | 11–19 Nov | 81 (27 Oct) → **100** | → 1 | → 2 | 11 | 23 |
| blog.conholdate.com | 11–19 Nov (+ feeds 28 Nov) | 58 (13 Nov) → **92** (19 Nov) | 31 → 14 | 11,697 → 11,478 ¹ | 1,531 | 33 |
| blog.groupdocs.cloud | 19–28 Nov | 54 (19 Nov) → **93** (28 Nov) | 39 → 14 | 9,950 → 7,353 | 2,914 | 45 |
| blog.aspose.com | 3 + 7 Nov (2 outage fixes) | 50 → 69 (11 Nov) | 24 → 23 | — | 47 | 2 |
| blog.aspose.cloud | next (scan 19 Nov) | 49 | 44 | 14,780 | — | — |
| blog.groupdocs.com | monitor only | 50 | 39 | 19,141 | — | — |

¹ most of the rest sits in translations waiting in the translation queue (retranslation fixes them).

## 2. Headline figures (for slides)

| Figure | Where | Date | Commit(s) |
|---|---|---|---|
| **Site outage ended:** Redirects.json invalid → 40 of 40 old URLs answered 404; after the fix 40 of 40 answer 301 | blog.aspose.com | 3 Nov | a0f21c6, 11ea88f |
| **SEO tags back in `<head>`:** title, description, canonical, 22 hreflang, Open Graph, JSON-LD had fallen into `<body>` on ~28,800 translated pages (Google ignores canonical/hreflang there) | blog.aspose.com | 7 Nov | b76c2369eb |
| Same head-order fix (OG/Twitter/JSON-LD in `<body>`) | blog.conholdate.cloud, blog.conholdate.com, blog.groupdocs.cloud (56,079 pages) | 11–26 Nov | batch 2 etc. |
| **x-default hreflang added** on every page | blog.groupdocs.cloud (100,364 pages), blog.conholdate.com (14,072 pages missing it), blog.conholdate.cloud | 11–26 Nov | batch 2 |
| **~87,000 duplicate RSS feeds removed** (one per tag/category/section per language, full post text); one feed per language left | blog.groupdocs.cloud 43,241, blog.conholdate.com 43,801 | 28 Nov | 9ba456d8, 0f95b95d, b4e1cf38 |
| Build size blog.groupdocs.cloud: 172,523 → 129,282 files (−25%), 0 pages lost | blog.groupdocs.cloud | 28 Nov | same |
| **Leaked API key removed** from 1,766 + 36 post files (placeholders) | blog.groupdocs.cloud | 27 Nov | batch 3b, cef75257 |
| **Redirects.json cleaned:** 1,465 → 1,412 (blog.conholdate.com), 507 → 447 (blog.groupdocs.cloud) junk entries out | two blogs | 11–27 Nov | 9cc26f48, 2993d49c…, batch 3b |
| Tag pages, search, archives, page 2+: `noindex, follow` and out of sitemaps (blog.conholdate.com sitemap listed 43,584 tag pages) | conholdate blogs, blog.groupdocs.cloud | 11–26 Nov | B3/B4, batch 2 |
| **llms.txt generated at every build** (AI answer engines): newest posts per language; blog.groupdocs.cloud 30 most-read + 70 newest | blog.conholdate.cloud, blog.conholdate.com, blog.groupdocs.cloud | 12–26 Nov | 7bf0f7b, 23831516, 7a311dc1 |
| Broken / wrong-language internal links fixed | blog.conholdate.com 493 + 17; blog.groupdocs.cloud 494 category links + split URLs | 16–27 Nov | batch 4, batch 3 |
| Lost cover images restored | blog.conholdate.com 238, blog.conholdate.cloud 62, blog.groupdocs.cloud 220 translations | 19–26 Nov | 3832d94d, 69e4ab9, batch 3 |
| Escaped `\"…\"` front matter fixed | blog.conholdate.com 306, blog.groupdocs.cloud 488 files | 19–26 Nov | 3832d94d, batch 3 |
| 3 posts restored that an optimizer had cut short | blog.conholdate.com | 19 Nov | adc1337b |
| Copied search titles: 49 posts carried another post's seoTitle (931 files) removed; 6 tutorials got new ones in 19 languages | blog.groupdocs.cloud | 27 Nov | 6eb6ea7e, 12d5c853 |
| Committed git conflict markers removed (shown as text on live pages) | blog.groupdocs.cloud | 27 Nov | 18b29302 |
| Translated / escaped tag URLs Google knew: 398, all now 404 (were real pages) | blog.groupdocs.cloud | 26–28 Nov | batch 3a |

## 3. Tools improved because of what the agent found

| Tool | Bug found | Fixed |
|---|---|---|
| Translation agent | Home-page links kept English in translations | 4886783 (27 Nov) |
| Translation agent | Code blocks split at blank lines, code comments translated | a22f921 (27 Nov), verified 28 Nov |
| Translation agent | Unresolved git conflicts committed | 6a9002c (27 Nov), verified 28 Nov |
| Translation agent | Over-long titles/descriptions | 423a608 (12 Nov) |
| Our audit | 30+ new checks, each from an issue found by hand (rule AUD-3), run on every blog | Nov 2026 |

## 4. Search baseline (Search Console 28 days; AI visits GA4; DR Ahrefs)

Recorded so the effect can be measured later. Window = 28 days ending on the date shown.

| Blog | Window end | Clicks | Impressions | Keywords | Top 10 | Top 3 | AI visits | DR |
|---|---|---|---|---|---|---|---|---|
| blog.groupdocs.cloud | 16 Nov | — | 66,466 | 6,542 | 1,250 | 72 | 2 | 30 |
| blog.groupdocs.cloud | 25 Nov | 861 (prev. 28 days 585; six months ago 2,387) | 77,349 | 7,038 | 1,469 | 111 | 1 | 30 |
| blog.conholdate.com | 17 Nov | 2,711 (prev. 2,729; six months ago 5,928) | 142,277 | 12,885 | 2,983 | 300 | 4 | 28 |
| blog.conholdate.cloud | 17 Nov | 3 | 174 | 7 | 3 | 1 | 0 | 21 |

Six months earlier (window ending 18 May 2026): blog.conholdate.com top 10 1,988 / top 3 153; blog.groupdocs.cloud
top 10 949 / top 3 82. The rise to November came mostly before the fix rounds; do not credit it to them.
Monthly history: `reports/<tenant>/visibility-monthly.json` (charts on each blog page).

**Next readings to add:** end of December 2026 and end of January 2027 (first full months after the fixes).
