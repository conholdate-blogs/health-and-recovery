# Plan: commit watch and full site map (parked)

**State (SK, 20 Nov 2026):** documented only. **We plan and build it after the other domains are fixed.** The
translation agent's 72 h wait (part of A5) is already live. Nothing else has been started.

Two ideas from SK:

1. **Commit watch:** check every new commit on the blog repos (new articles, translations, optimizer commits)
   soon after it lands, instead of finding the issues at the next full scan. Posts with issues get flagged, and
   translation waits until the English article has settled.
2. **Full site map:** one map of every URL a blog serves or should serve, with Google's view of it and the
   internal link graph. Pilot: blog.conholdate.cloud.

## Facts behind it (measured 20 Nov)

| Fact | Number | Why it matters |
|---|---|---|
| New English post → first translation (blog.conholdate.com, last 20 posts) | 0–1 day | An English error reached 17 languages by the next day (before the 72 h wait) |
| New English posts edited again within 1 / 3 / 7 days (since 1 May; `scripts/ops/early_edits.py`) | blog.conholdate.com 9 / 9 / 14 of 40; blog.aspose.cloud 5 / 6 / 6 of 91; blog.groupdocs.cloud 1 / 3 / 4 of 59; blog.conholdate.cloud 0 of 2 | Each early edit made the fresh translations outdated (often the message was "removed files for retranslation") |
| Commit types can be told apart by message and files | "Blog Optimization Agent", "Translate articles for…", "Retranslate articles for…", "Daily Blogs Translation", a new English `index.md` = new article, anything else = edit by a person | Each commit can be classified automatically |
| Translation agent queue | Skips rows with status `hold` (`translator.py` `is_open_row`); since fc15060 also rows whose Ready After has not passed | Flagging needs no new mechanism |
| Our side | `scripts/commit_check.py` (build and breakage checks, not deployed, `docs/commit-check/`); all repo checks run over the whole repo | New work = run the existing checks on the changed files only, plus before/after for optimizer commits |
| Deploy cron | 03:00 UTC (08:00 PKT) on the Conholdate blogs | A translation commit checked within the hour can be fixed before it goes live |

## Done: translation waits 72 h (conholdate/blog-translation-agent fc15060, 20 Nov, on origin/main)

- New and updated posts are translated only once their English `index.md` has gone 72 h
  (`TRANSLATION_SETTLE_HOURS`) without a commit; the wait restarts with every English commit.
- The scan (00:00 and 12:00 UTC, full history, committer time) writes **Ready After** (last English commit + 72 h)
  and a note "⏳ Waiting until … UTC". Step 2 holds such rows back before the language budget.
- Urgent priority and `ISSUE` rows do not wait; a blank Ready After (no git history, old tab) means ready.
- Reviewed 20 Nov: 22 tests pass; the scan checks out full history, so the time is per file (a shallow clone would
  have made every post look just edited). Notes from the review:
  - **Gap up to 12 h (low):** Ready After is refreshed only by the scan. An English edit made after the last scan
    is not seen until the next one, so a run in between can translate a just-edited post. Possible fix: Step 2
    rechecks the English file's last commit time in its own checkout before translating.
  - **Our English fixes restart the wait:** any commit we make to an English `index.md` (TR-10 fixes on queued
    posts) delays its translation by 72 h. Intended, but plan English fix batches with it in mind (playbook trap).
  - The commit's last line is `Co-Authored-By: Claude Opus 5.5` instead of `Assisted by Claude Code` (SK's commit
    rule). It is pushed, so leave it.

## Plan A: commit watch

