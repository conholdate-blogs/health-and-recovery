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
  link_redirected          the link works only through a redirect to another page of the blog (an old URL); the
                           fix is the redirect's target, in the page's language when that exists (SK, 2026-11-06:
                           a 404 link that starts redirecting is not fixed, the post still holds the old URL)
  link_differs_from_original  a translation's reference [n] points at another page than [n] in the default-language
                           post, although it works (only references the text uses; unused definitions are never
                           rendered and are skipped by every check)
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
    "link_redirected": ("crawl", "improvable", "Posts link to old URLs that redirect",
                        "Every internal link points at the page's current URL, not one that redirects", 1, "S"),
    "link_differs_from_original": ("intl", "incorrect", "Translations link another page than the English post",
                                   "Each reference link of a translation points at the same page as in the English "
                                   "post, in the translation's language when that exists", 1, "S"),
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


_REF_DEF = re.compile(r"^[ \t]{0,3}\[([^\]\n]+)\]:[ \t]*<?(\S+?)>?(?:[ \t]+[\"'(].*)?$", re.M)
_REF_USE = re.compile(r"\]\[([^\]\n]*)\]|\[([^\]\n]+)\](?![\[(:])")


def used_labels(body: str) -> set[str]:
    """Reference labels the text uses: [text][label], [label][] and the shortcut [label] (lower case, as Markdown
    matches them). A definition nobody uses is never rendered, so its link is not on the page (17 Nov 2026,
    blog.conholdate.com: a '[15]: …' left over in a post and all its translations)."""
    body = _REF_DEF.sub("", body)
    out = set()
    for m in _REF_USE.finditer(body):
        if m.group(1) is not None:
            if m.group(1):
                out.add(m.group(1).strip().lower())
            else:  # [label][]: the label is the preceding [..]
                pre = body.rfind("[", 0, m.start())
                if pre >= 0:
                    out.add(body[pre + 1:m.start()].strip().lower())
        else:
            out.add(m.group(2).strip().lower())
    return out


def _host_path(raw: str, host: str) -> str | None:
    if raw.startswith(("http://", "https://")):
        parts = urlsplit(raw)
        if parts.netloc.lower() != host:
            return None
        path = parts.path or "/"
    elif raw.startswith("/") and not raw.startswith("//"):
        path = raw
    else:
        return None
    return None if _FILE_EXT.search(path.split("#", 1)[0].split("?", 1)[0]) else path


def internal_links(text: str, start: int, host: str) -> list[tuple[str, str, int]]:
    """(raw link, path, line) for every link to `host` in the body (text[start:]); reference definitions only when
    the text uses their label."""
    body = mask_code(text)
    used = used_labels(body[start:])
    out = []
    for i, rx in enumerate(_LINKS):
        for m in rx.finditer(body, start):
            if i == 1 and m.group(0).strip()[1:].split("]", 1)[0].strip().lower() not in used:
                continue
            raw = m.group(1).strip()
            path = _host_path(raw, host)
            if path is None:
                continue
            out.append((raw, norm_path(path), text.count("\n", 0, m.start(1)) + 1))
    return sorted(set(out), key=lambda x: (x[2], x[1], x[0]))


