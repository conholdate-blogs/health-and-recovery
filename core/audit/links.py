"""Link auditor for multilingual Hugo blogs: every internal link in every post, read from the site's source repo
(read-only), checked against the live site.

- Links come from the repo's Markdown (`content/**/index.md`, `index.<lang>.md`): inline `[text](url)`, reference
  `[n]: url` and HTML `href="url"`, outside code blocks; only links to the same host. A post's URL is its `url`
  front matter; its language is the file name's (`index.md` = default language).
- Whether a target exists is judged on the live site, never from the repo: a path listed in the host's sitemaps
  (latest discovery run) exists; any other target is fetched once (GET, redirects followed: 200 = exists,
  404/410 = missing; anything else stays unchecked and is not reported). Whether a translation exists (for wrong
  language links) is judged from the sitemaps only, so English links to untranslated posts cost no requests.
- Per link on a page in language L (default language D):
  link_wrong_language      the target exists, but the page in L links to another language although /L/<path>
                           exists (or a page in D links to a translation)
  link_missing_translation the link is /L/<path>, which does not exist, while <path> (default language) does
  link_damaged             the link does not exist, but a repaired URL does: '//' collapsed, or a cut-off slug that
                           the same post's default-language file links in full
  link_broken              the link does not exist and cannot be repaired (also when the default-language post
                           has the same broken link: it was copied)
- Translation sets (only with `translation_languages` in the tenant YAML): translation_partial = a post translated
  into some supported languages but not all; language_unsupported = the sitemaps publish a language that is not
  supported (its pages are listed with no translated posts behind them).
- Every issue records its file and line; with git available, the commit that wrote the line (`git blame`: id,
  date and message, never the author), and whether that commit matches the tenant's
  `audit.links.translation_commits` pattern.

Findings: one per check and host, listing every affected page (the Prioritizer scores exactly those pages); the
full fix list (file, line, link, correct target, commit) is in the run report.
"""

from __future__ import annotations

import re
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

from core.findings import FindingIds, make_finding

AUDITOR = "link-audit"
MAX_LOCATIONS = 40  # per finding; the run report keeps every issue
STALE_DAYS = 7  # warn when the local clone's last commit is older

# check -> (dimension, type, title, expected, fix_tier, effort)
CHECKS = {
    "link_missing_translation": ("intl", "broken", "Translated posts link to translations that do not exist",
                                 "Links to the default-language post when the target has no translation", 1, "S"),
    "link_damaged": ("intl", "broken", "Translated posts contain damaged internal links",
                     "Each internal link exactly as in the original post, in the page's language when that "
                     "translation exists", 1, "S"),
    "link_wrong_language": ("intl", "incorrect", "Posts link to another language although a translation exists",
                            "Internal links point at the post in the page's own language", 1, "S"),
    "link_broken": ("crawl", "broken", "Posts link to blog pages that do not exist",
                    "Every internal link points at a live page", 1, "M"),
    "translation_partial": ("intl", "incorrect", "Posts translated into only some supported languages",
                            "A translated post exists in every supported language", 1, "S"),
    "language_unsupported": ("intl", "improvable", "Sitemaps publish languages that are not supported",
                             "Only supported languages in the sitemaps and the site's language list", 1, "S"),
}

_FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_URL = re.compile(r"^url:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.M)
_DRAFT = re.compile(r"^draft:\s*['\"]?true", re.M | re.I)
_NAME = re.compile(r"^index(?:\.([A-Za-z]{2,3}(?:-[A-Za-z]+)?))?\.md$")
_FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.M | re.S)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_LINKS = (
    re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)"),  # [text](url "title")
    re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*<?(\S+?)>?(?:[ \t]+[\"'(].*)?$", re.M),  # [n]: url
    re.compile(r"\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I),  # <a href="url">
)
# Downloadable files (sample inputs and results in posts), not pages. Not .js/.net/.html/.php: blog slugs end in
# "node.js", "for-.net" or "<product>.html"; .php links are WordPress leftovers that really are pages.
_FILE_EXT = re.compile(r"\.(png|jpe?g|gif|svg|webp|ico|bmp|tiff?|emf|wmf|psd|eps|pdf|zip|gz|tar|7z|rar|xml|txt|json|"
                       r"ya?ml|md|csv|tsv|css|mp3|wav|ogg|mp4|webm|avi|mov|docx?|xlsx?|pptx?|rtf|od[tsp]|epub|xps|"
                       r"dwg|dxf|msg|eml|mpp|vsdx?|woff2?|ttf|otf)$", re.I)


def norm_path(path: str) -> str:
    """Decoded path with a trailing slash; double slashes are kept (they are a finding)."""
    p = unquote(path.split("#", 1)[0].split("?", 1)[0]).strip()
    return p if p.endswith("/") else p + "/"


def read_post(path: Path) -> tuple[str | None, bool, str, int]:
    """(url, draft, text, body start offset) of a post file; line endings normalized to \\n."""
    text = path.read_text("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    fm = _FM.match(text)
    if not fm:
        return None, False, text, 0
    u = _URL.search(fm.group(1))
    return (u.group(1).strip() if u else None), bool(_DRAFT.search(fm.group(1))), text, fm.end()


def mask_code(text: str) -> str:
    """Blank out fenced and inline code (keeping offsets and line numbers): links in code samples are not links."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))  # noqa: E731
    return _INLINE_CODE.sub(blank, _FENCE.sub(blank, text))


def internal_links(text: str, start: int, host: str) -> list[tuple[str, str, int]]:
    """(raw link, path, line) for every link to `host` in the body (text[start:])."""
    body = mask_code(text)
    out = []
    for rx in _LINKS:
        for m in rx.finditer(body, start):
            raw = m.group(1).strip()
            if raw.startswith(("http://", "https://")):
                parts = urlsplit(raw)
                if parts.netloc.lower() != host:
                    continue
                path = parts.path or "/"
            elif raw.startswith("/") and not raw.startswith("//"):
                path = raw
            else:
                continue
            if _FILE_EXT.search(path.split("#", 1)[0].split("?", 1)[0]):
                continue
            out.append((raw, norm_path(path), text.count("\n", 0, m.start(1)) + 1))
    return sorted(set(out), key=lambda x: (x[2], x[1], x[0]))


@dataclass
class Post:
    file: Path
    rel: str
    folder: str
    lang: str
    path: str  # normalized URL path
    text: str
    body_start: int
    links: list = field(default_factory=list)


class LinkAudit:
    def __init__(self, tenant, fetcher, store, inventory_db, hosts=None, max_live: int = 5000, blame: bool = True,
                 log=print, now=time.time):
        self.tenant, self.fetcher, self.store = tenant, fetcher, store
        self.inventory = inventory_db
        raw = tenant.raw
        self.cfg = (raw.get("audit") or {}).get("links") or {}
        self.default_lang = (raw.get("audit") or {}).get("default_lang") or "en"
        self.langs = [lg for lg in raw.get("languages") or [] if lg != self.default_lang]
        self.supported = raw.get("translation_languages")
        self.agent_rx = re.compile(self.cfg["translation_commits"]) if self.cfg.get("translation_commits") else None
        repos = {h["host"]: h.get("local_path") for h in tenant.hosts}
        self.hosts = [h for h in tenant.host_names if (not hosts or h in hosts) and repos.get(h)]
        self.repos = {h: Path(repos[h]) for h in self.hosts}
        self.fix_channels = {h["host"]: h.get("fix_channel") for h in tenant.hosts}
        self.max_live, self.blame, self.now = max_live, blame, now
        self.log = log or (lambda *_: None)
        self.live: dict[str, int | str] = {}  # url -> status (int) or error text
        self.live_requests = 0
        self.results: dict = {}
        self.run_id: int | None = None

    # ---- live site ----

    def sitemap_paths(self, host: str) -> tuple[int | None, set[str], Counter]:
        """(discovery run, normalized paths in the sitemaps, URLs per language) from the latest discovery run."""
        row = self.inventory.execute("SELECT MAX(run_id) FROM urls WHERE host = ?", (host,)).fetchone()
        run = row[0] if row else None
        if run is None:
            return None, set(), Counter()
        paths, langs = set(), Counter()
        for url, lang in self.inventory.execute("SELECT url, lang FROM urls WHERE run_id = ? AND host = ?",
                                                (run, host)):
            paths.add(norm_path(urlsplit(url).path or "/"))
            langs[lang or self.default_lang] += 1
        return run, paths, langs

    def live_status(self, host: str, path: str) -> int | str:
        url = f"https://{host}{path}"
        if url not in self.live:
            if self.live_requests >= self.max_live:
                self.live[url] = "not checked"
            else:
                res = self.fetcher.get(url)
                self.live_requests += 1
                if res.status == 404 and path.endswith((".html/", ".htm/")):
                    res = self.fetcher.get(url[:-1])  # a static file: norm_path's trailing slash hides it
                    self.live_requests += 1
                self.live[url] = res.status if res.status is not None else (res.error or "no response")
        return self.live[url]

    # ---- repo ----

    def load_posts(self, host: str) -> tuple[list[Post], list[str]]:
        repo = self.repos[host]
        posts, skipped = [], []
        for f in sorted(repo.glob("content/**/index*.md")):
            m = _NAME.match(f.name)
            if not m:
                continue
            url, draft, text, start = read_post(f)
            rel = str(f.relative_to(repo))
            if draft:
                continue
            if not url:
                skipped.append(rel)
                continue
            lang = m.group(1) or self.default_lang
            if not url.startswith("/"):  # Hugo publishes a relative url under the language: th/x/ -> /th/th/x/
                url = f"/{url}" if lang == self.default_lang else f"/{lang}/{url}"
            posts.append(Post(f, rel, str(f.parent.relative_to(repo)), lang, norm_path(url), text, start))
        return posts, skipped

    def repo_state(self, host: str) -> dict:
        repo = self.repos[host]
        try:
            out = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%h %ct %s"], capture_output=True,
                                 text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return {"path": str(repo), "commit": None}
        sha, ts, subject = (out.split(" ", 2) + ["", ""])[:3]
        age = (self.now() - int(ts)) / 86400 if ts.isdigit() else None
        return {"path": str(repo), "commit": sha, "date": time.strftime("%Y-%m-%d", time.gmtime(int(ts))),
                "subject": subject, "age_days": round(age, 1) if age is not None else None,
                "stale": age is not None and age > STALE_DAYS}

    def blame_lines(self, host: str, rel: str) -> dict[int, dict]:
        try:
            out = subprocess.run(["git", "-C", str(self.repos[host]), "blame", "--line-porcelain", rel],
                                 capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            return {}
        lines, cur = {}, {}
        for row in out.splitlines():
            if re.match(r"^[0-9a-f]{40} \d+ \d+", row):
                sha, _, final = row.split()[:3]
                cur = {"commit": sha[:8], "line": int(final)}
            elif row.startswith("author-time "):
                cur["date"] = time.strftime("%Y-%m-%d", time.gmtime(int(row[12:])))
            elif row.startswith("summary "):
                cur["summary"] = row[8:]
            elif row.startswith("\t"):
                lines[cur["line"]] = dict(cur)
        return lines

    # ---- checks ----

    def split_lang(self, path: str) -> tuple[str | None, str]:
        seg = path.split("/", 2)
        if len(seg) > 2 and seg[1] in self.langs:
            return seg[1], "/" + seg[2]
        return None, path

    def localized(self, lang: str, rest: str) -> str:
        return rest if lang == self.default_lang else f"/{lang}{rest}"

    def classify(self, host: str, post: Post, path: str, known: set[str], en_links: list[str]) -> tuple | None:
        """(check, correct target or None, note) for one link, or None when it is fine or unchecked."""
        link_lang, rest = self.split_lang(path)
        page_lang = post.lang
        exists = path in known
        if not exists:
            st = self.live_status(host, path)
            if not isinstance(st, int) or st not in (200, 404, 410):
                return None  # unchecked (limit, error, 5xx): never reported
            exists = st == 200
        if exists:
            own = self.localized(page_lang, rest)
            if (link_lang or self.default_lang) != page_lang and own != path and own in known:
                return "link_wrong_language", own, f"the {page_lang} page exists"
            return None
        if link_lang == page_lang != self.default_lang and (rest in known or self.live_status(host, rest) == 200):
            return "link_missing_translation", rest, f"no {page_lang} translation of {rest}"
        repaired = self.repair(path, rest, page_lang, known, en_links)
        if repaired:
            return "link_damaged", repaired, "damaged URL"
        copied = rest in {self.split_lang(p)[1] for p in en_links} and page_lang != self.default_lang
        return "link_broken", None, "same broken link in the original post" if copied else "page does not exist"

    def repair(self, path: str, rest: str, lang: str, known: set[str], en_links: list[str]) -> str | None:
        candidates = []
        if "//" in path:
            fixed = re.sub(r"/{2,}", "/", path)
            candidates += [fixed, self.localized(lang, self.split_lang(fixed)[1]), self.split_lang(fixed)[1]]
        stem = rest.rstrip("/")
        if len(stem) > 8:
            for p in en_links:
                full = self.split_lang(p)[1]
                if full != rest and full.startswith(stem):
                    candidates += [self.localized(lang, full), full]
        return next((c for c in candidates if c in known), None)

    def check_host(self, host: str) -> dict:
        run, known, sitemap_langs = self.sitemap_paths(host)
        posts, skipped = self.load_posts(host)
        by_folder: dict[str, dict[str, Post]] = defaultdict(dict)
        for p in posts:
            by_folder[p.folder][p.lang] = p
        issues, counts = [], Counter()
        for p in posts:
            original = by_folder[p.folder].get(self.default_lang)
            en_links = [x[1] for x in internal_links(original.text, original.body_start, host)] if original else []
            for raw, path, line in internal_links(p.text, p.body_start, host):
                counts["links"] += 1
                verdict = self.classify(host, p, path, known, en_links)
                if verdict:
                    check, fix, note = verdict
                    issues.append({"check": check, "lang": p.lang, "page": f"https://{host}{p.path}",
                                   "file": p.rel, "line": line, "link": raw,
                                   "fix": f"https://{host}{fix}" if fix else None, "note": note})
        if self.blame:
            for rel in sorted({i["file"] for i in issues}):
                lines = self.blame_lines(host, rel)
                for i in (i for i in issues if i["file"] == rel):
                    b = lines.get(i["line"]) or {}
                    if b:
                        # no author: reports name issues, never people; the commit id finds it in git
                        i["commit"] = f"{b['commit']} {b.get('date')}: {b.get('summary', '')}"
                        i["by_translation_commit"] = bool(self.agent_rx and self.agent_rx.search(b.get("summary", "")))
        sets = self.translation_sets(host, by_folder, sitemap_langs)
        live = Counter(v == "not checked" for u, v in self.live.items() if urlsplit(u).netloc == host)
        return {"repo": self.repo_state(host), "discovery_run": run, "sitemap_paths": len(known),
                "posts": len(posts), "posts_without_url": skipped, "links": counts["links"],
                "live_checked": live[False], "not_checked": live[True], "issues": issues, **sets}

    def translation_sets(self, host: str, by_folder: dict, sitemap_langs: Counter) -> dict:
        if not self.supported:
            return {"partial": [], "unsupported": {}}
        supported = set(self.supported)
        partial = []
        for folder, files in sorted(by_folder.items()):
            have = set(files) - {self.default_lang}
            if have and not supported <= have and self.default_lang in files:
                partial.append({"page": f"https://{host}{files[self.default_lang].path}", "folder": folder,
                                "missing": sorted(supported - have), "has": len(have & supported)})
        unsupported = {lg: n for lg, n in sitemap_langs.items() if lg != self.default_lang and lg not in supported}
        return {"partial": partial, "unsupported": unsupported}

    def run(self) -> dict:
        started = time.monotonic()
        params = {"hosts": self.hosts, "max_live": self.max_live, "blame": self.blame}
        self.run_id = self.store.start_run(self.tenant.property, AUDITOR, params)
        for host in self.hosts:
            self.results[host] = r = self.check_host(host)
            if r["repo"].get("stale"):
                self.log(f"{host}: local clone's last commit is {r['repo']['age_days']} days old "
                         f"({r['repo']['date']}); pull it for current results")
            self.log(f"{host}: {r['posts']} posts, {r['links']:,} internal links, {len(r['issues'])} issues, "
                     f"{r['live_checked']} targets checked live")
        report = {"tenant": self.tenant.property, "auditor": AUDITOR, "run_id": self.run_id, "params": params,
                  "requests": self.fetcher.requests, "duration_s": round(time.monotonic() - started, 1),
                  "stopped_early": False, "summary": summarize(self.results)}
        report["findings"] = self.findings()
        self.store.finish_run(self.run_id, {k: v for k, v in report.items() if k != "findings"})
        report["hosts"] = self.results
        return report

    # ---- findings ----

    def _finding(self, ids, check, host, urls, observed, locations, affected) -> dict:
        dimension, ftype, title, expected, tier, effort = CHECKS[check]
        f = make_finding(ids=ids, tenant=self.tenant.property, subdomain=host, template="post", dimension=dimension,
                         type=ftype, check=check, title=title, urls=urls, observed=observed, expected=expected,
                         affected_pages=affected, effort=effort, fix_tier=tier, fix_channel=self.fix_channels.get(host))
        f["evidence"]["locations"] = locations[:MAX_LOCATIONS]
        return f

    def findings(self) -> list[dict]:
        ids = FindingIds()
        out = []
        for host, r in sorted(self.results.items()):
            by_check = defaultdict(list)
            for i in r["issues"]:
                by_check[i["check"]].append(i)
            for check in CHECKS:
                items = by_check.get(check)
                if not items:
                    continue
                pages = sorted({i["page"] for i in items})
                targets = {i["link"] for i in items}
                langs = Counter(i["lang"] for i in items)
                observed = (f"{len(items):,} links on {len(pages):,} pages ({len(targets):,} distinct targets); "
                            f"by language: {', '.join(f'{lg} {n}' for lg, n in langs.most_common(8))}"
                            f"{', ...' if len(langs) > 8 else ''}")
                agent = sum(1 for i in items if i.get("by_translation_commit"))
                if self.agent_rx:
                    observed += f"; {agent:,} written by translation commits"
                if check == "link_broken":
                    copied = sum(1 for i in items if i["note"].startswith("same broken"))
                    if copied:
                        observed += f"; {copied:,} copied from the original post"
                # separate fields, so the report can lay out page, link, fix, file and commit on their own lines
                locs = [{"role": "link", "url": i["link"] if i["link"].startswith("http") else f"https://{host}{i['link']}",
                         "page": i["page"], "file": i["file"], "line": i["line"], "fix": i["fix"],
                         "commit": i.get("commit")}
                        for i in sorted(items, key=lambda i: (i["page"], i["line"]))]
                out.append(self._finding(ids, check, host, pages, observed, locs, len(pages)))
            if r["partial"]:
                missing = Counter(lg for p in r["partial"] for lg in p["missing"])
                observed = (f"{len(r['partial'])} posts lack some supported languages "
                            f"(missing: {', '.join(f'{lg} {n}' for lg, n in missing.most_common())})")
                locs = [{"role": "post", "url": p["page"], "note": f"missing {', '.join(p['missing'])}"}
                        for p in r["partial"]]
                out.append(self._finding(ids, "translation_partial", host, [p["page"] for p in r["partial"]],
                                         observed, locs, len(r["partial"])))
            if r["unsupported"]:
                urls = [f"https://{host}/{lg}/" for lg in sorted(r["unsupported"])]
                listed = ", ".join(f"{lg} ({n} URLs)" for lg, n in sorted(r["unsupported"].items()))
                observed = f"Sitemaps list {listed}; supported: {len(self.supported)} languages"
                locs = [{"role": "language", "url": u, "note": "not a supported translation language"} for u in urls]
                out.append(self._finding(ids, "language_unsupported", host, urls, observed, locs,
                                         sum(r["unsupported"].values())))
        return out


def summarize(results: dict) -> dict:
    """Per host, what the report's reference table shows."""
    out = {}
    for host, r in results.items():
        issues = r["issues"]
        out[host] = {
            "repo": {k: r["repo"].get(k) for k in ("commit", "date", "stale")},
            "posts": r["posts"], "links": r["links"], "live_checked": r["live_checked"],
            "not_checked": r["not_checked"],
            "by_check": dict(Counter(i["check"] for i in issues)),
            "by_translation_commit": sum(1 for i in issues if i.get("by_translation_commit")),
            "partial": len(r["partial"]), "unsupported": sorted(r["unsupported"]),
            "posts_without_url": len(r["posts_without_url"]),
        }
    return out


def audit(tenant, fetcher, store, inventory_db, **kw) -> dict:
    return LinkAudit(tenant, fetcher, store, inventory_db, **kw).run()


def import_report(findings_store, report: dict) -> dict:
    """Record a link-audit report in the findings store; the run checked its hosts in full."""
    return findings_store.import_run(report["findings"], f"{AUDITOR}-run{report['run_id']}", AUDITOR,
                                     hosts=report["params"]["hosts"], resolve_unsectioned=True)
