# Commit check for blog.aspose.com

Checks every change to `Aspose/aspose-blog` for problems that break the site or hide it from search, and stops a deploy that would publish them.

**Status (11 Nov 2026):** built and tested locally; drafts only. Nothing runs on GitHub yet.

## Why

Three commits in one week caused real damage:

| Commit | Date | What broke | Effect |
|---|---|---|---|
| c099f6e | 2 Nov | `Redirects.json` became invalid JSON (missing commas) | Every old URL returned 404 instead of redirecting, until fixed on 3 Nov |
| e1e04d8582 | 3 Nov | A Persian translation had a stray `}` in a shortcode | The Hugo build failed |
| 241f3d2239 | 3 Nov | `head.html` put the language switcher (a `<div>`) at the top of `<head>` | Browsers and Google ended `<head>` early; title, canonical, hreflang and robots landed in `<body>` on ~28,800 translated pages, until fixed on 7 Nov |

The check catches all three. Tested on those exact commits, it fails each one.

## How it works: three layers, one script

```
push to aspose-blog master
   │
   ├─▶ 1. Push check (in aspose-blog, ~1–2 min)   ✓/✗ on the commit, email to the person who pushed
   │
   ├─▶ 2. Watch (in aspose-blog-workflows, every 15 min)   reads the push check's ✓/✗; email to SK on ✗
   │
   └─▶ 3. Deploy gate (AWS 08:00, Ceph 11:00 PKT, Mon–Fri)   runs the check again; on ✗ nothing deploys
```

| Layer | File | Runs | Checks | On failure |
|---|---|---|---|---|
| 1. Push check | aspose-blog `.github/workflows/commit-check.yml` | Every push to master | Exactly the commits in that push | Red ✗ on the commit; GitHub emails the person who pushed |
| 2. Watch | aspose-blog-workflows `.github/workflows/commit-watch.yml` | Every 15 min | Nothing itself: reads layer 1's results. Also fails if a push got no check at all | GitHub emails SK (he last edited the schedule) |
| 3. Deploy gate | aspose-blog-workflows `commit-check.yml`, called by both production pipelines | Before each deploy (scheduled or manual) | Everything since the commit the last complete deploy shipped | No deploy; the pipeline run fails and SK gets the build failure email he already receives |

- The script lives once, in aspose-blog `tools/commit_check.py` (source: this repo, `scripts/commit_check.py`). Layers 1 and 3 run that copy.
- **Redirects.json is special:** the redirect function on AWS reads it straight from the repo, with no deploy step. So layer 3 can't protect it. Layers 1 and 2 only alert, within minutes, so the commit can be reverted fast.
- What deploys is master as it is now. A later commit that fixes a problem clears the gate, even if an earlier push failed.

## What it checks

**Fail** = the deploy stops. **Warn** = reported only.

