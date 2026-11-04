import { BRAND_CONFIG, type Profile } from "../../ui/theme/brand.ts";
import { LANGUAGES } from "../../domain/languages.ts";
import { vendorPath } from "../../domain/paths.ts";
import type { OrganizationView } from "../../domain/views.ts";

export interface PageHeadMeta {
  title: string;
  canonicalUrl: string;
  description: string;
  ogType: "website" | "product" | "article";
  jsonLd: object;
  noindex?: boolean;
  image?: string;
}

const CARD_PATH = "/og-card.png";

type HeadMetaTag = readonly ["name" | "property", string, string];

export function headMetaTags(meta: PageHeadMeta): readonly HeadMetaTag[] {
  const image = meta.image ? (meta.image.startsWith("http") ? meta.image : new URL(meta.image, meta.canonicalUrl).href)
    : new URL(CARD_PATH, meta.canonicalUrl).href;
  return [
    ["name", "description", meta.description],
    ["property", "og:url", meta.canonicalUrl],
    ["property", "og:title", meta.title],
    ["property", "og:description", meta.description],
    ["property", "og:type", meta.ogType],
    ["property", "og:site_name", BRAND_CONFIG.wordmark],
    ["property", "og:image", image],
    ["name", "twitter:card", "summary_large_image"],
    ["name", "twitter:title", meta.title],
    ["name", "twitter:description", meta.description],
    ["name", "twitter:image", image],
  ];
}

export function brandOrganization(origin: string, profiles: readonly Profile[]) {
  const sameAs = profiles.filter((p) => p.url).map((p) => p.url);
  return { "@type": "Organization", name: BRAND_CONFIG.wordmark, url: `${origin}/`,
    ...(sameAs.length > 0 ? { sameAs } : {}) };
}

export const pageTitle = (name: string): string => `${name} — ${BRAND_CONFIG.wordmark}`;

const MAX_DESCRIPTION = 200;

export function formatMetaDescription(lead?: string | null): string {
  const tagline = BRAND_CONFIG.tagline;
  const cleaned = (lead || "").trim();
  if (!cleaned || cleaned === tagline) return tagline;
  if (cleaned.includes(tagline)) {
    return cleaned.length <= MAX_DESCRIPTION ? cleaned : `${cleaned.slice(0, MAX_DESCRIPTION - 1).trim()}…`;
  }
  const budget = MAX_DESCRIPTION - tagline.length - 1;
  const trimmedLead = cleaned.length <= budget ? cleaned : `${cleaned.slice(0, budget - 1).trim()}…`;
  return `${trimmedLead} ${tagline}`;
}

export function serializeJsonLd(value: unknown): string {
  return JSON.stringify(value)
    .replace(/&/g, "\\u0026")
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}

export const breadcrumbList = (trail: readonly { readonly name: string; readonly path: string }[], origin: string) => ({
  "@type": "BreadcrumbList",
  itemListElement: trail.map((step, n) =>
    ({ "@type": "ListItem", position: n + 1, name: step.name, item: `${origin}${step.path}` })),
});

function webSiteJsonLd(origin: string, description: string) {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: BRAND_CONFIG.wordmark,
    alternateName: BRAND_CONFIG.shortWordmark,
    url: `${origin}/`,
    description: formatMetaDescription(description),
    inLanguage: LANGUAGES.map((l) => l.code),
    publisher: brandOrganization(origin, BRAND_CONFIG.profiles),
    potentialAction: {
      "@type": "SearchAction",
      target: { "@type": "EntryPoint", urlTemplate: `${origin}/browse?q={search_term}` },
      "query-input": "required name=search_term",
    },
  };
}

export function buildHomeHeadMeta(origin: string, leadDescription?: string): PageHeadMeta {
  const description = formatMetaDescription(leadDescription);
  return {
    title: `${BRAND_CONFIG.wordmark} — ${BRAND_CONFIG.tagline}`,
    canonicalUrl: `${origin}/`,
    description,
    ogType: "website",
    jsonLd: webSiteJsonLd(origin, description),
  };
}

export function buildStaticHeadMeta(canonicalUrl: string, origin: string, title: string, lead: string): PageHeadMeta {
  const description = `${lead} ${BRAND_CONFIG.tagline}`;
  return { title: pageTitle(title), canonicalUrl, description, ogType: "website",
    jsonLd: webSiteJsonLd(origin, description) };
}

export function buildVendorHeadMeta(vendor: Pick<OrganizationView, "slug" | "name" | "website"> & { summary: string },
    origin: string): PageHeadMeta {
  const url = `${origin}${vendorPath(vendor.slug)}`;
  return {
    title: pageTitle(vendor.name),
    canonicalUrl: url,
    description: formatMetaDescription(vendor.summary || `${vendor.name} on ${BRAND_CONFIG.wordmark}.`),
    ogType: "website",
    jsonLd: { "@context": "https://schema.org", "@type": "Organization", name: vendor.name, url,
      ...(vendor.website ? { sameAs: vendor.website } : {}),
      ...(vendor.summary ? { description: vendor.summary } : {}) },
  };
}
