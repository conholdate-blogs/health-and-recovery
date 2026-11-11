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
| 7 | **No llms.txt** (`llms_txt_missing`) | `static/llms.txt`: H1, `>` summary, articles with one-line descriptions, a Languages section (English name + code → home page), sitemap | Every link 200 | Do not claim every post is translated; mark English-only posts |
| 8 | **Wrong-language links** (`link_wrong_language`) | Replace in the translated file (fix list CSV from the link check) | Built page links `/<lang>/…` | SK: fix from here, not by the translation agent |
| 9 | **Category / section structure**: duplicate categories, a post folder outside `mainSections` (never on the home page), stray `content/categories/*/_index.md` | One category name in all files; move the post folder (its `url` keeps the URL); delete stray files | `build_diff.py`: only the intended pages gone; home lists every post | Check `params.mainSections` against `content/` folders |
| 10 | **Redirects.json leftovers** (WordPress-template keys) | Keep only keys with a purpose; keys match exactly (`/category` ≠ `/category/`) | curl each key | The host forwards no-slash → slash (302) only for real folders; CloudFront caches redirect answers (query string ignored) |
| 11 | **Language menu names** (`languageName` in `config.yml`) | Native names (日本語, 한국어, 繁體中文, Bahasa Indonesia, Nederlands, ไทย, עברית) | Switcher shows them | blog.conholdate.cloud had "日本" (Japan), "한국인" (a Korean person), "中國傳統的" |

Per blog, before fixing: Redirects.json live or at deploy (blog.conholdate.cloud and blog.aspose.com live,
blog.conholdate.com at deploy); `mainSections`; which pages are translated (the switcher renders only there).

## Rules for our own audit

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

## URL rules (SK, 2026-11-11)

- Every post URL is English; a translation is published at `/<lang>/<English url>/`. A translated slug or another
  language's prefix is an error (`translated_url_mismatch`).
- No redirect entries for junk URLs: gist placeholders, a host in the key, `#` fragments, double slashes,
  non-English slugs (the "junk entry" warning). Old English WordPress URLs (`/2021/09/10/slug`) stay.
- The one wanted kind of new redirect: old URL → corrected URL when a post's URL is fixed.

## Traps

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