| Check | Level | Looks at | Example |
|---|---|---|---|
| Redirects.json is valid JSON | Fail | The whole file, every time | c099f6e: missing commas |
| New redirect source can never match | Fail | Entries added in the range | A host in the key, raw `{{ revealButtonHref }}` |
| New redirect target empty or not https | Warn | Entries added in the range | `http://…` target |
| New redirect points at itself | Warn | Entries added in the range | `/a/` → `https://blog.aspose.com/a/` |
| Hugo config does not parse | Fail | Every `config*.yml` | A YAML syntax error |
| Hugo shortcode damaged | Fail | Every changed post file, no limit | e1e04d8582: `caption="…"} >}}`; `{{<` and `>}}` counts differ |
| Code fences differ from the English post | Warn | Every changed translation | An extra or missing ```` ``` ```` |
| Front matter does not parse | Warn | Changed post files | A missing `---` block |
| `url` without a leading slash | Warn | Changed post files | `url: de/post/` (publishes under `/de/de/…`) |
| Hugo build fails | Fail | A sample build (below) | Any build error, shown with Hugo's own message |
| SEO tags land in `<body>` | Fail | Every page of the sample build | 241f3d2239: title, canonical, hreflang, robots in `<body>` |
| Page without `<title>` or canonical | Fail | Every page of the sample build | A template that drops the canonical |

The shortcode and code-fence checks come from the translation agent's own guards (`conholdate/blog-translation-agent`, commit c261e54). Here they run on the repo, so they also catch damage from any other source.

### The sample build

A full build of blog.aspose.com takes hours, so the check builds a small copy (seconds):

| Part | Pages |
|---|---|
| Posts changed in the range | Up to 10, newest first, with all their translations |
| If no post changed | The 3 newest posts |
| Fixed control set (always) | The post with the most translations, the newest English-only post, the newest post with a gist |
| Built from those | Home page, product section, category and tag pages, page 2 of the listings |

Why the control set: the head bug touched no post and showed only on translated pages. Testing only the changed posts would have missed it.

Time: 7–15 s on a Mac, about 600–2,000 pages checked.

## What the team sees

| Situation | Where |
|---|---|
| Push passes | Green ✓ next to the commit on GitHub |
| Push fails | Red ✗ next to the commit, plus an email to the pusher. "Details" opens a summary: check, count, first example, and the full list in the log |
| Deploy blocked | The pipeline run in aspose-blog-workflows fails at "commit-check"; no product deploys |
| Urgent deploy despite a false alarm | Run the pipeline by hand with **"Deploy even if the commit check fails"** ticked; the run records who did it |

## Tests (11 Nov 2026, local Hugo 0.120)

| Commit | Expected | Result |
|---|---|---|
| c099f6e (Redirects.json) | Fail | Fail: invalid JSON + 25 new bad entries with line numbers |
| e1e04d8582 (shortcode) | Fail | Fail: `index.fa.md` stray `}`, plus Hugo's error |
| 241f3d2239 (head.html) | Fail | Fail: 617 of 641 pages with SEO tags in `<body>` |
| b76c2369eb (head fix) | Pass | Pass |
| master (9 Nov) | Pass | Pass, 7 s |
| All changes since 4 Nov (23 posts) | Pass | Pass, 2,057 pages |
| All 877 files changed since 1 Oct (no build) | No false alarms | Pass |

Offline tests: `tests/test_commit_check.py` (8 tests, a tiny git repo, no Hugo).

Run it by hand:

```bash
.venv/bin/python scripts/commit_check.py <path to aspose-blog> [--rev <commit>] [--base <commit> | --since <ISO date>] --hugo <hugo binary>
```

`--no-build` skips the Hugo build (static checks only); `--json out.json` writes the result.

## Known limits

| Limit | Impact |
|---|---|
| Redirects.json can't be blocked, only alerted | A broken file is live until reverted; alert in 1–2 min (layer 1) or 15–30 min (layer 2). The lasting fix belongs to the owner of the AWS redirect function: keep using the last valid file when a new one doesn't parse |
| A push to a branch other than master | Layer 2 would report "check missing" (false alarm); the team pushes only to master today |
| Push between the gate's check and the deploy job (a few minutes) | That push deploys without the gate's check; layer 1 still checks it |
| `REPO_TOKEN` must read aspose-blog's Actions results and push history | If not, layer 2 and the gate's base lookup fail on their first run |
| GitHub schedules often start late | Layer 2 can lag 15–30 min |

## Rollout (each push needs SK's approval)

1. Review these drafts.
2. Check `REPO_TOKEN` permissions in aspose-blog-workflows.
3. Push to aspose-blog: `.github/workflows/commit-check.yml` and `tools/commit_check.py`. Test with a harmless commit.
4. Push to aspose-blog-workflows: `commit-watch.yml`, `commit-check.yml`, both pipelines. Manual pipeline run.
5. Two weeks of watching for false alarms; then decide whether the warnings start blocking.
6. Later: the other four blogs SK's team fixes (blog.groupdocs.com: monitor only), and a commits page on the report site.

## Files

| Draft here | Target |
|---|---|
| `aspose-blog/commit-check.yml` | aspose-blog `.github/workflows/commit-check.yml` |
| `../../scripts/commit_check.py` | aspose-blog `tools/commit_check.py` |
| `aspose-blog-workflows/commit-watch.yml` | aspose-blog-workflows `.github/workflows/commit-watch.yml` |
| `aspose-blog-workflows/commit-check.yml` | aspose-blog-workflows `.github/workflows/commit-check.yml` |
| `aspose-blog-workflows/aws-production-pipeline.yml` | aspose-blog-workflows `.github/workflows/aws-production-pipeline.yml` (changed) |
| `aspose-blog-workflows/ceph-production-pipeline.yml` | aspose-blog-workflows `.github/workflows/ceph-production-pipeline.yml` (changed, same as AWS) |
