# blog.conholdate.cloud: log

Next blog in the "scan and fix" program (SK, 2026-11-11: the smallest site, in a separate session, after
blog.conholdate.com's plan was set). Steps: [../playbook.md](../playbook.md). Updated in the same session as every
finding, decision, fix and check.

## Facts (collected 11 Nov 2026; confirm at the start of the session)

| Item | Value |
|---|---|
| Source repo | `conholdate-cloud/blog.conholdate.cloud`, branch **main**; local clone `/Users/Apple/Work/Aspose/GitHub/blog.conholdate.cloud-PROD/blog.conholdate.cloud` (clean, at `d2bc592` 4 Nov) |
| Workflows | **In the blog repo itself**: `.github/workflows/production-aws.yml`, `production-ceph.yml` (+ staging). So the commit check's push check and deploy gate would both live in this one repo |
| Production deploy | cron `0 3 * * 1-5` = **08:00 PKT** Mon–Fri (comment says 10–11 AM: wrong, as on blog.conholdate.com), skipped without new commits (`check-changes`); manual run from the Actions tab |
| Hugo | **0.101.0** extended (`/Users/Apple/Downloads/Softwares/Hugo/hugo_extended_0.101.0_darwin-amd64/hugo`) |
| Redirects.json | 4 entries (`/tag/`, `/category`, `/feed`, `/feed/`). Live or at deploy: **unknown, test first** (blog.conholdate.com applies at deploy) |
| Size (7 Nov) | 5 English posts, 93 post files, 23 languages, 27 tags (all single-post), 186 sitemap URLs, no tag URLs in sitemaps |
| Traffic (28 days to 3 Nov) | 2 clicks, 161 impressions |
| Health (7 Nov) | 86; 7 issue types, 4 open items |
| Theme | PaperMod (like blog.conholdate.com) |

## Open findings at the last scan (7 Nov, before the 11 Nov scan improvements)

| Id | Check | Severity |
|---|---|---|
| intl-0002 | Posts link to another language although a translation exists (4 links, 3 Arabic posts, from a 2025-08-12 commit) | incorrect |
| ai-0001 | Pages show almost no text without JavaScript (listing/category pages) | incorrect |
| intl-0001 | hreflang without x-default | improvable |
| onpage-0001 / 0003 | Description / title length | improvable |
| onpage-0002 | Pages without H1 | improvable |
| ai-0002 | No llms.txt | improvable |

## Plan for the session

1. Confirm the facts above; test whether Redirects.json applies live or at deploy (one harmless check: curl an entry).
2. Full scan with the new checks: `caffeinate -i .venv/bin/python scripts/run_cycle.py conholdate.cloud` (~2 min).
   New checks since the last scan: junk redirect entries, translated URLs, thin tag pages (27 of 27 tags single-post:
   expect a finding), tag pages in sitemaps (none expected).
3. Review, snapshot ("Full scan with the new checks"), update this log.
4. Propose fixes in the playbook order (smallest first), each push approved by SK: the 4 wrong-language links,
   hreflang x-default, tags, then others. Template fixes found here can carry over to blog.conholdate.com (same theme).
5. Verify live, agent-fixes table (`reports/conholdate.cloud/agent-fixes.json`), re-scan, snapshot, push.

## Fixes

None yet.

## Learned here

Nothing yet.
