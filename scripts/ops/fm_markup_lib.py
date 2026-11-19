"""Remove Markdown from front-matter title/seoTitle/description/summary of posts in groups A and B.

Edits raw lines (keeps formatting), then checks each file: YAML still parses, every other key unchanged, the four
fields equal the expected cleaned values, body untouched. Usage: python fix_fm_markup.py <repo> <plan.json> [--write]
"""
import json
import re
import sys
from pathlib import Path

import yaml

FIELDS = ("title", "seoTitle", "description", "summary")
FM = re.compile(r"^(---\s*\n)(.*?)(\n---\s*\n)", re.S)
KEY = re.compile(r"^([A-Za-z_][\w-]*):(.*)$")
GARBLED = {"2024-11-22-convert-dwf-to-pdf-java/index.ko.md", "2024-11-29-convert-cdr-to-psd-in-csharp/index.ko.md",
           "2024-12-16-convert-stl-to-pdf-in-csharp/index.tr.md", "2025-01-03-merge-pdf-java/index.pl.md",
           "2025-07-15-convert-markdown-to-pdf-java/index.ko.md", "2025-08-27-convert-txt-to-json-in-java/index.ko.md",
           "2025-09-15-convert-pub-to-pptx-in-csharp/index.tr.md", "2025-10-10-convert-mpp-to-mpx-in-csharp/index.tr.md",
           "2025-10-15-convert-xps-to-bmp-in-csharp/index.tr.md", "2025-10-17-convert-html-to-bmp-in-java/index.ko.md",
           "2025-10-28-convert-3mf-to-stl-in-java/index.nl.md"}
LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
TICK = re.compile(r"(?<=\w)`(?=\w)")


def clean_value(v: str) -> str:
    v = v.replace("**", "")
    v = LINK.sub(r"\1", v)
    return TICK.sub("'", v)


def clean_line(line: str, quote: str) -> str:
    line = line.replace("**", "")
    line = LINK.sub(r"\1", line)
    return TICK.sub("''" if quote == "'" else "'", line)


def fix(text: str) -> str:
    m = FM.match(text)
    lines, key, quote, out = m.group(2).split("\n"), None, "", []
    for ln in lines:
        k = KEY.match(ln)
        if k:
            key = k.group(1)
            quote = k.group(2).strip()[:1]
        out.append(clean_line(ln, quote) if key in FIELDS else ln)
    return text[:m.start(2)] + "\n".join(out) + text[m.end(2):]


def main():
    repo, plan = Path(sys.argv[1]), json.load(open(sys.argv[2]))
    write = "--write" in sys.argv
    changed, problems = [], []
    for d, p in sorted(plan.items()):
        if p["cat"].startswith("C"):
            continue
        files = (["index.md"] if p["en"] else []) + [x for x in p["fix"] if x not in p["outdated"]]
        for name in files:
            f = repo / d / name
            if f"{Path(d).name}/{name}" in GARBLED:
                continue
            raw = f.read_bytes().decode("utf-8")
            new = fix(raw)
            if new == raw:
                continue
            old_fm, new_fm = (yaml.safe_load(FM.match(t).group(2)) for t in (raw, new))
            exp = {k: clean_value(v) if k in FIELDS and isinstance(v, str) else v for k, v in old_fm.items()}
            if new_fm != exp or FM.sub("", raw, 1) != FM.sub("", new, 1):
                problems.append(str(f.relative_to(repo)))
                continue
            changed.append(str(f.relative_to(repo)))
            if write:
                f.write_bytes(new.encode("utf-8"))
    print(f"{len(changed)} files {'changed' if write else 'to change'}, {len(problems)} problems")
    for x in problems[:20]:
        print("  problem:", x)


main()
