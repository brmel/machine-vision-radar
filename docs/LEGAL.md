# Legal

The terms (`/terms`) and the privacy notice (`/privacy`) publish this policy in every language, from
`app/src/shell/i18n/messages/<code>/legal.json`; the About page states the radar's independence. This doc is what they
rest on and how the radar applies it. There is no contact address yet: all of it goes through "Report an error" on a
product page; the role addresses ([BRAND.md](BRAND.md), Presence) show on the pages once set.

## Licences

- **Code and `data/`** (the registry, the prompts, the banned words): `LICENSE`, Apache-2.0.
- **Data:** the catalog the site publishes is CC BY-NC 4.0, its terms at
  `https://mvradar.web.app/terms`. Reuse credits Machine Vision Radar, links to the
  product's page and keeps the link to each vendor source. Commercial use needs a licence from Machine Vision Radar.
- **Citing:** a record is cited by its product's permanent page, `https://mvradar.web.app/product/<slug>`. Agents
  read `llms-full.txt` or a page's embedded view rather than scrape its text.

## Sources and independence

- The catalog is compiled from public sources: vendor websites, press releases, product catalogs and datasheets.
  Every value cites its current source, with its type and retrieval date.
- A value no source states is left out and shown as "Not published", never guessed.
- Values are given as published, with no warranty; a reader verifies a value with its vendor before relying on it.
- Inclusion and ranking (filters, search, Ask) are never for sale; there is no paid placement.

## Media rights

`Document.rights` decides what a file may do ([SYSTEM.md](SYSTEM.md), §2):

- Vendor-copyright media (datasheets, manuals, vendor images and videos: `vendor`, `third_party`) is stored privately
  in Cloud Storage and never served; its page links to the vendor's URL, the Document's `source_url`.
- Only media whose rights allow it (`own`, `open_licence`) gets a public URL.
- Summaries are written in the radar's own words.

`contracts/firebase/storage.rules` lets anyone read a file only under public rights (`radar/tests/store/test_rules.py`).
A private file's link is its `source_url`, never its Storage address, in the read model
(`radar/tests/generated/test_fixture_category.py`) and on the product page
(`app/tests/e2e/pages/fixture-category.spec.ts`).

## Corrections and takedowns

- **Channel:** "Report an error" on a product page files a suggested proposal in the review queue. A takedown notice
  names the file or value, the right the sender holds and how to reach them. No response time is promised.
- **A takedown:** `radar media retract <id> --reason R` files the retraction, which `/admin` approves. Approving it
  deletes the file from Storage when no other record names it; the product's record stays. The reason records the
  notice (who sent it, when, for whom), and the retraction's Change event keeps it.
- **A counter-notice** comes the same way. Restoring a file is a new proposal.

## Privacy

`/privacy` says what the site sends and keeps, and for how long, and states only what the code does. It rests on:

- the browser: no cookie and no analytics; local storage holds the language, theme and compare list
  (`app/src/shell/`, `app/src/features/compare/`); a search's words go to `POST /api/find`, in the body, and are
  neither logged nor kept (`radar/adapters/web/api.py`);
- the counters and Ask: `radar/adapters/web/api.py` (a client is a daily digest of its address) and
  `radar/adapters/firestore/ledgers/ai.py` (the answer cache, the counters, the usage and the call log), none with an
  expiry; a question not answered before goes, with the records it matches, to Gemini on Vertex AI
  ([SEARCH.md](SEARCH.md));
- the error report: `app/src/adapters/review/HttpReportInbox.ts` (what the form sends, and reCAPTCHA through App
  Check, loaded when the form opens) and `radar/adapters/web/api.py` (what `/api/report` checks and files: the product,
  the message, the source link and the time; no address);
- the admin: Firebase Authentication with Google sign-in (`app/src/adapters/review/FirebaseAuthGateway.ts`).

A change to what any of these keeps changes `/privacy`'s text in the same commit.
