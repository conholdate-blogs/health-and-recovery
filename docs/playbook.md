# Scan and fix playbook (per blog)

How one blog is scanned, fixed and verified. Written on the pilot (blog.conholdate.com, November 2026); each blog
has its own log in [blogs/](blogs/) with its facts, findings, decisions and fixes.

## Order

1. **Facts first** (into the blog's log): source repo and branch, workflows repo, deploy trigger and time, Hugo
   version (`hugo_version` in the tenant YAML), whether Redirects.json applies live or at deploy, theme quirks.
2. **Scan:** `caffeinate -i .venv/bin/python scripts/run_cycle.py <tenant>` (full) or `--quick` (exact checks).
   Review the results, then `build_report.py --snapshot "<what changed>"`.
3. **Fix, smallest and safest first:** Redirects.json clean-ups → URL corrections with old→new redirects →
   template changes (head, hreflang) → structure (tags, pagination, sitemaps, robots.txt) → link fixes.
4. **Verify each fix live**, record it in `reports/<tenant>/agent-fixes.json` and in the blog's log.
5. **Re-scan:** fixes show in Fix progress; snapshot; push our repo.

## Rules for every change on a blog repo (Phase 1)

- SK approves each push at that time; approval does not carry over.
- Commit message: what and why, how it was tested, then `Fixed by Health and Recovery Agent` and
  `Assisted by Claude Code`. Commit identity `shoaib.khan@aspose.com` (check after each commit).
- Before the push: `scripts/commit_check.py <repo> --base <last pushed commit> --hugo <deploy's Hugo>`.
- Template change: build the affected page with the deploy's Hugo (`scripts/ops/hugo_check.py` or a temp copy)
  and check the rendered DOM in headless Chrome when JavaScript is involved. Small blog: full build before and
  after with the production config, compare with `scripts/ops/build_diff.py`.
- After the deploy: `scripts/ops/live_head.py` on a translated post, the home page and a tag page; screenshot desktop
  and 390 px when the layout changed.
- One commit per fix (revertable alone); each push and each deploy is SK's call. Tell SK when a manual deploy is
  needed (template, content, `static/` changes); Redirects.json may apply without one.
- Redirects.json: change line by line, parse before and after, check that every other entry is unchanged.
- After the push: verify live (curl, headless Chrome). If the blog applies changes at deploy, ask SK to run the
  production deploy (or wait for the cron).
- **Before editing translation files, read the translation agent's scan sheet** (`1FK2GWKyPuUyeCjJ7nDZNQIvP8jtwQcvSwig1KtXLnF0`,
  tab = blog host, read-only via the service account; columns Blog Post Directory, Issue, Target Translations).
  Since 17 Nov the scanner queues **OUTDATED → Retranslate** when `index.md` was committed after `index.<lang>.md`.
  - Translation queued for retranslation: do **not** edit it (it gets overwritten, and our commit would make it
    newer than the English post, so the scanner drops it from the queue). Fix only the English post if it has the bug.
  - Fixing a link in an English post that is not queued: change its translations **in the same commit**; an
    English-only commit makes all its translations OUTDATED and costs a full retranslation.
  - Known gap, accepted by SK (17 Nov): a commit touching every language (bulk link prefix, folder move, our tag
    fix) resets the dates, so older English rewrites are not seen as OUTDATED.
  - **A translation with more or fewer references than the English post is usually an outdated copy, not a link
    bug** (SK, 18 Nov): compare `git log --follow` of `index.md` with the translation's first commit. If the English
    changed after it, do not patch links (the text stays incomplete); queue the post for retranslation. Until the
    scanner keeps hand-added rows this was done with a small real English fix as the last commit (blog.conholdate.com
    3f942379); from then on it is a sheet record (below).
  - **Queue model (SK, 18 Nov; SK is changing the scanner):** the queue holds only (a) missing translations,
    (b) posts whose `index.md` the optimization agent changed, (c) translations we find with several considerable
    issues, (d) low-quality translations from the quality agent. Built by SK 18 Nov (translation agent 9ce1431,
    b6b85e7): the domain tab is a persistent queue; (c) and (d) are `ISSUE` rows added with
    `tools/translation_agent/queue_add.py --domain … --post <product>/<folder> --langs … --reason … --source "Health and
    Recovery Agent"` (dry run first; languages an open row already covers are skipped). OUTDATED still counts every
    English commit. Everything else we fix in place: links, `**`, shortcodes, tags, front matter, English and its
    current translations in one commit. Candidates for (c) go to `reports/<tenant>/retranslate-candidates.csv`; SK
    runs `queue_add.py` (it needs the write key; our service account reads the sheet only).
    Considerable = an LLM answer, code or garbage instead of a translated title/description (`translation_text_garbled`),
    or a translation older than an English rewrite with a different structure (headings, references).
  - **Items left for retranslation are listed per post** (SK, 19 Nov): whenever a fix skips queued translations,
    the item goes to `reports/<tenant>/after-retranslation.csv` (post, check, languages, example, state). After each
    translation run + rescan, `scripts/ops/translation_queue_report.py` updates the state: *fixed by
    retranslation*, or *still there after retranslation: fix here* (then the Health & Recovery Agent fixes it, and
    the translation agent gets a guard when it reproduced the defect). Nothing left for retranslation is forgotten.
  - **Markup-only fixes (`**` etc., rule TD-4) never queue a retranslation:** fix current translations in the same
    commit, leave queued (OUTDATED) translations alone, and wait with English-only changes that would mark clean
    current translations OUTDATED until only optimizer commits count.


