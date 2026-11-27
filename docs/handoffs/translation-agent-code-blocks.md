# Translation agent: two bugs found on blog.groupdocs.cloud (27 Nov 2026)

For: the developer of `conholdate/blog-translation-agent`.
Found by the Health and Recovery Agent while fixing blog.groupdocs.cloud. Both showed up in the same run, commit
`ec990f7b` "Retranslate articles for: CSV to JPG Conversion in Python: Quick Guide for Developers" (27 Nov 2026, 09:16).

| # | Bug | Where | Effect on the page |
|---|---|---|---|
| 1 | Code blocks split at blank lines; code comments translated | `tools/translation_agent/translator.py` | half of each code sample shows as text, the explanation after it as code |
| 2 | Unresolved autostash conflicts committed | `.github/workflows/translate-blog-*.yml` (all six), step "Prepare Git for Commit" | `<<<<<<< Updated upstream` / `>>>>>>> Stashed changes` shown as text |

---

## Bug 1: code blocks split at blank lines

### What happens

Example, German: `content/GroupDocs.Cloud/conversion/2026-08-24-csv-to-jpg-conversion-in-python-quick-guide-for-developers/index.de.md`

English (correct, `index.md` lines 76–86):

    <!--[CODE_SNIPPET_START]-->
    ```python
    from groupdocs_conversion_cloud import Configuration, ApiClient

    configuration = Configuration()
    configuration.client_id = "YOUR_CLIENT_ID"
    ...
    api_client = ApiClient(configuration)
    ```
    <!--[CODE_SNIPPET_END]-->

German after ec990f7b (lines 92–103): a closing fence was inserted after the first code line, at the blank line:

    <!--[CODE_SNIPPET_START]-->
    ```python
    from groupdocs_conversion_cloud import Configuration, ApiClient
    ```                                   <- inserted
    
    configuration = Configuration()       <- now plain text on the page
    ...
    api_client = ApiClient(configuration)
    ```                                   <- now OPENS a block: the next paragraph shows as code
    <!--[CODE_SNIPPET_END]-->

- English 28 fence lines, German 32; the same pattern in 14 languages (ar, de, es, fr, id, ko, pl, pt, th, tr, uk, vi,
  zh, zh-hant).
- **Code comments were translated too**, e.g. German `# -------------------- Konfiguration --------------------` for
  the English `# -------------------- Configuration --------------------`, against CRITICAL_RULES 3 ("Do NOT translate
  code blocks").

### Why the existing guards did not stop it

- The paragraph loop (`translate_content`, about lines 587–625) splits the body at blank lines (`content.split('\n\n')`)
  and re-joins paragraphs while the running ``` count is odd. Code blocks containing blank lines depend entirely on that
  re-joining.
- `_code_fence_count_mismatched` (since 4785131, June 2026) compares only the *number* of ``` per chunk. A model that
  moves a fence (adds one in the middle, drops one elsewhere) keeps the count and passes; paragraphs that are not
  combined are checked on their own.
- Nothing compares the code inside the blocks with the English, so translated comments pass.

### Fix (requested)

1. **Never send code to the model.** Before chunking, replace every fenced code block (opening ``` line to closing
   ``` line, together with the `<!--[CODE_SNIPPET_START]-->` / `<!--[CODE_SNIPPET_END]-->` /
   `<!--[COMPLETE_CODE_SNIPPET_START]-->` markers around it) with a placeholder line such as `⟦CODE_7⟧`. Translate the
   rest; restore every block byte for byte afterwards. This also keeps code comments in English.
2. **Check the placeholders:** each placeholder exactly once, in the same order, on its own line; otherwise retry the
   chunk, and after the retries keep the English chunk (as today).
3. **Check the whole file before committing:** the translation has the same sequence of fence lines as the English post
   (count, opening info strings such as ```python / ```bash, order) and identical code inside each block. If not, do
   not commit that language; write the reason in the queue row's Notes.
4. **Tests** (`tests/test_translator_guards.py`):
   - a code block with blank lines inside, wrapped in CODE_SNIPPET markers (the example above);
   - two code blocks in a row with no text between them;
   - a code block with Markdown-looking lines (`# comment`, `- item`, a line containing ``` inside a string);
   - a code comment: must come back untranslated;
   - a model output that moves a fence but keeps the count: must be rejected.

---

## Bug 2: unresolved autostash conflicts committed

### What happens

In the same run, 4 translations of the csv-to-jpg post (de, id, tr, uk) were committed with git conflict markers:

    <<<<<<< Updated upstream
    =======
    api_client = ApiClient(configuration)
    ```
    >>>>>>> Stashed changes

They showed as text on the live pages, and the missing side held a code line and a closing fence.

### Cause

All six workflows (`.github/workflows/translate-blog-*.yml`, step "Prepare Git for Commit") run, after translating for
10–30 minutes:

    git fetch origin
    git merge --ff-only --autostash origin/$DEFAULT_BRANCH
    git add content/

While the agent was translating, another commit changed the same translation files on master (here: the Health and
Recovery Agent's fix 4b6eda6a, which also edited the csv-to-jpg translations). `--autostash` re-applied the agent's
files on top, the re-apply conflicted, git left the markers in the files, and `git add content/` committed them.
`--autostash` does not fail the step when its re-apply conflicts.

### Fix (requested)

1. After the merge, stop if anything is unmerged or holds markers, e.g.
   `git diff --name-only --diff-filter=U` is not empty, or `git grep -l -e '^<<<<<<< ' -e '^>>>>>>> ' -- content/` finds files.
2. Better: avoid the conflict. Keep the new translations outside the work tree (or in a temporary branch), reset to
   `origin/$DEFAULT_BRANCH`, then write the files back. A full retranslation of a file replaces whatever another
   commit changed in it, so the agent's version should win; the queue scanner will flag the file again if its English
   changed meanwhile.
3. Never `git add` a file containing `^<<<<<<< ` (a pre-commit check in `commit_translations.py` is enough).

The Health and Recovery Agent will also avoid editing translations of posts that are being retranslated; its check
`post_merge_conflict` now reports committed markers on every blog.

---

## Already fixed, verified

- Home-page link not localized (`https://blog.<domain>/` kept English in translations): fixed in `4886783`
  ("Localize home-page links in translations", 27 Nov 2026); `tests/test_link_localizer.py` passes (28 tests).

## After the fixes: what to retranslate (blog.groupdocs.cloud)

| Post | Languages | State |
|---|---|---|
| conversion/2026-08-24-csv-to-jpg-conversion-in-python-quick-guide-for-developers | all 18 | 14 current (broken by ec990f7b; markers removed in 18b29302, split code blocks remain), 4 queued (fa, it, ja, ru) |
| conversion/2026-07-08-comprehensive-json-to-html-conversion-tutorial-in-php | fa, id, zh-hant | queued; code blocks damaged by an older run |

## How to verify

- Run the retranslation for the csv-to-jpg post (de is enough for a first test) and compare with the English: same
  fence lines in the same order, identical code inside each block, no `<<<<<<<` anywhere.
- The Health and Recovery Agent's repo check reports `code_fence_misplaced`, `post_merge_conflict` and
  `post_secret_literal` per file; after the retranslation the csv-to-jpg and json-to-html translations should have none.
