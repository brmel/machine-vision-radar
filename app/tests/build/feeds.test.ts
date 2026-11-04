import { cpSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { FilesCatalogRepository } from "../../src/adapters/read-model/files.ts";
import type { FeedItemView, FeedPageView } from "../../src/domain/views.ts";
import { feedDescription, prerenderNews } from "../../scripts/prerender/news.ts";
import { DEFAULT_MESSAGES } from "../../src/shell/i18n/messages.ts";
import { Sitemap } from "../../scripts/sitemap.ts";

const ORIGIN = "https://radar.example";
const REVISED = "2026-10-20T08:00:00.000Z";
const RFC3339 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;
const PUBLIC = join(process.env.MVR_E2E_FIXTURE ?? "", "dist", "public");
const read = (dir: string, file: string): unknown => JSON.parse(readFileSync(join(dir, file), "utf-8"));

function withArticles(extra: number): { dir: string; page: FeedPageView } {
  const dir = mkdtempSync(join(tmpdir(), "mvr-news-"));
  cpSync(PUBLIC, dir, { recursive: true });
  // Justification (typed boundary): the fixture's files, checked against contracts/model/views.json when exported.
  const page = read(dir, "news.json") as FeedPageView;
  const model = read(dir, `news/${page.items[0].slug}.json`) as FeedItemView;
  const added = Array.from({ length: extra }, (_, n): FeedItemView => ({
    ...model, slug: `generated-${n}`, title: { en: n === extra - 1 ? "Widgets <&> \"gauges\"" : `Generated ${n}` },
    published_at: `2026-10-19T${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60)
      .padStart(2, "0")}:00.000Z`,
    ...(n === extra - 1 ? { revised_at: REVISED } : {}),
  })).reverse();
  for (const view of added) writeFileSync(join(dir, "news", `${view.slug}.json`), JSON.stringify(view));
  const briefs = added.map((v) => ({ slug: v.slug, title: v.title, summary: v.summary, kind: v.kind,
    published_at: v.published_at, subjects: [], categories: [] }));
  const merged = { items: [...briefs, ...page.items], total: page.total + extra };
  writeFileSync(join(dir, "news.json"), JSON.stringify(merged));
  return { dir, page: merged };
}

describe("the news's pages and feeds", () => {
  it("writes /news, every article's page dated in the sitemap, and the latest 50 in a JSON Feed 1.1 and an Atom "
    + "feed", async () => {
    const { dir, page } = withArticles(55);
    const out = mkdtempSync(join(tmpdir(), "mvr-news-out-"));
    const written = new Map<string, string>();
    const sitemap = new Sitemap(out, ORIGIN);
    const pages = await prerenderNews(new FilesCatalogRepository(async (file) => read(dir, decodeURIComponent(file))),
        ORIGIN, "2026-10-19", {
      page: async (file, head) => {
        written.set(file, `${head.title}\n${JSON.stringify(head.jsonLd)}`);
      },
      file: (file, text) => written.set(file, text),
      sitemap,
    });
    sitemap.close();
    expect(pages).toBe(page.total + 1);
    expect([...written.keys()].filter((f) => f.endsWith(".html")).sort())
      .toEqual(["news.html", ...page.items.map((i) => `news/${i.slug}.html`)].sort());
    const map = readFileSync(join(out, "sitemap-1.xml"), "utf-8");
    const changed = (i: number) => (i === 0 ? REVISED : page.items[i].published_at).slice(0, 10);
    page.items.forEach((item, i) => expect(map)
      .toContain(`<loc>${ORIGIN}/news/${item.slug}</loc>\n    <lastmod>${changed(i)}</lastmod>`));
    expect(map).toContain(`<loc>${ORIGIN}/news</loc>\n    <lastmod>${REVISED.slice(0, 10)}</lastmod>`);
    expect(written.get(`news/${page.items[0].slug}.html`)).toContain('"@type":"NewsArticle"');

    const json = JSON.parse(written.get("news/feed.json") ?? "");
    expect(json.version).toBe("https://jsonfeed.org/version/1.1");
    expect(typeof json.title).toBe("string");
    expect(new URL(json.home_page_url).pathname).toBe("/news");
    expect(new URL(json.feed_url).pathname).toBe("/news/feed.json");
    expect(json.authors.every((a: { name?: string }) => typeof a.name === "string")).toBe(true);
    expect(json.items[0].date_modified).toBe(REVISED);
    expect(json.items.map((i: { url: string }) => i.url))
      .toEqual(page.items.slice(0, 50).map((i) => `${ORIGIN}/news/${i.slug}`));
    const byline = (read(dir, `news/${page.items[0].slug}.json`) as FeedItemView).byline.en;
    for (const item of json.items) {
      expect(item.authors).toEqual([{ name: byline }]);
      expect(typeof item.id).toBe("string");
      expect(typeof item.content_text).toBe("string");
      expect(item.date_published).toMatch(RFC3339);
    }

    const atom = written.get("news/feed.atom") ?? "";
    const [head, ...entries] = atom.split("<entry>");
    expect(head).toMatch(/^<\?xml version="1.0" encoding="utf-8"\?>\n<feed xmlns="http:\/\/www.w3.org\/2005\/Atom"/);
    for (const element of ["<id>", "<title>", "<updated>", "<author><name>"]) expect(head, element).toContain(element);
    expect(atom.trimEnd().endsWith("</feed>")).toBe(true);
    expect(entries.map((e) => e.split("<id>")[1].split("</id>")[0]))
      .toEqual(json.items.map((i: { id: string }) => i.id));
    for (const entry of entries) {
      expect(entry.split("<updated>")[1].split("</updated>")[0]).toMatch(RFC3339);
      for (const element of ["<title>", `<author><name>${byline}</name></author>`, "<published>",
        '<link rel="alternate"', "</entry>"]) expect(entry, element).toContain(element);
    }
    expect(entries[0]).toContain("<title>Widgets &lt;&amp;&gt; &quot;gauges&quot;</title>");
    expect(entries[0]).toContain(`<updated>${REVISED}</updated>`);
    expect(head).toContain(`<updated>${REVISED}</updated>`);
  }, 60_000);

  it("gives the role addresses that are set in the feeds' description", () => {
    const description =
      feedDescription([{ role: "corrections", address: "" }, { role: "press", address: "press@radar.example" }]);
    expect(description)
      .toBe(`${DEFAULT_MESSAGES.newsDescription} ${DEFAULT_MESSAGES.contactPress} press@radar.example.`);
  });
});
