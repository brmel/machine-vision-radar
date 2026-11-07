# `python -m radar`: the CLI

`python -m radar <noun> <verb> [flags]`, run from the repo root. Its modules: `radar/AGENTS.md`; the store:
[SYSTEM.md](SYSTEM.md); search and the AI uses: [SEARCH.md](SEARCH.md); the model:
[DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md); outside agents: [MCP.md](MCP.md).

## Access

- **The project:** `--project <id>` (default `MVR_PROJECT`; `.firebaserc`'s project only) reaches its Firestore and
  Storage with the short-lived token in `MVR_ACCESS_TOKEN` (`gcloud auth application-default print-access-token`, never
  a key file), **read-only unless `--yes`**, and refuses any emulator or fixture variable set beside it (`TEST_ONLY` in
  `radar/adapters/wiring/stores.py`).
- **The registry the site serves:** with `--yes`, a command exits 1 before it writes when the registry here would publish
  another RegistryView than the store's `public_index/registry`: run from the deployed commit, or deploy first. The
  commands that publish the registry themselves (`store load`, `replay`, `reproject`, `restore`; `publishes` in
  `Commands.verb`) are exempt.
- **The emulators** serve the store otherwise, when `FIRESTORE_EMULATOR_HOST` and `FIREBASE_STORAGE_EMULATOR_HOST` are
  set, on a `demo-` project (`MVR_FIREBASE_PROJECT`) with no credentials. With neither, a command that needs the store
  exits 2. A file is read only when named (`model validate <path>`, `store load`).

## Shape, output, exit codes

- `radar --help` lists the nouns, `radar <noun> --help` the verbs. Global flags: `--verbose`/`-v` (debug logs),
  `--quiet`/`-q` (errors only), `--json`, `--project`, `--yes`.
- **`--json`**, before the noun or after the verb: one JSON document on stdout, in the shape `contracts/operations.json`
  gives the command. Logs and errors go to stderr (JSON lines with `--json`) through `radar/adapters/console/log.py`,
  on `contracts/logging.json`; an error with a remedy carries `fix`.
- **Exit codes:** `0` success; `1` failure (a refused changeset, a missing record, a failed check, a cap, a missing
  `fastembed` or `google-adk`, with its install command); `2` usage or setup (a bad flag or argument, no store, no
  search index).
- `--actor A` (default `founder`; `feed detect`'s, `feed detector`) names who acts; a decision takes `--note N`, a
  proposed change `--reason R`.
- A list gives 20 rows a page, its `total`, and the `next` cursor `--cursor` takes.

## Commands

`radar --help` lists the nouns, and `radar <noun> <verb> --help` each verb's arguments, flags and limits;
`contracts/operations.json` gives every command its `--json` shape, its admin screen and its MCP tool.
`store export <dir>` writes the store as the catalog folder `store load` reads; the maintainers keep the
production store's snapshot in their private data repo. A structural move is a plan that `store rewrite` applies to an
export offline, or `model migrate` files through review (DATA_ARCHITECTURE.md §7).

## Gotchas

- **AI spend.** `catalog ask`, `eval run ask|solve|draft|datasheet|image_judge`, `research run` and `feed draft --ai` call the
  use's model under the caps ([SEARCH.md](SEARCH.md)), recorded in `ai_calls`; on the project they need `--yes`. The
  emulators run the scripted models.
