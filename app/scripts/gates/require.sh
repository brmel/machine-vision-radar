#!/usr/bin/env bash
set -euo pipefail

# `require.sh node java`: fail fast, before any step, when a tool the gates need is missing or too old.
for tool in "$@"; do
  case "$tool" in
    node)
      VERSION=$(node -v 2>/dev/null || true)
      [[ "$VERSION" == v22.* ]] || { echo "ERROR: Node.js ${VERSION:-is not installed or not in PATH}: the gates" \
        "need Node 22 (>=22.0.0 <23.0.0); switch with 'nvm use 22'." >&2; exit 1; } ;;
    java)
      VERSION=$(java -version 2>&1 | sed -n 's/.*version "\([0-9]*\).*/\1/p' | head -1)
      (( ${VERSION:-0} >= 21 )) || { echo "ERROR: Java ${VERSION:-is not installed or not in PATH}: the Firebase" \
        "emulators need Java 21 or later (brew install openjdk@21, then put it on PATH)." >&2; exit 1; } ;;
    *) echo "require.sh: unknown tool '$tool'" >&2; exit 2 ;;
  esac
done
