---
name: brand-content
description: Use when the founder has an idea for a post, a spotlight or a short video. Makes the post's text, image cards and captioned clip with the brand studio (app/studio), from the site's own components and the read model's data.
---

# brand-content

The founder brings an idea; you pick a template, sharpen the hook and write the post's text; the studio records, draws
and renders; the founder reviews and posts by hand. Every figure you write is **held**: a record the post is `about`,
or the catalog's counts and data date, states it. The studio refuses a figure that is not held and every word
`data/no_filler.json` bans.

The voice is `docs/BRAND.md` (Voice). The npm commands run in `app/`; each post is one folder,
`app/studio/out/<template>-<slug>/` (`catalog/` for the catalog's), outside the repo's history.

## The studio

- `npm run studio:make -- <template> [id]` fills a post from one record: `product`, `compare` and `ask` take a
  product, `vendor` a vendor, `article` a published article, `catalog` nothing (`app/studio/clips/templates.ts`). It
  records the template's flow on the live site (desktop 1920×1080; phone 540×675, stills at 2×), draws its card if it
  has one (1200×627 and 1080×1350) and writes `script.json`, whose captions are the site's words and the record's data.
- `npm run studio:clip -- <post folder>` renders the hook, the footage and the card each under its caption, and the
  end card with the address, at 1080×1350, 1080×1080 and 1920×1080, 15 to 30 s, an `.srt` beside each MP4.
- A script that runs long, says a word `data/no_filler.json` bans, or states a figure that neither a record it is
  `about` nor the catalog's counts and data date hold is refused before anything renders;
  `npm run studio:check -- <post folder>` checks `<post folder>/post.md` the same way.
- `npm run studio:still -- <template> [id]` draws a card alone; `npm run studio -- --public-dir=<post folder>
  --props=<a render's .json>` opens it in Remotion Studio. Rendering is local and costs nothing.

## Steps

1. **Template.** Match the idea to a template in `app/studio/clips/templates.ts`: `product`, `compare`, `ask`,
   `vendor`, `article` or `catalog`. Find the record's id or slug with `python3 -m radar --project mvradar product get
   <slug> --json` (read-only; access: docs/CLI.md) or on the
   site. `ask` spends one of Ask's daily calls per size; take it only when the idea is the Ask page. Done when the idea
   has one template and one record.
2. **Make.** `npm run studio:make -- <template> <id>`. Done when its folder holds the footage, the card if the template
   has one, and `script.json`.
3. **Hook.** Rewrite `script.json`'s hook as the idea's point, in two seconds of reading; leave the captions, which are
   the site's words and the record's data. Render: `npm run studio:clip -- studio/out/<post>` (add `portrait` for the
   4:5 alone). Done when it renders with no finding and you have looked at the footage's stills and the card.
4. **Text.** Write `<post>/post.md`: what the live page shows today, one fact with its source, the page's address.
   `npm run studio:check -- studio/out/<post>`. Done when it passes; fix the text, never the check.
5. **Hand-off.** `gh issue create --label post --title "Post: <idea>"` (or comment on the idea's issue) with the text,
   the folder's path, each image's alt text, the `.srt`, the data date and the pages the facts come from. Done when
   the issue holds everything the founder needs to post without asking. Posting waits for the founder's go
   (`docs/BRAND.md`, Announcing).

## Cost

Your tokens for one hook and one text; recording and rendering are local and free. A paid image or video model is
#408, a port behind the Meter, never a call from here.
