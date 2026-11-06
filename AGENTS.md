# AGENTS.md — Machine Vision Radar

A structured radar of the machine-vision industry, to be the source of truth about machine vision: validated product
and vendor records, a React+Vite site, and a CLI-first agent interface. One maintainer, the founder, decides
what gets built; the gates decide whether it's done. This file binds every change; it wins over an issue's text.

**Two repos**: this one, public, holds the code and `data/`, what the code is driven by (the registry, the
agents' prompts, the banned words). The catalog itself lives in the store, and its snapshot, the plan and the issues in
the maintainers' private tracker. Every path here is relative to this repo's root, and every command runs from
there. Code finds `data/` through `radar/paths.py` and `app/scripts/head.ts` alone (`DATA`: `MVR_DATA`, else `data`;
`test_layout`).

**Per system** (loaded when you touch its files): `app/AGENTS.md`, `radar/AGENTS.md`, `contracts/AGENTS.md`.
**Owners:** `docs/CLI.md` (the CLI, access to the project, AI spend), `docs/DATA_ARCHITECTURE.md` (the model,
validation), `docs/SYSTEM.md` (the store, read and write paths), `docs/SEARCH.md` (search, every AI use),
`docs/BRAND.md`, `docs/LEGAL.md`. **Skills** (`.claude/skills`): `radar`, `verify`, `standards-review`, `architecture`,
`brand-content`, `slice` (the founder's). **Agents** (`.claude/agents`): `Explore`, `reviewer`.

## How work happens

1. **The plan is the maintainers' private tracker.** A milestone is a sprint, `Sprint N · <goal>`: its
   description is the goal, its issues the stories. The current sprint is the open one with the lowest number; nothing
   outside it starts without the founder, and one issue at a time is finished before the next starts. Open issues
   without a milestone are the backlog. Every issue has an area label (`model`, `acquisition`, `review`, `site`,
   `search`, `insights`, `repo`), and its acceptance criteria are its scope. There is no plan file in the repo. An
   outside contributor's issue or PR here is triaged into it; [CONTRIBUTING.md](CONTRIBUTING.md) says how to send one.
2. **Design first, whole or not at all.** Before an issue's first line, post a **Design** comment on it: the domain
   objects and ports it touches, the data shape it adds or changes, the tests that will prove it, what it leaves out.
   The code matches it and the criteria; a departure is a decision comment first. An issue ships complete: no
   placeholder, stub, flag hiding unfinished work, unreachable path, `TODO` or "follow-up". What cannot be finished is
   split into its own issue before the PR, which names it. What a change replaces goes in the same commit.
3. **A sprint ships as one PR**, with one gate run. A change to how the site looks is shown to the founder as
   before/after screenshots, desktop and mobile, before the merge. Then the merge, which deletes the sprint's branch
   (between sprints, `main` is the only branch), a manual test pass, the founder's deploy and a cleanup that lowers the
   line count; the cleanup runs the emulator stage first and drops a test as covered only once the covering test goes
   red with the guarded code removed (commands: the verify skill).
4. **Keep the issue true.** Tick each criterion as it lands; the merged PR is the release note. The sprint's PR closes
   with a **Retrospective**: the bad patterns the sprint exposed, their cause and the fix, done now if a few lines,
   else an issue.
5. **No untracked work.** Found something outside the sprint? Open an issue with its area label (and `bug` for a
   defect); don't fix it on the side. Parked issues carry `not-now`; research and curation carry `curation`.
6. **No process files.** Vision, roadmap, plans, sprint docs and session logs live in GitHub, never in the repo. PR
   screenshots go in `../MVRadar-screenshots/pr-<n>/`, beside the repo and outside git (`test_layout`), with a README
   naming each.
7. **Decisions live in GitHub:** a comment on the issue (at least two options, the choice, why, reversal cost, when to
   revisit) and the `decision` label. **Plain names:** "Firestore move #167", never a sprint, step or model code
   (`test_docs`).
8. **Review, and ask.** Before committing, run the standards-review skill on the diff; fix or rebut each finding. Unsure?
   Ask in the issue; don't guess.
9. **Interface first.** Each pillar (model, acquisition, review, site, search, insights) has one top-level module,
   whose interface an `interface` issue states: its input, its output, how it starts and stops when it runs, its
   errors, and the measure that scores the pillar. Work that deepens a pillar names that issue, starts once it is
   closed, and keeps the interface as it is; changing it is a new `interface` issue, designed twice. The rule holds
   back capability work; defects, validation rules and measures go ahead without a closed `interface` issue. Only
   typed values cross an interface (Standards 6). One maker's products go from its site to ours before every maker's
   do. Polish waits until every pillar scores 7 on both of the architecture skill's scores; the skill runs at a
   sprint's start and in its Retrospective, and the sprint's PR shows its scorecard before and after.

## Session habits

- One session per sprint. Independent reads, greps and commands go in one message.
- `grep -n`, then `sed -n 'A,Bp'` on the range; no whole-file `cat` of a long file, no multi-file dumps.
- Fetch the slice issue once: `gh issue view N --json title,body,comments --jq '.title, .body, (.comments[].body)'`.
- Run the gate in the background under its limit and await its exit (the verify skill); never poll its log.

## Gates

Local, through `.githooks/` (`npm run setup` wires them), on fixtures, in emulators on a `demo-` project, with no
credentials. Each step runs under its own limit, about three times its usual run (`app/scripts/limits.sh`), and is
stopped past it with everything it started. All gates green before every push. Never commit red. Never weaken a gate.

- **Pre-commit**, on a working tree equal to what is committed: `npm run verify` (`app/scripts/gates/verify.sh`, about
  15 s): `radar model validate`, `model generate --check`, the repo guards (`radar/tests/repo`), ruff's unused-import
  rules, vulture, tsc, the site's guards (`app/tests/guards`), knip, depcruise and jscpd.
- **Pre-push**, on a clean tree: `npm run check` (`app/scripts/gates/check.sh`, which names each step), ending with
  `GATES: PASS (commit=<sha>, node=<version>)`. A pass is recorded for its tree; pushing a passed tree or deleting a
  ref runs no gate.
- **Deploy**, the founder's alone and a separate step from done: `cd app && npm run deploy:local`
  (`app/scripts/deploy.sh` prints its steps). `.claude/hooks/guard.sh` refuses it, a radar `--yes` and
  `--no-verify`; only the founder's go in this session lets you prefix `FOUNDER_GO=1`.

## Standards

Binding for every change. A rule a tool enforces names it in parentheses; the tool's message says what to fix.

### Code

1. **Less code wins.** The best diff is a deletion. Never add a second way to do what one way already does.
2. **No dead code**, commented-out code, debug print or TODO without an issue number (knip, vulture,
   `i18n-keys.test.ts`, `test_every_radar_module_is_imported`).
3. **No speculative abstractions.** One use → inline. Two → consider a helper. Three → extract. No config for a single
   value, no `utils.py`/`helpers.ts` grab-bags.
4. **Small pure functions:** explicit arguments and return values, no hidden state, cyclomatic complexity ≤ 10
   (`test_layout`; `shape.test.ts`, whose allowlist only shrinks).
5. **Explicit over clever.** No metaprogramming; no regex where a split works. Names say what a thing is (`data`,
   `info`, `manager`, `handle` are banned). No comments or docstrings: names and types say what, the commit and
   the issue say why; the only ones are the marks a guard reads (`test_layout`).
6. **Typed boundaries.** Strict TS, no `any`, no `!` without a reason; Python public functions annotated, with
   `from __future__ import annotations`. No `Record<string, unknown>`/`dict[str, Any]` in domain logic: parse once at
   the boundary into unions and interfaces. An `as` cast in production TS has `// Justification (typed boundary): …`
   on the line above (`test_architecture`, `test_boundaries`, `shape.test.ts`).
7. **Boring tech.** Stdlib and existing deps first. A new dependency's commit message says what it replaces, why
   stdlib can't, and its weight. Heavy optional deps (`fastembed`, Firebase) degrade gracefully and stay lazy and
   code-split.
8. **Generated files are never hand-edited:** fix the generator, regenerate; output is byte-stable and carries no
   clock value (pre-commit `model generate --check`; the files: `contracts/AGENTS.md`).
9. **Secrets never reach the browser.** `app/` reads no API key but the public Firebase web config; LLM and other
   paid APIs run server-side only.
10. **Current state only:** no deprecated code, migrations, compat or re-export shims, legacy branches; all files
    migrate in the same change (`test_no_deprecated_legacy_or_compat_code`).

### Data

11. **A missing product is ALWAYS better than a wrong product.** Provenance or it didn't happen; nullable beats
    invented; the validator is the gate. Agents and AI suggest, the founder approves, nothing auto-publishes. The UI
    shows provenance and unknowns honestly, states each listing's count, reveals filters progressively (one filter
    panel per view), and leaves out anything it cannot back with data.
12. **Dates come from the clock.** Never a planned date: no record, file name, heading, doc or commit carries a date
    later than today. PartialDates declare their precision; a source's retrieval date is its actual access.
13. **Code, contracts and the registry never name a vendor;** vendor names live in the store and the curation
    dataset, and no domain logic branches on one (`test_data_driven`).

### Design

14. **One provider per port**, declared apart from its implementation (the `ModelRunner`'s model entries choose
    theirs: rule 15). A new provider replaces the old one in the same
    change, as one new adapter and no domain change; none runs beside it as a fallback or backup. Only `adapters/`
    imports a provider SDK (Firebase, Google Cloud, `fastembed`, ADK, Gen AI, `zod`, generated schemas) or makes a raw
    HTTP call (depcruise, `providers.test.ts`, `test_boundaries`).
15. **Agent seam.** LLM code sits behind one SDK-agnostic port per role in `domain/ports/ai/`, our own types in and out,
    each with a scripted model for tests and emulators. A use's adapter (`adapters/ai/prompted/`) renders its prompt
    and runs it on the `ModelRunner` port, server-side only. Its runners are the Meta Model API
    (`adapters/ai/meta/runner.py`) and Google ADK on Vertex AI
    (`adapters/ai/adk/runner.py`); a model's `provider` in `data/registry/ai.json` picks one in
    `adapters/wiring/models.py`, so each use runs on exactly one, never one as the other's fallback. Every
    prompt is one file a use in `data/prompts/` (`test_prompts`); every model call goes through the `Meter` (caps
    before, usage after). Outside agents' code is one package each side: `radar/domain/review/agents/`,
    `app/src/domain/ports/review/agents/`.
16. **Real domain objects:** typed objects with tight interfaces and one responsibility each (Product, Organization,
    Claim, Catalog, SearchEngine…), not loose dicts, free functions or scattered commands. Values are immutable;
    export only what a caller needs.
17. **Thin commands.** CLI handlers, routes and views parse input, call domain objects and format output.
18. **Interfaces and implementations never share a file** (`test_protocols_stand_alone`, `shape.test.ts`).
19. **No filler:** no re-validating typed values, no catch-and-ignore, no wrappers that only forward calls.
20. **Size and folders:** no file over 300 lines; at most 7 entries per code folder; no folder named `utils`, `misc`,
    `helpers`, `common`, `lib` or `config`; the root shows only `app/`, `radar/`, `contracts/`, `data/`, `docs/` and
    files tools require (`test_layout`, which lists the exceptions).
21. **Generic, data-driven code.** Code never names a category, spec or vocabulary term: it derives them from the
    registry and the read model, and reads a term's meaning off its marks, so a new one is a registry change only
    (`test_data_driven`; its docstring holds the allowlist and homonym rules).

### Tests and definition of done

- **Every test must fail without the fix:** red, fix, green, revert the fix, red again.
- End-to-end and integration tests only (the founder, 2026-11-02), beside the repo guards and the generated-file
  checks: real bundle, real flows, through a pillar's entry. No unit test of one function. Never mock our own
  modules; fake only true external boundaries (network, clock, Firebase). No snapshot tests of generated output,
  no "mock was called" tests, no `sleep`, no dependence on order, wall-clock or network. No inline asserts in
  `check.sh`.
- Keep the suite small: a test for deleted code goes in the same commit. One e2e spec per page kind: a slice extends
  it, never adds a spec that loads the same pages again. Tests live in `radar/tests/` and `app/tests/` only.
- **Definition of done:** merged with every acceptance criterion met; `npm run check` green on Node 22; verified in a
  real browser against the production build (Firebase emulator where hosting or auth matter); a Playwright e2e test
  for every feature added or changed (EN, plus FR where it shows text); every data capability reachable from the
  `radar` CLI, with the site, API and MCP on the same domain objects; failures through the shared logger with a clear
  message and a non-zero exit, or a visible error state on the site; a design review against Design; the code matches
  the slice's Design comment.

### Commits

- Conventional Commits (`type(scope): subject`), one issue per commit; the body ends with `Refs #N` for this repo's
  issues (or `Closes …`)
  and a `Lines: +A/-D` trailer (`.githooks/commit-msg`).
- Never commit secrets, `node_modules/`, build output or local env files.
- A PR description quotes the clean `GATES: PASS (commit=<sha>, node=<version>)` line; a `-dirty` one is rejected.
- Docs travel with code: a behaviour change updates its owning doc in the same commit, or deletes it; a doc pointing
  to a deleted path is fixed. Each fact lives in one place, and the others link to it; volatile facts (counts, file
  lists) live in code.
