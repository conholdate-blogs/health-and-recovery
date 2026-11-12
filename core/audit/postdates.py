"""Publication date of each post URL, read from a Hugo blog repo (front matter `url` + `date`), so the crawl
sample can look at newer posts first (SK, 2026-11-12). Sitemap lastmod cannot do it: many blogs stamp every URL
with the build date. Read-only."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_FM = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
_NAME = re.compile(r"^index(?:\.([A-Za-z]{2,3}(?:-[A-Za-z]+)?))?\.md$")
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def post_dates(repo: Path, host: str) -> dict[str, str]:
    """https URL -> 'YYYY-MM-DD' for every post file with a url and a date."""
    out: dict[str, str] = {}
    for f in Path(repo).glob("content/**/index*.md"):
        m = _NAME.match(f.name)
        if not m:
            continue
        text = f.read_text("utf-8", "replace").lstrip("﻿").replace("\r\n", "\n")
        fm = _FM.match(text)
        if not fm:
            continue
        try:
            data = yaml.load(fm.group(1), Loader=_LOADER) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or not data.get("url") or not data.get("date"):
            continue
        url, lang = str(data["url"]).strip(), m.group(1)
        path = url if url.startswith("/") else (f"/{lang}/" if lang else "/") + url
        path = "/" + path.strip("/") + "/"
        out[f"https://{host}{path}"] = str(data["date"])[:10]
    return out
