import { BRAND_CONFIG } from "../../ui/theme/brand.ts";
import type { ProductView } from "../../domain/views.ts";
import type { RegistryLabels } from "../../ui/specs/RegistryContext.tsx";
import { formatSpecLabel, formatSpecValueText, localized, termLabel,
  type SpecValueLabels } from "../../ui/specs/specFormat.ts";
import { browsePath, categoryPath, productPath } from "../../domain/paths.ts";
import { breadcrumbList, formatMetaDescription, pageTitle, type PageHeadMeta } from "./seo.ts";

interface SeoProductInput {
  id: string;
  slug: string;
  name: string;
  vendor: string;
  category: string;
  summary?: string;
  marked: readonly ({ property: string; value: string }
    | { property: string; product: { name: string; slug: string } })[];
  trail: readonly { name: string; path: string }[];
  properties: readonly { name: string; value: string; unitText?: string }[];
  indexable: boolean;
  thumbnailUrl?: string;
}

export function productSeo(view: ProductView, registry: RegistryLabels, labels: SpecValueLabels): SeoProductInput {
  const category = registry.categories.find((c) => c.id === view.category);
  if (!category) throw new Error(`productSeo: unknown category ${view.category}`);
  const { locale } = labels;
  return {
    id: view.id,
    slug: view.slug,
    name: view.name,
    vendor: view.vendor.name,
    category: localized(category.label, locale),
    summary: view.summary ? localized(view.summary, locale) : undefined,
    marked: [
      ...view.identifiers.flatMap((i) => (i.schema_org ? [{ property: i.schema_org, value: i.value }] : [])),
      ...view.relations.flatMap((r) =>
        (r.schema_org ? [{ property: r.schema_org, product: { name: r.product.name, slug: r.product.slug } }] : [])),
    ],
    trail: [
      { name: termLabel(registry.domains, category.domain, locale),
        path: browsePath(`domain=${encodeURIComponent(category.domain)}`) },
      { name: localized(category.label, locale), path: categoryPath(category.id) },
    ],
    properties: view.core.flatMap((cell) => cell.value === undefined ? [] : [{
      name: formatSpecLabel(cell.key, registry.spec_definitions, locale),
      value: formatSpecValueText(cell.value, labels, "label"),
      ...(registry.spec_definitions[cell.key].unit ? { unitText: registry.spec_definitions[cell.key].unit } : {}),
    }]),
    indexable: view.indexable,
    thumbnailUrl: view.thumbnail_url,
  };
}

type ProductRef = { "@type": "Product"; name: string; url: string };

function markedProperties(marked: SeoProductInput["marked"], origin: string): Record<string, string | ProductRef[]> {
  const related = new Map<string, ProductRef[]>();
  for (const m of marked) {
    if ("product" in m) related.set(m.property, [...(related.get(m.property) ?? []),
      { "@type": "Product", name: m.product.name, url: `${origin}${productPath(m.product.slug)}` }]);
  }
  return { ...Object.fromEntries(marked.flatMap((m) => ("value" in m ? [[m.property, m.value]] : []))),
    ...Object.fromEntries(related) };
}

const imageOf = ({ thumbnailUrl }: SeoProductInput, origin: string) =>
  (thumbnailUrl ? { image: thumbnailUrl.startsWith("http") ? thumbnailUrl : `${origin}${thumbnailUrl}` } : {});

function productJsonLd(product: SeoProductInput, origin: string) {
  const node = {
    "@type": "Product",
    name: product.name,
    sku: product.id,
    brand: { "@type": "Brand", name: product.vendor },
    category: product.category,
    url: `${origin}${productPath(product.slug)}`,
    ...(product.summary ? { description: product.summary } : {}),
    ...markedProperties(product.marked, origin),
    ...imageOf(product, origin),
    additionalProperty: product.properties.map((p) => ({ "@type": "PropertyValue", ...p })),
  };
  const trail = [{ name: BRAND_CONFIG.wordmark, path: "/" }, ...product.trail,
    { name: product.name, path: productPath(product.slug) }];
  return { "@context": "https://schema.org", "@graph": [node, breadcrumbList(trail, origin)] as const };
}

export function buildProductHeadMeta(product: SeoProductInput, origin: string): PageHeadMeta {
  const lead = product.summary || `${product.name} by ${product.vendor} (${product.category}).`;
  return {
    title: pageTitle(product.name),
    canonicalUrl: `${origin}${productPath(product.slug)}`,
    description: formatMetaDescription(lead),
    ogType: "product",
    jsonLd: productJsonLd(product, origin),
    ...imageOf(product, origin),
    ...(product.indexable ? {} : { noindex: true }),
  };
}
