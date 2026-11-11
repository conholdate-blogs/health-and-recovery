"""Repo file check: what is malformed and committed in a blog's source repo (SK, 2026-11-03, after a blog's
Redirects.json was found invalid), and whether its redirects work on the live site.

- Exact, every one is an item in the ledger (core/items.py), so fixes count one by one: an invalid Redirects.json
  (with the commit that broke it), redirect keys that cannot match a request, self-redirects, bad targets, post
  files whose front matter does not parse, post urls without a leading slash (Hugo publishes them under a doubled
  language).
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

    def check_posts(self, host: str) -> tuple[list[dict], int]:
        repo = self.repos[host]
        issues, posts = [], 0
        for f in sorted(repo.glob("content/**/index*.md")):
            if not _NAME.match(f.name):
                continue
            posts += 1
            rel = str(f.relative_to(repo))
            text = f.read_text("utf-8", "replace").lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
            m = _FM.match(text)
            if not m:
                first = text.split("\n", 1)[0][:40]
                issues.append({"check": "post_front_matter_broken", "file": rel, "line": 1, "link": None, "page": None,
                               "fix": None, "note": f"no front matter block; line 1: {first!r}",
                               "commit": self.last_commit(host, rel)})
                continue
            try:
                data = yaml.load(m.group(1), Loader=_LOADER)
            except yaml.YAMLError as e:
                issues.append({"check": "post_front_matter_broken", "file": rel, "line": 1, "link": None, "page": None,
                               "fix": None, "note": str(e).splitlines()[0][:100],
                               "commit": self.last_commit(host, rel)})
                continue
            url = data.get("url") if isinstance(data, dict) else None
            if url and not data.get("draft") and not str(url).startswith("/"):
                issues.append({"check": "post_url_relative", "file": rel, "line": 1, "link": str(url), "fix": f"/{url}",
                               "page": None, "note": "published under a doubled language",
                               "commit": self.last_commit(host, rel)})
        return issues, posts

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
        template = REDIRECTS if check.startswith("redirect") else "post"
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
                locs = [{"role": "file", "url": i["page"] or f"https://{host}/", "file": i["file"], "line": i["line"],
                         "note": i["note"], "fix": i["fix"], "commit": i.get("commit")} for i in items]
                urls = [i["page"] for i in items if i["page"]][:10] or [f"https://{host}/"]
                notes = Counter(i["note"] for i in items).most_common(4)
                observed = (items[0]["note"] if check == "redirect_file_invalid" else
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
