import { BRAND_CONFIG, type RoleAddress } from "../../src/ui/theme/brand.ts";
import { formatDate, localized } from "../../src/ui/specs/specFormat.ts";
import { PAGE_SIZE, type CatalogRepository } from "../../src/domain/ports/CatalogRepository.ts";
import { NEWS_PATH, articlePath } from "../../src/domain/paths.ts";
import type { FeedItemView } from "../../src/domain/views.ts";
import type { PageHeadMeta } from "../../src/shell/seo/seo.ts";
import type { Route } from "../../src/shell/routing/routes.ts";
import { buildArticleHeadMeta, buildNewsHeadMeta } from "../../src/shell/seo/news.ts";
import { DEFAULT_MESSAGES as messages } from "../../src/shell/i18n/messages.ts";
import { ROLE_LABELS } from "../../src/shell/i18n/roles.ts";
import type { Sitemap } from "../sitemap.ts";
import { escapeHtml } from "../head.ts";
import { EN } from "./language.ts";

const FEED_SIZE = 50;
const TITLE = `${messages.newsTitle} — ${BRAND_CONFIG.wordmark}`;

export const feedDescription = (contact: readonly RoleAddress[]): string =>
  [messages.newsDescription,
    ...contact.filter((c) => c.address).map((c) => `${messages[ROLE_LABELS[c.role]]} ${c.address}.`)].join(" ");
const DESCRIPTION = feedDescription(BRAND_CONFIG.contact);
const byline = (view: FeedItemView): string => localized(view.byline, EN);

const aiLabel = (view: FeedItemView): string[] =>
  view.authorship === "ai_draft" ? [messages.newsAiDrafted.replace("{date}", formatDate(view.published_at, EN))] : [];

const text = (view: FeedItemView): string =>
  [localized(view.summary, EN), ...view.body.map((s) => localized(s.text, EN)), ...aiLabel(view)].join("\n\n");
const updated = (view: FeedItemView): string => view.revised_at ?? view.published_at;

function jsonFeed(views: readonly FeedItemView[], base: string): string {
  return `${JSON.stringify({
    version: "https://jsonfeed.org/version/1.1",
    title: TITLE,
    home_page_url: `${base}${NEWS_PATH}`,
    feed_url: `${base}${NEWS_PATH}/feed.json`,
    description: DESCRIPTION,
    language: EN,
    authors: [{ name: BRAND_CONFIG.wordmark, url: `${base}/` }],
    items: views.map((v) => ({
      id: `${base}${articlePath(v.slug)}`,
      url: `${base}${articlePath(v.slug)}`,
      title: localized(v.title, EN),
      summary: localized(v.summary, EN),
      content_text: text(v),
      authors: [{ name: byline(v) }],
      date_published: v.published_at,
      ...(v.revised_at ? { date_modified: v.revised_at } : {}),
      tags: [localized(v.kind.label, EN)],
    })),
  }, null, 2)}\n`;
}

function atomFeed(views: readonly FeedItemView[], base: string, newest: string): string {
  const entry = (v: FeedItemView): string => {
    const url = escapeHtml(`${base}${articlePath(v.slug)}`);
    return `  <entry>
    <title>${escapeHtml(localized(v.title, EN))}</title>
    <link rel="alternate" type="text/html" href="${url}"/>
    <id>${url}</id>
    <author><name>${escapeHtml(byline(v))}</name></author>
    <published>${v.published_at}</published>
    <updated>${updated(v)}</updated>
    <summary>${escapeHtml(localized(v.summary, EN))}</summary>
    <content type="text">${escapeHtml(text(v))}</content>
    <category term="${escapeHtml(v.kind.id)}" label="${escapeHtml(localized(v.kind.label, EN))}"/>
  </entry>
`;
  };
  return `<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="${EN}">
  <title>${escapeHtml(TITLE)}</title>
  <subtitle>${escapeHtml(DESCRIPTION)}</subtitle>
  <link rel="alternate" type="text/html" href="${escapeHtml(`${base}${NEWS_PATH}`)}"/>
  <link rel="self" type="application/atom+xml" href="${escapeHtml(`${base}${NEWS_PATH}/feed.atom`)}"/>
  <id>${escapeHtml(`${base}${NEWS_PATH}`)}</id>
  <updated>${newest}</updated>
  <author><name>${escapeHtml(BRAND_CONFIG.wordmark)}</name><uri>${escapeHtml(`${base}/`)}</uri></author>
${views.map(entry).join("")}</feed>
`;
}

interface NewsOutput {
  page: (file: string, head: PageHeadMeta, route: Route) => Promise<void>;
  file: (file: string, text: string) => void;
  sitemap: Sitemap;
}

export async function prerenderNews(repo: CatalogRepository, base: string, asOf: string | undefined,
    out: NewsOutput): Promise<number> {
  const news = await repo.news();
  const first = news.items.slice(0, PAGE_SIZE);
  await out.page("news.html", buildNewsHeadMeta(first, news.total, base), { name: "news", query: "" });
  const latest: FeedItemView[] = [];
  const changed: string[] = [];
  for (const brief of news.items) {
    const view = await repo.article(brief.slug);
    if (!view) throw new Error(`prerender: the article ${brief.slug} is listed, yet it has no page`);
    await out.page(`news/${view.slug}.html`, buildArticleHeadMeta(view, base, EN),
      { name: "article", slug: view.slug });
    out.sitemap.add({ path: articlePath(view.slug), lastmod: updated(view).slice(0, 10) });
    changed.push(updated(view));
    if (latest.length < FEED_SIZE) latest.push(view);
  }
  const newest = changed.sort().at(-1);
  out.sitemap.add({ path: NEWS_PATH, lastmod: newest?.slice(0, 10) });
  out.file("news/feed.json", jsonFeed(latest, base));
  const since = newest ?? (asOf && `${asOf}T00:00:00Z`);
  if (!since) throw new Error("prerender: the Atom feed has no date, with no article and no data date");
  out.file("news/feed.atom", atomFeed(latest, base, since));
  return news.items.length + 1;
}
