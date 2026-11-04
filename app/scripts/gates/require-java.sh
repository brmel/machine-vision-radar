#!/usr/bin/env bash
set -euo pipefail

# The Firestore and Storage emulators need Java 21 or later. Fail fast, before any emulator starts.
VERSION=$(java -version 2>&1 | sed -n 's/.*version "\([0-9]*\).*/\1/p' | head -1)
if (( ${VERSION:-0} < 21 )); then
  echo "ERROR: Java ${VERSION:-is not installed or not in PATH}: the Firebase emulators need Java 21 or later" \
    "(brew install openjdk@21, then put it on PATH)." >&2
  exit 1
fi
