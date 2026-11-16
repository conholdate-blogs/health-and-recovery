"""Text check: spelling and topic errors in the title, H1 and meta description of every crawl-audit page.

No new requests to the site: it reads the pages the crawl audit fetched (newest result per URL) and asks an LLM
(core/llm.py) to proofread them in their own language. Only clear errors count: misspellings and words typed
twice (`text_typo`, improvable), leftover placeholder or garbled words (`text_leftover`), and a title or
description about a different product than the page (`text_topic_mismatch`). Brand names,
file formats, capitalization, punctuation and style are out of scope (see SYSTEM).

Guards against a model that invents or drifts:
- an answer is kept only if its wrong text really occurs in the field it names (and, for a repeated word, the
  word really is typed twice), so a finding always quotes the page;
- answers are cached per page text (data/, gitignored), keyed by prompt version and model: a rerun on unchanged
  text gives the same result, and only new or changed text is sent;
- reviewed false positives can be listed in the tenant YAML (audit.text.ignore: url, wrong) and are dropped;
- pages whose batch failed twice stay unchecked; a run with more than MAX_UNCHECKED_SHARE of them is
  incomplete and resolves nothing.

Findings are grouped per host, or per section on sectioned hosts (template `page` / `page:<section>`), and list
every affected page with the wrong and the corrected text. The Prioritizer scores them on those exact pages.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

from core.findings import FindingIds, make_finding
from core.llm import LLMError, parse_json

AUDITOR = "text-audit"
PROMPT_VERSION = 2  # bump when SYSTEM changes: cached answers of older prompts are then ignored
BATCH = 20
MAX_UNCHECKED_SHARE = 0.1
FIELDS = ("title", "h1", "description")
FIELD_NAMES = {"title": "title", "h1": "H1", "description": "meta description"}
KIND_CHECK = {"misspelling": "text_typo", "repeated_word": "text_typo", "stray_word": "text_leftover",
              "topic_mismatch": "text_topic_mismatch"}
REPEATED_RE = re.compile(r"\b(\w+)\s+\1\b", re.I | re.U)
NO_WORDS_RE = re.compile(r"^[\W\d_]+$", re.U)  # only digits and punctuation: never a spelling error
SKIP_ISSUES = {"soft_404", "meta_refresh"}  # error pages and redirect stubs say nothing about the copy

# check -> (dimension, type, title, expected, fix_tier, effort)
CHECKS = {
    # a plain typo is cosmetic; a leftover template key or a wrong product misinforms (SK, 2026-10-20)
    "text_typo": ("onpage", "improvable", "Typos in titles, headings or descriptions",
                  "Correctly spelled titles, H1s and meta descriptions", 1, "S"),
    "text_leftover": ("onpage", "incorrect", "Placeholder or garbled words in titles, headings or descriptions",
                      "Finished text in the page's language, without template keys or test words", 1, "S"),
    "text_topic_mismatch": ("onpage", "incorrect", "Title or description is about a different product",
                            "Title and meta description describe the page's own product, like its H1", 1, "S"),
}

SYSTEM = """You proofread the search snippets of a website: page title, main heading (H1) and meta description.
Input: a JSON list of pages {id, path, lang, title, h1, description}. lang is the page language.

Report only clear, certain errors a careful editor would fix:
- misspelling: a misspelled word ("Recoginze" -> "Recognize", "iamges" -> "images"), two words run together
  ("MergeEPS"), or a word with a letter from another alphabet (Cyrillic "С" in "Сonvert").
- repeated_word: the same word typed twice by mistake ("for for", "Image image").
- stray_word: a leftover placeholder or template key ("test", "lorem", "TODO", "CADWatermarkTitle2"), or an
  untranslated or garbled word that makes the sentence wrong in its language.
- topic_mismatch: the title or description names a specific product or file type that is clearly a DIFFERENT
  one than the page is about (path and H1): e.g. an SVG page whose title is about Photoshop PSD files, an audio
  converter whose description says "Visio files".

Not a topic_mismatch: text that is broader or more generic than the page (it names the family, the app's other
formats, or the technique, e.g. OCR or "3D formats"); text that agrees with the H1; the page's own source or
target format; a format the page legitimately produces.

Never report: product, brand or company names, also when transliterated into another script; file formats,
extensions and units (PSD, AI, ONE, XBRL, in, em, px, ...); numbers and years; words in capitals; capitalization
or title case; punctuation, accents or spacing between sentences; grammar or style; phrasing that is awkward but
understandable; translations that are loose but correct; error messages; login pages. Check each text in its own
language. When in doubt, do not report it.

