# Translation agent: code blocks split at blank lines (27 Nov 2026)

For: the developer of `conholdate/blog-translation-agent` (`tools/translation_agent/translator.py`).
Found by the Health and Recovery Agent on blog.groupdocs.cloud.

## What happens

The retranslation of 27 Nov 2026, commit `ec990f7b` "Retranslate articles for: CSV to JPG Conversion in Python",
split code blocks in the translations. Example, German:

`content/GroupDocs.Cloud/conversion/2026-08-24-csv-to-jpg-conversion-in-python-quick-guide-for-developers/index.de.md`

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

German (`index.de.md` lines 92–103): a closing fence was inserted after the first code line, at the blank line:

    <!--[CODE_SNIPPET_START]-->
    ```python
    from groupdocs_conversion_cloud import Configuration, ApiClient
    ```                                   <- inserted

    configuration = Configuration()       <- now plain text on the page
    ...
    api_client = ApiClient(configuration)
    ```                                   <- now OPENS a block: the next paragraph shows as code
    <!--[CODE_SNIPPET_END]-->

Result on the page: half of every code sample renders as text and the explanation after it renders as code.
English 28 fence lines, German 32; the same in ar, es, fa, fr, id, it and others (14 languages).

## Why the existing guards did not stop it

- The paragraph loop (`translate_content`, about lines 587–625) splits the body at blank lines and re-joins paragraphs
  while the running ``` count is odd. Code blocks that contain blank lines are exactly the case it is built for.
- `_code_fence_count_mismatched` (since 4785131, June 2026) compares only the *number* of ``` per chunk. A model that
  moves a fence (adds one in the middle, drops one elsewhere) keeps the count and passes; and paragraphs that are not
  combined are checked on their own.

## Fix (requested)

1. **Never send code to the model.** Before chunking, replace every fenced code block (from an opening ``` line to its
   closing ``` line, including the `<!--[CODE_SNIPPET_START]-->` / `<!--[CODE_SNIPPET_END]-->` and
   `<!--[COMPLETE_CODE_SNIPPET_START]-->` markers around it) with a placeholder line such as `⟦CODE_7⟧`. Translate the
   rest. Restore every block byte for byte afterwards. Code is never translated anyway (CRITICAL_RULES 3).
2. **Check the placeholders:** the translation must contain each placeholder exactly once, in the same order, each on
   its own line. Otherwise retry the chunk; after the retries keep the English chunk (as today).
3. **Check the whole file before committing**, not only chunks: the translation has the same sequence of fence lines as
   the English post (same count, same opening info strings such as ```python / ```bash, in the same order). If not,
   do not commit that language and write the reason in the queue row's Notes.
4. **Tests** (`tests/test_translator_guards.py`):
   - a code block with blank lines inside, wrapped in CODE_SNIPPET markers (the example above);
   - two code blocks in a row with no text between them;
   - a code block holding text that looks like Markdown (`# comment`, `- item`, a line with ``` inside a string);
   - a model output that moves a fence but keeps the count: must be rejected.

## Second bug: unresolved stash conflicts committed (27 Nov 2026)

The same run (`ec990f7b`) committed git conflict markers into 4 translations of the csv-to-jpg post (de, id, tr, uk):
`<<<<<<< Updated upstream` … `=======` … `>>>>>>> Stashed changes`, shown as text on the live pages, with the missing
side holding a code line and a closing fence. The agent apparently stashes local changes, pulls, and pops the stash;
when the pop conflicts it commits the files anyway. Requested: after `git stash pop` (or any merge), stop if
`git diff --name-only --diff-filter=U` lists files or any staged file contains `<<<<<<< `; never commit such files.
Fixed in the blog by the Health and Recovery Agent (18b29302); its check `post_merge_conflict` now reports them.

## Already fixed, verified

- Home-page link not localized (`https://blog.<domain>/` kept English in translations): fixed in `4886783`
  ("Localize home-page links in translations", 27 Nov 2026); `tests/test_link_localizer.py` passes (28 tests).

## After the fix

The csv-to-jpg translations (14 languages) can be retranslated with an ISSUE row; the Health and Recovery Agent's
check `code_fence_misplaced` shows which translations still have a broken code block.
