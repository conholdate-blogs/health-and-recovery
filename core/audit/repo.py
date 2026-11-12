"""Repo file check: what is malformed and committed in a blog's source repo (SK, 2026-11-03, after a blog's
Redirects.json was found invalid), and whether its redirects work on the live site.

- Exact, every one is an item in the ledger (core/items.py), so fixes count one by one: an invalid Redirects.json
  (with the commit that broke it), redirect keys that cannot match a request, self-redirects, bad targets, post
  files whose front matter does not parse, post urls without a leading slash (Hugo publishes them under a doubled
  language).
- Exact, added 2026-11-12 from what the blog.conholdate.cloud session found by hand (the crawl only samples pages):
  search title and description length on every post file, posts outside `params.mainSections` (never on the home
  page), translations older than the English title or description (stale), sections whose `_index.md` exists in
  English only (Hugo builds unlinked stand-ins for the other languages), wrong `languageName` values, right-to-left
  languages without `languageDirection: rtl`, category pages no post uses, and URLs without the trailing slash
  that forward with a temporary (302/307) redirect.
- Sampled, finding level only: redirect_not_working, a live test of well-formed redirect sources. One 404 without a
  redirect is a failure; anything else (a working redirect, a real page at that URL, an error) is not.

Only commit id, date and message are recorded, never the author. Read-only.
"""

from __future__ import annotations

import json
import random
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import yaml

from core.audit.keep_terms import looks_untranslated
from core.findings import FindingIds, make_finding

AUDITOR = "repo-audit"
REDIRECTS = "Redirects.json"
LIVE_SAMPLE = 40
MAX_LOCATIONS = 40  # per finding; the run report keeps every issue
MAX_HISTORY = 30  # Redirects.json commits walked back to find the one that broke it
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_PAIR = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"')
_FM = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
_NAME = re.compile(r"^index(?:\.[A-Za-z]{2,3}(?:-[A-Za-z]+)?)?\.md$")
_NON_ASCII = re.compile(r"[^\x00-\x7f]")
_TEXT_KEYS = re.compile(r"^(seoTitle|title|description|summary):")
TEMPLATES = {"llms_txt_outdated": "host", "llms_txt_charset": "host", "menu_id_invalid": "config",
             "menu_id_missing": "config",
             "menu_id_wrong_script": "config",
             "language_name_wrong": "config", "rtl_direction_missing": "config", "slash_redirect_temporary": "host",
             "section_index_untranslated": "listing", "category_page_unused": "listing"}
STALE_SIMILARITY = 0.75  # below this the English title or description counts as rewritten, not trimmed
RTL = {"ar", "fa", "he", "ur", "ps", "yi"}
# Native language names accepted in a language menu (casefolded); a code not listed here is not checked.
NATIVE_NAMES = {
    "en": ["english"], "ar": ["العربية", "عربي"], "bg": ["български"], "cs": ["čeština"], "da": ["dansk"],
    "de": ["deutsch"], "el": ["ελληνικά"], "es": ["español"], "fa": ["فارسی"], "fi": ["suomi"],
    "fr": ["français"], "he": ["עברית"], "hi": ["हिन्दी", "हिंदी"], "hu": ["magyar"], "id": ["bahasa indonesia"],
    "it": ["italiano"], "ja": ["日本語"], "ko": ["한국어"], "ms": ["bahasa melayu"], "nl": ["nederlands"],
    "no": ["norsk"], "pl": ["polski"], "pt": ["português"], "ro": ["română"], "ru": ["русский"],
    "sk": ["slovenčina"], "sv": ["svenska"], "th": ["ไทย"], "tr": ["türkçe"], "uk": ["українська"],
    "vi": ["tiếng việt"], "zh": ["中文", "简体中文", "中文(简体)", "中文（简体）"],
    "zh-hant": ["繁體中文", "正體中文", "中文(繁體)", "中文（繁體）"], "zh-tw": ["繁體中文", "正體中文"],
}