Answer with JSON only: {"issues": [{"id": <page id>, "field": "title" | "h1" | "description",
"kind": "misspelling" | "repeated_word" | "stray_word" | "topic_mismatch", "wrong": "<only the wrong word or
words, exactly as written>", "fix": "<the same words corrected, empty to delete>", "why": "<a few words>"}]}.
Return {"issues": []} when there is nothing to report."""


def page_item(p: dict) -> dict | None:
    """What the LLM sees of a crawl-audit page, or None when the page has no copy worth checking."""
    f = p.get("facts")
    if not f or p.get("status") != 200 or p.get("ignored"):
        return None
    if any(c in SKIP_ISSUES for c, _ in p.get("issues") or []):
        return None
    item = {"title": (f.get("titles") or [None])[0], "h1": (f.get("h1") or [None])[0],
            "description": (f.get("descriptions") or [None])[0]}
    if not any(item.values()):
        return None
    u = urlsplit(p["url"])
    return {"path": u.netloc + u.path, "lang": p.get("lang") or f.get("html_lang") or "en", **item}


def valid_issue(issue: dict, item: dict) -> dict | None:
    """The issue in canonical form if it holds up against the page text, else None."""
    kind, field = issue.get("kind"), issue.get("field")
    wrong, fix = str(issue.get("wrong") or "").strip(), str(issue.get("fix") or "").strip()
    text = item.get(field) if field in FIELDS else None
    if kind not in KIND_CHECK or not text or not wrong or wrong == fix:
        return None
    if wrong.casefold() not in text.casefold():
        return None
    if kind == "repeated_word" and not REPEATED_RE.search(wrong):
        return None
    if NO_WORDS_RE.match(wrong):
        return None
    if kind == "topic_mismatch" and field != "h1" and wrong.casefold() in (item.get("h1") or "").casefold():
        return None  # the H1 says the same: not a different product
    return {"field": field, "kind": kind, "wrong": wrong, "fix": fix, "why": str(issue.get("why") or "")[:120]}


class TextCache:
    """Answers per page text: {key: [issues]} in a JSON file."""

    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self.data: dict = {}
        if self.path and self.path.is_file():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    @staticmethod
    def key(item: dict, model: str) -> str:
        blob = json.dumps({"v": PROMPT_VERSION, "model": model, **item}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")


class TextAudit:
    def __init__(self, tenant, llm, store, pages: list[dict], cache: TextCache, hosts=None, crawl_runs=(),
                 batch=BATCH, log=print):
        self.tenant, self.llm, self.store, self.cache = tenant, llm, store, cache
        self.pages = [p for p in pages if not hosts or p["host"] in hosts]
        self.hosts = sorted({p["host"] for p in self.pages})
        self.crawl_runs, self.batch = list(crawl_runs), batch
        self.log = log or (lambda *_: None)
        self.fix_channels = {h["host"]: h.get("fix_channel") for h in tenant.hosts}
        cfg = ((tenant.raw.get("audit") or {}).get("text") or {})
        self.ignore = [(r["url"], r.get("wrong")) for r in cfg.get("ignore") or []]
        self.run_id: int | None = None

    def ignored(self, url: str, issue: dict) -> bool:
        """Reviewed false positives (tenant audit.text.ignore: url, optional wrong text)."""
        return any(u == url and (w is None or w.casefold() == issue["wrong"].casefold()) for u, w in self.ignore)

    def _ask(self, batch: list[tuple[int, dict]]) -> dict[int, list[dict]]:
        """{local id: [valid issues]} for one batch; a failed call or reply is retried once."""
        payload = json.dumps([{"id": i, **item} for i, item in batch], ensure_ascii=False)
        last = None
        for _ in range(2):
            try:
                reply = parse_json(self.llm.complete(SYSTEM, payload))
                break
            except LLMError as e:
                last = e
        else:
            raise LLMError(str(last))
        items = dict(batch)
        out: dict[int, list[dict]] = {i: [] for i, _ in batch}
        for issue in reply.get("issues") or []:
            if not isinstance(issue, dict) or issue.get("id") not in items:
                continue
            ok = valid_issue(issue, items[issue["id"]])
            if ok and ok not in out[issue["id"]]:
                out[issue["id"]].append(ok)
        return out

    def check(self) -> tuple[dict, list[str], int]:
        """url -> issues for every checked page, the URLs left unchecked, and cache hits."""
        items = {p["url"]: it for p in self.pages if (it := page_item(p))}
        keys = {u: self.cache.key(it, self.llm.model) for u, it in items.items()}
        results = {u: self.cache.data[k] for u, k in keys.items() if k in self.cache.data}
        hits = len(results)
        todo = [u for u in items if u not in results]
        batches = [todo[i:i + self.batch] for i in range(0, len(todo), self.batch)]
        self.log(f"{len(items)} pages with copy: {hits} cached, {len(todo)} to check in {len(batches)} LLM calls")
        unchecked: list[str] = []

        def ask(urls):
            return self._ask([(n, items[u]) for n, u in enumerate(urls)])

        # the LLM client limits parallel calls and backs off after failures
        with ThreadPoolExecutor(max_workers=getattr(self.llm, "concurrency", 1)) as pool:
            for done, (urls, fut) in enumerate([(b, pool.submit(ask, b)) for b in batches], 1):
                try:
                    answer = fut.result()
                except LLMError as e:
                    self.log(f"  batch {done}/{len(batches)} failed twice: {e}")
                    unchecked += urls
                    continue
                for n, u in enumerate(urls):
                    results[u] = answer[n]
                    self.cache.data[keys[u]] = answer[n]
                self.cache.save()  # an interrupted run keeps what it has
                self.log(f"  batch {done}/{len(batches)}: {sum(len(v) for v in answer.values())} issues")
        return results, unchecked, hits

    def run(self) -> dict:
        started = time.monotonic()
        params = {"hosts": self.hosts, "crawl_runs": self.crawl_runs, "model": self.llm.model,
                  "prompt_version": PROMPT_VERSION}
        self.run_id = self.store.start_run(self.tenant.property, AUDITOR, params)
        results, unchecked, hits = self.check()
        suppressed = sum(1 for u, iss in results.items() for i in iss if self.ignored(u, i))
        results = {u: [i for i in iss if not self.ignored(u, i)] for u, iss in results.items()}
        by_url = {p["url"]: p for p in self.pages}
        checked = len(results)
        report = {"tenant": self.tenant.property, "auditor": AUDITOR, "run_id": self.run_id, "params": params,
                  "duration_s": round(time.monotonic() - started, 1), "stopped_early": False,
                  "pages_checked": checked, "unchecked": unchecked,
                  "incomplete": len(unchecked) > MAX_UNCHECKED_SHARE * max(1, checked + len(unchecked)),
                  "llm": {**self.llm.usage.as_dict(), "cache_hits": hits}, "ignored": suppressed,
                  "summary": summarize(results, by_url)}
        report["findings"] = self.findings(results, by_url)
        # flagged pages, so the next crawl rechecks them (CrawlAudit.text_issue_urls; 16 Nov 2026)
        report["flagged"] = [{"url": u, "host": by_url[u]["host"]} for u, iss in sorted(results.items()) if iss]
        self.store.finish_run(self.run_id, {k: v for k, v in report.items() if k != "findings"})
        report["pages"] = [{"url": u, "host": by_url[u]["host"], "section": by_url[u]["section"],
                            "lang": by_url[u].get("lang"), "issues": iss} for u, iss in sorted(results.items()) if iss]
        return report

    def findings(self, results: dict, by_url: dict) -> list[dict]:
        checked: dict = defaultdict(int)  # (host, section) -> checked pages
        hits: dict = defaultdict(list)  # (check, host, section) -> [(url, issue)]
        for u, issues in results.items():
            p = by_url[u]
            checked[(p["host"], p["section"])] += 1
            for i in issues:
                hits[(KIND_CHECK[i["kind"]], p["host"], p["section"])].append((u, i))
        ids, out = FindingIds(), []
        for (check, host, section), items in sorted(hits.items()):
            dimension, ftype, title, expected, tier, effort = CHECKS[check]
            urls = list(dict.fromkeys(u for u, _ in items))
            notes = [(u, f"{FIELD_NAMES[i['field']]}: " + (f"'{i['wrong']}' → '{i['fix']}'" if i["fix"]
                                                           else f"remove '{i['wrong']}'")) for u, i in items]
            examples = "; ".join(f"{urlsplit(u).path} {n}" for u, n in notes[:5])
            more = f"; and {len(notes) - 5} more" if len(notes) > 5 else ""
            f = make_finding(
                ids=ids, tenant=self.tenant.property, subdomain=host,
                template=f"page:{section}" if section else "page", dimension=dimension, type=ftype, check=check,
                title=title + (f" (/{section}/)" if section else ""), urls=urls[:10],
                observed=f"{len(urls)} of {checked[(host, section)]} checked pages: {examples}{more}",
                expected=expected, affected_pages=len(urls), effort=effort, fix_tier=tier,
                fix_channel=self.fix_channels.get(host))
            f["evidence"]["locations"] = [{"role": "page", "url": u, "note": n} for u, n in notes[:30]]
            out.append(f)
        return out


def summarize(results: dict, by_url: dict) -> dict:
    out: dict = {}
    for u, issues in results.items():
        h = out.setdefault(by_url[u]["host"], {"checked": 0, "pages_with_issues": 0, "issues": defaultdict(int)})
        h["checked"] += 1
        h["pages_with_issues"] += int(bool(issues))
        for i in issues:
            h["issues"][KIND_CHECK[i["kind"]]] += 1
    return {h: {**v, "issues": dict(v["issues"])} for h, v in sorted(out.items())}


def merge_crawl_pages(reports: list[dict]) -> list[dict]:
    """Pages of several crawl-audit reports (oldest first); the newest result wins per URL."""
    pages: dict = {}
    for r in reports:
        for p in r["pages"]:
            pages[p["url"]] = p
    return list(pages.values())


def audit(tenant, llm, store, pages, cache, **kw) -> dict:
    return TextAudit(tenant, llm, store, pages, cache, **kw).run()


def import_report(findings_store, report: dict) -> dict:
    """Record a text-check report in the findings store; an incomplete run resolves nothing."""
    hosts = [] if report.get("incomplete") else report["params"]["hosts"]
    return findings_store.import_run(report["findings"], f"{AUDITOR}-run{report['run_id']}", AUDITOR,
                                     hosts=hosts, resolve_unsectioned=True)
