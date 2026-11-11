"""Where do a live page's SEO tags land: <head> or <body>? (2026-11-11, blog.conholdate.cloud: Open Graph, Twitter and
JSON-LD sat in <body> on every page because a language-switcher <div> ended <head> early.)

    .venv/bin/python scripts/ops/live_head.py <url> [<url> ...]

Parses each page like a browser (selectolax/lexbor) and prints, per tag, how many are in <head> and in <body>, plus the
robots meta and the H1s. Use it before and after a head/template fix; check a translated post, the home page and a
tag page (the switcher only renders where a page has translations). Read-only: one GET per URL.
"""
import sys

import requests
from selectolax.lexbor import LexborHTMLParser

TAGS = {
    "title": "title",
    "canonical": "link[rel=canonical]",
    "hreflang": "link[hreflang]",
    "x-default": "link[hreflang=x-default]",
    "og": "meta[property^='og:']",
    "twitter": "meta[name^='twitter:']",
    "json-ld": "script[type='application/ld+json']",
}


def main(urls: list[str]) -> int:
    if not urls:
        print(__doc__)
        return 2
    for url in urls:
        r = requests.get(url, headers={"User-Agent": "SiteHealthAudit/0.1 (read-only SEO audit)"}, timeout=30)
        t = LexborHTMLParser(r.text)
        robots = t.css_first("meta[name=robots]")
        print(f"{url}  HTTP {r.status_code}  robots={robots.attributes.get('content') if robots else None}"
              f"  x-robots-tag={r.headers.get('x-robots-tag')}")
        for name, sel in TAGS.items():
            head, body = len(t.css("head " + sel)), len(t.css("body " + sel))
            print(f"  {name:10} head {head:3}  body {body:3}{'   <-- in <body>' if body and name != 'json-ld' else ''}")
        print(f"  h1         {[h.text(strip=True)[:60] for h in t.css('h1')]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