def reference_links(text: str, start: int, host: str) -> dict[str, tuple[str, str, int]]:
    """label -> (raw link, path, line) of the used reference definitions that point at `host`."""
    body = mask_code(text)
    used = used_labels(body[start:])
    out = {}
    for m in _REF_DEF.finditer(body, start):
        label = m.group(1).strip().lower()
        path = _host_path(m.group(2).strip(), host)
        if label in used and path is not None and label not in out:
            out[label] = (m.group(2).strip(), norm_path(path), text.count("\n", 0, m.start(2)) + 1)
    return out


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
        self.moved: dict[str, str] = {}  # url -> normalized path it redirects to on the same host (old URLs)
        self._index_of, self._index = None, {}  # suggest(): English paths by (section, content words)
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
                if res.redirects and res.final_url:
                    final = urlsplit(res.final_url)
                    target = norm_path(final.path or "/")
                    if final.netloc.lower() == host and target != path:
                        self.moved[url] = target
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

    def created_on(self, host: str, rel: str) -> str | None:
        """Date the file was first committed, following renames (a translation's 'translated on' date)."""
        try:
            out = subprocess.run(["git", "-C", str(self.repos[host]), "log", "--follow", "--format=%as", "--", rel],
                                 capture_output=True, text=True, check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            return None
        return out[-1] if out else None

    def link_added_on(self, host: str, rel: str, text: str) -> dict | None:
        """The newest commit that added or removed `text` in the file (git log -S, following renames): when the
        English post got its current link. Unlike blame, a commit that rewrites the line unchanged does not count."""
        try:
            out = subprocess.run(["git", "-C", str(self.repos[host]), "log", "--follow", "-S", text,
                                  "--format=%h%x09%as%x09%s", "--", rel], capture_output=True, text=True,
                                 check=True).stdout.splitlines()
        except (OSError, subprocess.CalledProcessError):
            return None
        if not out:
            return None
        sha, date, summary = (out[0].split("\t") + ["", ""])[:3]
        return {"commit": sha, "date": date, "summary": summary}

    def add_history(self, host: str, issues: list[dict], by_folder: dict) -> None:
        """For a bad link only translations have (SK, 2026-11-17): did the English post get its current link after
        the translation was made (translation out of date), or did it have it already (the translation introduced
        the bad link)? Compares when the English post last added that link (git log -S) with the translation's
        creation date."""
        def path_of(url):
            return self.split_lang(urlsplit(url).path if url.startswith("http") else url)[1].rstrip("/")

        en_has = {(i["file"].rsplit("/", 1)[0], path_of(i["link"])) for i in issues if i["lang"] == self.default_lang}
        added, created = {}, {}
        folder_of = {p.rel: files for files in by_folder.values() for p in files.values()}
        for i in issues:
            folder_rel = i["file"].rsplit("/", 1)[0]
            if i["lang"] == self.default_lang or (folder_rel, path_of(i["link"])) in en_has:
                continue
            en = (folder_of.get(i["file"]) or {}).get(self.default_lang)
            if not en:
                continue
            wanted = [w for w in (path_of(i["fix"]) if i["fix"] else None, path_of(i["link"])) if w and len(w) > 1]
            w = next((w for w in wanted if w + "/" in en.text or w + ")" in en.text or w + "\n" in en.text), None)
            if not w:
                continue
            if (en.rel, w) not in added:
                added[(en.rel, w)] = self.link_added_on(host, en.rel, w)
            if i["file"] not in created:
                created[i["file"]] = self.created_on(host, i["file"])
            b, made = added[(en.rel, w)], created[i["file"]]
            if b and b.get("date") and made:
                i["history"] = {"english_line": b["date"], "english_commit": f"{b['commit']} {b['date']}: "
                                f"{b['summary']}", "translated": made, "english_newer": b["date"] > made}

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
            target = self.moved.get(f"https://{host}{path}")
            if exists and target:
                own = self.localized(page_lang, self.split_lang(target)[1])
                return "link_redirected", own if own in known else target, f"redirects to {target}"
        if exists:
            own = self.localized(page_lang, rest)
            if (link_lang or self.default_lang) != page_lang and own != path and own in known:
                return "link_wrong_language", own, f"the {page_lang} page exists"
            return None
        if link_lang == page_lang != self.default_lang and (rest in known or self.live_status(host, rest) == 200):
            moved = self.moved.get(f"https://{host}{rest}")  # an old English slug: its current page may be translated
            if moved:
                current = self.split_lang(moved)[1]
                own = self.localized(page_lang, current)
                if own in known:
                    return "link_redirected", own, f"old URL; {rest} redirects to {current}"
                return "link_missing_translation", current, f"no {page_lang} translation of {current}"
            return "link_missing_translation", rest, f"no {page_lang} translation of {rest}"
        repaired = self.repair(path, rest, page_lang, known, en_links)
        if repaired:
            return "link_damaged", repaired, "damaged URL"
        copied = rest in {self.split_lang(p)[1] for p in en_links} and page_lang != self.default_lang
        note = "same broken link in the original post" if copied else "page does not exist"
        guess, how = self.suggest(rest, page_lang, known, en_links)
        if guess:
            if page_lang != self.default_lang and self.split_lang(guess)[0] is None:
                how += f"; no {page_lang} translation of it, so the English page"
            return "link_broken", guess, f"{note}; suggested fix ({how}), check before applying"
        return "link_broken", None, note

    _FILLER = frozenset("a an the in on of to for with by and or using via from".split())

    def _words(self, path: str) -> tuple:
        """Content words of a slug in order: filler words dropped, plurals folded (find-synonyms-in-java =
        find-synonym-in-java); the order counts (convert-word-to-pdf is not convert-pdf-to-word)."""
        slug = path.strip("/").rsplit("/", 1)[-1].lower()
        return tuple(w[:-1] if len(w) > 3 and w.endswith("s") else w
                     for w in re.split(r"[-_]+", slug) if w and w not in self._FILLER)

    def suggest(self, rest: str, lang: str, known: set[str], en_links: list[str]) -> tuple[str | None, str]:
        """A likely target for a broken link (16-17 Nov 2026, blog.conholdate.com: wrong slugs in English posts).
        1. exactly one existing English post with the same content words in the same section;
        2. in a translation: the English original links a very similar existing page (a word changed in translation).
        Anything less certain gives no suggestion: a wrong 'fix' is worse than none."""
        import difflib

        if self._index_of is not known:  # English paths by (section, content words), built once per host
            self._index_of, self._index = known, defaultdict(set)
            for p in known:
                if self.split_lang(p)[0] is None:
                    self._index[(p.strip("/").split("/")[0], self._words(p))].add(p)
        section = rest.strip("/").split("/")[0]
        hits = self._index.get((section, self._words(rest)), set()) - {rest}
        if len(hits) == 1:
            target = next(iter(hits))
            own = self.localized(lang, target)
            return (own if own in known else target), "existing post with the same words"
        if lang != self.default_lang:
            scored = sorted(((difflib.SequenceMatcher(None, rest.lower(), self.split_lang(p)[1].lower()).ratio(),
                              self.split_lang(p)[1]) for p in en_links if self.split_lang(p)[1] in known), reverse=True)
            if scored and scored[0][0] >= 0.9 and (len(scored) == 1 or scored[1][0] < scored[0][0] - 0.05):
                own = self.localized(lang, scored[0][1])
                return (own if own in known else scored[0][1]), "the English post links this page"
        return None, ""

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
            if original and p is not original:
                issues += self.differs_from_original(host, p, original, known, issues)
        if self.blame:
            for rel in sorted({i["file"] for i in issues}):
                lines = self.blame_lines(host, rel)
                for i in (i for i in issues if i["file"] == rel):
                    b = lines.get(i["line"]) or {}
                    if b:
                        # no author: reports name issues, never people; the commit id finds it in git
                        i["commit"] = f"{b['commit']} {b.get('date')}: {b.get('summary', '')}"
                        i["by_translation_commit"] = bool(self.agent_rx and self.agent_rx.search(b.get("summary", "")))
            self.add_history(host, issues, by_folder)
        sets = self.translation_sets(host, by_folder, sitemap_langs)
        live = Counter(v == "not checked" for u, v in self.live.items() if urlsplit(u).netloc == host)
        return {"repo": self.repo_state(host), "discovery_run": run, "sitemap_paths": len(known),
                "posts": len(posts), "posts_without_url": skipped, "links": counts["links"],
                "live_checked": live[False], "not_checked": live[True], "issues": issues, **sets}

    def differs_from_original(self, host: str, p: Post, original: Post, known: set[str], issues: list[dict]
                              ) -> list[dict]:
        """A translation's reference [n] that points at another page than the English post's [n] (17 Nov 2026,
        blog.conholdate.com: '[27] Extract Text from Word…' pointed at the JPG post in th/tr/vi; the link works, so
        no other check saw it). Reported only when the English target exists and the line has no other issue."""
        flagged = {i["line"] for i in issues if i["file"] == p.rel}
        en_refs = reference_links(original.text, original.body_start, host)
        out = []
        for label, (raw, path, line) in reference_links(p.text, p.body_start, host).items():
            if label not in en_refs or line in flagged:
                continue
            en_rest = self.split_lang(en_refs[label][1])[1]
            if self.split_lang(path)[1] == en_rest:
                continue
            if en_rest not in known and self.live_status(host, en_rest) != 200:
                continue
            own = self.localized(p.lang, en_rest)
            fix = own if own in known else en_rest
            out.append({"check": "link_differs_from_original", "lang": p.lang, "page": f"https://{host}{p.path}",
                        "file": p.rel, "line": line, "link": raw, "fix": f"https://{host}{fix}",
                        "note": f"[{label}] in the English post links {en_rest}"})
        return out

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

    def grouped_locations(self, host: str, items: list[dict]) -> list[dict]:
        """One location per post and link target (SK, 2026-11-17: say clearly that the English post has the bad link
        and its translations copied it, instead of 18 rows that each show a translation commit). When the English
        post has the issue, the location is the English line (page, file, commit) with `copies` and `copy_langs`;
        when only translations share it, the first translation stands for the group (`origin: translations`)."""
        def target(i):
            path = urlsplit(i["link"]).path if i["link"].startswith("http") else i["link"]
            return self.split_lang(path)[1].rstrip("/")

        groups: dict[tuple, list[dict]] = defaultdict(list)
        for i in items:
            groups[(i["file"].rsplit("/", 1)[0], target(i))].append(i)
        locs = []
        for members in groups.values():
            members.sort(key=lambda i: (i["lang"] != self.default_lang, i["lang"], i["line"]))
            head, rest = members[0], members[1:]
            # separate fields, so the report can lay out page, link, fix, file and commit on their own lines
            loc = {"role": "link", "url": head["link"] if head["link"].startswith("http") else f"https://{host}{head['link']}",
                   "page": head["page"], "file": head["file"], "line": head["line"], "fix": head["fix"],
                   "commit": head.get("commit")}
            if head["fix"] and "suggested fix" in head["note"]:
                loc["suggested"] = head["note"].split("suggested fix (", 1)[1].split(")", 1)[0]
            if rest:
                loc.update(copies=len(rest), copy_langs=[i["lang"] for i in rest],
                           origin="english" if head["lang"] == self.default_lang else "translations")
            # SK's rule: a translation links the target in its own language when it exists, else the English page,
            # and the missing translation is named (17 Nov 2026)
            missing = [i["lang"] for i in members if i["fix"] and i["lang"] != self.default_lang
                       and self.split_lang(urlsplit(i["fix"]).path)[0] is None]
            if missing:
                loc["no_translation"] = missing
            if head.get("history"):  # only translations have it: introduced by them, or English changed later?
                loc["history"] = head["history"]
            locs.append(loc)
        return sorted(locs, key=lambda x: (x["page"], x["line"]))

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
                locs = self.grouped_locations(host, items)
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
