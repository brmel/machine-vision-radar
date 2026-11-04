#!/usr/bin/env bash
set -euo pipefail

# Records check.sh's pass for the tree it started on, only while that tree is still checked out and clean.
TREE="$1"
if [[ "$(git rev-parse 'HEAD^{tree}')" != "$TREE" || -n "$(git status --porcelain)" ]]; then
  echo "The tree changed during the run: the pass is not recorded, and the next push runs the gate again" >&2
  exit 0
fi
echo "$TREE $(node -v)" > "$(git rev-parse --git-common-dir)/mvradar-gates-pass"