# check -> (dimension, type, title, expected, fix_tier, effort)
CHECKS = {
    "redirect_file_invalid": ("crawl", "broken", "Redirects.json is not valid JSON",
                              "Redirects.json parses as JSON, checked before every merge", 1, "S"),
    "redirect_not_working": ("crawl", "broken", "Redirects in Redirects.json do not work on the live site",
                             "Every well-formed source answers with a redirect to its target", 3, "M"),
    # Internal name kept (finding keys and ledger items stay); since 2026-11-11 it covers every junk entry (SK's rule:
    # no redirect for junk URLs; every post URL is English, translations only add a language prefix).
    "redirect_key_malformed": ("crawl", "improvable", "Junk entries in Redirects.json",
                               "Every source is a real blog URL: an English path starting with /, without a host, "
                               "# fragment, {{ placeholder }}, double slash or non-English slug", 1, "S"),
    "redirect_self_loop": ("crawl", "incorrect", "Redirects that point at themselves",
                           "A redirect's target differs from its source", 1, "S"),
    "redirect_target_bad": ("crawl", "improvable", "Redirect targets that are empty or not https",
                            "Every target is a full https URL", 1, "S"),
    "post_front_matter_broken": ("crawl", "broken", "Post files whose front matter does not parse",
                                 "Every post file starts with a valid front matter block", 1, "S"),
    "post_url_relative": ("crawl", "incorrect", "Post urls without a leading slash",
                          "A post's url starts with /", 1, "S"),
    "translated_url_mismatch": ("intl", "incorrect",
                                "Translations published under a different URL than the English post",
                                "A translation's URL is the English post's URL with only its language prefix added",
                                3, "M"),
    "post_title_length": ("onpage", "improvable", "Post search titles too long or too short",
                          "Every post's search title (seoTitle, else title) is 10-70 characters wide "
                          "(CJK count double)",
                          1, "S"),
    "post_description_length": ("onpage", "improvable", "Post descriptions too long or too short",
                                "Every post's description (description, else summary) is 50-170 characters wide",
                                1, "S"),
    "post_text_untranslated": ("intl", "incorrect", "Translations that keep the English title or description",
                               "A translation's seoTitle, title and description are in its own language", 3, "M"),
    "post_outside_main_sections": ("crawl", "incorrect", "Posts outside the home page's sections",
                                   "Every post folder is under a section listed in params.mainSections", 1, "S"),
    "translation_stale": ("intl", "improvable", "Translations older than the English title or description",
                          "A translation is updated whenever the English title or description changes", 3, "M"),
    "section_index_untranslated": ("intl", "incorrect", "Section pages with an English-only _index.md",
                                   "A section with _index.md has _index.<lang>.md for every language it has posts in",
                                   1, "S"),
    "language_name_wrong": ("intl", "incorrect", "Language menu shows a wrong language name",
                            "Each language's languageName is its own name in that language (日本語, not 日本)", 1, "S"),
    "rtl_direction_missing": ("intl", "improvable", "Right-to-left languages render left to right",
                              "Arabic, Persian, Hebrew (and other RTL languages) set languageDirection: rtl", 1, "S"),
    # the company menu bar a menu service draws from params.dynamicmenuid (12 Nov 2026: missing on zh-hant pages)
    "menu_id_invalid": ("ux", "incorrect", "Company menu bar missing in a language",
                        "Each language's menu id is <venture>-<language>, two parts: the menu script rejects more",
                        1, "S"),
    "menu_id_missing": ("ux", "improvable", "Company menu bar in English on translated pages",
                        "Every language has its own menu id in params.dynamicmenuid", 1, "S"),
    "menu_id_wrong_script": ("ux", "improvable", "Traditional Chinese pages show the Simplified Chinese menu",
                             "zh-hant / zh-tw pages use the Traditional Chinese menu (<venture>-zht)", 1, "S"),
    "llms_txt_outdated": ("ai", "improvable", "llms.txt misses the newest posts",
                          "llms.txt lists the newest posts (built from the content on every deploy)", 1, "S"),
    "llms_txt_charset": ("ai", "improvable", "llms.txt served without charset=utf-8",
                         "llms.txt is served as text/plain; charset=utf-8 when it holds non-ASCII text", 1, "S"),
    "category_page_unused": ("crawl", "improvable", "Category pages no post uses",
                             "Every content/categories/<name>/_index.md belongs to a category that posts use", 1, "S"),
    "slash_redirect_temporary": ("crawl", "improvable", "URLs without the trailing slash forward with a 302",
                                 "A URL without its trailing slash answers a permanent redirect (301/308)", 3, "S"),
}


def key_problem(key: str) -> str | None:
    """Why a redirect source is a junk entry, or None (SK, 2026-11-11: junk URLs get no redirect).

    Some can never match a request (placeholder, host, fragment); the others may still redirect (a double slash
    answers 301 on every blog; non-ASCII slugs do on some), but no real blog URL looks like that. Junk entries are
    left out of the live redirect sample, so redirect_not_working measures real redirects only."""
    if "{{" in unquote(key) or "revealbuttonhref" in key.lower():  # raw or percent-encoded
        return "gist placeholder {{ revealButtonHref }}"
    if not key.startswith("/"):
        return "host or scheme in the key"
    if "#" in key or "%23" in key.lower():
        return "fragment in the key (#, never sent by browsers)"  # e.g. a copied #:~:text= scroll-to-text link
    if "//" in key:
        return "double slash"
    if _NON_ASCII.search(unquote(key)):
        return "non-English slug"
    return None


