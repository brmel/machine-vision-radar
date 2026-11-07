# Search and AI

How the catalog is searched and asked, and how every AI use is built. The store and read model they build on:
[SYSTEM.md](SYSTEM.md); the commands: [CLI.md](CLI.md).

**The agents.** Each is one domain entry whose loop is code: its model makes one structured judgement a step, and its
tools are ports the loop calls (AGENTS.md rule 15). Each model port runs on the runner its registry model's `provider`
picks. A better crawler is another `Reader` adapter
(`radar/domain/ports/web/reader.py`), picked in the wiring.

| agent | entry | loop | model port (prompt) | tools | measure |
|---|---|---|---|---|---|
| research | `Researcher` (`radar/domain/review/agents/research/run.py`) | frontier, read, table or model, file; 8 pages, 40 s | `ResearchAgent` (`research`), `ImageJudge` (`image_judge`), `DatasheetExtractor` (`datasheet`) | `Reader`, `CrawlRecords`, `HeldRecords`, `Files`, `Proposing` | `research measure` |
| search | `SearchEngine`, `Indexer`, `Retriever` | none | none: the `Embedder` | none | `eval run search` |
| ask and solve | `Answerer` (`radar/domain/ai/answerer.py`) | retrieve, answer, ground | `AnswerModel` (`ask`): `Answered` or `Solved` | `Retriever` | `eval run ask`, `eval run solve` |
| news drafts | `Drafter` (`radar/domain/review/feed/drafter.py`) | subject, draft, ground, propose | `ArticleModel` (`draft`) | `Retriever`, `Feed` | `eval run draft` |

- **The search engine** is one port, `SearchEngine` (`radar/domain/ports/search/search_engine.py`): `index` (an update
  or a rebuild), `last_indexed` and `search`. It is implemented by `radar/adapters/ai/search/` (`ShardedSearch`, its
  ranking, records, files and the fastembed embedder); another engine replaces that folder with no domain change. Its measured cold start, the function's first answer after a deploy, is about 2 s (1.70 to 2.00 s over five deploys), so the embedder stays in the function. The
  index is built from the public read model only: `radar index rebuild` embeds every product, `radar index update`
  those whose fingerprint changed, and every applied change runs an update. A product's record: its card, the terms of
  its name and aliases, vendor, category and tag labels, summary and published values (each with its spec's registry
  aliases, so "fps" finds a frame rate), and the values, which its embedding text reads. A category's shard: its
  records (JSON) and their vectors (float16, in record order). Files are named by their sha256 under `index/blobs/`;
  each version's manifest names the embedder, the read model's hash, the shards and each product's fingerprint, and
  `index/current.json` points at it. Only the server reads them. The `Indexer` (`radar/domain/search/indexing.py`)
  records each run in `index_runs`, which `radar index status` reads.
- **One model.** The registry names the embedding model (`model` in `search.json`); the index and every query embed
  with it, on the server. A new model is a registry change and `radar index rebuild`; until then the engine answers a
  query its words match and refuses one that needs vectors (`IndexMismatch`).
