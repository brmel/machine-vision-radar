# System

How the catalog runs: the store, the read and write paths, media, and what the pages give search engines and agents. The
model and its rules: [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md); search and every AI use: [SEARCH.md](SEARCH.md); the
commands: [CLI.md](CLI.md).

## 1. System & Deployment

Firestore holds every entity, Change event and public read doc, and Cloud Storage for Firebase every media file, both
behind domain ports; the repo holds only fictional fixtures and `data/` (the registry, prompts and banned words); the store's
snapshot (`radar store export`) stays in the maintainers' private data repo. Pages read only through the `CatalogRepository` port, the CLI through
`CatalogRepository`, `CatalogWriter`, `ChangeLog`, `VersionStore` and `BlobStore`, each one file in
`radar/domain/ports/`. Operations: Firebase Hosting, Firestore, Storage and admin auth.

- **Read path:** static and prerendered, real URLs, no hash routing, no SSR server. `app/scripts/prerender/` streams the
  read model through `CatalogRepository` (each category's listing pages by cursor, each page's products in one batch
  read and rendered on a pool of worker threads, one per core; the organizations a hundred at a time) and writes each
  page's body as the app's server render of its route
  (`app/src/shell/root/server.tsx`, built by `vite build --ssr`): the `App` the browser mounts, in the default language
  with no saved choice, its reads made first, in passes. It writes every product (its view embedded as JSON,
  `#mvr-product`) and its history, vendor, article and static route; each category's hub (`/category/<id>`, with its
  first listing page) and component's hub (`/<path>/<slug>`, the products that use it, at the path its category's
  `component_hub` names); /news's first page and its feed of the latest 50 articles (`/news/feed.atom`,
  `/news/feed.json` in JSON Feed 1.1); the home, the 404, `robots.txt` and the sitemap (§3). The browser's state
  (location, saved language, theme, compared products) enters the app once, at `app/src/shell/root/start.ts`. A
  production build serves the registry and the organizations as files under `/read-model/`, so they cost no read; the
  app's Firestore adapter is REST over `fetch`, lazy and code-split. The build guards: `app/scripts/build-guards.ts`.
- **Reads per page:** a prerendered page reads nothing before the app renders; then a page landed on costs what a client
  navigation to it does, so a change approved after the build shows: a product **1** (`public_products/{id}`, or a query
  on its `slug`), a vendor **1** (`public_organizations/{slug}`), a category page **2** (`public_facets/{category}` and
  one listing page), /news, /market and an article **1** each (`public_index/news`, `public_index/market`,
  `public_news/{slug}`). A vendor, category or component hub page costs 1 more for its recent articles; a product page
  reads none, and the home's latest come with the registry. Browse without a category, a vendor page and a component hub
  each run one paged query on `public_products` for one page of cards, and one `count()`.
