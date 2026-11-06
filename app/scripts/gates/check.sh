#!/usr/bin/env bash
set -euo pipefail

# The quality gates, run locally before a push or a deploy.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

bash "$REPO_ROOT/app/scripts/gates/require.sh" node java

# The commit and tree this run tests, read before its first step.
COMMIT_SHA=$(git rev-parse --short HEAD)
TREE=$(git rev-parse 'HEAD^{tree}')
DIRTY=""
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  DIRTY="-dirty"
fi

# Each step's limit is about three times its usual run; its output goes to a log, kept when the gate fails.
source "$REPO_ROOT/app/scripts/limits.sh"
GATE_LOGS="$(mktemp -d)"
export GATE_LOGS

run_gate() {
  step "$@" || { echo "  rerun from $(pwd): ${*:3}" >&2; exit 1; }
}

run_gate 300 "[1/4] The fast checks (app/scripts/gates/verify.sh)" bash "$REPO_ROOT/app/scripts/gates/verify.sh"
run_gate 60 "[2/4] Running Python test suite (contracts & drift)" python3 -m pytest radar/tests/ -q

cd "$REPO_ROOT/app"
run_gate 120 "[3/4] a. Vitest suite (build, guards, integration)" npm test

# The emulators' hosting serves the gates' build from firebase.gate.json, with their hosts in the CSP.
run_gate 60 "[3/4] b. The gates' hosting config" node --experimental-strip-types scripts/gates/test-hosting.ts
# The Storage emulator's files live under TMPDIR, which other emulator runs share and remove.
GATE_TMP="$(mktemp -d)"
# A crashed Firebase CLI leaves its Java emulators up: stop what this checkout left on an emulator port.
sweep() {
  for port in $(python3 -c 'import json, sys
emulators = json.load(open(sys.argv[1]))["emulators"].values()
print(*(v["port"] for v in emulators if isinstance(v, dict) and "port" in v))' "$REPO_ROOT/firebase.json"); do
    for pid in $(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null); do
      if [[ "$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')/" == "$REPO_ROOT"/* ]]; then
        kill "$pid" 2>/dev/null || true
      fi
    done
  done
}
trap 'sweep; rm -f "$REPO_ROOT/firebase.gate.json"; rm -rf "$GATE_TMP"' EXIT
EMULATOR_GATE="[4/4] Emulator gate: store suites, the site built from Firestore, Playwright, perf budgets and smoke"
run_gate 900 "$EMULATOR_GATE (fixtures, demo-mvradar)" \
  env TMPDIR="$GATE_TMP" npx firebase emulators:exec --config ../firebase.gate.json \
    --only firestore,storage,hosting,auth --project demo-mvradar "bash scripts/gates/emulator.sh"

rm -rf "$GATE_LOGS"
echo "GATES: PASS (commit=${COMMIT_SHA}${DIRTY}, node=$(node -v))"
# A clean pass is recorded for its tree: a push or deploy of the same tree here does not run the gate again.
if [[ -z "$DIRTY" ]]; then
  bash "$REPO_ROOT/app/scripts/gates/record-pass.sh" "$TREE"
fi
