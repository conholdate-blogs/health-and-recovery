"""Set front-matter values in blog post files from a JSON spec, one line each, formatting kept (2026-11-11,
blog.conholdate.cloud: 66 seoTitle/description values in 43 files, Excel translations re-synced to the English).

    .venv/bin/python scripts/ops/front_matter_set.py <blog repo> <spec.json> [--dry-run]
    .venv/bin/python scripts/ops/front_matter_set.py <blog repo> --scan        # list titles/descriptions out of range

spec.json: {"content/<...>/index.de.md": {"seoTitle": "...", "description": "..."}, ...}
Each key must exist exactly once in the file's front matter (a `key: ...` line, possibly wrapped onto indented lines);
the value is written double-quoted on one line.
Checks every value against the crawl audit's limits (core/audit/crawl.py: TITLE_LEN 10-70, DESCRIPTION_LEN 50-170,
CJK counted double) and re-parses the front matter to confirm. --scan reports every post whose search title
(seoTitle, else title) or description (description, else summary) is out of range, over all index*.md files: the
crawl audit only samples pages, so fix the whole repo, not just the sampled ones.
"""
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.audit.crawl import DESCRIPTION_LEN, TITLE_LEN, display_len  # noqa: E402

LIMITS = {"seoTitle": TITLE_LEN, "title": TITLE_LEN, "description": DESCRIPTION_LEN, "summary": DESCRIPTION_LEN}
FM = re.compile(r"\A---\n(.*?)\n---", re.S)


def q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def scan(repo: Path) -> int:
    bad = 0
    for p in sorted((repo / "content").rglob("index*.md")):
        m = FM.match(p.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        t = str(fm.get("seoTitle") or fm.get("title") or "")
        d = str(fm.get("description") or fm.get("summary") or "")
        for kind, val, (lo, hi) in (("title", t, TITLE_LEN), ("description", d, DESCRIPTION_LEN)):
            if not lo <= display_len(val) <= hi:
                bad += 1
                print(f"{display_len(val):4} {kind:11} {p.relative_to(repo)} | {val[:100]}")
    print(f"{bad} values out of range (titles {TITLE_LEN}, descriptions {DESCRIPTION_LEN})")
    return 0


def apply(repo: Path, spec: dict, dry: bool) -> int:
    for rel, kv in spec.items():
        p = repo / rel
        text = p.read_text(encoding="utf-8")
        m = FM.match(text)
        assert m, f"{rel}: no front matter"
        fm = m.group(1)
        for key, val in kv.items():
            lo, hi = LIMITS.get(key, (0, 10**6))
            assert lo <= display_len(val) <= hi, f"{rel} {key}: width {display_len(val)} outside {lo}-{hi}"
            # the value may wrap onto indented lines (yaml.dump wraps at 80 characters, as the translation agent writes)
            pat = re.compile(rf"^{re.escape(key)}:.*(?:\n[ \t]+\S.*)*$", re.M)
            assert len(pat.findall(fm)) == 1, f"{rel}: {key} not exactly once"
            fm = pat.sub(lambda _, k=key, v=val: f"{k}: {q(v)}", fm)
        parsed = yaml.safe_load(fm)
        assert all(parsed[k] == v for k, v in kv.items()), f"{rel}: re-parse mismatch"
        if not dry:
            p.write_text(text[:m.start(1)] + fm + text[m.end(1):], encoding="utf-8")
    print(f"{'would set' if dry else 'set'} {sum(map(len, spec.values()))} values in {len(spec)} files")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    repo = Path(sys.argv[1])
    if sys.argv[2] == "--scan":
        sys.exit(scan(repo))
    sys.exit(apply(repo, json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), "--dry-run" in sys.argv))
