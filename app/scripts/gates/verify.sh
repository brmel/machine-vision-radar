#!/usr/bin/env bash
set -euo pipefail

# The fast checks, about 15 s: `npm run verify`, the pre-commit hook, and the first step of check.sh.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/app/scripts/limits.sh"
if [[ -z "${GATE_LOGS:-}" ]]; then
  GATE_LOGS="$(mktemp -d)"
  trap 'rm -rf "$GATE_LOGS"' EXIT
fi
export GATE_LOGS

run_step() {
  step "$@" || { echo "  rerun from $(pwd): ${*:3}" >&2; exit 1; }
}

run_step 60 "[verify 1/10] The model and the registry" python3 -m radar model validate
run_step 60 "[verify 2/10] Generated files (fix: python3 -m radar model generate)" \
  python3 -m radar model generate --check
run_step 60 "[verify 3/10] The repo guards" python3 -m pytest radar/tests/repo -q -p no:cacheprovider
run_step 30 "[verify 4/10] Unused imports, variables and redefinitions (ruff)" \
  python3 -m ruff check radar --select F401,F841,F811
run_step 30 "[verify 5/10] Unused Python (vulture, confidence 60, radar/vulture.toml)" \
  python3 -m vulture radar --config radar/vulture.toml
cd "$REPO_ROOT/app"
run_step 60 "[verify 6/10] TypeScript" npx tsc --noEmit
run_step 60 "[verify 7/10] The site's guards" npx vitest run tests/guards --reporter=dot
run_step 60 "[verify 8/10] Unused exports, files and dependencies (knip)" npm run knip
run_step 60 "[verify 9/10] Architecture boundaries (depcruise)" npm run arch
run_step 60 "[verify 10/10] Duplicated code (jscpd, its key in app/package.json)" npm run duplication
echo "VERIFY: PASS"
