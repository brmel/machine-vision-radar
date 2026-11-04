# Brand — machineVisionRadar

The product is the complete collection of machine vision knowledge; the brand says "trustworthy index" before
anything else.

## Name

- **Display name (UI):** "Machine Vision Radar", separate words, title case, never translated; "MV radar" for icons
  and tight spaces.
- **Written name (docs, prose):** `machineVisionRadar`, one word, camelCase; "the radar" after first use. Never "MVR".
- **Infra slug:** `mvradar`, the GitHub repo, Firebase project and domain: an identifier, never the name in prose or
  copy. The acronym ban does not rename working infra.

## Tagline

**All machine vision knowledge, in one place.** Positive and concrete, no "not"-phrasing. "Knowledge" reaches past
products: the catalog and the news today.

## Look

- **Mark:** a reticle and a radar sweep on dark. The header draws it as `RadarSweepGlyph`
  (`app/src/ui/theme/glyphs.tsx`, placed by `BrandLogo.tsx`), its sweep in the accent; the favicon,
  `app/public/favicon.svg`, is the same tile in the light theme's colors. Never stretched, recolored or placed on a
  busy background.
- **Social card:** `app/public/og-card.png`, 1200×630: the name and the tagline, no counts.
- **Roles:** every color, type size, spacing, radius, shadow and motion is a role in `app/src/ui/theme/tokens.css`
  (light in `@theme`, dark in `.dark`); the page color is also the browser's theme color.
- **Color:** a radar-yellow accent on dark and light surfaces.
- **Type:** the system stack, no webfont: speed is brand. Sizes are in rem, so the root size in `app/src/index.css`
  scales them all. Headings take the heading weight (`font-heading`, semibold), never bold.
- **Brand text:** `BRAND_CONFIG` in `app/src/ui/theme/brand.ts`: the wordmark and its short form, the tagline, the
  profiles, the role addresses and the data licence; `index.html` reads the wordmark and the tagline from it at build
  time. The favicon and the social card are images, redrawn by hand.
- **A language:** its entry in `contracts/languages.json` and its strings, no code ([app/AGENTS.md](../app/AGENTS.md));
  catalog text with no translation shows in English.

## Presence

The radar shows up as a brand, never as a person: no personal name or personal address in public output.

- **Profiles:** `BRAND_CONFIG.profiles`, LinkedIn first. The footer and the About page link each one that has a URL,
  and the brand's Organization JSON-LD lists them as `sameAs`.
- **Byline:** `byline` in `data/registry/feed.json`, on every article's page, its JSON-LD `author` and its
  entry in the Atom and JSON feeds; the validator rejects an article with any other.
- **Role addresses:** `BRAND_CONFIG.contact` (corrections, privacy, press), all reaching the one working mailbox. The
  About page and the feeds' description give each one that is set, the terms the corrections one, the privacy page the
  privacy one. A hosting domain (`*.web.app`, `*.firebaseapp.com`) receives no mail: a repo test and the build guard
  fail on an address at one.
- **Share previews:** `headMetaTags` in `app/src/shell/seo/seo.ts` gives every page its Open Graph and Twitter card
  tags: its title, summary, canonical URL and the social card.
- **Deny list:** the build guard fails when the built site or `docs/` carries a name from the file `MVR_DENY_LIST`
  names, one name a line. The file stays outside the repo and the bundle; without it, the guard says the names went
  unchecked.

## Voice

All copy, docs and external notes: concrete, short, human sentences; no AI-generated phrasing. Numbers over
adjectives: an exact count, never a superlative. Honest states ("Planned", "unverified") over silent gaps. Not playful
(this is metrology), not corporate (no stock photos, no "solutions"), not hype. The words the radar never writes are in
`data/no_filler.json`, each with its reason; the validator, the site's slop guard
(`app/tests/guards/slop.test.ts`) and the studio (`app/studio/clips/script.ts`) read it.

## Making assets

The brand studio (`app/studio/`) draws a post's footage, cards and clip from the live site and the read model; its
commands and steps are the brand-content skill (`.claude/skills/brand-content/SKILL.md`). Footage is the real site,
never generated; every figure comes from the read model. No GIF; generated imagery may frame the site, never stand in
for it.

## Announcing

Announce shipped things only, never a roadmap as a promise: no "coming soon". A post describes what the live URL does
today, with one number or screenshot. LinkedIn is the channel. Public claims state only what the measured KPIs support
("compiled from public sources, every source cited", never "every one verified"). Posts are drafted for the founder
in their GitHub issue and posted by hand from the brand's accounts; nothing posts on its own.

Every new user-facing surface (route, post, demo) gets a brand check before it ships: the name, the tagline, the
voice, the role colors.