| Step | What | Where | Needs |
|---|---|---|---|
| A1 | `scripts/commit_watch.py <tenant> --since <commit or date>`: classify each commit; run the checks that fit (table below) on changed post folders only | our repo, read-only | nothing |
| A2 | Backtest on the last 30–60 days of blog.conholdate.com and blog.conholdate.cloud: issues it would have caught before translation, and retranslations the 72 h wait would have saved | local | nothing |
| A3 | "Recent commits" page per blog (commit, type, issues found, status); Issue log rows with `found_by: commit watch` and the commit id | site | nothing |
| A4 | Hourly schedule | GitHub Actions in our repo | decisions 2 and 3 |
| A5 | Translation gate: **72 h wait done (fc15060)**; still open: optimizer output held the same way before it triggers OUTDATED retranslation | blog-translation-agent | SK |
| A6 | The watch sets `hold` plus a reason on posts with English issues during the 72 h window and clears it on the next clean run | translation sheet | decision 1 |

Checks per commit type (almost all exist already as repo checks or ops scripts):

| Commit type | Checks |
|---|---|
| New article, English edit | Front matter (title and description length, English `url`, duplicate URL, copied seoTitle, cover, tag count), English body check with the LLM (`scripts/ops/english_body_check.py`), cut-off body, raw HTML, shortcodes and code fences, internal links exist, Hugo build of the post |
| Translation, retranslation | `/<lang>/<English url>/`, links in the wrong language or to untranslated posts, `\"`, lost cover, English left untranslated, garbled text, lengths, shortcode damage, code-fence count equal to the English |
| Optimizer | Before/after: body cut off (TD-5), raw HTML dropped, escaped shortcodes (TD-3), links removed, Markdown in front matter, lengths |
| Any commit | `scripts/commit_check.py` (Redirects.json, SEO tags in `<head>`, config, Hugo sample build) |

The 72 h window is when the watch's English findings must be fixed; without the watch the wait only delays.

## Plan B: full site map (pilot blog.conholdate.cloud)

| Step | What |
|---|---|
| B1 | One row per URL from every source: production Hugo build (incl. noindex and tag pages), sitemaps, Redirects.json, every URL with Search Console impressions in 16 months, live status. Per URL: final URL, canonical, robots, language, English original, hreflang group, in sitemap, clicks, impressions |
| B2 | Google's view: URL Inspection for every URL (index state, last crawl, Google-chosen canonical); ~170 calls on this blog, limit 2,000 per day per property |
| B3 | Link graph from the built HTML: links into each page, clicks from home, orphans, dead ends, links to redirects or 404s, menu vs body links |
| B4 | New checks: orphan page, sitemap URL not built, indexable page not in the sitemap, page indexed that should not be, Google canonical differs, crawled but not indexed, old URL with impressions answering 404, page more than 3 clicks deep, uneven hreflang groups |
| B5 | "Site map" page per blog: tree (home → section → post × languages), filterable table, CSV. Big blogs: summary tables, CSV, rotating URL Inspection sample |
| B6 | Roll out blog by blog (blog.conholdate.com next, blog.aspose.com last) |

Expectation: blog.conholdate.cloud is small and at health 100, so the pilot proves the method more than it finds
issues; the value shows on the bigger blogs. Overlaps the earlier "Pages page" idea (CLAUDE.md, 7 Nov handoff item 4)
and the "indexed % via URL Inspection" later plan; this plan replaces both.

## Proposed order

A1 → A2 → A3 → B1–B4 → A4 / A6 → B5 → B6 (A5's wait is done).

## Open decisions for SK (when we pick this up)

1. **Hold flags:** may the watch write `hold` rows to the translation sheet itself after the backtest, or does SK
   keep adding them with `queue_add.py`?
2. **Where it runs:** GitHub Actions needs a read-only token for the 5 blog repos and the LLM key as secrets (the
   Mac sleeps after 1 minute). The LLM key is still the translation agent's; a dedicated key first.
3. **Bot commits vs "SK is the only author":** results written by Actions would be `github-actions[bot]` commits.
   Options: a separate data branch, or workflow artifacts only.
4. **Map scope:** blog.conholdate.cloud only, or every conholdate.cloud host (GA4 253119926 also covers www,
   products, reference, forum and others)?
5. **The 12 h gap** above: should Step 2 recheck the English commit time itself?
