"""Commit check for a Hugo blog repo (SK, 2026-11-10): is what was committed since a base revision safe to deploy?

Built after two commits of 3 Nov 2026 cost search visibility on a blog: one left Redirects.json invalid JSON
(every old URL 404 until fixed), one moved a <div> to the top of <head>, so browsers and Google ended <head> early
and title, canonical, hreflang and robots landed in <body> on every translated page.

    python scripts/commit_check.py <repo> [--rev REV] [--base REV | --since ISO-DATE] [--hugo PATH] [--json OUT]

Checks (fail = exit 1, the deploy should stop; warn = reported only):
- Redirects.json parses as JSON (fail); entries added in the range: source not a plain /path, e.g. a host or raw
  {{ }} in the key, target empty or not https, target equal to its source (warn). With --deploy (the deploy gate)
  every Redirects.json check only warns: the file is read live from the repo, a deploy neither ships nor fixes it.
- Every config*.yml parses (fail).
- Front matter of changed post files parses, url starts with / (warn; old posts already have some).
- Every changed post file (no cap): Hugo shortcode delimiters balanced; a translation keeps the English post's
  shortcode counts and gains no damage pattern ({{< x a=\\"..\\" >}}, a stray } before >}}) (fail: Hugo cannot build
  the product); a translation's ``` count differs from the English post (warn). From blog-translation-agent c261e54.
- Hugo build of a sample: the posts changed in the range (max 10, newest first; else the 3 newest posts) plus a
  fixed control set (the post with the most translations, the newest English-only post, the newest post with a gist),
  their home, section, category, tag and page-2 listing pages. Build error (fail); title, meta description/robots/
  viewport, canonical or hreflang found in <body> (fail); a page without <title> or canonical in <head> (fail).

Reads the repo through git only (git archive of the revision), so it never touches the working tree and can check
any old commit. Standalone on purpose (PyYAML + selectolax, no project imports) so the same file can run in CI.
In GitHub Actions it also writes ::error/::warning annotations and a step summary.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

import yaml
from selectolax.lexbor import LexborHTMLParser

FAIL, WARN = "fail", "warn"
LEVEL = {
    "build_failed": FAIL,
    "seo_tag_in_body": FAIL,
    "seo_tag_missing": FAIL,
    "config_invalid": FAIL,
    "redirects_invalid": FAIL,
    # A key that can never match is a dead entry, not an outage; its source (gist placeholders harvested by
    # crawlers) is not fixed on every blog, so failing on it would raise alarms for harmless entries (SK, 11 Nov).
    "redirect_key_malformed": WARN,
    "redirect_target_bad": WARN,
    "redirect_self_loop": WARN,
    "front_matter_broken": WARN,
    "url_relative": WARN,
    "shortcode_damaged": FAIL,
    "code_fence_mismatch": WARN,
}
TITLE = {
    "build_failed": "Hugo build fails",
    "seo_tag_in_body": "SEO tags land in <body> (<head> ends early)",
    "seo_tag_missing": "Page without <title> or canonical in <head>",
    "config_invalid": "Hugo config does not parse",
    "redirects_invalid": "Redirects.json is not valid JSON",
    "redirect_key_malformed": "New junk entry in Redirects.json",
    "redirect_target_bad": "New redirect target empty or not https",
    "redirect_self_loop": "New redirect points at itself",
    "front_matter_broken": "Changed post: front matter does not parse",
    "url_relative": "Changed post: url without a leading slash",
    "shortcode_damaged": "Changed post: Hugo shortcode damaged (breaks the build)",
    "code_fence_mismatch": "Changed translation: code fences differ from the English post",
}
# Shortcode damage seen in LLM translations (blog-translation-agent, translator._shortcode_syntax_corrupted, c261e54)
DAMAGE = [(r'=\(\\?"', 'value wrapped in ("'), (r'\\"\)', 'value ends with \\")'), (r'=\\"', 'escaped quote =\\"'),
          (r"\}\s*>\}\}", "stray } before >}}")]
DELIMS = [("{{<", ">}}"), ("{{%", "%}}")]
REDIRECTS = "Redirects.json"
# Read live from the repo by the redirect function, never deployed: a deploy gate (--deploy) reports these, never blocks
REDIRECT_CHECKS = {"redirects_invalid", "redirect_key_malformed", "redirect_target_bad", "redirect_self_loop"}
SITE_DIRS = ["layouts", "themes", "static", "assets", "data", "i18n", "archetypes"]
BODY_TAGS = {
    "title": "title",
    "meta description": 'meta[name="description"]',
    "meta robots": 'meta[name="robots"]',
    "meta viewport": 'meta[name="viewport"]',
    "canonical": 'link[rel="canonical"]',
    "hreflang": "link[rel=alternate][hreflang]",
}
MAX_CHANGED = 10
FALLBACK = 3
MAX_PER_CHECK = 30  # locations printed per check
_PAIR = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"')
_FM = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
_INDEX = re.compile(r"^index(?:\.[A-Za-z]{2,3}(?:-[A-Za-z]+)?)?\.md$")
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class Repo:
    def __init__(self, path: str, rev: str):
        self.path, self.rev = path, rev

    def git(self, *args: str, check: bool = True) -> str:
        r = subprocess.run(["git", "-C", self.path, *args], capture_output=True, text=True, errors="replace")
        if check and r.returncode:
            raise SystemExit(f"git {' '.join(args[:3])}: {r.stderr.strip()[:300]}")
        return r.stdout

    def show(self, rel: str) -> str | None:
        r = subprocess.run(["git", "-C", self.path, "show", f"{self.rev}:{rel}"], capture_output=True, text=True,
                           errors="replace")
        return r.stdout.lstrip("﻿") if r.returncode == 0 else None

    def extract(self, paths: list[str], dest: Path) -> None:
        p = subprocess.Popen(["git", "-C", self.path, "archive", "--format=tar", self.rev, "--", *paths],
                             stdout=subprocess.PIPE)
        with tarfile.open(fileobj=p.stdout, mode="r|") as tar:
            tar.extractall(dest, filter="data")
        if p.wait():
            raise SystemExit("git archive failed")


class Result:
    def __init__(self, deploy: bool = False):
        self.items: dict[str, list[str]] = defaultdict(list)
        self.info: list[str] = []
        self.levels = {c: WARN if deploy and c in REDIRECT_CHECKS else lvl for c, lvl in LEVEL.items()}

    def add(self, check: str, where: str) -> None:
        self.items[check].append(where)

    @property
    def failed(self) -> bool:
        return any(self.levels[c] == FAIL for c in self.items)


def key_problem(key: str) -> str | None:
    """Why a redirect source is a junk entry (same rule as the repo check, SK 2026-11-11: no redirect for junk URLs;
    post URLs are English and translations only add a language prefix)."""
    if "{{" in unquote(key) or "revealbuttonhref" in key.lower():
        return "gist placeholder {{ revealButtonHref }}"
    if not key.startswith("/"):
        return "host or scheme in the key"
    if "#" in key or "%23" in key.lower():
        return "fragment in the key (#, never sent by browsers)"
    if "//" in key:
        return "double slash"
    if re.search(r"[^\x00-\x7f]", unquote(key)):
        return "non-English slug"
    return None


def json_error(text: str) -> str | None:
    try:
        json.loads(text)
    except ValueError as e:
        return f"line {getattr(e, 'lineno', '?')}: {getattr(e, 'msg', e)}"
    return None


def resolve_base(repo: Repo, base: str | None, since: str | None) -> str | None:
    if base:
        return repo.git("rev-parse", base).strip()
    if since:
        found = repo.git("rev-list", "-1", f"--before={since}", repo.rev).strip()
        return found or None
    return repo.git("rev-parse", f"{repo.rev}~1", check=False).strip() or None


def check_redirects(repo: Repo, base: str | None, host: str | None, res: Result) -> None:
    text = repo.show(REDIRECTS)
    if text is None:
        return
    err = json_error(text)
    if err:
        res.add("redirects_invalid", f"{REDIRECTS} {err}")
    diff = repo.git("diff", "-U0", base, repo.rev, "--", REDIRECTS) if base else ""
    line = 0
    for row in diff.splitlines():
        if row.startswith("@@"):
            m = re.search(r"\+(\d+)", row)
            line = int(m.group(1)) if m else 0
            continue
        if not row.startswith("+") or row.startswith("+++"):
            continue
        m = _PAIR.match(row[1:])
        if m:
            src, target = m.group(1), m.group(2)
            where = f"{REDIRECTS}:{line} {src}"
            if problem := key_problem(src):
                res.add("redirect_key_malformed", f"{where} ({problem})")
            if not target.strip() or not target.startswith("https://"):
                res.add("redirect_target_bad", f"{where} -> {target or 'empty'}")
            elif host and target.rstrip("/") == f"https://{host}{src}".rstrip("/"):
                res.add("redirect_self_loop", where)
        line += 1


def check_configs(repo: Repo, res: Result) -> list[str]:
    names = [n for n in repo.git("ls-tree", "--name-only", repo.rev).split() if re.match(r"config.*\.ya?ml$", n)]
    for name in names:
        try:
            yaml.load(repo.show(name) or "", Loader=_LOADER)
        except yaml.YAMLError as e:
            res.add("config_invalid", f"{name}: {str(e).splitlines()[0][:120]}")
    return names


def check_front_matter(repo: Repo, changed: list[str], res: Result) -> None:
    for rel in changed:
        if not rel.startswith("content/") or not _INDEX.match(rel.rsplit("/", 1)[-1]):
            continue
        text = (repo.show(rel) or "").replace("\r\n", "\n").replace("\r", "\n")
        m = _FM.match(text)
        if not m:
            res.add("front_matter_broken", f"{rel}: no front matter block")
            continue
        try:
            data = yaml.load(m.group(1), Loader=_LOADER)
        except yaml.YAMLError as e:
            res.add("front_matter_broken", f"{rel}: {str(e).splitlines()[0][:100]}")
            continue
        url = data.get("url") if isinstance(data, dict) else None
        if url and not data.get("draft") and not str(url).startswith("/"):
            res.add("url_relative", f"{rel}: url {url}")


def check_shortcodes(repo: Repo, changed: list[str], res: Result) -> None:
    """Every changed post file, no cap: shortcode delimiters balanced; a translation keeps the English post's shortcode
    and code-fence counts and has no damage pattern the English post lacks (code can contain =\\" legitimately)."""
    english: dict[str, str | None] = {}
    for rel in changed:
        folder, _, name = rel.rpartition("/")
        if not rel.startswith("content/") or not _INDEX.match(name):
            continue
        text = repo.show(rel)
        if text is None:
            continue
        problems = [f"{o} {text.count(o)} vs {c} {text.count(c)}" for o, c in DELIMS if text.count(o) != text.count(c)]
        if name != "index.md":
            if folder not in english:
                english[folder] = repo.show(f"{folder}/index.md")
            en = english[folder]
            if en is not None:
                problems += [f"{d} {text.count(d)} vs English {en.count(d)}" for pair in DELIMS for d in pair
                             if text.count(d) != en.count(d)]
                problems += [label for pat, label in DAMAGE if re.search(pat, text) and not re.search(pat, en)]
                if text.count("```") != en.count("```"):
                    res.add("code_fence_mismatch", f"{rel}: ``` {text.count('```')} vs English {en.count('```')}")
        if problems:
            res.add("shortcode_damaged", f"{rel}: {'; '.join(dict.fromkeys(problems))}")


def choose_sample(repo: Repo, changed: list[str], res: Result) -> list[str]:
    """Post folders to build: changed ones (newest first, capped), else the newest few, plus a fixed control set."""
    files: dict[str, list[str]] = defaultdict(list)
    for rel in repo.git("ls-tree", "-r", "--name-only", repo.rev, "content/").splitlines():
        folder, _, name = rel.rpartition("/")
        if _INDEX.match(name) and folder.count("/") >= 2:
            files[folder].append(name)
    newest = sorted(files, key=lambda f: f.rsplit("/", 1)[-1], reverse=True)

    hit = set()
    for rel in changed:
        parts = rel.split("/")
        for i in range(len(parts) - 1, 0, -1):
            if "/".join(parts[:i]) in files:
                hit.add("/".join(parts[:i]))
                break
    picked = sorted(hit, key=lambda f: f.rsplit("/", 1)[-1], reverse=True)[:MAX_CHANGED]
    why = {f: "changed" for f in picked}
    if len(hit) > MAX_CHANGED:
        res.info.append(f"{len(hit)} post folders changed; built the newest {MAX_CHANGED}")
    if not picked:
        for f in newest[:FALLBACK]:
            why[f] = "newest"
    most = max(newest, key=lambda f: len(files[f]), default=None)
    english_only = next((f for f in newest if files[f] == ["index.md"]), None)
    gist = None
    # gists come as script links (blog.aspose.com) or as Hugo's gist shortcode (blog.conholdate.com)
    grep = repo.git("grep", "-l", "-E", r"gist\.github\.com|\{\{< ?gist ", repo.rev, "--", "content/", check=False)
    gist_folders = {line.split(":", 1)[1].rpartition("/")[0] for line in grep.splitlines() if ":" in line}
    gist = next((f for f in newest if f in gist_folders), None)
    for f, label in ((most, "most translations"), (english_only, "English only"), (gist, "gist")):
        if f and f not in why:
            why[f] = f"control: {label}"
    for f, label in why.items():
        res.info.append(f"sample: {f} ({label}, {len(files[f])} language files)")
    return list(why)


def ancestors_index(repo: Repo, folders: list[str]) -> list[str]:
    """_index*.md files of each sample folder's parent sections, so section pages build as on the site."""
    out = set()
    for f in folders:
        parts = f.split("/")
        for i in range(1, len(parts)):
            d = "/".join(parts[:i])
            for name in repo.git("ls-tree", "--name-only", repo.rev, f"{d}/").splitlines():
                if re.match(r".*/_index(\.[\w-]+)?\.md$", name):
                    out.add(name)
    return sorted(out)


def in_svg(node) -> bool:
    p = node.parent
    while p is not None:
        if p.tag == "svg":
            return True
        p = p.parent
    return False


def check_pages(out: Path, res: Result) -> int:
    checked = 0
    for page in sorted(out.rglob("*.html")):
        if page.name == "404.html" or page.stat().st_size < 1500:
            continue
        raw = page.read_bytes()
        if b'http-equiv="refresh"' in raw[:2000] or b"http-equiv=refresh" in raw[:2000]:
            continue  # alias redirect page
        doc = LexborHTMLParser(raw)
        checked += 1
        rel = str(page.relative_to(out))
        moved = [label for label, sel in BODY_TAGS.items()
                 if [n for n in doc.css(f"body {sel}") if not (label == "title" and in_svg(n))]]
        if moved:
            res.add("seo_tag_in_body", f"{rel}: {', '.join(moved)}")
        missing = [label for label in ("title", "canonical") if not doc.css(f"head {BODY_TAGS[label]}")]
        if missing and not moved:
            res.add("seo_tag_missing", f"{rel}: no {' or '.join(missing)} in <head>")
    return checked


def build_sample(repo: Repo, configs: list[str], folders: list[str], hugo: str, base_url: str | None,
                 res: Result) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        top = set(repo.git("ls-tree", "--name-only", repo.rev).split())
        paths = [d for d in SITE_DIRS if d in top] + configs + folders + ancestors_index(repo, folders)
        repo.extract(paths, work)
        tool = work / "tools/generate_global_post_order.py"
        if repo.show("tools/generate_global_post_order.py") is not None:
            repo.extract(["tools/generate_global_post_order.py"], work)
            subprocess.run([sys.executable, "-I", str(tool)], cwd=work, capture_output=True)
        cfg = ",".join(c for c in ("config.yml", "config.production.yml") if c in configs) or configs[0]
        cmd = [hugo, "--minify", "--config", cfg, "-d", "out"] + (["-b", base_url] if base_url else [])
        env = {**os.environ, "HUGO_PAGINATE": "2"}  # small sample: page 2 of the listings exists
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, env=env)
        if r.returncode:
            lines = [ln.strip() for ln in (r.stderr + "\n" + r.stdout).splitlines() if ln.strip()]
            errors = [ln.replace(str(work.resolve()) + "/", "").replace(str(work) + "/", "")
                      for ln in lines if "ERROR" in ln or "Error" in ln] or lines[-3:]
            res.add("build_failed", " / ".join(errors[:3])[:500] or f"exit {r.returncode}")
            return
        n = check_pages(work / "out", res)
        res.info.append(f"built and checked {n} pages")


