#!/usr/bin/env bash
set -euo pipefail

# Exits 0 when check.sh passed here, on a clean tree, for the given commit's tree (default HEAD) with this Node.
STAMP="$(git rev-parse --git-common-dir)/mvradar-gates-pass"
[[ -f "$STAMP" && "$(cat "$STAMP")" == "$(git rev-parse "${1:-HEAD}^{tree}") $(node -v)" ]]
