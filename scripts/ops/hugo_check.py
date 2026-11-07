"""Test a Hugo template change before pushing it to a blog repo (2026-11-07, head fix on blog.aspose.com): build a tiny
copy of the blog (its real layouts, themes, assets, data and config, plus ONE post folder with its translations) in a
temp folder and report where the SEO tags land in the built pages: <head> or <body> (parsed like a browser).

    .venv/bin/python scripts/ops/hugo_check.py <blog repo> <post folder under the repo> [--rev <git rev>] [--hugo PATH]

--rev builds layouts/partials/head.html as it is at that revision (e.g. HEAD = live), default the working tree.
Example (2026-11-07): repo .../blog.aspose.com-PROD/aspose-blog,
post content/Aspose.Blog/cells/2020-12-14-protect-or-unprotect-excel-files-using-csharp.
A full build of a big blog takes long and needs GBs of disk; this takes seconds. Read-only on the repo.
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from selectolax.lexbor import LexborHTMLParser

HUGO = "/Users/Apple/Downloads/Softwares/Hugo/hugo_extended_0.120.0_darwin-universal/hugo"  # deploys use 0.120.4
TAGS = ["title", "meta[name=description]", "meta[name=robots]", "link[rel=canonical]", "link[rel=alternate][hreflang]",
        "meta[property^='og:']", 'script[type="application/ld+json"]', "#locale"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("post")
    ap.add_argument("--rev")
    ap.add_argument("--hugo", default=HUGO)
    args = ap.parse_args()
    src = Path(args.repo)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        configs = [p.name for p in src.glob("config*.y*ml")]
        for name in ["layouts", "themes", "static", "assets", "data", "i18n"] + configs:
            p = src / name
            if p.exists():
                (shutil.copytree if p.is_dir() else shutil.copy)(p, work / name)
        shutil.copytree(src / args.post, work / args.post)
        if args.rev:
            head = subprocess.run(["git", "-C", str(src), "show", f"{args.rev}:layouts/partials/head.html"],
                                  capture_output=True, text=True, check=True).stdout
            (work / "layouts/partials/head.html").write_text(head)
        cfg = ",".join(c for c in ("config.yml", "config.production.yml", "config-production.yml")
                       if (work / c).is_file())
        r = subprocess.run([args.hugo, "--quiet", "--environment", "production", "--config", cfg, "-d", "out"],
                           cwd=work, capture_output=True, text=True)
        if r.returncode:
            print("BUILD FAILED:", r.stderr[-800:])
            return 1
        pages = sorted((work / "out").rglob("index.html"))
        print(f"built {len(pages)} pages")
        for page in [p for p in pages if p.stat().st_size > 2000][:3]:
            t = LexborHTMLParser(page.read_bytes())
            print(" ", page.relative_to(work / "out"))
            for sel in TAGS:
                print(f"    {sel:34} head {len(t.css('head ' + sel)):3}  body {len(t.css('body ' + sel)):3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
