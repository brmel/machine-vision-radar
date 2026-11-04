import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { runBuildGuards, checkHtmlPrerender, checkNews, type BuildGuardOptions } from "../../scripts/build-guards.ts";

let root: string;
let data: string;
const dist = (...parts: string[]) => path.join(root, "app/dist", ...parts);
const write = (file: string, text: string) => {
  fs.mkdirSync(path.dirname(dist(file)), { recursive: true });
  fs.writeFileSync(dist(file), text);
};
const ADMIN = "signInWithPopup()";

beforeEach(() => {
  root = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "mvr-guards-test-")), "code");
  fs.mkdirSync(dist("assets"), { recursive: true });
  fs.mkdirSync(dist("news"));
  fs.mkdirSync(path.join(root, "docs"));
  write("assets/index-abc.js", "/* clean */");
  write("news/feed.json", JSON.stringify({ items: [] }));
  write("news/feed.atom", "<feed></feed>");
  data = path.join(path.dirname(root), "data");
  fs.mkdirSync(path.join(data, "registry"), { recursive: true });
  fs.writeFileSync(path.join(data, "registry/spec_definitions.json"),
    JSON.stringify([{ id: "width_px", label: { en: "Width (px)", fr: "Largeur (px)" } }]));
});
afterEach(() => fs.rmSync(path.dirname(root), { recursive: true, force: true }));

describe("runBuildGuards", () => {
  it("passes a clean build, and one whose admin is a lazy chunk with the flag on", () => {
    expect(() => runBuildGuards({ repoRoot: root, dataRoot: data })).not.toThrow();
    write("assets/AdminSection-1.js", ADMIN);
    expect(() => runBuildGuards({ repoRoot: root, dataRoot: data, adminEnabled: true })).not.toThrow();
  });

  it.each<[string, () => unknown, BuildGuardOptions, RegExp]>([
    ["no main bundle", () => fs.rmSync(dist("assets/index-abc.js")), {},
      /exactly one dist\/assets\/index-\*\.js, found 0/],
    ["two main bundles", () => write("assets/index-def.js", "1;"), {}, /found 2/],
    ["admin code with the admin flag off", () => write("assets/AdminSection-1.js", ADMIN), { adminEnabled: false },
      /ships admin code with VITE_ENABLE_ADMIN off/],
    ["no lazy admin chunk with the flag on", () => undefined, { adminEnabled: true }, /no lazy AdminSection chunk/],
    ["admin code in the main bundle", () => [write("assets/AdminSection-1.js", ADMIN),
      write("assets/index-abc.js", ADMIN)], { adminEnabled: true }, /index-abc.js ships admin code in the main bundle/],
    ["a main bundle over its budget", () => write("assets/index-abc.js", "a".repeat(600 * 1024)), { maxBundleKiB: 565 },
      /exceeds budget/],
  ])("fails on %s", (_fault, make, options, error) => {
    make();
    expect(() => runBuildGuards({ repoRoot: root, dataRoot: data, ...options })).toThrow(error);
  });
});

describe("checkHtmlPrerender", () => {
  it("passes formatted labels, permanent ids and snake_case inside a script, a short page of a record, compare with "
    + "nothing picked and a History's change log", () => {
    write("prod.html",
      `<h1>Product prd_abc123</h1><table class="spec-table"><tr><td>Width (px)</td>`
      + `<td>1920 px <a href="#src_xyz">src_xyz</a></td></tr></table>
      <p>Managed by org_vendor99 and clm_fact123</p><script>const inner_code = "snake_allowed_here";</script>`);
    write("compare.html",
      "<head><title>Compare</title></head><body><h1>Compare products</h1><p>Pick up to 3 products.</p></body>");
    write("admin.html", '<body><div id="root"></div></body>');
    write("product/widget/history.html",
      '<body><main><h1>History</h1><ol '
        + 'class="history"><li><dl><dt>website_url</dt><dd>fixture_colour</dd></dl></li></ol></main></body>');
    expect(() => checkHtmlPrerender(dist(), data)).not.toThrow();
  });

  it.each([
    ["[object Object]", "bad.html", "<div>Spec value is [object Object]</div>", /contains \[object Object\]/],
    ["a raw spec key in a spec table", "bad.html",
      '<table class="spec-table"><tr><td>width_px</td><td>1920</td></tr></table>', /raw spec key 'width_px'/],
    ["visible snake_case", "bad.html", "<p>Feature is dark_field illumination</p>",
      /visible snake_case found.*dark_field/],
    ["visible snake_case on a History page outside its change log", "widget/history.html",
      '<h1>History</h1><p>dark_field</p><ol class="history"><li>website_url</li></ol>',
      /visible snake_case found.*dark_field/],
    ["a head-only page", "vendor.html", '<head><title>A vendor</title></head><body><div id="root"></div></body>',
      /vendor.html has 0 h1 headings/],
    ["two h1", "vendor.html", "<body><h1>A vendor</h1><h1>Its products</h1></body>", /vendor.html has 2 h1 headings/],
    ["a page of the site's own words under 200 characters in its main region, however long its header",
      "about.html",
      `<body><header>${"Browse Ask News ".repeat(20)}</header><main><h1>About</h1><p>A catalog.</p></main></body>`,
      /about.html shows 16 characters/],
  ])("fails on %s", (_fault, file, html, error) => {
    write(file, html);
    expect(() => checkHtmlPrerender(dist(), data)).toThrow(error);
  });
});

