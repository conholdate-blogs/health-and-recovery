"""Exact replace that keeps a file's line endings. usage: repl.py <file> <spec.json>  spec: [[old, new], ...] with \n."""
import json, sys
path = sys.argv[1]; pairs = json.load(open(sys.argv[2]))
raw = open(path, "rb").read().decode("utf-8")
crlf = "\r\n" in raw
for old, new in pairs:
    if crlf: old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    assert raw.count(old) == 1, ("not exactly once", old[:80])
    raw = raw.replace(old, new)
open(path, "wb").write(raw.encode("utf-8"))
print(path, "CRLF" if crlf else "LF", len(pairs), "edit(s)")
