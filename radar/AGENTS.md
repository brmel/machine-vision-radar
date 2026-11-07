# radar/ — the pipeline, the agent CLI and the function

`python3 -m radar <noun> <verb>`, run from the repo root. The CLI's contract (shape, `--json`, exit codes, logs, access
to the project, AI spend) is `docs/CLI.md`; the model, `docs/DATA_ARCHITECTURE.md`; the store and the function, `docs/SYSTEM.md`; search and
the AI uses, `docs/SEARCH.md`.

## Map

| package | holds |
|---|---|
| `paths.py` | the repo root and every derived path, resolved once; nothing else computes one |
| `cli.py` | argparse dispatch only: the nouns and verbs of `adapters/console/parser.py`; it hands each command `args.wiring` |
| `commands/` | one module per command group: `catalog/` (reads, ask, eval), `data/` (validate, quality, category, hub, metrics), `build/` (site export, index, model generate), `store/` (store, change, media), `review/` (proposals, catalog editing, admin, ai-caps, feed, agent tokens, mcp, research) |
| `domain/` | pure, reading no file and not the environment: `model/` (`model.py` the `Model`: schema and registry, loaded once by the wiring, and its one record parser; generated entities, schema, registry, dates, `catalog.py` the in-memory Catalog, `history/` with the changeset and `plan.py`, what `Model.change` takes and gives), `validation/` (every rule a `Rule`, their `Verdict`), `ports/` (every interface, one a file, by what it serves), `review/` (proposals and review, its one entry; `feed/` the news desk; `agents/` outside agents and research runs), `search/`, `ai/` (the Answerer, quota, grounding, caps, the Meter, prompts, evals), `read_model/` (the views; `derived/`; it and `validation/` never import each other) |
| `build/` | `codegen/` (`model generate`) and `llms` (`site export`) |
| `adapters/` | `wiring/` (the composition root: `stores.py` the store ports, `models.py` the search and AI ports), `console/` (log, output, the command tree), `files/` (a catalog folder and its kept files, the model JSON, the prompt registry), `firestore/` (the `Docs` port, layout, projection, writer, whole-store jobs, repository, server-only `ledgers/`), `storage/` (the BlobStore, and the in-memory ChangeLog), `ai/` (`search/`, the one SearchEngine: the sharded index, its ranking, records and files, and fastembed; `scripted.py`; `prompted/`, one adapter per model port, each on the `ModelRunner`; `runners/`, that port's runners: `chat_completions.py` and `adk.py`, the latter the only module that imports ADK or Gen AI), `web/` (`function.py`, the only module that imports Firebase's functions SDK; `api.py`, the public routes; `admin/`, the founder's API; `mcp.py`; `pages.py`, the `Reader`: the only code that calls a maker's site; `app_check.py`) |
| `tests/` | pytest mirroring `radar/`, plus `repo/` (repo-wide guards), `generated/`, `store/` (store suites and the CLI on the emulators), `fixtures/` (fictional only) |

## Python rules

- `from __future__ import annotations`; every public function annotated (`test_architecture`).
- One blank line between definitions, never two in a row outside a string (`test_layout`).
- Layers: `domain/` never imports `adapters/` or `build/`; command groups never import each other; no module named
  `types.py`, and none that nothing imports (`test_architecture`).
- `cli.py` only dispatches; a command module parses, calls domain objects and formats (AGENTS.md rule 17).
- Every command takes `--json`, in the shape `contracts/operations.json` gives it; every noun, verb, argument and flag
  has accurate help, which is its documentation (`test_cli_contract`).
- One logger, `adapters/console/log.py`, on `contracts/logging.json`; nothing else prints (`test_logging`).
- Dependencies: `radar/requirements.txt` is the function's runtime, `requirements-dev.txt` the tests and gates;
  `fastembed` and `google-adk` are imported only where used.

## One test fast

- `python3 -m pytest radar/tests/<path>::<test> -q`; the repo guards: `python3 -m pytest radar/tests/repo -q`.
- The store suites skip without emulators. Start them (`cd app && npm run emulators`), then from the repo root:
  `FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_STORAGE_EMULATOR_HOST=127.0.0.1:9195 python3 -m pytest
  radar/tests/store/<file> -q`. The ports are `firebase.json`'s `emulators`.

## Fixture and env

A fictional catalog seeds the emulators, as the emulator gate does (`app/scripts/gates/emulator.sh`):

```sh
python3 -m radar.tests.fixtures.fixture_category <dir> 16
MVR_DATA=<dir> python3 -m radar store load <dir>/data --blobs <dir>/blobs   # with the emulator hosts set
MVR_DATA=<dir> python3 -m radar index rebuild
```

| variable | sets |
|---|---|
| `MVR_PROJECT`, `MVR_ACCESS_TOKEN` | the project the CLI reaches and its token (`docs/CLI.md`) |
| `MODEL_API_KEY` | the Meta Model API key a Muse Spark call sends (`docs/SEARCH.md`) |
| `FIRESTORE_EMULATOR_HOST`, `FIREBASE_STORAGE_EMULATOR_HOST`, `FIREBASE_AUTH_EMULATOR_HOST` | the emulators the ports use |
| `MVR_FIREBASE_PROJECT` | the emulators' `demo-` project (default `demo-mvradar`) |
| `MVR_FIRESTORE_DATABASE` | the database, default `(default)`; another is a replay or restore target |
| `MVR_DATA` | the data folder (registry, prompts, banned words), from the repo root; empty or unset: `data` |
| `MVR_STORAGE_BUCKET`, `MVR_MEDIA_BASE` | the bucket and the host of a media URL (the emulator's) |
| `MVR_WEB_BASE` | where a research run's reader reads recorded pages (tests) |
| `MVR_AGENT_TOKEN` | `mcp serve`'s agent token |
| `MVR_EMULATOR_GATE` | set by the emulator gate: a store suite without emulators fails instead of skipping |

`--project` beside a test-only variable is refused (docs/CLI.md, Access).

## Recipes

- **A CLI command:** its noun in `adapters/console/parser.py` (if new); the verb in `commands/<group>/`, calling a
  domain object; an entry in `contracts/operations.json` (id, summary, `cli`, the `--json` output schema, and its
  admin screen or MCP tool if any); a test in `tests/commands/` (store-backed ones in
  `tests/store/cli/`).
- **A tool for an agent** (a better crawler, a feed reader): an adapter of the port its loop already calls
  (`domain/ports/web/reader.py` for pages and files), picked in `adapters/wiring/`, with no domain change. A new kind
  of tool is a port in `domain/ports/<area>/` that the loop calls; the model never calls one (AGENTS.md rule 15).
- **An AI use:** a port in `domain/ports/ai/`; its adapter in `adapters/ai/prompted/`, on the `ModelRunner`; its scripted
  model in `adapters/ai/scripted.py`; both wired in `adapters/wiring/models.py`; its prompt
  `data/prompts/<use>.md`; its model and caps in `data/registry/ai.json`; calls through the `Meter`;
  an eval case for `radar eval run`; a line in `docs/SEARCH.md`'s AI uses, and a row in its agents table when it is a
  new agent.
