#!/bin/bash
# Build a blog at two commits with the deploy's Hugo and production config, for scripts/ops/build_diff.py
# (13 Nov 2026). Uses git worktrees, so the blog's working copy is never touched.
#
#   scripts/ops/build_pair.sh <blog repo> <old rev> <new rev> <out dir> [hugo binary]
#   .venv/bin/python scripts/ops/build_diff.py <out dir>/old <out dir>/new
#
# Hugo: the version in the tenant YAML (hugo_version; 0.101.0 for the conholdate/groupdocs/aspose.cloud blogs).
set -euo pipefail
REPO=$1; OLD=$2; NEW=$3; OUT=$4
HUGO=${5:-/Users/Apple/Downloads/Softwares/Hugo/hugo_extended_0.101.0_darwin-amd64/hugo}
mkdir -p "$OUT"
for pair in "old:$OLD" "new:$NEW"; do
  name=${pair%%:*}; rev=${pair#*:}
  wt="$OUT/wt-$name"
  rm -rf "$wt" "$OUT/$name"
  git -C "$REPO" worktree add -q --detach "$wt" "$rev"
  (cd "$wt" && "$HUGO" --config config.yml,config-production.yml --minify -d "$OUT/$name" --quiet)
  git -C "$REPO" worktree remove --force "$wt"
done
echo "built $OUT/old ($OLD) and $OUT/new ($NEW)"
