import { BRAND_CONFIG } from "../../ui/theme/brand.ts";
import { localized } from "../../ui/specs/specFormat.ts";
import { NEWS_PATH, articlePath } from "../../domain/paths.ts";
import type { FeedBrief, FeedItemView } from "../../domain/views.ts";
import { DEFAULT_LANGUAGE } from "../../domain/languages.ts";
import { DEFAULT_MESSAGES as messages } from "../i18n/messages.ts";
import { buildHubHeadMeta } from "./hubs.ts";
import { brandOrganization, formatMetaDescription, pageTitle, type PageHeadMeta } from "./seo.ts";

export function buildNewsHeadMeta(items: readonly FeedBrief[], total: number, origin: string): PageHeadMeta {
  const listed =
    items.map((item) => ({ name: localized(item.title, DEFAULT_LANGUAGE.code), path: articlePath(item.slug) }));
  return buildHubHeadMeta({ path: NEWS_PATH, name: messages.newsTitle, lead: messages.newsDescription,
    trail: [{ name: messages.navHome, path: "/" }], items: listed, total, feeds: NEWS_PATH }, origin);
}

export function buildArticleHeadMeta(view: FeedItemView, origin: string, locale: string): PageHeadMeta {
  const url = `${origin}${articlePath(view.slug)}`;
  return {
    title: pageTitle(localized(view.title, locale)),
    canonicalUrl: url,
    description: formatMetaDescription(localized(view.summary, locale)),
    ogType: "article",
    jsonLd: {
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      headline: localized(view.title, DEFAULT_LANGUAGE.code),
      description: localized(view.summary, DEFAULT_LANGUAGE.code),
      datePublished: view.published_at,
      url,
      mainEntityOfPage: url,
      inLanguage: Object.keys(view.title),
      author: { "@type": "Organization", name: localized(view.byline, DEFAULT_LANGUAGE.code), url: `${origin}/` },
      publisher: brandOrganization(origin, BRAND_CONFIG.profiles),
    },
  };
}
