# Machine Vision Radar

A sourced catalog of machine-vision products and the companies that make them: cameras, lenses, lighting, frame
grabbers, 3D sensors, code readers, vision software and more. Every published value cites the page or datasheet it
came from. Research agents propose new records, a person approves them, and a validator guards every write.

Live at **[mvradar.web.app](https://mvradar.web.app)**, in English and French.

## What is in this repo

| | |
|---|---|
| **Site** (`app/`) | React + Vite + TypeScript, prerendered, with search, progressive filters, compare, Ask and a review desk at `/admin` |
| **CLI** (`radar/`) | `python3 -m radar <noun> <verb> [--json]`: read, search, ask, validate, propose, review, research |
| **API and MCP** (`radar/adapters/web/`) | one Cloud Function serving `/api/find`, `/api/ask`, the admin API and an MCP server for outside agents |
| **Model** (`contracts/`) | the typed schema that Python, TypeScript and Zod are generated from |
| **Registry** (`data/`) | categories, specs, units, vocabularies, the agents' prompts and the AI settings the code is driven by |
| **Docs** (`docs/`) | the system, the data model, the CLI, search and AI, MCP, brand and legal |

The catalog itself (products, organizations, claims, sources, documents) lives in Firestore and Cloud Storage, never
in this repo. The code is generic: no vendor, category or spec is named in code, and a new category is a registry
change only.

## How it works

```text
maker sites ──► research agent ──► proposals ──► review (a person approves) ──► store ──► read model ──► site, API, MCP
                (any model runner)                  validator on every write      Firestore   prerendered
```

- **Provenance first.** A value without a source is never published; a missing product beats a wrong one.
- **Agents suggest, people decide.** Nothing an agent finds reaches the catalog without approval.
- **One typed model.** `contracts/model/` generates the Python dataclasses, the TypeScript types and the Zod
  schemas, so every layer agrees on the shape.
- **Any model.** Every AI use renders its prompt (`data/prompts/`) and runs it through one `ModelRunner` port. Gemini
  on Vertex AI through Google ADK is today's runner; another provider is one new runner file, chosen in
  `radar/adapters/wiring/models.py`.
- **Search and Ask** rank on words, then on meaning (fastembed), on the server. Ask answers only from catalog
  records and cites them.

Read more: [docs/SYSTEM.md](docs/SYSTEM.md) (the store and the read and write paths),
[docs/DATA_ARCHITECTURE.md](docs/DATA_ARCHITECTURE.md) (the model and validation),
[docs/SEARCH.md](docs/SEARCH.md) (search and every AI use), [docs/CLI.md](docs/CLI.md), [docs/MCP.md](docs/MCP.md).

## Quick start

Requirements: Python 3.12 or later (the function runs on 3.12), Node 22 (`.nvmrc`), and Java 21 or later for the
Firebase emulators.

```sh
python3 -m venv .venv && source .venv/bin/activate   # a virtual environment for the Python requirements
npm run setup    # git hooks, the site's dependencies, the Python requirements
npm run check    # every gate, on fictional fixtures in the emulators; ends with GATES: PASS
```

`npm run check` needs no account and no credentials: it runs on a `demo-` Firebase project with a fictional catalog.

```sh
python3 -m radar --help                    # the CLI's nouns and verbs
cd app && npm run emulators                # Firestore and Storage emulators, for the CLI and the site
```

## Run your own

1. Create a Firebase project. Enable Firestore, Storage, Hosting, Functions and Google sign-in.
2. Put its id in `.firebaserc`.
3. Load a catalog folder into the empty store, then build the search index. The folder holds one JSON Lines file
   per kind and must validate against `data/registry/`. The CLI only reads a project unless `--yes` lets it write
   ([docs/CLI.md](docs/CLI.md)).

   ```sh
   python3 -m radar --project <id> --yes store load <folder> --blobs <files>
   python3 -m radar --project <id> --yes index rebuild
   ```

   To see the whole flow first on a fictional catalog in the emulators, follow
   [radar/AGENTS.md](radar/AGENTS.md), Fixture and env.
4. Deploy: `cd app && npm run deploy:local` ([app/scripts/deploy.sh](app/scripts/deploy.sh) prints each step).
5. Sign in once at `/admin`, then run `python3 -m radar --project <id> --yes admin grant <email>` and sign in again:
   the review desk opens.

The AI uses run on Vertex AI through your Google Cloud credentials, metered against the caps in
`data/registry/ai.json`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The standards every change follows, and the map of each part of the code, are
in [AGENTS.md](AGENTS.md). Report security issues privately: [SECURITY.md](SECURITY.md).

## Licence

Apache-2.0 for the code and `data/`, CC BY-NC 4.0 for the catalog the site publishes:
[docs/LEGAL.md](docs/LEGAL.md).
