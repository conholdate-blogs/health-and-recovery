"""Fix Markdown in flagged front-matter fields of current translations whose English post is clean.
Usage: python scripts/ops/fm_markup_fix.py <repo> [--write]"""
import pathlib, re, subprocess, sys, importlib.util
import yaml
sys.path.insert(0, "/Users/Apple/Work/Aspose/GitHub/conholdate-blogs/health-and-recovery")
from core.audit.repo import front_matter_markup
spec = importlib.util.spec_from_file_location("f1", str(pathlib.Path(__file__).with_name("fm_markup_lib.py")))
src = open(spec.origin).read().split("\ndef main():")[0]
ns = {}; exec(src, ns)
FM, KEY, clean_line, clean_value, GARBLED = ns["FM"], ns["KEY"], ns["clean_line"], ns["clean_value"], ns["GARBLED"]
repo = pathlib.Path(sys.argv[1]); write = "--write" in sys.argv
out = subprocess.run(["git", "-C", str(repo), "log", "--format=@%ct", "--name-only", "--no-renames", "--", "content"],
                     capture_output=True, text=True).stdout
ct, t = {}, None
for l in out.splitlines():
    if l.startswith("@"): t = int(l[1:])
    elif l and l not in ct: ct[l] = t
def fm(text):
    m = FM.match(text)
    try: d = yaml.safe_load(m.group(2)) if m else None
    except yaml.YAMLError: return None
    return d if isinstance(d, dict) else None
changed, problems = [], []
for en in sorted(repo.glob("content/**/index.md")):
    E = fm(en.read_text("utf-8").replace("\r\n", "\n"))
    if E is None or front_matter_markup(E): continue
    Et = ct.get(str(en.relative_to(repo)), 0)
    for f in sorted(en.parent.glob("index.*.md")):
        rel = str(f.relative_to(repo))
        if ct.get(rel, 0) < Et or f"{f.parent.name}/{f.name}" in GARBLED: continue
        raw = f.read_bytes().decode("utf-8"); d = fm(raw)
        if d is None: continue
        fields = {fl for fl, _, _ in front_matter_markup(d)}
        if not fields: continue
        m = FM.match(raw); key = quote = None; lines = []
        for ln in m.group(2).split("\n"):
            k = KEY.match(ln)
            if k: key, quote = k.group(1), k.group(2).strip()[:1]
            lines.append(clean_line(ln, quote) if key in fields else ln)
        new = raw[:m.start(2)] + "\n".join(lines) + raw[m.end(2):]
        exp = {k: clean_value(v) if k in fields and isinstance(v, str) else v for k, v in d.items()}
        if fm(new) != exp or FM.sub("", raw, 1) != FM.sub("", new, 1) or front_matter_markup(fm(new)):
            problems.append(rel); continue
        changed.append((rel, sorted(fields)))
        if write: f.write_bytes(new.encode("utf-8"))
print(len(changed), "files", "changed" if write else "to change", len(problems), "problems", problems[:10])
import collections; print(collections.Counter(tuple(x[1]) for x in changed))
