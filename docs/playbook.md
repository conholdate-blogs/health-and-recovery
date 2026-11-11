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
  and check the rendered DOM in headless Chrome when JavaScript is involved.
- Redirects.json: change line by line, parse before and after, check that every other entry is unchanged.
- After the push: verify live (curl, headless Chrome). If the blog applies changes at deploy, ask SK to run the
  production deploy (or wait for the cron).

## Rules for our own audit

- Before calling something broken, test it live. (The "double slash never matches" rule was wrong: 46 false
  issues.)
- A false finding that was published is **deleted** from the findings store and the item ledger
  (`scripts/ops/drop_false_items.py`), never marked fixed or resolved. Back up `data/<tenant>/findings.sqlite`
  first.
- An unpublished run that used a wrong rule: restore the store from the backup, delete the run's files, re-run.
- Keep internal check names when widening a check (finding keys and ledger items carry on).
- New finding ids carry the date first found (`crawl-261111-1`); old ids stay.

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
