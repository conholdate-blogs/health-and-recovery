"""Line-preserving Redirects.json edit. usage: redir_edit.py <Redirects.json> <spec.json>
spec: {"remove": [keys], "retarget": {key: new_value}}; keys match exactly or after percent-decoding."""
import json, sys, urllib.parse as up
path, spec = sys.argv[1], json.load(open(sys.argv[2]))
lines = open(path, encoding="utf-8").read().split("\n")
norm = lambda k: up.unquote(k)
rm = {norm(k) for k in spec.get("remove", [])}
rt = {norm(k): v for k, v in spec.get("retarget", {}).items()}
out, removed, changed = [], [], []
for ln in lines:
    s = ln.strip()
    if s.startswith('"'):
        (k, v), = json.loads("{" + s.rstrip(",") + "}").items()
        if norm(k) in rm:
            removed.append(k); continue
        if norm(k) in rt:
            new = rt[norm(k)]
            ln = ln.replace(json.dumps(v, ensure_ascii=False)[1:-1], new) if v in ln else None
            assert ln, k
            changed.append(k)
    out.append(ln)
# last entry must have no trailing comma
idx = max(i for i, l in enumerate(out) if l.strip().startswith('"'))
out[idx] = out[idx].rstrip().rstrip(",")
for i in range(idx):
    if out[i].strip().startswith('"') and not out[i].rstrip().endswith(","):
        out[i] = out[i].rstrip() + ","
text = "\n".join(out)
n = len(json.loads(text))
assert {norm(k) for k in removed} == rm, (sorted(rm - {norm(k) for k in removed}))
assert len(changed) == len(rt), (sorted(set(rt) - {norm(k) for k in changed}))
open(path, "w", encoding="utf-8").write(text)
print(f"removed {len(removed)}, retargeted {len(changed)}, entries now {n}")
