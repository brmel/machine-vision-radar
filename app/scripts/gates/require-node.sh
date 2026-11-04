#!/usr/bin/env bash
set -euo pipefail

# The gates and the site run on Node 22 (>=22.0.0 <23.0.0). Fail fast, before any step.
NODE_VERSION=$(node -v 2>/dev/null || true)
if [[ "$NODE_VERSION" != v22.* ]]; then
  echo "ERROR: Node.js ${NODE_VERSION:-is not installed or not in PATH}: the gates need Node 22 (>=22.0.0 <23.0.0);" \
    "switch with 'nvm use 22'." >&2
  exit 1
fi
