import { BRAND_CONFIG, type RoleAddress } from "../../src/ui/theme/brand.ts";
import { formatDate, localized } from "../../src/ui/specs/specFormat.ts";
import { PAGE_SIZE, type CatalogRepository } from "../../src/domain/ports/CatalogRepository.ts";
import { NEWS_PATH, articlePath, categoryPath, feedPath, vendorPath } from "../../src/domain/paths.ts";
import type { FeedBrief, FeedItemView } from "../../src/domain/views.ts";
import { FEED_TYPES, type PageHeadMeta } from "../../src/shell/seo/seo.ts";
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

interface Scope {
  readonly title: string;
  readonly home: string;
}

function jsonFeed(views: readonly FeedItemView[], base: string, scope: Scope): string {
  return `${JSON.stringify({
    version: "https://jsonfeed.org/version/1.1",
    title: scope.title,
    home_page_url: `${base}${scope.home}`,
    feed_url: `${base}${feedPath(scope.home, "json")}`,
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

function atomFeed(views: readonly FeedItemView[], base: string, newest: string, scope: Scope): string {
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
  <title>${escapeHtml(scope.title)}</title>
  <subtitle>${escapeHtml(DESCRIPTION)}</subtitle>
  <link rel="alternate" type="text/html" href="${escapeHtml(`${base}${scope.home}`)}"/>
  <link rel="self" type="${FEED_TYPES.atom}" href="${escapeHtml(`${base}${feedPath(scope.home, "atom")}`)}"/>
  <id>${escapeHtml(`${base}${scope.home}`)}</id>
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

function scopedFeeds(all: readonly FeedItemView[], briefs: readonly FeedBrief[], base: string, since: string,
    out: NewsOutput): (scope: Scope, cited: (brief: FeedBrief) => boolean) => void {
  return (scope, cited) => {
    const slugs = new Set(briefs.filter(cited).map((b) => b.slug));
    const views = all.filter((v) => slugs.has(v.slug)).slice(0, FEED_SIZE);
    out.file(feedPath(scope.home, "json").slice(1), jsonFeed(views, base, scope));
    const newest = views.map(updated).sort().at(-1) ?? since;
    out.file(feedPath(scope.home, "atom").slice(1), atomFeed(views, base, newest, scope));
  };
}

export async function prerenderNews(repo: CatalogRepository, base: string, asOf: string | undefined,
    out: NewsOutput): Promise<number> {
  const news = await repo.news();
  const first = news.items.slice(0, PAGE_SIZE);
  await out.page("news.html", buildNewsHeadMeta(first, news.total, base), { name: "news", query: "" });
  const all: FeedItemView[] = [];
  for (const brief of news.items) {
    const view = await repo.article(brief.slug);
    if (!view) throw new Error(`prerender: the article ${brief.slug} is listed, yet it has no page`);
    await out.page(`news/${view.slug}.html`, buildArticleHeadMeta(view, base, EN),
      { name: "article", slug: view.slug });
    out.sitemap.add({ path: articlePath(view.slug), lastmod: updated(view).slice(0, 10) });
    all.push(view);
  }
  const newest = all.map(updated).sort().at(-1);
  out.sitemap.add({ path: NEWS_PATH, lastmod: newest?.slice(0, 10) });
  const since = newest ?? (asOf && `${asOf}T00:00:00Z`);
  if (!since) throw new Error("prerender: the Atom feed has no date, with no article and no data date");
  const feeds = scopedFeeds(all, news.items, base, since, out);
  feeds({ title: TITLE, home: NEWS_PATH }, () => true);
  const [registry, organizations] = await Promise.all([repo.registry(), repo.organizations()]);
  for (const c of registry.categories) {
    feeds({ title: `${localized(c.label, EN)} — ${TITLE}`, home: categoryPath(c.id) },
      (b) => b.categories.includes(c.id));
  }
  for (const o of organizations) {
    feeds({ title: `${o.name} — ${TITLE}`, home: vendorPath(o.slug) }, (b) => b.subjects.includes(o.id));
  }
  return news.items.length + 1;
}
