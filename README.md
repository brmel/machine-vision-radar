# Machine Vision Radar

**All machine vision knowledge, in one place.**

Machine vision engineers choose cameras, lenses, lighting, frame grabbers, code readers and software from hundreds of
makers. Each one names the same spec its own way, hides half of it in a PDF datasheet and changes its range without
notice. Machine Vision Radar turns that scattered knowledge into one sourced, searchable body of knowledge, built on
three parts:

- **The catalog.** Every product and every maker, in one vocabulary, with each published value citing the page or
  datasheet it came from. Today: 950 products from 433 vendors in 22 categories, browsed by category, filtered on
  their specs and compared side by side.
- **The news.** What the industry launches and changes, written from the records the catalog holds, every sentence
  citing the products, makers and sources it rests on.
- **Application solving.** Describe an inspection task in plain words ("read small barcodes on bottles moving at
  2 m/s, camera 40 cm away") and get it split into needs, each answered with catalog products whose specs fit, and
  every claim cited.

Live at **[mvradar.web.app](https://mvradar.web.app)**, in English and French. Demo, 2 minutes:
**[youtu.be/_aXJb3SvHYI](https://youtu.be/_aXJb3SvHYI)**.

## AI that grows the knowledge and puts it to work

AI works on both sides of the catalog, and a person stays in charge of what it publishes.

- **Growing the knowledge.** Research agents read makers' product pages and datasheets, extract each spec in the
  catalog's vocabulary with its source, and file proposals. A person approves each one in the review desk, and a
  validator checks every write. A missing product beats a wrong one.
- **Finding your way.** Search ranks on words and on meaning, in either language. Ask answers a question from catalog
  records only and cites each one.
- **Solving an application.** Ask turns a described problem into its needs and answers each from the catalog; a need
  nothing meets is said to be unmet, not filled in.
- **Opening it to other agents.** An MCP server lets outside agents read the catalog and propose changes to it under
  the same review ([docs/MCP.md](docs/MCP.md)).

Every AI use renders a versioned prompt from `data/prompts/` and runs it through one `ModelRunner` port, metered
against per-use caps before each call and logged after it with its tokens and cost. This build adds **Muse Spark**,
through the Meta Model API (`radar/adapters/ai/meta/runner.py`), and points every use at it in
`data/registry/ai.json`; a model's `provider` entry picks its runner, so Muse Spark and Gemini (through Google ADK)
are each one registry line away ([docs/SEARCH.md](docs/SEARCH.md)). The live site still runs Gemini: it switches to
Muse Spark once its Meta key is set.

Code: Apache-2.0. Catalog: CC BY-NC 4.0. The catalog lives in Firestore and Cloud Storage behind the app and is served
through the site, the API and MCP; this repo holds the code and the registry it is driven by, not the data.

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
- **Any model.** Every AI use runs through one `ModelRunner` port; another provider is one new runner file.
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

The AI uses run on the model `data/registry/ai.json` (or a use's `ai-caps` record) names for each, metered against
its caps: Muse Spark needs a Meta Model API key as `MODEL_API_KEY` in the environment; a Gemini model runs on Vertex AI
with your Google Cloud credentials.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The standards every change follows, and the map of each part of the code, are
in [AGENTS.md](AGENTS.md). Report security issues privately: [SECURITY.md](SECURITY.md).

## Licence

Apache-2.0 for the code and `data/`, CC BY-NC 4.0 for the catalog the site publishes:
[docs/LEGAL.md](docs/LEGAL.md).