**Check sheet:** [check-sheet.md](check-sheet.md) lists what to look at on every English and translated post page
(front matter, body, links, rendered page), the check that covers it or *by hand*, and where it is fixed.

## Fix catalogue (proven on blog.conholdate.cloud, 11 Nov 2026: 84 → 100 with real fixes only)

Hugo/PaperMod blogs share these problems. Check each blog for every row; commits in
[blogs/blog.conholdate.cloud.md](blogs/blog.conholdate.cloud.md), live proof in `reports/conholdate.cloud/agent-fixes.json`.

| # | Problem (how to see it) | Fix | Test | Gotcha |
|---|---|---|---|---|
| 1 | **`<head>` ends early**: a language-switcher `<div>` (`extend_head.html` → `langswitcher.html`) inside `<head>`; tags after it land in `<body>` (`scripts/ops/live_head.py <translated post> <home> <tag page>`) | Make `extend_head.html` the **last** include of `head.html` | `build_diff.py`: no SEO tag in `<body>` | If the div comes before canonical/hreflang it is `head_closed_early` (broken, blog.aspose.com 3 Nov); after them `social_tags_in_body` (OG/Twitter/JSON-LD; blog.conholdate.cloud and blog.conholdate.com) |
| 2 | **No x-default** (`hreflang_no_xdefault`) | `head.html` after the hreflang range: `{{ $d := (index .Sites 0).Language.Lang }}{{ range .AllTranslations }}{{ if eq .Lang $d }}<link rel="alternate" hreflang="x-default" href="{{ .Permalink }}">{{ end }}{{ end }}`; same inside the sitemap template's `IsTranslated` block (`index site.Sites 0`) | x-default on every translated page; sitemaps change only by x-default lines | Hugo 0.101: `.Sites.First` not needed; a section with `_index.md` in English only gets **unlinked** auto-generated translations (titled e.g. "Conholdate.Clouds"): add `_index.<lang>.md` per language |
| 3 | **Thin tag pages** (`tag_pages_thin`; tags with one post; tag pages competing with posts in Search Console) | `head.html` robots: `else if and (in (slice "taxonomy" "term") .Kind) (eq .Data.Plural "tags")` → `noindex, follow`; remove `Disallow: /tags/` and `/tag/` from `layouts/robots.txt` (a blocked page's noindex is never read); keep tags out of the sitemap | Only tag pages change robots | The structure step now reads `/tags/` + 2 tag pages live and skips the finding when all are noindex |
| 4 | **Utility pages indexed**: `/search/`, `/archives/` (one-word titles/descriptions, "text needs JavaScript") | Same robots branch: `or … (in (slice "search" "archives") .Layout)`; sitemap filter `(in (slice "search" "archives") .Layout)` | Exactly those pages change | Google advises against indexing internal search pages |
| 5 | **Titles/descriptions out of range** (`title_length` 10–70, `description_length` 50–170; CJK double) | `scripts/ops/front_matter_set.py <repo> --scan`, then a JSON spec of new values | `--scan` shows 0 | The crawl samples pages: fix the whole repo. Look for **stale translations** (English rewritten later, translations kept the old title) |
| 6 | **No H1 on the home page** (`h1_missing`, 1 per language) | PaperMod `params.homeInfoParams: {Title, Content}`, per language under `languages.<lang>.params` (merge into an existing `params:` block, e.g. sv had `params.flag`); compact CSS in `assets/css/extended/custom.css`: `.first-entry.home-info { min-height: 0; margin: 8px 0 24px 0 }` | One H1 per home page in its language; post list unchanged; screenshot desktop + 390 px | The theme's 320 px hero looks empty; SK's wording: "<Brand> Blog", "Articles on …" (not "Tutorials"), brand without the dot ("Conholdate Cloud") |
| 7 | **No llms.txt / stale llms.txt** (`llms_txt_missing`, `llms_txt_outdated`) | **Generate it at build:** `config.yml` output format `llms` (mediaType text/plain, baseName llms, isPlainText, notAlternative) added to `outputs.home`, and `layouts/index.llms.txt` (posts of `mainSections` newest first with their description, "English only" for untranslated posts, languages on the default language, sitemap, categories); delete `static/llms.txt` (it would override) | Full build before/after: only llms.txt changes (+ one per language); every link exists | A hand-made file went stale within a day (blog.conholdate.cloud 12 Nov: the Java post got 22 translations, the file still said "English only"). Big blogs: list the newest N per section in the template |
| 8 | **Wrong-language links** (`link_wrong_language`) | Replace in the translated file (fix list CSV from the link check) | Built page links `/<lang>/…` | SK: fix from here, not by the translation agent |
| 9 | **Category / section structure**: duplicate categories, a post folder outside `mainSections` (never on the home page), stray `content/categories/*/_index.md` | One category name in all files; move the post folder (its `url` keeps the URL); delete stray files | `build_diff.py`: only the intended pages gone; home lists every post | Check `params.mainSections` against `content/` folders |
| 10 | **Redirects.json leftovers** (WordPress-template keys) | Keep only keys with a purpose; keys match exactly (`/category` ≠ `/category/`) | curl each key | The host forwards no-slash → slash (302) only for real folders; CloudFront caches redirect answers (query string ignored) |
| 12 | **English home title on translated pages** (`title_untranslated`, `description_untranslated`) | `languages.<lang>.title` and `languages.<lang>.params.description` in `config.yml` | Each language home has its own `<title>` | PaperMod builds the home `<title>` from the site title: localizing the H1 (row 6) leaves it English |
| 13 | **Translations that keep English text** (`post_text_untranslated`) | Translate the seoTitle/title/description in the file | Repo check 0 | The translation agent sometimes leaves one field English |
| 14 | **RTL languages left to right** (`rtl_direction_missing`) | `languageDirection: rtl` per language | `<html dir=rtl>`; screenshot the RTL layout | Not yet proven on a blog (12 Nov) |
| 15 | **Company menu bar missing or in the wrong language** (`menu_id_invalid`, `menu_id_missing`, `menu_id_wrong_script`) | `params.dynamicmenuid.<languageCode>: <venture>-<lang>` with exactly two parts; Traditional Chinese is `<venture>-zht` | Screenshot a page of that language: the black company bar shows, in its language | The menu script (menucdn.containerize.com) splits on `-`; `x-zh-hant` / `x-zh-tw` draw nothing (blog.conholdate.cloud, blog.aspose.cloud, blog.groupdocs.cloud, 12 Nov). Missing JSON on the CDN can still work through the service's API fallback (he, nl, sv) |
| 16 | **Section page repeats the home list** (`section_lists_home_posts`; one `mainSections` entry, so `/<section>/` lists the home page's posts) | `head.html` robots branch: `(and (eq .Kind "section") (eq (len site.Params.mainSections) 1) (in site.Params.mainSections .Section))` → `noindex, follow`; same condition in the sitemap template's skip list | Build diff: only the section pages (one per language) change robots; home unchanged | Proven on blog.conholdate.com (dae84823) and blog.conholdate.cloud (5b4cd9a), 13 Nov; the other four blogs have it too (dry run) |
| 17 | **Redirects to the home page** (junk rule RED-1: soft 404s) | Remove the key (gone URL answers 404); feeds → `/index.xml` | curl: removed keys 404, `/feed/` 301 → `/index.xml` | Keep redirects to *another site's* home (`/about` → about.<domain>) |
| 18 | **Markdown in front matter** (`post_front_matter_markup`, rule TD-4: `**`, backticks, `[x](url)` in title, seoTitle, description; summary only without a description) | `scripts/ops/fm_markup_fix.py <repo> [--write]`: cleans flagged fields of **current** translations whose English is clean (a backtick between letters becomes `'`); English posts: English + all current translations in one commit | Each file re-parsed: only those fields change; live meta/og/JSON-LD without `**` | PaperMod uses `description` for meta, og, JSON-LD, RSS and renders `summary` as Markdown on cards: `**` in a summary next to a description is harmless (first count 1,013 files was mostly that). An English-only commit queues every current translation (OUTDATED counts any English commit). blog.conholdate.com 82e16439 (77 files), 19 Nov |
| 19 | **Titles/descriptions left in English or that are an LLM answer** (`post_text_untranslated`, `translation_text_garbled`, rules TR-7, TR-9) | Translate the field only, by hand, in the blog's style per language (check 2–3 existing titles of that language first), product names and formats kept, title/seoTitle ≤ 70, description ≤ 170 wide; replace multi-line values with one quoted line; garbled ones in their **own commit** (SK) | Re-parse: only those fields changed, widths in range, not equal to English, not garbled | Only current translations. A garbled title often comes with the body inlining the gist code (older pipeline convention, not a defect). blog.conholdate.com 1f806a91 (7), c49b7358 (151), 19 Nov |
| 20 | **Wrong-language links in current translations** (`link_wrong_language`) | Replace each link on its line with the check's `fix` (localized absolute URL) from `link-audit-*-issues.csv`, current translations only | Live sample of the new targets 200; next link check | blog.conholdate.com 777e7263 (493 links, 255 files), 19 Nov |
| 21 | **Translation without cover image / `\"…\"` values** (`post_cover_lost`, `post_front_matter_escaped`, rule TR-8) | `scripts/ops/fm_cover_repair.py <repo> [--write]`: indents image/alt/caption/hidden under `cover:`, renames translated keys (`capa`, `cobrir`, `キャプション`, `légende`, `chú thích`, `כיתוב`, `заголовок`, Arabic/Thai caption) to English, turns `\"…\"` into `"…"`; current translations only | Re-parse: cover image = the English one, no `\"` left, other keys unchanged; live translated page has `entry-cover` | The 2025 pipeline did it (424 files on blog.conholdate.com, 62 on blog.conholdate.cloud). One nl file named a translated image file that does not exist (`convert-html-bestanden.jpg`): set the English image. Don't rewrite unchanged lines: re-emitting `key: value` broke nested `https:` text in a first draft. 3832d94d (306), 69e4ab9 (62), 19 Nov |
| 22 | **Broken link in a queued translation** | Fix the link here, then an `ISSUE` row (`queue_add.py --source "Health and Recovery Agent"`) for the English rewrite the translation still misses | Link target 200; the row in the queue | Our commit makes the translation newer than the English post, so the scanner drops it. blog.conholdate.com 638cf070 (view-stl-files-online, 17), 19 Nov |
| 23 | **English of queued posts first** (rule TR-10, SK 19 Nov) | After each scan run `scripts/ops/translation_queue_report.py --tenant <t>` (queued translations by English change size and author, English issues of fully queued posts, optimizer cuts, check-sheet by-hand items F7/F8/F11/F15) and fix the English issues of posts whose translations are all queued (free: no new queue rows); run `scripts/ops/english_body_check.py --tenant <t>` (LLM, one call per post, cached) and review every finding in context; record the decision in the CSV's `review` column | Re-check: counts drop; commit check | First run blog.conholdate.com: 217 posts, 109 findings, 27 fixed, 42 false (See also lists, code after a colon, image links emptied by the stripping), 13 uncertain, 27 skipped. 9ee68667 (5 lengths), 752c021d (18 text errors) |
| 24 | **English post cut off** (`post_body_cut_off`, rule TD-5) | Keep the current text up to the cut, append the rest from the version before the cutting commit (`git log --follow`, line counts per commit); take lost `[n]` definitions from an older healthy version; remove stray `---` | Same H2 set as the healthy version; every `[n]` defined; fences even | The optimizer cut 5 posts (Feb-Mar 2026), 2 restored later by others. A pre-cut version can itself be damaged at its end (truncated definitions): compare with an older one. Current translations of such posts are complete: fix them in the same commit only where the English fix applies. adc1337b, 19 Nov |
| 25 | **Listing page 2+ indexed with canonical to page 1** (`canonical_elsewhere` on `/page/N/`, `/p/N/` on blog.aspose.com; mixed signal: `index, follow` but canonical → home or section page 1; 0 search clicks on every blog) | `head.html`: page number from the same `.Paginate` input as `_default/list.html` (home: `site.RegularPages` where Type in `mainSections`; section: `union .RegularPages .Sections`); `gt $pageNum 1` → robots `noindex, follow` and canonical `$pager.URL \| absURL` | Build diff: only page 2+ change (robots + canonical); page 1, posts, tags unchanged; live `curl <blog>/page/2/` shows `noindex, follow` and a self canonical | Hugo keeps the first paginator of a page, so head and list must paginate the same input or the numbers differ. Proven on blog.conholdate.com 0cb83582 (13 Nov); blog.conholdate.cloud needs none (one page). **Open on blog.aspose.cloud, blog.groupdocs.cloud, blog.aspose.com** (live check 19 Nov). blog.groupdocs.com: monitor only, not fixed |
| 11 | **Language menu names** (`languageName` in `config.yml`) | Native names (日本語, 한국어, 繁體中文, Bahasa Indonesia, Nederlands, ไทย, עברית) | Switcher shows them | blog.conholdate.cloud had "日本" (Japan), "한국인" (a Korean person), "中國傳統的" |

Per blog, before fixing: Redirects.json live or at deploy (blog.conholdate.cloud and blog.aspose.com live,
blog.conholdate.com at deploy); `mainSections`; which pages are translated (the switcher renders only there).

## Rules for our own audit

- A fix that renames or removes a page must be able to resolve the findings on it: the crawl rechecks pages flagged
  by its own last run and by the last text check; a rechecked page gone from the sitemaps that 404s is no error
  (16 Nov, renamed tag on blog.conholdate.com).
- New checks are dry-run on the blog being fixed and the blogs already fixed only; waiting blogs get them on their
  turn (SK, 16 Nov).
- Before calling something broken, test it live. (The "double slash never matches" rule was wrong: 46 false
  issues.)
- A false finding that was published is **deleted** from the findings store and the item ledger
  (`scripts/ops/drop_false_items.py`), never marked fixed or resolved. Back up `data/<tenant>/findings.sqlite`
  first.
- An unpublished run that used a wrong rule: restore the store from the backup, delete the run's files, re-run.
- Keep internal check names when widening a check (finding keys and ledger items carry on).
- New finding ids carry the date first found (`crawl-261111-1`); old ids stay.
- **Target = 100 in Google's eyes too (SK, 2026-11-11):** never relax a check to raise a score; fix the site. A rule
  change is right only when the old rule was wrong about what search engines see (e.g. thin tags that are noindex).
- `commit_check.py` reports only problems a commit range adds (old damage in touched files is not blamed).
- **Audit the auditors after each blog (SK, 2026-11-12):** every problem found by hand becomes a check (or a
  seed finding), then rescan. 12 Nov added 11 checks (repo: title/description length on every file, stale and
  untranslated translations, sections outside `mainSections`, English-only section `_index.md`, language names,
  RTL, unused categories, no-slash 302; crawl: untranslated title/description) and a full crawl for hosts with
  ≤ 500 sitemap URLs (`audit.full_crawl_max_urls`); the full crawl alone surfaced 22 English home titles.
- An LLM answer that is a real problem under a wrong label: record it as reviewed in `audit.text.ignore` with the
  reason, and count it with a deterministic check instead.

## URL rules (SK, 2026-11-11)

- Every post URL is English; a translation is published at `/<lang>/<English url>/`. A translated slug or another
  language's prefix is an error (`translated_url_mismatch`).
- No redirect entries for junk URLs: gist placeholders, a host in the key, `#` fragments, double slashes,
  non-English slugs (the "junk entry" warning). Old English WordPress URLs (`/2021/09/10/slug`) stay.
- The one wanted kind of new redirect: old URL → corrected URL when a post's URL is fixed.

## Traps

- "Last changed" (git blame) is the last commit on a line, not where a link came from: bulk prefix commits and
  optimizers that re-write identical lines take the blame. To date a link, use `git log --follow -S <url> -- <file>`.
- Two full Hugo builds of blog.conholdate.com need ~9 GB (4.6 GB each, 1.5 GB of it tag pages); the disk filled on
  16 Nov. Build old, delete its `*/tag/*` folders except the ones the change touches, then build new.
- `requests` decodes these blogs' HTML as Latin-1 (Content-Type has no charset; pages declare UTF-8 in a meta tag):
  decode `r.content` as UTF-8 in live checks. System Python's urllib has no CA bundle here: use `requests`.
- **Line endings (13 Nov):** blog.conholdate.com's `head.html` is CRLF; a Python text-mode edit rewrote all 341 lines.
  Edit blog files with `scripts/ops/replace_keep_eol.py` (keeps CRLF/LF; each old string must match exactly once).
- **Shell quoting doubles backslashes:** a `printf`-written `"^.+\\.txt$"` became `\\\\.` and matched nothing;
  after editing YAML regexes, load the file and test the pattern.
- **Pages no sitemap lists are never crawled:** listing page 2 (`/page/2/`, `/p/2/` on blog.aspose.com) needs
  `audit.extra_urls`; the page-2 canonical bug hid there on five blogs.
- **Every URL a crawl samples needs its own template (19 Nov):** `/page/2/` matched `post` (`/<category>/<slug>/`),
  so 2 failing page-2 listings were scaled over all posts (`canonical_elsewhere` est. 1,101 on blog.groupdocs.com,
  922 blog.groupdocs.cloud, 1,125 blog.aspose.cloud for 2 real pages). All six tenants now have a `paginated`
  template before `post` (`/p/N/` on blog.aspose.com, where `/page/<slug>/` are Aspose.Page posts). When adding
  `extra_urls`, test which template each one gets.
- **Front-matter dates come in two formats** (ISO and RFC 2822 "Thu, 25 Jan 2024 …"): parse them
  (`core/audit/repo.iso_date`), never cut strings.
- **Hugo prefixes menu URLs with the language** (`/categories/` renders as `/de/categories/`): check the built page
  before "fixing" config URLs (CB4 was a false premise).
- **Redirects.json edits:** `scripts/ops/redirects_edit.py` (remove/retarget by key, line by line, keeps the format,
  JSON validated); before/after builds of any two commits: `scripts/ops/build_pair.sh` (git worktrees, the deploy's
  Hugo and production config), then `scripts/ops/build_diff.py`.

- **Fix here or retranslate (SK, 19 Nov, rule TR-9):** before queueing, compare the English changes since the
  translation (`git diff <English commit at the translation's date> HEAD -- index.md`, ignoring heading levels and
  link targets). Body rewritten (> 5 lines): retranslate. Front matter or a few lines, or only our own fixes: fix
  here. blog.conholdate.com 19 Nov: 3,767 outdated translations = 168 posts > 20 lines, 28 posts 6–20, 26 posts
  ≤ 5 lines or front matter only, 2 posts our fixes only.
- **A sample for the user must come from the commit:** the first example given for c49b7358 (fr export-data) was a
  queued file the commit never touched; pick samples with `git show --name-only <commit>`.
- **Translated YAML keys:** the 2025 pipeline translated keys too (`capa:`, `légende :`, `キャプション:`); Hugo ignores
  them. Look for keys outside the English file's key set when a translated page misses something the English has.
- **The English body check strips code, links and images:** a colon followed by code, or an image link (`[][5]`),
  looks broken to the LLM: review each finding in context before fixing. Raw HTML outside backticks is stripped on
  purpose (Hugo drops it too).
- **Optimizer edits can cut posts:** compare line counts across `git log --follow` of an English post when its end
  looks odd; the translations made before the cut still hold the full text.
- **Gist code inline in translations** (5,855 files on blog.conholdate.com): the older pipeline's convention (comments
  translated), not damage; the commit check's code-fence warning on such files is expected.
- **The link and repo checks read the local clone:** after local, unpushed commits a scan shows their effect before
  it is live; the crawl checks show the live site.

| Trap | Avoid |
|---|---|
| `cd` in a Bash call carries over to later calls | Absolute paths; `git -C <repo>` |
| `git diff --name-only` lists deleted files | `--diff-filter=d` |
| `git ls-files … \| split()` breaks on file names with spaces | `ls-files -z`, split on `\0` |
| `git grep -E` has no `\s` | `-F` with a plain string, or `[[:space:]]` |
| A `url` without a leading slash gets the language prefix from Hugo | Compare effective paths |
| Local Hugo 0.120 vs deploy 0.101 | Use `hugo_version` from the tenant YAML |
| Mac sleeps after 1 minute idle | `caffeinate -i` for long runs |
| Live redirect sample is random per file content | A changed Redirects.json shifts the sample; small score moves can be noise |
| A Hugo build writes `.hugo_build.lock` and `resources/` into the blog repo | `rm -rf` both after every local build, before `git status` |
| `Path.read_text`/`write_text` on blog files | Fine (LF files); check `git diff --stat` stays small (a CRLF file would show whole-file changes) |
| Regex edits to YAML front matter or config | Parse before and after with PyYAML and assert only the intended keys changed (a second `params:` key silently replaces the first) |
| Screenshots: headless Chrome renders ≥ ~500 px, live blogs send `x-frame-options: DENY` | Build locally with `-b http://localhost:8765/`, serve with `python3 -m http.server`, load in a 390 px iframe |
| `file://` screenshots lose the CSS (absolute, integrity-checked stylesheet) | Same: serve the build locally |
| SK may push blog commits himself between messages | `git fetch` before reporting what is pushed |
| Local Python `urllib` fails TLS (no CA bundle) | Use `requests` (certifi) |
| Hugo 0.101: a language-level `title` (languages.<lang>.title) is copied into `params.title`, which PaperMod uses for `og:site_name` | Keep the site name in a separate param (`params.siteName`) read by an `opengraph.html` override (blog.conholdate.cloud F13) |
| `hugo deploy` re-uploads only files whose content changed: a new `deployment.matchers` content type does not reach unchanged files (12 Nov: llms.txt kept `text/plain` without charset) | Change the file's content (llms.txt: "Last updated" line) or deploy once with `--force` |
| Deleting run files with a shell loop (12 Nov: a loop removed the newest repo-audit run, and the snapshot taken next missed the repo data) | Use `scripts/ops/prune_runs.py --go` only; if a snapshot was built from incomplete runs, drop its archive file, its `archive/index.json` entry (restore the file from git: it keeps 2-space indents) and its `health-history.json` entry, re-run the step, snapshot again |
| SK's translation agent pushes to blog repos between our commits | `git fetch` and `git pull --ff-only` before committing; check its new files with the repo check (new translations can bring long titles) |
| conholdate-blogs Pages deploy refused: "due to in progress deployment. Please cancel <sha> first", while cancelling that sha says "it's finished" (12 Nov 2026, twice) | A GitHub-side stuck record: the workflow's cancel + retry cannot clear it. SK re-runs the failed job after ~30 min (cleared both times); else Settings → Pages → Source off and on. The shoaibkhan copy keeps deploying meanwhile |