- **The function:** one Cloud Function behind `/api` (`radar/adapters/web/`) serves the ask endpoint and the
  catalogue's search ([SEARCH.md](SEARCH.md)), the admin API (`/api/admin/*`, an ID token with the admin claim on every
  request), the MCP server (`/api/mcp`, [MCP.md](MCP.md)) and a reader's error report (`POST /api/report {subject,
  message, source_url?}`). A report carries a limited-use App Check token (reCAPTCHA Enterprise, loaded when the form opens),
  which the function verifies and consumes before filing the report through review: no token, a bad or a replayed one
  answers 401; one App Check cannot check (a 5xx, a 429 or no answer) 503; the same report again counts once more. The
  form names the protection and its owner's policy links only when the build has App Check; a token not given in time
  fails the report, and the next one starts App Check afresh. On a `demo-` project, which has no App Check emulator,
  every report attests. Enforcement stays off for Firestore, Storage and Auth: public reads need no token.
- **Write path:** a **Changeset** is the only write, applied when the founder approves a **proposal** (`radar proposal
  approve`, or `/admin`) or applies one (`radar change apply`). The `CatalogWriter` validates it against its
  neighborhood only (the records it touches, those that refer to them and those they refer to, and those holding a
  value of theirs in a field marked `unique`, before and after); a
  finding the change adds refuses it, and nothing is written. Then, for each changed entity, it appends one Change event
  (DATA_ARCHITECTURE.md §4), stores version n+1 and its snapshot, and rewrites the canonical doc and the public docs the
  change reaches, at most 500 writes a batch. A page is rebuilt from the records it shows: a family keeps the stored
  rows of its unchanged models, as a category page keeps its unchanged cards, so an approval reads as much in a family
  of 200 models as in one of 2; a failed batch puts back the batches before it. A changeset applied twice
  writes nothing. Every job (load, change, rollback, replay, backup, index rebuild or update) has one correlation id, on
  every log line and Change event. Every applied change then updates the search index ([SEARCH.md](SEARCH.md)); the
  deploy rewrites the public docs that differ from what the entities project (`radar store reproject`).
- **Review** (`radar/domain/review/review.py`) is the one entry to the review queue; the CLI, the admin API, the MCP
  server, the news desk, the quality check and research runs call only it. A proposal (the founder's edit or rollback, a
  reader's report, a quality check's quarantine, a news draft, an agent's) carries its changeset, sources, reason,
  author, actor kind and the event it was filed on (`files_on`, stored as its `proposal_kinds` term). Each call takes
  who acts as a typed value (founder, agent, our own job or reader); only the founder decides: `submit` (one draft,
  validated); `file` (a research run's bundle, a refused proposal filed again without the records it names); `decide`
  (approve, reject, retract or edit, or the founder's own change filed and approved at once; each proposal applied on
  its own in dependency order); `queue`, `proposal`; `bundle` (a run's proposals in dependency order, the riskiest
  first); `log` (the audit log, a line per submit, edit and decision with its correlation id). An agent reads its own
  proposals only and holds the `Proposing` port, which cannot decide. Applied Change events name the proposal;
  retracting one returns each record to its version before it, as new Change events.
- **Layout** (`radar/adapters/firestore/layout.py`, derived from the model and the registry). Rules default to deny: the
  `public_*` docs, the search index and public media are world-readable, everything else is read and written with admin
  credentials only, and no client writes anything (`contracts/firebase/`: `firestore.rules`, `storage.rules`).
  `firestore.indexes.json` beside them holds the paged listings' composite indexes and keeps the `json` and `card` text
  fields out of the indexes.

| Where | What |
|---|---|
| `<collection>/{id}` | an entity with its `version`, a collection per kind (`contracts/model/`); claims by `subject` |
| `changes/{id}` | the Change events, append-only, queried by `entity`, or in recorded order from a cursor |
| `versions/{entity}/v/{n}` | each version's fields as JSON text, so `VersionStore.get` is one read |
| `public_index/registry` | the RegistryView, its card chunk count and the date tally a write updates |
| `public_index/organizations`, `public_index/cards-{n}` | every organization brief; the index's cards, 500 a doc |
| `public_index/market` | the MarketView, counted from the index's cards in the same projection as the index |
| `public_index/news`, `public_news/{slug}` | every article's FeedPageView, newest first; an article's FeedItemView |
| `public_products/{id}` | a ProductView, its `slug`, its card, and the fields the paged listings filter and sort by |
| `public_facets/{category}`, `public_facets/{category}/pages/{n}` | a category's facets with their counts; its listing pages of 20 cards |
| `public_organizations/{slug}` | an OrganizationView |
| `public_history/{id}` | a product's HistoryView: its versions and those of each public record naming it, if several |
| `index_runs/{newest first}-{correlation id}` | each search-index update and rebuild: its model, who ran it, the version it made or its error |
| the ledgers | server-only: the AI uses', Ask's and the outside agents' ([SEARCH.md](SEARCH.md)) |
| Storage `media/{2 hex}/{62 hex}.{ext}` | a file by its sha256, with `public` metadata from its rights (§2) |
| Storage `backups/{instant}/{collection}.jsonl`, `backups/{instant}/manifest.json` | `radar store backup`: each doc as `{path, fields}`, and the counts |
| Storage `index/current.json`, `index/blobs/{sha256}.{ext}` | the search index ([SEARCH.md](SEARCH.md)) |

Review's queue and audit log are `proposals/{id}` and `proposal_log/{…}`, newest first; `feed_state/detector` holds
where the news detector stopped in the Change events.

- **Loading and recovery.** `radar store load` seeds an empty store, the emulators' fixture: it validates first (any
  error: exit 1, nothing written), then writes every entity at version 1 through one `import` Change event (an entity
  with recorded changes keeps them) and every file, under one correlation id. `radar store replay` rebuilds every entity
  and public doc from the Change events alone into an empty database, and compares; `radar store backup` and `restore`
  round-trip every collection as JSON Lines, into an empty database.
- **Retention.** Firestore delete protection is on. The managed export (Cloud Scheduler job `firestore-daily-export`,
  03:00 UTC, service account `firestore-export@`) writes `gs://<the default bucket>/managed-exports/`, where a Storage
  lifecycle rule deletes what is older than 30 days; each run rewrites the same names, so the last export goes 30 days
  after the runs stop. `radar store backup`'s sets have no lifecycle; `radar store purge` keeps only the newest. To
  restore: create an empty named database (`gcloud firestore databases create --database=<db> --location=us-central1
  --project mvradar`), then `radar --project mvradar --yes store restore <instant> --into <db>`, or `gcloud firestore
  import gs://<the default bucket>/managed-exports --database=<db>`; nothing is deleted in the console.
