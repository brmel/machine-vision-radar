# app/ — the site, the admin and the brand studio

React + Vite + TypeScript on the public read model; npm commands run here. The data and the system:
`docs/SYSTEM.md`; search and Ask: `docs/SEARCH.md`; the voice: `docs/BRAND.md`.

## Map

- **Entry points:** `src/main.tsx` (the browser), `src/shell/root/start.ts` (what only a browser knows, read once),
  `src/shell/root/App.tsx` (wires the adapters), `src/shell/root/server.tsx` (the prerender's render of a route).
- **Routes:** the `Route` union in `src/shell/routing/routes.ts`, `routeFromPath`/`pathFromRoute` and the static pages
  in `src/shell/routing/router.ts`, mounted by `src/shell/routing/RouteView.tsx`.
- **Features** (`src/features/`): `home` (home, about, agents, legal, news, 404), `browse` (browse, category and
  component hubs), `product-detail` (a product, its history, the error report), `vendor-detail`, `compare`, `ask`,
  `admin` (one folder per section; `shell/admin/` holds the gate, the section list and the lazy wiring).
- **Ports → adapters:** `CatalogRepository` → `adapters/read-model/firestore.ts` (REST on the `public_*` docs; in
  production the registry and organizations come from the build's `/read-model/` files, `files.ts`); `ProductSearch` →
  `adapters/search/HttpProductSearch.ts` (`POST /api/find`, ranked on the server); `AskApi` → `HttpAskApi.ts`;
  `domain/ports/review/*` → `adapters/review/` (`HttpAdminApi.ts` serves every admin port, `HttpReportInbox.ts`,
  `FirebaseAuthGateway.ts`).
- **Request flow:** a page is prerendered by `scripts/prerender/` through `CatalogRepository` and `server.tsx`, then
  the app reads the same docs as a client navigation would. `/api` is one Cloud Function (`radar/adapters/web/`):
  `api.py` (ask, find, report), `admin/` (`/api/admin/*`, the admin claim on every request), `mcp.py` (`/api/mcp`).
- **Scripts:** `scripts/gates/` (the gate), `scripts/build-guards.ts` (the build guards; their list is the file),
  `scripts/deploy.sh`, `scripts/head.ts`, `scripts/sitemap.ts`. **Studio:** `studio/` (the brand-content skill).
- **Tests:** `tests/build/`, `tests/guards/`, `tests/integration/` (Vitest); `tests/e2e/` (Playwright: `pages/`,
  `checks/`, `search/`, `honesty/`, `news.spec.ts`; `emulator/` writes to the store).

## TypeScript and React rules

- Layers: `shell/` (the only composition root: adapters, i18n, routing, layout, seo) → `features/<name>/` → `ui/`
  (presentational, i18n-free) → `domain/` (types, ports, pure logic; imports nothing). `adapters/` implement domain
  ports. No cross-feature imports; features never import adapters (depcruise).
- Never call a hook after an early return. One component per file; named handlers, not inline arrow soup; no prop
  drilling past 3 levels.
- Pages load only the data they show, through domain ports, never the whole catalog. Firebase clients stay lazy and
  code-split.
- Every user-facing string goes through i18n: `contracts/languages.json` lists the languages, and
  `src/shell/i18n/messages/<code>/` holds one language's strings, with the default language's keys in every language;
  no code names a language (`i18n-keys.test.ts`). Dates and numbers via `Intl`, in the language's `intl` locale.
- Role tokens only: every color, type size, radius and shadow is a role in `src/ui/theme/tokens.css`, with no raw
  color elsewhere (`slop.test.ts`); every component works in light and dark.
- Accessibility, WCAG 2.2 AA: landmarks, one `h1` per view, logical tab order, visible `:focus-visible`, no
  interactive element nested in a clickable card, contrast ≥ 4.5:1 (`checks/a11y.spec.ts`).
- View state a user would share (filters, query, compare) serializes to the URL.
- Brand voice (`docs/BRAND.md`): terse, technical, no marketing words; public claims only what the data supports
  (`slop.test.ts` on `data/no_filler.json`).

## One test fast

- Vitest: `npx vitest run tests/<dir>/<file> --reporter=dot` (`-t "<name>"` for one test). `npm test` runs them all
  but `e2e/`; `npx tsc --noEmit`, `npm run arch`, `npm run knip` each take seconds.
- Playwright needs a production build reading the fixture in the emulators: the setup of
  `scripts/gates/emulator.sh` (fixture loaded, `MVR_FIRESTORE_DOCS`, the `VITE_*` admin config, `MVR_E2E_FIXTURE`,
  then `npm run build`). With that build in `dist/`, `npx playwright test tests/e2e/pages/<spec> --reporter=line`
  serves it with `vite preview`; `--config playwright.emulator.config.ts` runs the store-writing specs.

## Env

| variable | sets |
|---|---|
| `MVR_DATA` | the data folder, from the repo root; empty or unset: `data` (`scripts/head.ts`, `radar/paths.py`) |
| `MVR_FIRESTORE_DOCS` | the read model's documents URL (the emulator's), else the project's |
| `MVR_READ_MODEL_DIR` | a fixture's read model on disk, for a test build |
| `MVR_SITE_URL` | the canonical origin, else `.firebaserc`'s project |
| `MVR_ASK_LOCAL` | where `vite preview` proxies `/api` |
| `MVR_E2E_FIXTURE` | the gate's fixture, which the suites read instead of building their own |
| `MVR_DENY_LIST`, `MVR_PRERENDER_OUT`, `MVR_SITEMAP_URLS`, `MVR_STUDIO_OUT` | the build guard's deny list, the prerender's output, URLs per sitemap file, the studio's output |
| `VITE_ENABLE_ADMIN`, `VITE_FIREBASE_*` | the admin in the build and its public web config |
| `VITE_APPCHECK_SITE_KEY` | the reCAPTCHA Enterprise site key a reader's report gets its App Check token with; without it, none |
| `SMOKE_BASE_URL` | the smoke spec's server |

## Recipes

- **A page:** a `Route` and its path in `routes.ts` and `router.ts`; its view in `features/<name>/`, mounted in
  `RouteView.tsx`; its reads through `CatalogRepository` (a new read-model doc is a `contracts/model/views.json` change,
  `radar model generate`, and the projection in `radar/adapters/firestore/`); its prerender in `scripts/prerender/`
  and head in `src/shell/seo/`; its strings in every language; the page kind's e2e spec extended, EN and FR.
- **An admin screen:** the operation's CLI command first (`radar/AGENTS.md`, Recipes), then its route in
  `radar/adapters/web/admin/`, the method on a port in `src/domain/ports/review/`, implemented in `HttpAdminApi.ts`; the
  view in `features/admin/<section>/`, the section in `src/shell/admin/AdminView.tsx` with its `adminNav…` key in every
  language; the screen named in the operation's `admin` field; a spec in `tests/e2e/emulator/`.
