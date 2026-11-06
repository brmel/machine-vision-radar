#!/usr/bin/env bash
set -euo pipefail

# The emulator gate, run by check.sh inside `firebase emulators:exec`, which sets the *_EMULATOR_HOST variables.
# Fixtures only; no credentials. Each step's limit is about three times its usual run.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/app/scripts/limits.sh"
: "${GATE_LOGS:=$(mktemp -d)}"
export GATE_LOGS
export MVR_EMULATOR_GATE=1 MVR_FIREBASE_PROJECT=demo-mvradar MVR_STORAGE_BUCKET=demo-mvradar.appspot.com
export MVR_MEDIA_BASE="http://${FIREBASE_STORAGE_EMULATOR_HOST}"
# fastembed's model comes offline from a cache that outlives the run's TMPDIR: the gate downloads nothing.
export FASTEMBED_CACHE_PATH="${FASTEMBED_CACHE_PATH:-${XDG_CACHE_HOME:-$HOME/.cache}/fastembed}" HF_HUB_OFFLINE=1

step 240 "store suites" python3 -m pytest radar/tests/store radar/tests/adapters/web radar/tests/domain/review \
  radar/tests/commands/test_search_admin.py radar/tests/commands/test_feed.py radar/tests/domain/test_budget.py \
  radar/tests/adapters/test_answers.py radar/tests/adapters/test_search_engine.py -q

FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT
step 60 "fixture" python3 -m radar.tests.fixtures.fixture_category "$FIXTURE" 16
step 60 "fixture loaded" env MVR_DATA="$FIXTURE" python3 -m radar store load "$FIXTURE/data" \
  --blobs "$FIXTURE/blobs" >/dev/null
step 60 "fixture's search index" env MVR_DATA="$FIXTURE" python3 -m radar index rebuild

# The function's routes on the scripted answer model, behind vite preview's /api proxy; its log is printed on failure.
MVR_DATA="$FIXTURE" python3 -m radar.tests.fixtures.ask_server 5056 2>"$FIXTURE/ask-server.log" &
ASK_SERVER=$!
trap 'status=$?; kill "$ASK_SERVER" 2>/dev/null
  [[ $status -eq 0 ]] || tail -n 40 "$FIXTURE/ask-server.log" >&2; rm -rf "$FIXTURE"' EXIT
export MVR_ASK_LOCAL="http://127.0.0.1:5056"
curl -s -o /dev/null --retry 30 --retry-delay 1 --retry-connrefused -X POST "$MVR_ASK_LOCAL/api/count" \
  || { echo "the gate's ask endpoint did not answer on $MVR_ASK_LOCAL" >&2; exit 1; }

export MVR_FIRESTORE_DOCS="http://${FIRESTORE_EMULATOR_HOST}/v1/projects/demo-mvradar/databases/(default)/documents"
# The admin is in the build, as in the deploy's, signed in on the Auth emulator with a demo web config.
export VITE_ENABLE_ADMIN=true VITE_FIREBASE_API_KEY=demo-key VITE_FIREBASE_AUTH_DOMAIN=demo-mvradar.firebaseapp.com \
  VITE_FIREBASE_PROJECT_ID=demo-mvradar VITE_FIREBASE_APP_ID=demo-app \
  VITE_FIREBASE_AUTH_EMULATOR="http://${FIREBASE_AUTH_EMULATOR_HOST}"
export MVR_E2E_FIXTURE="$FIXTURE"
cd app
step 120 "production build" npm run build
step 60 "byte-stable build" npx vitest run tests/build/build-deterministic.test.ts
step 60 "prerender from Firestore" npx vitest run tests/build/prerender.test.ts -t "Firestore emulator"
step 180 "Playwright" npx playwright test
step 60 "smoke on the hosting emulator" env SMOKE_BASE_URL=http://127.0.0.1:5055 npx playwright test
step 400 "Playwright, store writes" npx playwright test --config playwright.emulator.config.ts