- **Headers** (`firebase.json`): HSTS, nosniff, `DENY` framing, `strict-origin-when-cross-origin`, and a strict CSP, the
  admin's its own. The gates and `vite preview` add the emulators' hosts to `connect-src`, `frame-src` and `img-src`
  (`app/scripts/gates/test-hosting.ts`).
- **Not adopting:** an SSR framework, bot sniffing or prerender services, a relational database for writes, business
  logic in the database, a vector database (brute-force cosine is milliseconds here).

## 2. Blob Store

JSON stays text-only. A file lives once, named by its sha256: in Cloud Storage at `media/<2 hex>/<62 hex>.<ext>`
(`radar/adapters/storage/blobs.py`), and in a catalog folder at `<2 hex>/<62 hex>.<ext>` until `radar store load` loads
it (`radar/adapters/files/blob_files.py`). The adapter derives the path from the digest and the mime; only its Firestore
doc stores it (`storage_path`). The `BlobStore` port puts a file once, streams it back verifying its sha256 (`radar
media get`), and gives a public file's URL (`radar media url`). The search index's files and the backups are the bucket
adapter's own, by path; no port names a path.

Every file has exactly one Document (DATA_ARCHITECTURE.md §3.1); `sha256` is the 64-character lowercase hex digest.
Every Source that cites the file points to that Document through `Source.document`. `radar store load` hashes each file
it is given (rule `document_integrity`) and fails on a sha256, bytes or mime mismatch, a mime the `kind` does not allow,
`width`/`height` outside images and videos or `duration` outside videos, a file without a Document, or a Document
without a file; rule `unique` refuses two Documents for one file.

**Rights.** `rights` is a `media_rights` term; a file is public only under a term the registry marks `public` (`own`,
`open_licence`). A public file's page link is its Storage download URL (the object carries `public` metadata, which
`storage.rules` lets anyone read); any other file stays private and its page links the Document's `source_url`. A file a
research run finds is stored private and proposed under the term marked `research` (`vendor`): only the CatalogWriter,
applying an approved proposal, makes a file public, and only under public rights. Video and large PDFs are linked or
streamed, never inlined. The media-rights policy and takedowns: [LEGAL.md](LEGAL.md).

## 3. SEO & GEO

- **Read model:** the store's public docs (§1). Every view is checked against `contracts/model/views.json`, whose TS
  types and zod schemas `radar model generate` writes, and holds only what the CategoryProfile exposes. The fixture
  builder (`radar/tests/fixtures/fixture_category.py`) writes the same views as files for the tests.
- **Sitemap:** written from the same stream as the pages, so they cannot diverge: `sitemap.xml` indexes
  `sitemap-<n>.xml` files of at most 50,000 URLs. A product's `lastmod` is its latest Change that is not an `import` (a
  load only moved it), else the newest `retrieved_at` of its page's sources; an article's is its revision, else its
  publication. A thin product page (not `indexable`) is left out, and its head says `noindex`.
- **Canonical and `og:url`** are set per route on the production origin (`MVR_SITE_URL`, else the `.firebaserc`
  project's), in the prerendered HTML and after the app renders; unknown products and routes render a real 404 view.
  Every image has `alt`.
- **JSON-LD**, one escaped block in the head, prerendered and replaced after the app renders (`syncDocumentHead` in
  `app/src/shell/seo/documentHead.ts`): on home a `WebSite` with a `SearchAction` to `/browse?q=`; on a product page a
  `Product` (`sku` its id; each identifier and related product whose registry term names a schema.org property, as that
  property; the core specs as `additionalProperty` with the page's value text and `unitText`) and a `BreadcrumbList`; on
  a category or component hub an `ItemList` and a `BreadcrumbList`; on an article a `NewsArticle`.
- **Agents:** `llms.txt` (the catalog card and taxonomy) and `llms-full.txt` (a section per product, with `ID: <id>`),
  byte-stable, from `radar site export`.
