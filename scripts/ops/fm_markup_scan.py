"""Dry run of the post_front_matter_markup check on a blog clone: counts per field and markup, posts affected.

Usage: python scripts/ops/fm_markup_scan.py <repo> [--list FILE]
  --list writes one 'file<TAB>field<TAB>marks' row per value
"""
import argparse
import collections
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.audit.repo import front_matter_markup  # noqa: E402

FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)

ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("--list")
a = ap.parse_args()
repo = Path(a.repo)
rows, by = [], collections.Counter()
for f in sorted(repo.glob("content/**/index*.md")):
    m = FM.match(f.read_text("utf-8", "replace").lstrip("﻿").replace("\r\n", "\n"))
    if not m:
        continue
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        continue
    if not isinstance(data, dict):
        continue
    for field, marks, _ in front_matter_markup(data):
        rel = str(f.relative_to(repo))
        rows.append((rel, field, marks))
        by[(field, marks, "en" if f.name == "index.md" else "tr")] += 1
files = {r[0] for r in rows}
posts = {str(Path(r).parent) for r in files}
en_posts = {str(Path(r[0]).parent) for r in rows if r[0].endswith("/index.md")}
print(f"{len(rows)} values in {len(files)} files, {len(posts)} posts ({len(en_posts)} with it in English)")
for k, n in by.most_common():
    print(f"  {n:5}  {k[0]:12} {k[1]:20} {k[2]}")
if a.list:
    Path(a.list).write_text("".join("\t".join(r) + "\n" for r in rows), "utf-8")