describe("checkNews", () => {
  const page = (slug: string, jsonLd: string) =>
    write(`news/${slug}.html`, `<script type="application/ld+json">${jsonLd}</script>`);
  const feeds = (slugs: readonly string[], dated = true) => {
    const url = (slug: string) => `https://radar.example/news/${slug}`;
    write("news/feed.json", JSON.stringify({ items: slugs.map((s) =>
      ({ url: url(s), ...(dated ? { date_published: "2026-10-20T10:00:00.000Z" } : {}) })) }));
    write("news/feed.atom", `<feed>${slugs.map((s) =>
      `<entry><id>${url(s)}</id><published>2026-10-20T10:00:00.000Z</published></entry>`).join("")}</feed>`);
  };

  beforeEach(() => page("first-words", '{"@type":"Article","datePublished":"2026-10-20T10:00:00.000Z"}'));

  it("passes when every page and feed entry is a published article's", () => {
    feeds(["first-words"]);
    expect(() => checkNews(dist())).not.toThrow();
  });

  it.each<[string, () => unknown, RegExp]>([
    ["an article page without a publication date", () =>
      [feeds(["first-words"]), page("a-draft", '{"@type":"Article"}')], /news\/a-draft.html has no publication date/],
    ["a missing feed", () => fs.rmSync(dist("news/feed.json")), /missing news\/feed.json/],
    ["a feed entry with no date", () => feeds(["first-words"], false), /feed carries .*first-words/],
    ["a feed entry with no page", () => feeds(["first-words", "a-draft"]), /feed carries .*a-draft/],
  ])("fails on %s", (_fault, make, error) => {
    make();
    expect(() => checkNews(dist())).toThrow(error);
  });
});

describe("the public text", () => {
  const denyList = () => {
    fs.writeFileSync(path.join(root, "deny.txt"), "Jane Fixture\n\nquill\n");
    return path.join(root, "deny.txt");
  };

  it("passes with no name of the deny list, a name only inside a word, and says when no deny list is given", () => {
    write("llms.txt", "Quillon gauges, by the editorial desk.");
    expect(runBuildGuards({ repoRoot: root, dataRoot: data, denyList: denyList() }))
      .toContain("no name of the deny list's 2");
    expect(runBuildGuards({ repoRoot: root, dataRoot: data, denyList: "" }))
      .toContain("personal names unchecked: MVR_DENY_LIST names no deny list");
  });

  it.each<[string, string, string, RegExp]>([
    ["a page", "app/dist/vendor.html", `<h1>A vendor</h1><a href="mailto:${["legal", "radar.web.app"].join("@")}">`,
      /vendor\.html gives legal@radar\.web\.app, at a hosting domain/],
    ["a feed", "app/dist/news/feed.atom", "<feed><author><name>JANE FIXTURE</name></author></feed>",
      /feed.atom carries name 1 of the deny list/],
    ["a public doc", "docs/LEGAL.md", "Ask Quill.", /LEGAL.md carries name 2 of the deny list/],
  ])("fails on %s that gives a dead address or a denied name", (_where, file, text, error) => {
    fs.writeFileSync(path.join(root, file), text);
    expect(() => runBuildGuards({ repoRoot: root, dataRoot: data, denyList: denyList() })).toThrow(error);
  });
});
