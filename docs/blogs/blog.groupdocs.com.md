# blog.groupdocs.com

**Monitor only** (`fix_channel: none`, SK 2026-10-30): we find and track its issues; SK's team does not fix them and
no longer translates its posts. Tenant `groupdocs.com`, repo `/Users/Apple/Work/Aspose/GitHub/blog.groupdocs.com-PROD`.

## Scan 1 with all checks (19 Nov 2026, SK: "scan blog.groupdocs.com as well")

- Full `run_cycle.py` (26 min, link check 22 min); clone pulled to 4726a3d0. Runs: discovery 3, crawl audit 14 + 21,
  speed 16, AI 15, text 17, link 18, repo 19. Snapshot 2026-11-19-2 "Full scan 19 Nov, all checks (monitor only)";
  live page before it downloaded as 2026-11-19.
- **Health 69 → 50**, issue types 15 → 39 (24 new, all from checks added since 7 Nov; none of the 15 old ones
  resolved), open items 5,579 → 19,141. Areas: crawl 89 → 75, on-page 92, languages 83 → 78, AI 95, speed 100.
  Search: 8,511 clicks / 515k impressions (28 days to 16 Nov).
- Items fixed since the 3 Nov baseline: 241 (120 missing translations, 56 links to missing translations, 55 old-URL
  links, 10 broken links), by whoever edits the blog.

| Biggest open | Size |
|---|---|
| `<head>` ends early (Open Graph, Twitter, JSON-LD in `<body>`; same theme bug as blog.conholdate.cloud/.com) | 32 of 37 sampled pages; 6,122 clicks |
| Links to another language although a translation exists | 6,213 links |
| Post title / description length (repo) | 5,014 / 5,112 posts |
| Junk Redirects.json entries | 1,191 |
| Post bodies with their own H1 | 664 |
| Translations not a translation (garbled) | 137 |
| hreflang without x-default, no llms.txt | site-wide |
| Posts cut off mid-sentence | 37 |

## Audit correction (19 Nov)

- `/page/N/` matched the `post` URL template (`/<category>/<slug>/`), so the 2 sampled page-2 listings (tenant
  `audit.extra_urls`) were counted as posts and "Sitemap URLs canonicalize to a different URL" was scaled to 1,101
  pages. Real issue: page 2+ canonical → home page (2 pages, in no sitemap). Tenant gained a `paginated` template;
  crawl re-run as run 21 (2 pages). Health unchanged (25% minimum share).
- Same miscount on blog.groupdocs.cloud (922) and blog.aspose.cloud (1,125): the `paginated` template was added to
  all other tenants the same day (blog.aspose.com `/p/N/`); their counts correct at the next crawl. The blog fix
  (playbook row 25) is documented for every blog except this one: **SK, 19 Nov: "we won't fix blog.groupdocs.com"**.
