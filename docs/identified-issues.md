# Identified issues (register)

Everything found and not yet fixed or not yet in a report, per blog, so nothing is lost (SK, 2026-11-12: "note all
identified issues"). Counts from the 12 Nov dry runs of the repo checks (exact, every file) unless a date says
otherwise. When a blog is scanned, its report and Issue log take over; tick the row here with the scan date.

## blog.conholdate.cloud (health 100, 12 Nov)

| Issue | Count | State |
|---|---|---|
| Company menu bar missing on /zh-hant/ (`menu_id_invalid`) | 1 language | F17 fix 39f62ad: ✓ verified live 12 Nov |
| Java post translations: titles/descriptions too long (`post_title_length`, `post_description_length`) | 9 + 9 | F18 fix 98431b5: ✓ verified live 12 Nov |
| llms.txt calls the Java post "English only" | 1 | F19 fix 50ce0eb: ✓ verified live 12 Nov |
| No-slash URLs answer 302 (`slash_redirect_temporary`) | host | F16: CDN setting, owner to be named |
| Translation agent writes over-long titles/descriptions | tool | agent commit 423a608 (length limits), pushed to GitHub |
| Tags: 27 tags, all with one post | 27 | SK: retag later (tag pages noindex meanwhile) |
| English H2s in translated post bodies (e.g. "Convert HTML to DOCX" on /ar/) | seen by hand | not a check yet (body text); for the translation agent |
| Header label "Home" in English on every language | site-wide | small config change (`params.label.text` per language) |
| llms.txt maintained by hand (goes stale as posts and translations land daily) | file | proposed: generate at build (Hugo output format), pilot here (SK, 12 Nov) |

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
