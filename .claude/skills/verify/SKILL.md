---
name: verify
description: Use before a commit, a cleanup commit or a push, or when a gate fails. The fast check of one test per runtime, the red check that proves a test, the emulator stage, and how to read a gate's failure.
---

# verify

The gates are AGENTS.md's (Gates); `app/scripts/gates/check.sh` names every step. Never commit red; never weaken a
gate.

## One test fast

Python: `radar/AGENTS.md`, One test fast. TypeScript and Playwright: `app/AGENTS.md`, One test fast.

Done when the test you touched and the pre-commit hook's checks pass.

## The red check

Every test must fail without its fix. With the fix and its test both in the working tree:

```sh
git diff -- <the fix's files, not the test's> > "$TMPDIR/red-check.patch"
git checkout -- <the fix's files>
<run the test>          # expect red, failing on the line the fix guards
git apply "$TMPDIR/red-check.patch"
<run the test>          # green again
```

Not `git stash`: worktrees and other sessions share its stack.

Done when you saw it red for the right reason, then green. A test dropped as covered goes only after the covering
test turns red with the guarded code removed, the same way.

## Before a cleanup commit

A cleanup (code removed or merged, no feature) also runs the emulator stage, whose store-writing Playwright specs
alone see what the admin still sends. From `app/`:

```sh
node --experimental-strip-types scripts/gates/test-hosting.ts
env TMPDIR="$(mktemp -d)" npx firebase emulators:exec --config ../firebase.gate.json \
  --only firestore,storage,hosting,auth --project demo-mvradar "bash scripts/gates/emulator.sh"
rm ../firebase.gate.json
```

The Storage emulator keeps its files under `TMPDIR`, hence a folder of its own. Done when it ends green.

## Before a push

`npm run check` on a clean tree. It takes 9–12 minutes, past a foreground call's limit: run it in the background as
`bash -c 'source app/scripts/limits.sh && timed 1500 "npm run check" npm run check' > <log> 2>&1` and wait for its
exit, without polling. A pass prints one line a step and ends with
`GATES: PASS (commit=<sha>, node=<version>)`, the line a PR quotes. Done when that line is printed with no `-dirty`.

## A failure

A failing step prints `FAIL <step>`, its last lines (the nested step's block, when one inside it failed), `log:
<path>` and `rerun from <dir>: <command>`. Read that block; open the log only with `grep -n`; rerun that step alone,
not the gate.

- **Generated drift:** `python3 -m radar model generate`, and commit what it writes.
- **`test_data_driven.py`:** derive the id from the registry, or add an allowlist entry with its
  `# Data-driven exception: <why>` mark.
- **A stuck emulator:** on exit the gate stops what this checkout left listening on `firebase.json`'s emulator
  ports; run it again.
- **An embedding model not cached:** the emulator stage reads fastembed's models offline from `~/.cache/fastembed`.
  The error gives the command that fetches the missing one; run it once with the network on.
