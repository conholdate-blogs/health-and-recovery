"""Pick a small, stable sample of URLs per template from a discovery inventory run.

A group is (host, section, template); section is '' on hosts without configured sections, as in discovery
findings. Per group: `per_template` URLs in the default language (no language segment, or `default_lang`)
plus one URL in each of up to `other_langs` other languages; `per_template_by_host` overrides `per_template`
for single hosts (e.g. a forum with one template and many pages). URLs are ranked by a hash of the URL, so the
same inventory always gives the same sample and findings stay comparable between runs.

A host with at most `full_max` URLs is crawled in full (every URL; 2026-11-12, after a 120-URL blog showed 2 long
titles in the sample while 45 posts had one): its findings then count pages exactly instead of extrapolating.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

FULL_MAX = 1000  # hosts with at most this many sitemap URLs are crawled in full


@dataclass(frozen=True)
class SampledUrl:
    url: str
    host: str
    section: str
    lang: str | None
    template: str
    group_urls: int  # URLs of this (host, section, template) in the inventory
    source: str = "sitemap"  # sitemap | homepage | extra | search
    sitemap: str | None = None  # the sitemap file that lists the URL (inventory), for evidence


def _rank(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def group_langs(db, run_id: int, sectioned_hosts: set[str]) -> dict[tuple[str, str], set]:
    """Languages per (host, section) group: more than one means the pages are localized."""
    out: dict = defaultdict(set)
    for host, section, lang in db.execute("SELECT DISTINCT host, section, lang FROM urls WHERE run_id = ?", (run_id,)):
        out[(host, section if host in sectioned_hosts else "")].add(lang)
    return dict(out)


def sample_inventory(db, run_id: int, hosts: list[str], sectioned_hosts: set[str], sections: list[str] | None = None,
                     per_template: int = 2, other_langs: int = 2, default_lang: str = "en",
                     max_per_host: int | None = None, per_template_by_host: dict | None = None,
                     full_max: int = FULL_MAX, salt: str | None = None, seen: set | None = None,
                     dates: dict | None = None) -> list[SampledUrl]:
    """Per group, half the picks are fixed (stable hash rank: runs stay comparable) and half rotate (SK, 2026-11-12):
    pages not checked in recent runs (`seen`) first, newest first (`dates`: url -> ISO date, from the posts' front
    matter), then a hash salted per run (`salt`), so each run looks at other pages and coverage grows. Without salt,
    seen and dates the rotating picks are stable too (tests, ad hoc runs)."""
    marks = ", ".join("?" * len(hosts))
    sizes = dict(db.execute(f"SELECT host, COUNT(*) FROM urls WHERE run_id = ? AND host IN ({marks}) GROUP BY host",
                            [run_id, *hosts]).fetchall())
    full = {h for h, n in sizes.items() if n <= full_max}
    seen, dates = seen or set(), dates or {}
    whole: list = []
    rows_by_group: dict = defaultdict(list)  # group -> [(url, lang, sitemap)]
    counts: dict = defaultdict(int)
    rows = db.execute("SELECT url, host, section, lang, template, sitemap FROM urls "
                      f"WHERE run_id = ? AND host IN ({marks})", [run_id, *hosts])
    for url, host, section, lang, template, sitemap in rows:
        sec = section if host in sectioned_hosts else ""
        if sections is not None and host in sectioned_hosts and sec not in sections:
            continue  # a section filter narrows only hosts with sections; other hosts are sampled in full
        group = (host, sec, template)
        counts[group] += 1
        if host in full:
            whole.append((url, host, sec, lang, template, sitemap))
        else:
            rows_by_group[group].append((url, lang, sitemap))

    def rot_key(url: str):
        return (url in seen, _neg_date(dates.get(url)), _rank(f"{salt}|{url}") if salt else _rank(url))

    # Per host, take the 1st pick of every group, then the 2nd, ... so a host cap trims evenly across templates.
    by_host: dict = defaultdict(list)  # host -> [[SampledUrl, ...] per group]
    for group in sorted(rows_by_group):
        host, sec, template = group
        n_default = (per_template_by_host or {}).get(host, per_template)
        default = [r for r in rows_by_group[group] if r[1] is None or r[1] == default_lang]
        other = [r for r in rows_by_group[group] if not (r[1] is None or r[1] == default_lang)]
        fixed_n = (n_default + 1) // 2
        by_rank = sorted(default, key=lambda r: _rank(r[0]))
        picks = by_rank[:fixed_n]
        taken = {r[0] for r in picks}
        picks += sorted((r for r in default if r[0] not in taken), key=lambda r: rot_key(r[0]))[:n_default - fixed_n]
        extra = other_langs if picks else other_langs + 1  # no default-language page: one more localized page
        best: dict = {}  # language -> its lowest-ranked URL (the fixed choice per language)
        for r in other:
            if r[1] not in best or _rank(r[0]) < _rank(best[r[1]][0]):
                best[r[1]] = r
        langs = sorted(best, key=lambda lang: _rank(best[lang][0]))
        fixed_l = (extra + 1) // 2
        lpicks = [best[lang] for lang in langs[:fixed_l]]
        used = {r[1] for r in lpicks}
        for r in sorted((r for r in other if r[1] not in used), key=lambda r: rot_key(r[0])):
            if len(lpicks) >= extra:
                break
            if r[1] not in used:
                used.add(r[1])
                lpicks.append(r)
        by_host[host].append([SampledUrl(url, host, sec, lang, template, counts[group], sitemap=sm)
                              for url, lang, sm in picks + lpicks])

    out: list[SampledUrl] = [SampledUrl(url, host, sec, lang, template, counts[(host, sec, template)], sitemap=sm)
                             for url, host, sec, lang, template, sm in sorted(whole, key=lambda r: (r[1], _rank(r[0])))]
    for host in sorted(by_host):
        groups = by_host[host]
        taken = []
        for i in range(max(len(g) for g in groups)):
            taken += [g[i] for g in groups if i < len(g)]
        out += taken[:max_per_host] if max_per_host is not None else taken
    return out


def _neg_date(value: str | None) -> str:
    """Newest first in an ascending sort; no date sorts last."""
    if not value:
        return "~"
    return "".join(chr(ord("9") - ord(c) + ord("0")) if c.isdigit() else c for c in str(value)[:10])


def _neg(rank: str) -> str:
    """Invert a hex rank so a min-heap keeps the lowest ranks (heap root = the highest kept rank)."""
    return rank.translate(str.maketrans("0123456789abcdef", "fedcba9876543210"))
