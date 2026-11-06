import { localized } from "../../ui/specs/specFormat.ts";
import { categoryPath, familyComparePath, hubPath, productPath } from "../../domain/paths.ts";
import type { CategoryEntry, ProductCard, ProductView } from "../../domain/views.ts";
import { DEFAULT_LANGUAGE } from "../../domain/languages.ts";
import { DEFAULT_MESSAGES as messages } from "../i18n/messages.ts";
import { breadcrumbList, formatMetaDescription, pageTitle, type PageHeadMeta } from "./seo.ts";

interface HubInput {
  readonly path: string;
  readonly name: string;
  readonly lead: string;
  readonly trail: readonly { readonly name: string; readonly path: string }[];
  readonly items: readonly { readonly name: string; readonly path: string }[];
  readonly total: number;
  readonly feeds?: string;
}

const TRAIL = [{ name: messages.navHome, path: "/" }, { name: messages.catalogTitle, path: "/browse" }];
const listed = (cards: readonly ProductCard[]) => cards.map((c) => ({ name: c.name, path: productPath(c.slug) }));

const usersLead = (total: number, name: string): string =>
  (total === 1 ? messages.hubLeadOne : messages.hubLeadOther).replace("{count}", String(total)).replace("{name}", name);

export function categoryHub(category: CategoryEntry, cards: readonly ProductCard[]): HubInput {
  return { path: categoryPath(category.id), name: localized(category.label, DEFAULT_LANGUAGE.code),
    lead: localized(category.description, DEFAULT_LANGUAGE.code), trail: TRAIL, items: listed(cards),
    total: category.products, feeds: categoryPath(category.id) };
}

export function componentHub(product: { readonly slug: string; readonly name: string }, category: CategoryEntry,
    cards: readonly ProductCard[], total: number): HubInput {
  return {
    path: hubPath(category.component_hub ?? "", product.slug), name: product.name, lead: usersLead(total, product.name),
    trail: [...TRAIL, { name: localized(category.label, DEFAULT_LANGUAGE.code), path: categoryPath(category.id) }],
    items: listed(cards), total,
  };
}

export function familyCompare(family: ProductView, category: CategoryEntry): HubInput {
  const fill = (text: string): string => text.replace("{name}", family.name).replace("{vendor}", family.vendor.name)
    .replace("{count}", String(family.models.length));
  return {
    path: familyComparePath(family.slug), name: fill(messages.compareFamilyTitle),
    lead: fill(messages.compareFamilyLead),
    trail: [...TRAIL, { name: localized(category.label, DEFAULT_LANGUAGE.code), path: categoryPath(category.id) },
      { name: family.name, path: productPath(family.slug) }],
    items: family.models.map((m) => ({ name: m.name, path: productPath(m.slug) })), total: family.models.length,
  };
}

export function buildHubHeadMeta(hub: HubInput, origin: string): PageHeadMeta {
  return {
    title: pageTitle(hub.name),
    canonicalUrl: `${origin}${hub.path}`,
    description: formatMetaDescription(hub.lead),
    ogType: "website",
    ...(hub.feeds ? { feeds: hub.feeds } : {}),
    jsonLd: {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "ItemList",
          name: hub.name,
          numberOfItems: hub.total,
          itemListElement: hub.items.map((item, n) =>
            ({ "@type": "ListItem", position: n + 1, url: `${origin}${item.path}`, name: item.name })),
        },
        breadcrumbList([...hub.trail, { name: hub.name, path: hub.path }], origin),
      ],
    },
  };
}