- **Ranking** is one algorithm, on the knobs of `data/registry/search.json` (the admin's search settings
  show them): stopwords dropped, terms stemmed, a query term matching the start of a record's terms, field weights
  times the square root of each term's rarity, boosts for a whole word, neighbouring query terms and an exact id, slug
  or name, and a cut relative to the best score. Vectors keep the products at or above `semantic_threshold`. Every
  caller (the site, Ask, `radar product search`, the admin's console, MCP, the evals) asks the one `SearchEngine`,
  which ranks by words, and by vectors alone only when no word matches: the measure backs words first, and the
  embedder reads English. A semantic search (`--semantic`) blends the two by reciprocal rank fusion on `rrf_k`.
- **The site's search box** (`/browse`, `q` in its URL beside the filters) searches on Enter, never while typing, through
  `POST /api/find {words}`, which answers a `Found`: the products, best first, and their ranking, `words` or `meaning`.
  Products found by meaning are listed as "closest matches". The words travel in the body, so no request log keeps
  them. When the search fails (503 without an index), the page says search is unavailable and offers a retry, never
  listing the whole catalog instead. A test holds the site to `radar product search`'s ranking on the fixture, and the
  deploy's smoke spec fails on a search error.
- **Answers, in layers**, each behind its port in `radar/domain/ports/`: the `SearchEngine`, on the `Embedder`; the
  `Retriever` (`radar/domain/search/retriever.py`), which takes the best few products the engine returns
  (`evidence` in search.json) and gives their published values and sources as `Evidence`; the `AnswerModel`, which
  writes `Sentence`s, each citing ids of that evidence; and the `Answerer` (`radar/domain/ai/answerer.py`), which
  refuses a question nothing matches before any model call and keeps the answer only when the grounding check passes.
- **Solving.** The same call solves an application problem: the `ask` prompt returns either sentences (`Answered`) or,
  for a problem (`Solved`), at most three needs, each a few words and the sentences naming the products of the
  evidence that meet it. Every sentence of every need is grounded; a need no product meets has none, and the site says
  so. `AskAnswer.needs` carries them, the answer's `citations` every need's. The Ask page, `radar catalog ask` and the
  admin's console show them. The scripted model reads a request split by `;` as a problem, one need a part.
- **The grounding check** (`radar/domain/ai/grounding.py`) is one, for answers and drafts alike: a sentence that cites
  nothing, cites an id outside the evidence, or states a number what it cites (or the question) does not hold rejects the
  output, with that reason, and the asker gets the `not_enough_evidence` refusal.
- **The AI uses** (their ports: AGENTS.md rule 15) are answers, web research, its image judge (its own use, model and
  caps; each candidate's call counted), datasheet extraction and news drafts, each on its prompt (`ask`, `research`,
  `image_judge`, `datasheet`, `draft`) and its registry model, run through the `ModelRunner` port (`radar/domain/ports/ai/prompts.py`). A model's
  `provider` picks its runner (`radar/adapters/wiring/models.py`). `meta` runs on the Meta Model API
  (`radar/adapters/ai/runners/chat_completions.py`): its OpenAI-compatible chat completions, the prompt's instruction as the system
  message, its output schema as `response_format`, a datasheet as a `file` part and an image as an `image_url` part,
  with minimal reasoning, and the key `MODEL_API_KEY` from the environment, never a file. `local` runs on the same
  runner against an OpenAI-compatible server the caller runs, with no key: Muse Glimmer, Meta's open-weight model
  distilled from Muse Spark, served by Ollama (`ollama run muse-glimmer`) at `localhost:11434`, for the CLI on that
  machine; it reads text and images, not PDFs, so the datasheet use stays on a model that reads files. `vertex` runs
  on Gemini on the project's Vertex AI through ADK (`radar/adapters/ai/runners/adk.py`), with the service account's
  credentials or the CLI's access token. The full request is logged at debug level only. On
  the emulators, for the tests, the gates and the CLI, the scripted models (`radar/adapters/ai/scripted.py`) stand
  in, metered at the use's model's price.
- **Prompts** are files, `data/prompts/<id>.md`, one each, with its inputs, output schema, instruction and message,
  loaded through the `PromptRegistry`; `test_prompts` renders every one against its inputs. Research and datasheet
  extraction read the registry's specs (`radar/adapters/ai/prompted/specs.py`): each one's label, aliases, and a quantity's
  units and bounds; research reads only the profiles of its cards' categories (every one for a maker with no card yet),
  their specs and filters, and names the links its run reads next.
  A page that names one card and holds at least three values in its table or its schema.org properties files them with
  no model call (`radar/domain/review/agents/research/tables.py`): a label finds its spec through the registry's labels
  and aliases, a value is read by its datatype, and a bound, two figures for one spec or two rows that disagree file
  nothing. The labels no
  spec names are kept in the run's log.
- **Each use's model and caps** (`radar/domain/ai/budget.py`, `meter.py`). `data/registry/ai.json` lists the
  models a use may run, each with its provider (a Vertex AI region or the Meta Model API's base URL) and its price per
  million tokens in and out, with its source and
  the day read; the CAD rate; and each use's default model and caps, and all uses' together. An `AiCap` record replaces
  its use's (one per use, the `ai_caps` rule), read on the next call; `radar ai-caps set` and the admin file it. A use's
  port is reachable only through its `Meter`, which on each call checks the use's caps and all uses' against the
  `Budget`'s ledgers and refuses a call past one with the reason (`ask: CAD 2 a month, spent`), opens the port on the
  use's model, and charges the call's tokens at that model's price. Each prompted adapter reads its reply once, into its
  port's types (`read`, `radar/adapters/ai/prompted/reply.py`); a reply that does not fit is `Unparsed`, which the `Meter` records as an `error` and
  charges at its tokens' cost, as its provider bills it.
- **The usage log.** Every model call, and every one a cap refused, is a `model call` line of the shared logger and an
  `ai_calls` doc: use, prompt, model, tokens in and out, cost, latency, correlation id and outcome (`answered`,
  `refused`, `capped`, `error`), redacted like every log line; never the question or the answer.
- **Evals per use** (`radar eval run <use>`). `ask` answers the curated queries (`EvalQuery`) in each of the site's
  languages, whatever their own, and passes one that cites a target or, as Hit@k counts it, a product of its category.
  `solve` asks the problems of a `--cases` catalog file (`EvalQuery` records) and passes one solved with every target
  cited by a need. `image_judge` judges the recorded candidate images of a `--cases` file (each case a product, its
  images as base64 and the photo to pick, or none) and passes one whose best photo is that one.
  The store suites run each use on the fixture and the scripted models with `--floor 1`, under the fixture's `AiCap`
  records, which open the uses the registry caps at 0.
- **The admin's search routes** (`radar/adapters/web/admin/search.py`, under `/api/admin/search/`) each answer what
  their command prints, which a test holds them to. Its Settings tab (`/admin/search/settings`) shows every setting
  above and how it changes: a use's model and caps there, through the queue; the embedding model by a rebuild; prices,
  prompts and search.json's knobs by a registry change and a deploy.
- **The ask endpoint** (`radar/adapters/web/api.py`), on the function behind `/api/**` (SYSTEM.md §1): `POST /api/ask`,
  which the Ask page (`/search`) calls, and `POST /api/count`, which adds the day's anonymous counters (page views,
  searches, clicks, answers and refusals, and from a visit's first count the referring site's name or an AI
  assistant's); no page, query text, address or id is stored. Its `Quota` meters each ask under the caps and serves a repeated question from `ask_cache` at
  no cost, though it still counts for the day and the client; a change of Ask's model leaves the cache as it is. A
  client is the address Hosting appends to `X-Forwarded-For`, never what the client wrote there.

The server-only docs (`radar/adapters/firestore/ledgers/`), which no rule lets a client read:

| Where | What |
|---|---|
| `<use>_usage/{yyyy-mm}` | a use's model spend of the month in CAD |
| `<use>_usage/{yyyy-mm-dd}` | a use's calls of the day; Ask's per client, under a digest of its address and the day |
| `ai_calls/{yyyy-mm-dd}-{random}` | one model call, or one a cap refused, as its usage log line |
| `ask_cache/{digest}` | an answer, by its question's words, language, index version and function revision |
| `metrics/{yyyy-mm-dd}` | the day's searches, empty searches, result clicks, answers, refusals, AI assistant visits |
| `agent_tokens/{id}` | an outside agent's token ([MCP.md](MCP.md)) by its sha256, never the token |
| `agent_usage/{id}-{yyyy-mm-dd}` | what that token used of its limits that day: requests per minute, proposals |
| `research_log/{newest first}-{id}` | a research run as its loop saved it, with its typed scope and lines, newest first; its id is its correlation id |
| `research_cancels/{id}` | the founder's cancel of a run, kept apart so neither write overwrites the other |
