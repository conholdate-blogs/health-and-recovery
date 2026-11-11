"""Compare two full Hugo builds of a blog (before / after a change) and say exactly what changed (2026-11-11,
blog.conholdate.cloud: every template and content fix was proven this way before the push).

    # build both with the DEPLOY's Hugo and config (see the tenant YAML hugo_version and the blog's workflow), e.g.
    C="--config config.yml,config-production.yml --minify --cleanDestinationDir"
    git -C <repo> stash;     hugo -s <repo> $C -d /tmp/old
    git -C <repo> stash pop; hugo -s <repo> $C -d /tmp/new
    rm -rf <repo>/.hugo_build.lock <repo>/resources      # Hugo leaves these in the repo
    .venv/bin/python scripts/ops/build_diff.py /tmp/old /tmp/new

Prints: files only in one build; changed non-HTML files; robots-meta changes grouped by folder; pages with SEO tags in
<body> in the new build; x-default coverage; per-sitemap whether anything besides x-default lines changed.
Run it on small blogs (a full build of blog.aspose.com is GBs); for big ones use scripts/ops/hugo_check.py.
"""
import re
import sys
from collections import Counter
from pathlib import Path

from selectolax.lexbor import LexborHTMLParser

BODY = {"title": "title", "canonical": "link[rel=canonical]", "hreflang": "link[hreflang]",
        "og": "meta[property^='og:']", "twitter": "meta[name^='twitter:']"}
XDEF = re.compile(r'<xhtml:linkrel="alternate"hreflang="x-default"href="[^"]*"/>')


def robots(tree) -> str | None:
    m = tree.css_first("meta[name=robots]")
    return m.attributes.get("content") if m else None


def folder(rel: Path) -> str:
    parent = str(rel.parent) + "/"
    return re.sub(r"^(ar|cs|de|es|fa|fr|he|id|it|ja|ko|nl|pl|pt|ru|sv|th|tr|uk|vi|zh|zh-hant|hi)/", "<lang>/", parent)


def main(old: Path, new: Path) -> int:
    fo = {p.relative_to(old) for p in old.rglob("*") if p.is_file()}
    fn = {p.relative_to(new) for p in new.rglob("*") if p.is_file()}
    print("only in old:", sorted(map(str, fo - fn))[:20])
    print("only in new:", sorted(map(str, fn - fo))[:20])
    changes, in_body, xdef, real = Counter(), Counter(), Counter(), 0
    for rel in sorted(fo & fn):
        a, b = old / rel, new / rel
        if rel.suffix not in (".html", ".xml", ".txt") and a.read_bytes() != b.read_bytes():
            print("non-HTML changed:", rel)
        if rel.name == "sitemap.xml":
            sa, sb = re.sub(r"\s+", "", a.read_text()), re.sub(r"\s+", "", b.read_text())
            if XDEF.sub("", sb) != XDEF.sub("", sa):
                print("sitemap changed beyond x-default lines:", rel)
            continue
        if rel.suffix != ".html":
            continue
        ta, tb = LexborHTMLParser(a.read_text(errors="replace")), LexborHTMLParser(b.read_text(errors="replace"))
        if not tb.css_first("title"):
            continue  # alias redirect pages
        real += 1
        if robots(ta) != robots(tb):
            changes[(folder(rel), robots(ta), robots(tb))] += 1
        for name, sel in BODY.items():
            if tb.css_first("body " + sel) is not None:
                in_body[name] += 1
        xdef[bool(tb.css_first("link[hreflang=x-default]"))] += 1
    print(f"pages (not aliases): {real}")
    for (f, ro, rn), n in sorted(changes.items()):
        print(f"robots {n:4}  {f:30} {ro} -> {rn}")
    print("SEO tags in <body> (new build):", dict(in_body) or "none")
    print("x-default present:", xdef[True], " missing:", xdef[False])
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