def config_value(repo: Repo, configs: list[str], key: str) -> str | None:
    for name in ("config.production.yml", "config.yml"):
        if name in configs:
            try:
                data = yaml.load(repo.show(name) or "", Loader=_LOADER) or {}
            except yaml.YAMLError:
                continue
            if isinstance(data, dict) and data.get(key):
                return str(data[key])
    return None


def report(res: Result, repo: Repo, base: str | None, changed: list[str], out_json: str | None) -> None:
    head = repo.git("log", "-1", "--format=%h %cs %s", repo.rev).strip()
    base_s = repo.git("log", "-1", "--format=%h %cs", base).strip() if base else "none"
    print(f"Commit check: {head}")
    print(f"Range: {base_s} .. {head.split()[0]} ({len(changed)} files changed)")
    for line in res.info:
        print(f"  {line}")
    order = sorted(res.items, key=lambda c: (res.levels[c] != FAIL, c))
    for check in order:
        where = res.items[check]
        print(f"{res.levels[check].upper():4} {TITLE[check]} ({len(where)})")
        for w in where[:MAX_PER_CHECK]:
            print(f"       {w}")
        if len(where) > MAX_PER_CHECK:
            print(f"       ... {len(where) - MAX_PER_CHECK} more")
    verdict = "FAILED" if res.failed else ("PASSED with warnings" if res.items else "PASSED")
    print(verdict)
    if os.environ.get("GITHUB_ACTIONS"):
        for check in order:
            kind = "error" if res.levels[check] == FAIL else "warning"
            print(f"::{kind} title={TITLE[check]}::{len(res.items[check])}: {res.items[check][0][:300]}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            rows = [f"## Commit check: {verdict}", "", f"`{head}` (since {base_s}, {len(changed)} files changed)", "",
                    "| Level | Check | Count | First |", "|---|---|---|---|"]
            rows += [f"| {res.levels[c]} | {TITLE[c]} | {len(res.items[c])} | `{res.items[c][0][:120]}` |"
                     for c in order]
            with open(summary, "a") as f:
                f.write("\n".join(rows + ["", *[f"- {i}" for i in res.info], ""]) + "\n")
    if out_json:
        Path(out_json).write_text(json.dumps({
            "commit": head, "base": base_s, "changed": len(changed), "passed": not res.failed, "info": res.info,
            "checks": {c: {"level": res.levels[c], "title": TITLE[c], "items": res.items[c]} for c in order},
        }, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo")
    ap.add_argument("--rev", default="HEAD", help="revision to check (default HEAD)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--base", help="compare with this revision (default REV~1)")
    g.add_argument("--since", help="compare with the last commit before this date (e.g. the last complete deploy)")
    ap.add_argument("--hugo", default="hugo")
    ap.add_argument("--no-build", action="store_true", help="skip the Hugo sample build")
    ap.add_argument("--json", help="write the result as JSON")
    ap.add_argument("--deploy", action="store_true",
                    help="deploy gate: Redirects.json problems warn instead of fail (the deploy does not ship it)")
    args = ap.parse_args()

    repo = Repo(args.repo, args.rev)
    repo.rev = repo.git("rev-parse", args.rev).strip()
    base = resolve_base(repo, args.base, args.since)
    # deleted files left out: nothing of them is built or published any more
    changed = repo.git("diff", "--name-only", "--diff-filter=d", base, repo.rev).splitlines() if base else []
    res = Result(deploy=args.deploy)
    if args.deploy:
        res.info.append("deploy gate: Redirects.json checks report only (the file is read live, not deployed)")
    configs = check_configs(repo, res)
    base_url = config_value(repo, configs, "baseURL")
    host = re.sub(r"^https?://([^/]+).*", r"\1", base_url) if base_url else None
    check_redirects(repo, base, host, res)
    check_front_matter(repo, changed, res)
    check_shortcodes(repo, changed, res)
    if not args.no_build and "config_invalid" not in res.items and configs:
        build_sample(repo, configs, choose_sample(repo, changed, res), args.hugo, base_url, res)
    report(res, repo, base, changed, args.json)
    return 1 if res.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