def parse_pairs(text: str) -> list[tuple[int, str, str]]:
    """(line, source, target) per entry, line by line, so an invalid file can still be read."""
    return [(n, m.group(1), m.group(2)) for n, line in enumerate(text.splitlines(), 1) if (m := _PAIR.match(line))]


def json_error(text: str) -> str | None:
    try:
        json.loads(text)
    except ValueError as e:
        return f"line {getattr(e, 'lineno', '?')}: {getattr(e, 'msg', e)}"
    return None


class RepoAudit:
    def __init__(self, tenant, fetcher, store, hosts=None, sample: int = LIVE_SAMPLE, log=print):
        self.tenant, self.fetcher, self.store, self.sample = tenant, fetcher, store, sample
        repos = {h["host"]: h.get("local_path") for h in tenant.hosts}
        self.hosts = [h for h in tenant.host_names if (not hosts or h in hosts) and repos.get(h)]
        self.repos = {h: Path(repos[h]) for h in self.hosts}
        self.fix_channels = {h["host"]: h.get("fix_channel") for h in tenant.hosts}
        self.log = log or (lambda *_: None)
        self.results: dict = {}
        self.run_id: int | None = None

    def git(self, host: str, *args: str) -> str:
        try:
            return subprocess.run(["git", "-C", str(self.repos[host]), *args], capture_output=True, text=True,
                                  errors="replace").stdout
        except OSError:
            return ""

    def broke_it(self, host: str) -> str | None:
        """The oldest commit of the current invalid stretch: id, date, message."""
        found = None
        for row in self.git(host, "log", f"-{MAX_HISTORY}", "--format=%h %cs %s", "--", REDIRECTS).splitlines():
            sha = row.split()[0]
            if not json_error(self.git(host, "show", f"{sha}:{REDIRECTS}").lstrip("﻿")):
                break
            found = row
        return found

    def last_commit(self, host: str, rel: str) -> str:
        return self.git(host, "log", "-1", "--format=%h %cs %s", "--", rel).strip()

    def line_commits(self, host: str) -> dict[int, str]:
        """Redirects.json line -> the commit that wrote it (git blame; no author)."""
        lines, cur = {}, {}
        for row in self.git(host, "blame", "--line-porcelain", REDIRECTS).splitlines():
            if re.match(r"^[0-9a-f]{40} \d+ \d+", row):
                sha, _, final = row.split()[:3]
                cur = {"sha": sha[:8], "line": int(final)}
            elif row.startswith("author-time "):
                cur["date"] = time.strftime("%Y-%m-%d", time.gmtime(int(row[12:])))
            elif row.startswith("summary "):
                cur["summary"] = row[8:]
            elif row.startswith("\t"):
                lines[cur["line"]] = f"{cur['sha']} {cur.get('date')}: {cur.get('summary', '')}"
        return lines

    def check_redirects(self, host: str) -> tuple[list[dict], dict]:
        f = self.repos[host] / REDIRECTS
        if not f.is_file():
            return [], {"present": False}
        text = f.read_text("utf-8", "replace").lstrip("﻿")
        pairs = parse_pairs(text)
        error = json_error(text)
        info: dict = {"present": True, "entries": len(pairs), "invalid": error, "broke_it": None}
        issues = []
        blame = self.line_commits(host)

        def add(check, line, link, note, fix=None):
            issues.append({"check": check, "file": REDIRECTS, "line": line, "link": link, "note": note, "fix": fix,
                           "page": f"https://{host}{link}" if link and link.startswith("/") else None,
                           "commit": blame.get(line)})

        if error:
            info["broke_it"] = self.broke_it(host)
            add("redirect_file_invalid", 0, None, f"{error}; since {info['broke_it'] or 'unknown'}")
        for line, src, target in pairs:
            problem = key_problem(src)
            if problem:
                add("redirect_key_malformed", line, src, problem, target)
            if not target.strip() or not target.startswith("https://"):
                add("redirect_target_bad", line, src, f"target: {target or 'empty'}")
            elif src.startswith("/") and urlsplit(target).netloc == host and urlsplit(target).path == src:
                add("redirect_self_loop", line, src, "target is the source")
        info["live"] = self.live_test(host, [(s, t) for _, s, t in pairs if not key_problem(s)])
        return issues, info

    def live_test(self, host: str, pairs: list[tuple[str, str]]) -> dict:
        """A fixed sample per host (same seed each run), so runs compare the same redirects while the file holds."""
        chosen = random.Random(host).sample(sorted(pairs), min(self.sample, len(pairs)))
        tally: Counter = Counter()
        failed = []
        for src, _ in chosen:
            res = self.fetcher.get(f"https://{host}{quote(src, safe='/%+.,~-_=&?:@!$()*;')}")
            if res.redirects:
                tally["redirected"] += 1
            elif res.status in (404, 410):
                tally["not_working"] += 1
                failed.append(src)
            else:
                tally["other"] += 1
        return {"eligible": len(pairs), "sampled": len(chosen), **tally, "failed": failed}

    def file_commits(self, host: str) -> dict[str, tuple[int, str]]:
        """content file -> (commit time, "sha date message") of its last commit: one git log pass, not one per file."""
        out: dict[str, tuple[int, str]] = {}
        cur = None
        for row in self.git(host, "log", "--format=%x00%ct %h %cs %s", "--name-only", "--", "content").splitlines():
            if row.startswith("\x00"):
                t, _, rest = row[1:].partition(" ")
                cur = (int(t), rest)
            elif row and cur and row not in out:
                out[row] = cur
        return out

    def text_changes(self, host: str) -> dict[str, int]:
        """English post file -> commit time of the last change to its title, seoTitle, description or summary line."""
        out: dict[str, int] = {}
        t = None
        for row in self.git(host, "log", "-G", _TEXT_KEYS.pattern, "--format=%x00%ct", "--name-only", "--",
                            "content").splitlines():
            if row.startswith("\x00"):
                t = int(row[1:])
            elif row.endswith("/index.md") and t and row not in out:
                out[row] = t
        return out

    def config(self, host: str) -> dict:
        f = self.repos[host] / "config.yml"
        try:
            data = yaml.load(f.read_text("utf-8", "replace"), Loader=_LOADER) if f.is_file() else None
        except yaml.YAMLError:
            return {}
        return data if isinstance(data, dict) else {}

    def check_posts(self, host: str) -> tuple[list[dict], int]:
        from core.audit.crawl import DESCRIPTION_LEN, TITLE_LEN, display_len

        repo = self.repos[host]
        issues, posts = [], 0
        commits = self.file_commits(host)
        cfg = self.config(host)
        main = [str(m).strip("/") for m in ((cfg.get("params") or {}).get("mainSections") or [])]
        langs = cfg.get("languages") if isinstance(cfg.get("languages"), dict) else {}
        default = str(cfg.get("defaultContentLanguage") or "en")

        def commit(rel):
            return commits.get(rel, (0, None))[1] or self.last_commit(host, rel)

        urls: dict[str, dict[str, tuple[str, str]]] = {}  # post folder -> language ("" = English) -> (url, file)
        section_langs: dict[str, set] = {}  # top-level and nested content dirs -> languages with posts there
        stale_candidates = []
        posts_by_date: list[tuple[str, str, str]] = []  # English posts: (date, page, file), for the llms.txt check
        texts: dict[str, dict[str, tuple[dict, str, str | None]]] = {}  # folder -> language -> (values, file, page)
        cats_used: set[str] = set()
        for f in sorted(repo.glob("content/**/index*.md")):
            if not _NAME.match(f.name):
                continue
            posts += 1
            rel = str(f.relative_to(repo))
            text = f.read_text("utf-8", "replace").lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
            m = _FM.match(text)
            if not m:
                first = text.split("\n", 1)[0][:40]
                issues.append({"check": "post_front_matter_broken", "file": rel, "line": 1, "link": None, "page": None,
                               "fix": None, "note": f"no front matter block; line 1: {first!r}", "commit": commit(rel)})
                continue
            try:
                data = yaml.load(m.group(1), Loader=_LOADER)
            except yaml.YAMLError as e:
                issues.append({"check": "post_front_matter_broken", "file": rel, "line": 1, "link": None, "page": None,
                               "fix": None, "note": str(e).splitlines()[0][:100], "commit": commit(rel)})
                continue
            if not isinstance(data, dict) or data.get("draft"):
                continue
            lang = f.name[len("index."):-len(".md")] if f.name != "index.md" else ""
            url = data.get("url")
            if url and not str(url).startswith("/"):
                issues.append({"check": "post_url_relative", "file": rel, "line": 1, "link": str(url), "fix": f"/{url}",
                               "page": None, "note": "published under a doubled language", "commit": commit(rel)})
            page = f"https://{host}{url}" if url and str(url).startswith("/") else None
            if url:
                urls.setdefault(str(f.parent.relative_to(repo)), {})[lang] = (str(url).strip(), rel)
            for cat in data.get("categories") or []:
                cats_used.add(str(cat).strip().lower())
            title = str(data.get("seoTitle") or data.get("title") or "")
            desc = str(data.get("description") or data.get("summary") or "")
            for check, val, (lo, hi) in (("post_title_length", title, TITLE_LEN),
                                         ("post_description_length", desc, DESCRIPTION_LEN)):
                w = display_len(val)
                if not lo <= w <= hi:
                    issues.append({"check": check, "file": rel, "line": 1, "link": None, "page": page, "fix": None,
                                   "note": f"{'too long' if w > hi else 'too short'} (width {w}): {val[:80]!r}",
                                   "commit": commit(rel)})
            parts = Path(rel).parts[1:-1]  # under content/, without the file
            if main and parts and parts[0] not in main:
                issues.append({"check": "post_outside_main_sections", "file": rel, "line": 1, "link": None,
                               "page": page, "fix": f"move under content/{main[0]}/ (its url keeps the URL)",
                               "note": f"in content/{parts[0]}/; mainSections: {', '.join(main)}",
                               "commit": commit(rel)})
            for i in range(1, len(parts)):
                section_langs.setdefault("/".join(parts[:i]), set()).add(lang or default)
            if lang:
                stale_candidates.append((rel, str(f.parent.relative_to(repo) / "index.md"), page))
            elif page and data.get("date"):
                posts_by_date.append((str(data["date"])[:10], page, rel))
            texts.setdefault(str(f.parent.relative_to(repo)), {})[lang] = (
                {k: str(data.get(k) or "") for k in ("seoTitle", "title", "description")}, rel, page)
        issues += self.check_translated_urls(host, urls, commit)
        issues += self.check_stale(host, stale_candidates, commits, commit)
        issues += self.check_untranslated(host, texts, commit)
        issues += self.check_sections(host, section_langs, langs, default, commit)
        issues += self.check_categories(host, cats_used, commit)
        issues += self.check_languages(host, langs)
        issues += self.check_menu_ids(host, langs, (cfg.get("params") or {}).get("dynamicmenuid"))
        issues += self.check_slash(host, urls)
        issues += self.check_llms(host, posts_by_date)
        return issues, posts

    def front_matter_at(self, host: str, rev: str, rel: str) -> dict:
        text = self.git(host, "show", f"{rev}:{rel}").lstrip("\ufeff").replace("\r\n", "\n")
        m = _FM.match(text)
        try:
            data = yaml.load(m.group(1), Loader=_LOADER) if m else None
        except yaml.YAMLError:
            return {}
        return data if isinstance(data, dict) else {}

    def check_stale(self, host, candidates, commits, commit) -> list[dict]:
        """A translation whose English title or description was rewritten after the translation's last commit (the
        Blog Optimization Agent rewrote blog.conholdate.com's English titles in March 2026; the translations kept the
        old ones). The dates only pick candidates; the English values at the translation's last commit are then
        compared with today's, and only a rewrite counts (similarity below STALE_SIMILARITY), not a trim or a
        reformatting of the same text."""
        from difflib import SequenceMatcher

        if not candidates:
            return []
        changed = self.text_changes(host)
        repo, out, now_cache, then_cache = self.repos[host], [], {}, {}
        for rel, en, page in candidates:
            en_t, (tr_t, tr_commit) = changed.get(en), commits.get(rel, (0, None))
            if not (en_t and tr_t and tr_t < en_t and tr_commit):
                continue
            sha = tr_commit.split()[0]
            if en not in now_cache:
                now_cache[en] = self.front_matter_at(host, "HEAD", en) if (repo / en).is_file() else {}
            if (sha, en) not in then_cache:
                then_cache[(sha, en)] = self.front_matter_at(host, sha, en)
            now, then = now_cache[en], then_cache[(sha, en)]
            if not then:
                continue  # the English file did not exist (or sat elsewhere) at the translation's commit
            rewritten = []
            for keys in (("seoTitle", "title"), ("description", "summary")):
                old = str(next((then[k] for k in keys if then.get(k)), "") or "")
                new = str(next((now[k] for k in keys if now.get(k)), "") or "")
                if old and new and old != new and SequenceMatcher(None, old, new).ratio() < STALE_SIMILARITY:
                    rewritten.append(f"{keys[0]}: {old[:50]!r} -> {new[:50]!r}")
            if rewritten:
                out.append({"check": "translation_stale", "file": rel, "line": 1, "link": None, "page": page,
                            "fix": f"re-translate from {en}",
                            "note": f"English rewritten {time.strftime('%Y-%m-%d', time.gmtime(en_t))} after the "
                                    f"translation ({time.strftime('%Y-%m-%d', time.gmtime(tr_t))}); "
                                    + "; ".join(rewritten),
                            "commit": commit(rel)})
        return out

    def check_untranslated(self, host, texts, commit) -> list[dict]:
        """A translation whose seoTitle, title or description is the English value word for word (the crawl check
        title_untranslated sees only crawled pages; this reads every file). Words a translation keeps in English do not
        count (core/audit/keep_terms.py)."""
        keep = ((self.tenant.raw.get("audit") or {}).get("translation") or {}).get("keep_terms")
        out = []
        for folder in sorted(texts):
            by = texts[folder]
            if "" not in by:
                continue
            en = by[""][0]
            for lang, (vals, rel, page) in sorted(by.items()):
                if not lang:
                    continue
                same = [k for k, v in vals.items() if v and v == en.get(k) and looks_untranslated(v, host, keep)]
                if same:
                    out.append({"check": "post_text_untranslated", "file": rel, "line": 1, "link": None, "page": page,
                                "fix": f"translate {', '.join(same)}",
                                "note": "; ".join(f"{k} in English: {vals[k][:60]!r}" for k in same),
                                "commit": commit(rel)})
        return out

    def check_sections(self, host, section_langs, langs, default, commit) -> list[dict]:
        """A section whose _index.md exists only in English: Hugo builds the other languages' section pages on its own,
        and those are not linked to the English one as translations (no hreflang, no x-default; blog.conholdate.cloud
        titled them "Conholdate.Clouds")."""
        if any(isinstance(v, dict) and v.get("contentDir") for v in langs.values()):
            return []  # one folder per language: translations pair by path, not by file name
        repo, out = self.repos[host], []
        for section, have in sorted(section_langs.items()):
            d = repo / "content" / section
            if section.split("/")[0] in ("categories", "tags") or not (d / "_index.md").is_file():
                continue
            missing = sorted(lang for lang in have if lang != default and not (d / f"_index.{lang}.md").is_file())
            for lang in missing:
                rel = f"content/{section}/_index.md"
                out.append({"check": "section_index_untranslated", "file": f"content/{section}/_index.{lang}.md",
                            "line": 0, "link": None, "page": None, "fix": f"add content/{section}/_index.{lang}.md",
                            "note": f"{lang} posts in a section whose _index.md is English only",
                            "commit": commit(rel)})
        return out

    def check_categories(self, host, used, commit) -> list[dict]:
        out = []
        for f in sorted((self.repos[host] / "content" / "categories").glob("*/_index*.md")):
            rel = str(f.relative_to(self.repos[host]))
            text = f.read_text("utf-8", "replace")
            m = _FM.match(text.lstrip("\ufeff").replace("\r\n", "\n"))
            try:
                title = str((yaml.load(m.group(1), Loader=_LOADER) or {}).get("title") or "") if m else ""
            except yaml.YAMLError:
                title = ""
            names = {f.parent.name.lower(), title.strip().lower(), f.parent.name.lower().replace("-", " ")}
            if not names & used and not any(n.replace(" ", "-") == f.parent.name.lower() for n in used):
                out.append({"check": "category_page_unused", "file": rel, "line": 1, "link": None,
                            "page": f"https://{host}/categories/{f.parent.name}/", "fix": "delete the file",
                            "note": f"no post has category {title or f.parent.name!r}", "commit": commit(rel)})
        return out

    def check_languages(self, host, langs) -> list[dict]:
        out = []
        for code, v in langs.items():
            v = v if isinstance(v, dict) else {}
            code = str(code).lower()
            name = str(v.get("languageName") or "").strip()
            accepted = NATIVE_NAMES.get(code)
            if accepted and name and name.casefold() not in accepted:
                out.append({"check": "language_name_wrong", "file": "config.yml", "line": 0, "link": code,
                            "page": None, "fix": accepted[0][:1].upper() + accepted[0][1:],
                            "note": f"{code}: languageName {name!r}", "commit": None})
            if code.split("-")[0] in RTL and str(v.get("languageDirection") or "").lower() != "rtl":
                out.append({"check": "rtl_direction_missing", "file": "config.yml", "line": 0, "link": code,
                            "page": f"https://{host}/{code}/", "fix": "languageDirection: rtl",
                            "note": f"{code}: languageDirection {v.get('languageDirection') or 'not set'}",
                            "commit": None})
        return out

    def check_menu_ids(self, host, langs, ids) -> list[dict]:
        """The theme looks up params.dynamicmenuid by each language's languageCode and hands it to a menu script that
        splits it on "-" and accepts exactly two parts (venture, language): "x-zh-hant" draws no bar at all. A
        language without an id gets the default (English) menu."""
        if not isinstance(ids, dict) or not ids:
            return []
        out = []
        for code, v in langs.items():
            v = v if isinstance(v, dict) else {}
            key = str(v.get("languageCode") or code)
            mid = ids.get(key)
            page = f"https://{host}/{code}/" if code != "en" else f"https://{host}/"
            if mid is None:
                if str(code) != "en":
                    out.append({"check": "menu_id_missing", "file": "config.yml", "line": 0, "link": str(code),
                                "page": page, "fix": f"params.dynamicmenuid.{key}: <venture>-{key}",
                                "note": f"{code}: no menu id, so the English menu is shown", "commit": None})
                continue
            parts = str(mid).split("-")
            if len(parts) != 2:
                fix = f"{parts[0]}-zht" if key.lower() in ("zh-hant", "zh-tw") else f"{parts[0]}-{''.join(parts[1:])}"
                out.append({"check": "menu_id_invalid", "file": "config.yml", "line": 0, "link": str(code),
                            "page": page,
                            "fix": fix, "note": f"{code}: menu id {mid!r} has {len(parts)} parts; the menu script "
                            "rejects it and draws no bar", "commit": None})
            elif key.lower() in ("zh-hant", "zh-tw") and parts[1].lower() == "zh":
                out.append({"check": "menu_id_wrong_script", "file": "config.yml", "line": 0, "link": str(code),
                            "page": page, "fix": f"{parts[0]}-zht",
                            "note": f"{code}: menu id {mid!r} is the Simplified Chinese menu", "commit": None})
        return out

    def check_llms(self, host: str, posts: list) -> list[dict]:
        """The live llms.txt lists N posts; the newest N English posts should all be among them (12 Nov 2026: a
        hand-made file goes stale as posts and translations land daily). No llms.txt: the AI audit reports that."""
        if not posts:
            return []
        res = self.fetcher.get(f"https://{host}/llms.txt")
        body = res.body.decode("utf-8", "replace") if res.status == 200 and res.body else ""
        if not body or "<html" in body[:500].lower():
            return []
        out = []
        ctype = (res.headers or {}).get("content-type", "")
        if _NON_ASCII.search(body) and "charset" not in ctype.lower():  # browsers then guess and garble it
            out.append({"check": "llms_txt_charset", "file": "llms.txt", "line": 0, "link": f"https://{host}/llms.txt",
                        "page": f"https://{host}/llms.txt", "fix": "serve .txt as text/plain; charset=utf-8",
                        "note": f"content-type {ctype or 'missing'} for a file with non-ASCII text", "commit": None})
        listed = {u.rstrip("/") + "/" for u in re.findall(r"\]\((https?://[^)\s]+)\)", body)}
        n = sum(1 for _, page, _ in posts if page.rstrip("/") + "/" in listed)
        newest = sorted(posts, reverse=True)[:max(n, 1)]
        return out + [{"check": "llms_txt_outdated", "file": "llms.txt", "line": 0, "link": page, "page": page,
                       "fix": "list it (generate llms.txt from the content at build)",
                       "note": f"post of {d} missing from llms.txt ({n} posts listed)", "commit": None}
                      for d, page, _ in newest if page.rstrip("/") + "/" not in listed]

    def check_slash(self, host: str, urls: dict) -> list[dict]:
        """A few URLs without their trailing slash (a post, the tags list, a language home): does the host forward
        them with a permanent redirect? S3 website hosting answers 302 for folders."""
        en = sorted(u for by in urls.values() if "" in by and (u := by[""][0]).startswith("/") and u != "/")
        paths = ([en[0]] if en else []) + ["/tags/"]
        out = []
        for p in paths:
            bare = "/" + p.strip("/")
            res = self.fetcher.get(f"https://{host}{quote(bare, safe='/%-._~')}")
            codes = res.redirect_statuses
            if codes and codes[0] in (302, 307) and res.status == 200:
                out.append({"check": "slash_redirect_temporary", "file": "(host)", "line": 0, "link": bare,
                            "page": f"https://{host}{bare}", "fix": "301 to the URL with /",
                            "note": f"{codes[0]} to {res.final_url}", "commit": None})
        return out

    def check_translated_urls(self, host: str, urls: dict[str, dict[str, tuple[str, str]]], commit=None) -> list[dict]:
        """A translation is published at the English post's URL with only its language prefix added (SK, 2026-11-11:
        every post URL is English; a translated slug or another prefix is an error). Hugo adds the language prefix
        itself to a url without a leading slash, so effective paths are compared, not the raw front matter."""
        def path(url: str, lang: str) -> str:
            p = url if url.startswith("/") else (f"/{lang}/" if lang else "/") + url
            return "/" + p.strip("/")

        issues = []
        for folder in sorted(urls):
            by = urls[folder]
            if "" not in by:
                continue
            en = path(by[""][0], "")
            for lang, (url, rel) in sorted(by.items()):
                if not lang or not url.startswith("/"):
                    continue  # a url without a leading slash is reported once, as post_url_relative
                got, want = path(url, lang), f"/{lang}{en}"
                if got == want:
                    continue
                first, _, rest = got.lstrip("/").partition("/")
                if got == en:
                    note = "same URL as the English post (no language prefix)"
                elif first == lang:
                    note = "own slug (translated or changed)"
                elif "/" + rest == en:
                    note = f"language prefix {first} on a {lang} post"
                else:
                    note = "other"
                issues.append({"check": "translated_url_mismatch", "file": rel, "line": 1, "link": url,
                               "fix": want + "/", "page": f"https://{host}{got}/", "note": note,
                               "commit": commit(rel) if commit else self.last_commit(host, rel)})
        return issues

    def run(self) -> dict:
        started = time.monotonic()
        params = {"hosts": self.hosts, "sample": self.sample}
        self.run_id = self.store.start_run(self.tenant.property, AUDITOR, params)
        for host in self.hosts:
            red_issues, redirects = self.check_redirects(host)
            post_issues, posts = self.check_posts(host)
            issues = red_issues + post_issues
            self.results[host] = {"commit": self.last_commit(host, "."), "posts": posts, "redirects": redirects,
                                  "issues": issues}
            self.log(f"{host}: {len(issues)} issues, {posts} post files, redirects {redirects.get('live')}")
        report = {"tenant": self.tenant.property, "auditor": AUDITOR, "run_id": self.run_id, "params": params,
                  "requests": self.fetcher.requests, "duration_s": round(time.monotonic() - started, 1),
                  "stopped_early": False, "summary": summarize(self.results)}
        report["findings"] = self.findings()
        self.store.finish_run(self.run_id, {k: v for k, v in report.items() if k != "findings"})
        report["hosts"] = self.results
        return report

    def _finding(self, ids, check, host, urls, observed, locations, affected) -> dict:
        dimension, ftype, title, expected, tier, effort = CHECKS[check]
        template = (REDIRECTS if check.startswith("redirect") else TEMPLATES.get(check, "post"))
        f = make_finding(ids=ids, tenant=self.tenant.property, subdomain=host, template=template, dimension=dimension,
                         type=ftype, check=check, title=title, urls=urls, observed=observed, expected=expected,
                         affected_pages=affected, effort=effort, fix_tier=tier, fix_channel=self.fix_channels.get(host))
        f["evidence"]["locations"] = locations[:MAX_LOCATIONS]
        return f

    def findings(self) -> list[dict]:
        ids = FindingIds()
        out = []
        for host, r in sorted(self.results.items()):
            redirects = r["redirects"]
            entries = redirects.get("entries") or 0
            by_check: dict = {}
            for i in r["issues"]:
                by_check.setdefault(i["check"], []).append(i)
            for check, items in by_check.items():
                if check == "slash_redirect_temporary":  # a live request, not a file: show the URL to try
                    locs = [{"role": "live test", "url": i["page"], "note": f"answers {i['note']}; try: curl -I "
                             f"{i['page']}", "fix": i["fix"]} for i in items]
                else:
                    locs = [{"role": "file", "url": i["page"] or f"https://{host}/", "file": i["file"],
                             "line": i["line"], "note": i["note"], "fix": i["fix"], "commit": i.get("commit")}
                            for i in items]
                urls = [i["page"] for i in items if i["page"]][:10] or [f"https://{host}/"]
                notes = Counter(i["note"] for i in items).most_common(4)
                observed = (items[0]["note"] if check == "redirect_file_invalid" else
                            "Live test (CDN, not a repo file): " + "; ".join(f"{i['page']} answers {i['note']}"
                                                                              for i in items)
                            if check == "slash_redirect_temporary" else
                            f"{len(items):,} entries or files; " + ", ".join(f"{n}: {c:,}" for n, c in notes))
                affected = entries if check == "redirect_file_invalid" else len(items)
                out.append(self._finding(ids, check, host, urls, observed, locs, affected))
            live = redirects.get("live") or {}
            if live.get("not_working"):
                share = live["not_working"] / live["sampled"]
                urls = [f"https://{host}{s}" for s in live["failed"][:10]]
                observed = (f"{live['not_working']} of {live['sampled']} sampled sources return 404 without a redirect "
                            f"({live.get('redirected', 0)} redirect, {live.get('other', 0)} other); "
                            f"{live['eligible']:,} well-formed entries")
                locs = [{"role": "redirect", "url": f"https://{host}{s}", "note": "404, no redirect"}
                        for s in live["failed"]]
                f = self._finding(ids, "redirect_not_working", host, urls, observed, locs,
                                  round(live["eligible"] * share))
                f["evidence"]["live_sample"] = [live["not_working"], live["sampled"]]
                out.append(f)
        return out


def summarize(results: dict) -> dict:
    return {host: {"commit": r["commit"], "posts": r["posts"], "entries": r["redirects"].get("entries"),
                   "invalid": r["redirects"].get("invalid"), "broke_it": r["redirects"].get("broke_it"),
                   "live": {k: v for k, v in (r["redirects"].get("live") or {}).items() if k != "failed"},
                   "by_check": dict(Counter(i["check"] for i in r["issues"]))} for host, r in results.items()}


def audit(tenant, fetcher, store, **kw) -> dict:
    return RepoAudit(tenant, fetcher, store, **kw).run()


def import_report(findings_store, report: dict) -> dict:
    """Record a repo-file report in the findings store; the run checked its hosts in full."""
    return findings_store.import_run(report["findings"], f"{AUDITOR}-run{report['run_id']}", AUDITOR,
                                     hosts=report["params"]["hosts"], resolve_unsectioned=True)
