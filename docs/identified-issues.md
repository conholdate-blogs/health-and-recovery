# Identified issues (register)

Everything found and not yet fixed or not yet in a report, per blog, so nothing is lost (SK, 2026-11-12: "note all
identified issues"). Counts from the 12 Nov dry runs of the repo checks (exact, every file) unless a date says
otherwise. When a blog is scanned, its report and Issue log take over; tick the row here with the scan date.

## All blogs: old date-based URLs (SK, 13 Nov 2026: "these are bugs, replace all date-based URLs"; plan, start Monday)

Old WordPress URLs look like `/2021/12/16/slug/` (sometimes with a language prefix). Counted 13 Nov (repo, every file):

| Where | blog.aspose.com | blog.groupdocs.com | blog.conholdate.com | blog.aspose.cloud | blog.groupdocs.cloud | blog.conholdate.cloud | Action |
|---|---|---|---|---|---|---|---|
| 1. Links inside posts to a date URL | 18,120 in 9,692 files | 156 in 21 | 0 | 391 in 254 | 272 in 119 | 0 | **Replace** each with the post's current URL (localized when the translation exists) |
| 2. Posts whose own `url:` is a date URL | 41 | 0 | 0 | 4 | 0 | 0 | **Change** to the English slug URL; translations follow; one redirect old → new each (rule RED-1) |
| 3. Redirects.json keys for old date URLs | 15,934 | 2,638 | 1,311 | 943 | 344 | 0 | **Keep** (they catch old links from other sites and search results); only fix keys whose target 404s or chains |

Plan:
1. New exact checks so every fix counts: `link_date_url` (item per link, with the current URL as `fix`) and
   `post_url_dated` (item per post). Today such links count only as `link_redirected` / `link_broken`.
2. Fix list per blog from Redirects.json (date key → target) plus post `url`/aliases; links with no match listed
   for review (garbled slugs).
3. Scripted replacement, batch by batch with SK's approval, build diff + commit check per batch; blog.aspose.com
   last (18k links, live Redirects.json).
4. Translation agent: never write a date URL (it copies links from English, so fixing English first stops most).
5. Order with the rest: after B5/B10 on blog.conholdate.com (which has none of these), then blog.groupdocs.cloud →
   blog.aspose.cloud → blog.aspose.com; blog.groupdocs.com monitor only (report, no fix).

## blog.conholdate.cloud (health 100, 12 Nov)

| Issue | Count | State |
|---|---|---|
| Company menu bar missing on /zh-hant/ (`menu_id_invalid`) | 1 language | F17 fix 39f62ad: ✓ verified live 12 Nov |
| Java post translations: titles/descriptions too long (`post_title_length`, `post_description_length`) | 9 + 9 | F18 fix 98431b5: ✓ verified live 12 Nov |
| llms.txt calls the Java post "English only" | 1 | F19 fix 50ce0eb: ✓ verified live 12 Nov |
| No-slash URLs answer 302 (`slash_redirect_temporary`) | host | F16: answered by Amazon S3; **wait for the Ceph move** (nginx-redirector adds the slash; SK, 12 Nov) |
| Translation agent writes over-long titles/descriptions | tool | agent commit 423a608 (length limits), pushed to GitHub |
| Tags: 27 tags, all with one post | 27 | SK: retag later (tag pages noindex meanwhile) |
| English H2s in translated post bodies (e.g. "Convert HTML to DOCX" on /ar/) | seen by hand | not a check yet (body text); for the translation agent |
| Header label "Home" in English on every language | site-wide | small config change (`params.label.text` per language) |
| llms.txt without charset=utf-8 (garbled in browsers) | header | F22: ✓ verified live 12 Nov (32f3330 + f83b80c) |
| llms.txt maintained by hand (goes stale as posts and translations land daily) | file | F20: ✓ verified live 12 Nov (generated at build); next: the other blogs |

## blog.conholdate.com (next blog; plan B1–B6 in its log)

| Issue | Count |
|---|---|
| Stale translations: English rewritten by the Blog Optimization Agent (Mar 2026), translations kept old titles (`translation_stale`) | 3,638 |
| Post descriptions / titles out of range | 5,070 / 1,802 |
| Translations keeping English text (`post_text_untranslated`) | 198 |
| Section `_index.md` English only (`section_index_untranslated`) | 17 |
| Translated URLs not `/<lang>/<English url>/` (`translated_url_mismatch`, all French) | 15 |
| Junk redirect entries (`redirect_key_malformed`) | 15 |
| Wrong language names (`language_name_wrong`: ja 日本, ko 한국인, nl "Dutch", …) | 5 |
| RTL off (ar, fa) | 2 |
| Company menu in English on vi, th, tr (`menu_id_missing`) | 3 |
| No-slash 302 | host |
| Head bug: OG/Twitter/JSON-LD in `<body>`; no x-default; tag pages in sitemaps | template (B3, B4) |
| Links: wrong language 374, broken 81, damaged 54, missing translations 20 (11 Nov scan) | B5 |

## blog.aspose.cloud

| Issue | Count |
|---|---|
| **Company menu bar missing on /zh-tw/** (`asposecloud-zh-tw`, 3 parts; `asposecloud-zht` exists) | 1 language |
| Post descriptions / titles out of range | 6,027 / 2,957 |
| Stale translations | 630 |
| Translations keeping English text | 304 |
| Junk redirect entries (incl. 64 non-ASCII keys that do not redirect) | 75 |
| Translated URLs not `/<lang>/<English url>/` (21 own slug, 1 French file under `fa/`) | 22 |
| Section `_index.md` English only | 21 |
| Wrong language names | 7 |
| Redirects pointing at themselves | 4 |
| RTL off | 3 |
| Broken front matter | 1 |
| No-slash 302 | host |

## blog.groupdocs.cloud

| Issue | Count |
|---|---|
| **Company menu bar missing on /zh-hant/** (`groupdocscloud-zh-hant`; `groupdocscloud-zht` exists) | 1 language |
| Post descriptions / titles out of range | 3,870 / 2,390 |
| Stale translations | 234 |
| Translations keeping English text | 117 |
| Junk redirect entries | 63 |
| Section `_index.md` English only | 18 |
| Wrong language names | 5 |
| RTL off | 2 |
| Redirect target not https | 1 |
| Translated URL mismatch | 1 |
| No-slash 302 | host |

## blog.aspose.com

| Issue | Count |
|---|---|
| Company menu: Simplified Chinese bar on /zh-hant/ (`aspose-zh`; `aspose-zht` exists) | 1 language |
| Post titles / descriptions out of range | 12,288 / 11,788 |
| Stale translations | 7,391 |
| Translated URLs not `/<lang>/<English url>/` (375 own slug, 168 `zh-tw/` on zh-hant, …) | 608 |
| Translations keeping English text | 251 |
| Junk redirect entries (incl. 74 non-ASCII keys that do not redirect) | 121 |
| Post urls without a leading slash | 48 |
| Broken front matter | 32 |
| Section `_index.md` English only | 21 |
| Wrong language names | 8 |
| Redirects pointing at themselves | 4 |
| RTL off | 3 |
| Redirect targets not https | 2 |
| No-slash 302 | host |
| Gist footer fix not ported (`{{ revealButtonHref }}` URLs); commit check not deployed | open from 3–10 Nov |

## blog.groupdocs.com (monitor only)

Not in the 12 Nov dry run (its repo has no `config.yml` at the expected place); covered by its last full scan (7 Nov).

## Our audit and site

| Item | State |
|---|---|
| Indexed % via URL Inspection | later plan (SK) |
| English-H2-in-body check (translated bodies) | idea, not built |
| Crawl sample English bias | addressed for small hosts (full crawl); big hosts use the rotating sample from the next scan |
