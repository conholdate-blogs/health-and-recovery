"""Proven on blog.conholdate.com (3832d94d, 306 files) and blog.conholdate.cloud (69e4ab9, 62 files), 19 Nov 2026.
Repair front matter of current translations: cover block flattened (image/alt/caption/hidden not indented under
cover:, caption key sometimes translated) and values wrapped in \\" ... \\". Usage: scripts/ops/fm_cover_repair.py <repo> [--write]
[--only cover|escaped] (26 Nov 2026, Shoaib Khan: one commit per fix type; run escaped first: an escaped image path blocks the cover check)
"""
import json
import pathlib
import re
import subprocess
import sys

import yaml

FM = re.compile(r"^(---\s*\n)(.*?)(\n---\s*\n)", re.S)
KEY = re.compile(r"^(\s*)([^\s:#][^:]*):\s?(.*)$")
COVER_KEYS = {"image", "alt", "caption", "hidden"}
CAPTION_ALIASES = {"キャプション", "légende", "legenda", "التسمية التوضيحية", "التسمية التوضيحيه", "คำบรรยาย", "заголовок", "chú thích", "כיתוב"}
repo = pathlib.Path(sys.argv[1])
write = "--write" in sys.argv
ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None  # cover | escaped | None (both)
DO_COVER, DO_ESC = ONLY in (None, "cover"), ONLY in (None, "escaped")

out = subprocess.run(["git", "-C", str(repo), "log", "--format=@%ct", "--name-only", "--no-renames", "--", "content"],
                     capture_output=True, text=True).stdout
ct, t = {}, None
for line in out.splitlines():
    if line.startswith("@"):
        t = int(line[1:])
    elif line and line not in ct:
        ct[line] = t


def unesc(v: str) -> str:
    v = v.strip()
    if v.startswith('\\"') and v.endswith('\\"') and len(v) >= 4:
        v = v[2:-2]
    return v.replace('\\"', '"')


def load(text):
    m = FM.match(text)
    try:
        d = yaml.safe_load(m.group(2)) if m else None
    except yaml.YAMLError:
        return None
    return d if isinstance(d, dict) else None


def fix(raw: str) -> str:
    m = FM.match(raw)
    lines, out_lines, in_cover = m.group(2).split("\n"), [], False
    for ln in lines:
        k = KEY.match(ln)
        if not k:
            out_lines.append(ln)
            continue
        indent, key, val = k.groups()
        key = key.strip()
        if DO_COVER and not indent and key in ("cover", "capa", "cobrir") and not val.strip():
            in_cover = True
            out_lines.append("cover:")
            continue
        touched = False
        if not DO_COVER and not indent and key in ("cover", "capa", "cobrir") and not val.strip():
            in_cover = True  # cover already a block: still unescape inside it
        elif DO_COVER and in_cover and not indent and (key in COVER_KEYS or key in CAPTION_ALIASES):
            indent, key, touched = "    ", ("caption" if key in CAPTION_ALIASES else key), True
        elif DO_COVER and in_cover and indent and key in CAPTION_ALIASES:
            key, touched = "caption", True  # cover block already indented, caption key translated
        elif not indent:
            in_cover = False
        v = val.strip()
        if DO_ESC and (not indent or in_cover) and v.startswith('\\"') and v.endswith('\\"') and len(v) >= 4:
            val, touched = json.dumps(unesc(v), ensure_ascii=False), True
        if not touched:
            out_lines.append(ln)
            continue
        out_lines.append(f"{indent}{key}: {val}" if val != "" else f"{indent}{key}:")
    return raw[:m.start(2)] + "\n".join(out_lines) + raw[m.end(2):]


def walk_esc(d):
    for v in (d.values() if isinstance(d, dict) else []):
        if isinstance(v, str) and '\\"' in v:
            return True
        if isinstance(v, dict) and walk_esc(v):
            return True
    return False


changed, problems = [], []
for en in sorted(repo.glob("content/**/index.md")):
    E = load(en.read_text("utf-8")) or {}
    ecover = E.get("cover") if isinstance(E.get("cover"), dict) else None
    for f in sorted(en.parent.glob("index.*.md")):
        rel = str(f.relative_to(repo))
        if ct.get(rel, 0) < ct.get(str(en.relative_to(repo)), 0):
            continue  # queued for retranslation: leave it
        raw = f.read_text("utf-8")
        old = load(raw)
        if old is None:
            continue
        new = fix(raw)
        if new == raw:
            continue
        d = load(new)
        if d is None:
            problems.append(rel)
            continue
        moved = COVER_KEYS | CAPTION_ALIASES | {"capa", "cobrir"}
        same_rest = all(d.get(k) == (unesc(v) if isinstance(v, str) and DO_ESC and v.strip().startswith('\\"') else v)
                        for k, v in old.items() if k not in moved and k != "cover")
        cov_ok = (not ecover) or (isinstance(d.get("cover"), dict) and d["cover"].get("image") == ecover.get("image"))
        esc_left = walk_esc(d.get('cover') or {}) or any(isinstance(d.get(k), str) and d[k].startswith('\\"') for k in d)
        cover_left = any(k in d for k in CAPTION_ALIASES) or (ecover and any(k in d for k in ("image", "alt", "caption")))
        if not d or (DO_ESC and esc_left) or not same_rest or (DO_COVER and (not cov_ok or cover_left)) or FM.sub("", raw, 1) != FM.sub("", new, 1):
            problems.append(rel)
            continue
        changed.append(rel)
        if write:
            f.write_text(new, "utf-8")
print(len(changed), "files", "changed" if write else "to change", "|", len(problems), "problems")
for p in problems[:15]:
    print("  problem:", p)
