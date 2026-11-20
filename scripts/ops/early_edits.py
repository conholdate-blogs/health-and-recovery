"""For English posts added since a date: how many got another commit within 1/3/7 days, and by what.

Usage: python scripts/ops/early_edits.py <blog repo> <since YYYY-MM-DD>
Evidence for the translation agent's settling time (docs/plans/commit-watch-and-site-map.md).
"""
import subprocess, sys, collections

repo, since = sys.argv[1], sys.argv[2]
def git(*a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True).stdout

files = sorted({l for l in git("log", f"--since={since}", "--diff-filter=A", "--name-only", "--format=",
                               "--", "content/").splitlines() if l.endswith("/index.md")})
win = collections.Counter(); msgs = collections.Counter()
for f in files:
    rows = [l.split("\t", 1) for l in git("log", "--format=%at\t%s", "--", f).splitlines()]
    rows = [(int(t), s) for t, s in rows]
    add = min(t for t, _ in rows)
    later = [(t - add, s) for t, s in rows if t > add]
    for d in (1, 3, 7):
        if any(x <= d * 86400 for x, _ in later):
            win[d] += 1
    for x, s in later:
        if x <= 7 * 86400:
            msgs[s[:60]] += 1
print(f"{repo.split('/')[-1]}: {len(files)} new English posts since {since}")
for d in (1, 3, 7):
    print(f"  edited again within {d} day(s): {win[d]}")
for m, c in msgs.most_common(8):
    print(f"   {c:3}  {m}")
