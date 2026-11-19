# Check sheet: English post and translated post

What we look at on every blog post, in the English original and in each translation. **Checked by** names the
audit check (automatic on every scan) or says *by hand* (not automated yet: a candidate check). Keep it current:
every issue found by hand gets a row here and, when it can be automated, a check (rule AUD-3). Started 19 Nov 2026
(SK: "maintain a check sheet that we are and should be taking care of while inspecting an English version and a
translation page"). Fix catalogue rows (playbook) say how each fix was done.

Legend: **E** = English post, **T** = translation, ✓ = applies. **Fix** = where it is fixed: *here* (blog repo,
rule TR-9) or *retranslate* (ISSUE row) or *English first* (fix the English, then its translations follow).

## 1. Front matter

| # | Look at | E | T | Checked by | Fix |
|---|---|---|---|---|---|
| F1 | Front matter parses (YAML), starts with `---` | ✓ | ✓ | `post_front_matter_broken` | here |
| F2 | `url` starts with `/`; a translation's url = `/<lang>` + the English url | ✓ | ✓ | `post_url_relative`, `translated_url_mismatch` | here |
| F3 | No two posts on one URL | ✓ | ✓ | `post_url_duplicate` | here (blog developer decides which stays) |
| F4 | title / seoTitle 10–70 wide, description 50–170 wide (CJK counts 2) | ✓ | ✓ | `post_title_length`, `post_description_length` | here |
| F5 | title, seoTitle, description plain text: no `**`, `` ` ``, `[x](url)` (summary only matters without a description) | ✓ | ✓ | `post_front_matter_markup` (TD-4) | here; English + current translations in one commit |
| F6 | Values quoted `"…"`, never `\"…\"` | ✓ | ✓ | `post_front_matter_escaped` (TR-8) | here (`fm_cover_repair.py`) |
| F7 | `cover:` block with `image`, `alt`, `caption` indented under it; image file exists | ✓ | ✓ | `post_cover_lost` (TR-8); image file exists: *by hand* | here |
| F8 | Keys in English (`cover`, `caption`, never `capa`, `légende`, `キャプション`) | – | ✓ | via `post_cover_lost`; other keys: *by hand* (compare with the English key set) | here |
| F9 | title / seoTitle / description translated (not the English words) | – | ✓ | `post_text_untranslated` | here (translate the field) |
| F10 | Title / description is a translation: one line, about as long as the English (not an LLM answer, steps, code, zero-width characters) | – | ✓ | `translation_text_garbled` (TR-7) | here, own commit |
| F11 | Title fully translated, not half English ("Convert LaTeX zu PDF in Java", "Convert PUB ke Word") | – | ✓ | *by hand* (candidate check) | here |
| F12 | Translation up to date with the English title / description | – | ✓ | `translation_stale` | retranslate, or here when only the field changed |
| F13 | Post folder under a `mainSections` section; categories used have a page | ✓ | – | `post_outside_main_sections`, `category_page_unused` | here |
| F14 | Not `draft: true` when it should be live | ✓ | ✓ | *by hand* | here |

## 2. Body

| # | Look at | E | T | Checked by | Fix |
|---|---|---|---|---|---|
| B1 | No `# ` / `<h1>` in the body (the theme renders the title as the only H1) | ✓ | ✓ | `post_body_h1` | here, English first |
| B2 | Shortcodes written `{{< … >}}`, never `{{ … }}` or `{{&lt; … &gt;}}` | ✓ | ✓ | `post_shortcode_as_text` (TD-3) | here, English first |
| B3 | No raw HTML tag in the text outside backticks (`**<input>**` renders as an empty bold: Hugo drops raw HTML) | ✓ | ✓ | `post_raw_html_dropped` (bolded tags); other raw tags: English body check | here: put the tag in backticks |
| B9 | The post is complete: ends with a finished sentence / list / link definitions, every code block closed, every `[n]` reference defined; not shorter than its healthy version | ✓ | (✓) | `post_body_cut_off` (TD-5); missing sections vs older versions: *by hand* (`git log` line counts) | here: restore the rest from the version before the cut |
| B4 | No typos, repeated words, placeholders, cut-off sentences | ✓ | (✓) | English: `scripts/ops/english_body_check.py` (LLM, posts with queued translations, review by hand); titles/H1/descriptions of crawled pages: `text_typo`, `text_leftover` | here |
| B5 | No sentence or heading copied from another post (another product or format than the topic) | ✓ | ✓ | English body check (`copied_from_other_post`, `wrong_product`); `text_topic_mismatch` for titles | here, English first |
| B6 | Code fences balanced; same number of code blocks as the English (gist code inline in translations is the older pipeline's convention, fine) | ✓ | ✓ | commit check `code_fence_mismatch` (warn) | here |
| B7 | Body translated: no English headings or paragraphs left in a translation | – | ✓ | *by hand* (seen on blog.conholdate.cloud /ar/: "Convert HTML to DOCX" H2) | retranslate when much, else here |
| B8 | Translation has the same structure as the English (headings, steps, "See also", reference count) | – | ✓ | `link_differs_from_original` (references); headings: *by hand* | here when small (translate the missing lines), retranslate when the English was rewritten |

## 3. Links

| # | Look at | E | T | Checked by | Fix |
|---|---|---|---|---|---|
| L1 | Internal links reach a page (no 404) | ✓ | ✓ | `link_broken`, `link_missing_translation` | here, English first (name the English article first) |
| L2 | No malformed links (`//`, cut slugs) | ✓ | ✓ | `link_damaged` | here |
| L3 | Links to old URLs that redirect → the target | ✓ | ✓ | `link_redirected` | here |
| L4 | A translation links the translated page when it exists | – | ✓ | `link_wrong_language` | here (current translations) |
| L5 | A translation links the same pages as the English post | – | ✓ | `link_differs_from_original` (TR-6) | here, or retranslate when outdated |
| L6 | No leftover date-based URLs (`/2021/12/16/slug/`) | ✓ | ✓ | `link_redirected` / `link_broken` | here (plan: replace all) |

## 4. Rendered page (live)

| # | Look at | E | T | Checked by | Fix |
|---|---|---|---|---|---|
| R1 | Title, description, canonical, hreflang (+ x-default), robots, Open Graph, JSON-LD in `<head>` | ✓ | ✓ | `head_closed_early`, `social_tags_in_body`, `canonical_*`, `hreflang_*`, `title_*`, `description_*` | template |
| R2 | One H1 | ✓ | ✓ | `h1_missing`, `h1_multiple` | here / template |
| R3 | Cover image shows (`entry-cover`) | ✓ | ✓ | via `post_cover_lost`; live: *by hand* after each fix | here |
| R4 | `<html lang>` and `dir=rtl` for ar/fa/he | – | ✓ | `html_lang_*`, `rtl_direction_missing` | config |
| R5 | Company menu bar in the page's language; native language names in the switcher | – | ✓ | `menu_id_*`, `language_name_wrong` | config |
| R6 | Speed (Core Web Vitals) | ✓ | ✓ | `lcp_*`, `inp_*`, `cls_*` | template |

## 5. Before a post is retranslated

1. Its English passes every check above (rows marked E; rule TR-10): fix the English first (free while all its translations are
   queued; otherwise English + current translations in one commit).
2. Run `scripts/ops/english_body_check.py` on posts with queued translations; review and fix the findings here.
3. Decide per post (rule TR-9): English body rewritten → retranslate; front matter or a few lines → fix here.
