import { z } from "zod";
import { isProductId } from "../../domain/paths.ts";
import type { CatalogRepository, ListingPage, ListingQuery } from "../../domain/ports/CatalogRepository.ts";
import type { CategoryPage, FeedItemView, FeedPageView, HistoryView, MarketView, OrgBrief, OrganizationView,
  ProductView, RegistryView } from "../../domain/views.ts";
import {
  FacetViewSchema, FeedItemViewSchema, FeedPageViewSchema, HistoryViewSchema, MarketViewSchema,
  OrgBriefSchema, OrganizationViewSchema, ProductCardSchema, ProductViewSchema, RegistryViewSchema,
} from "../generated-views-zod.ts";
import { Recent } from "./recent.ts";

const Facets = z.array(FacetViewSchema);
const Cards = z.array(ProductCardSchema);
const Organizations = z.array(OrgBriefSchema);
const ListingChunk =
  z.object({ category: z.string(), page: z.number(), pages: z.number(), next: z.string().optional(), products: Cards });
// Justification (typed boundary): the Firestore REST document shape; only the fields the adapter writes are read.
const Doc = z.object({ fields: z.record(z.string(),
  z.object({ stringValue: z.string().optional(), integerValue: z.string().optional() })) });
const Found = z.array(z.object({ found: Doc.extend({ name: z.string() }).optional(), missing: z.string().optional() }));
const CardRows =
  z.array(z.object({ document: z.object({ fields: z.object({ card: z.object({ stringValue: z.string() }) }) })
    .optional() }));
const Counted =
  z.array(z.object({ result: z.object({ aggregateFields: z.object({ total: z.object({ integerValue: z.string() }) }) })
    .optional() }));

const by = (fieldPath: string, direction: "ASCENDING" | "DESCENDING" = "ASCENDING") =>
  ({ field: { fieldPath }, direction });
const ORDER: Record<ListingQuery["sort"], ReturnType<typeof by>[]> = {
  name: [by("name_key")],
  "name-desc": [by("name_key", "DESCENDING")],
  vendor: [by("vendor_key"), by("name_key")],
};

type Fields = Record<string, { stringValue?: string; integerValue?: string }>;

const viewIn = <T>(fields: Fields, schema: z.ZodType<T>): T =>
  schema.parse(JSON.parse(fields.json?.stringValue ?? "null"));

const ATTEMPTS = 3;

async function fetched(url: string, init?: RequestInit): Promise<Response> {
  for (let attempt = 1; ; attempt++) {
    try {
      return await fetch(url, init);
    } catch (err) {
      if (attempt === ATTEMPTS) throw err;
      await new Promise((wake) => setTimeout(wake, 200 * attempt));
    }
  }
}

export class FirestoreCatalogRepository implements CatalogRepository {
  private readonly docs: string;
  private readonly site?: Pick<CatalogRepository, "registry" | "organizations">;
  private readonly recent = new Recent<Fields | null>();

  constructor(docs: string, site?: Pick<CatalogRepository, "registry" | "organizations">) {
    this.docs = docs;
    this.site = site;
  }

  private fields(path: string): Promise<Fields | null> {
    return this.recent.get(path, async () => {
      const res = await fetched(`${this.docs}/${path}`);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`Firestore: ${path} answered HTTP ${res.status}`);
      return Doc.parse(await res.json()).fields;
    });
  }

  private async json<T>(path: string, schema: z.ZodType<T>): Promise<T | null> {
    const fields = await this.fields(path);
    return fields ? viewIn(fields, schema) : null;
  }

  private async required<T>(path: string, schema: z.ZodType<T>): Promise<T> {
    const found = await this.json(path, schema);
    if (found === null) throw new Error(`Firestore: no ${path}`);
    return found;
  }

  private async views<T>(paths: readonly string[], schema: z.ZodType<T>): Promise<T[]> {
    if (paths.length === 0) return [];
    const root = this.docs.slice(this.docs.indexOf("/projects/") + 1);
    const answer =
      await this.post("batchGet", { documents: paths.map((p) => `${root}/${p}`) }, `a batch of ${paths.length} views`);
    const found = new Map(Found.parse(answer)
      .flatMap((r) => (r.found ? [[r.found.name.slice(root.length + 1), r.found.fields] as const] : [])));
    return paths.map((p) => {
      const fields = found.get(p);
      if (!fields) throw new Error(`Firestore: no ${p}`);
      this.recent.keep(p, fields);
      return viewIn(fields, schema);
    });
  }

  private async post(verb: string, body: unknown, what: string): Promise<unknown> {
    const res = await fetched(`${this.docs}:${verb}`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(`Firestore: ${what} answered HTTP ${res.status}`);
    return res.json();
  }

  registry(): Promise<RegistryView> {
    return this.site ? this.site.registry() : this.required("public_index/registry", RegistryViewSchema);
  }

  async product(slugOrId: string): Promise<ProductView | null> {
    if (isProductId(slugOrId)) return this.json(`public_products/${slugOrId}`, ProductViewSchema);
    const where = { fieldFilter: { field: { fieldPath: "slug" }, op: "EQUAL", value: { stringValue: slugOrId } } };
    const answer = await this.post("runQuery",
      { structuredQuery: { from: [{ collectionId: "public_products" }], where, limit: 1 } }, `product ${slugOrId}`);
    // Justification (typed boundary): a runQuery answer is a list of {document?}; the document is parsed below.
    const [hit] = answer as { document?: unknown }[];
    return hit?.document ? viewIn(Doc.parse(hit.document).fields, ProductViewSchema) : null;
  }

  products(ids: readonly string[]): Promise<readonly ProductView[]> {
    return this.views(ids.map((id) => `public_products/${id}`), ProductViewSchema);
  }

  async listing(query: ListingQuery, page: number, size: number): Promise<ListingPage> {
    if (query.categories?.length === 0) return { products: [], total: 0 };
    const filters = [
      ...(query.categories ? [{ fieldFilter: { field: { fieldPath: "category" }, op: "IN",
        value: { arrayValue: { values: query.categories.map((c) => ({ stringValue: c })) } } } }] : []),
      ...(query.vendor ? [{ fieldFilter: { field: { fieldPath: "vendor" }, op: "EQUAL",
        value: { stringValue: query.vendor } } }] : []),
      ...(query.uses ? [{ fieldFilter: { field: { fieldPath: "uses" }, op: "ARRAY_CONTAINS",
        value: { stringValue: query.uses } } }] : []),
    ];
    const where = filters.length > 1 ? { where: { compositeFilter: { op: "AND", filters } } } : filters.length === 1
      ? { where: filters[0] } : {};
    const from = [{ collectionId: "public_products" }];
    const orderBy = ORDER[query.sort];
    const [rows, counted] = await Promise.all([
      this.post("runQuery", { structuredQuery: { from, ...where, select: { fields: [{ fieldPath: "card" }] }, orderBy,
        offset: (page - 1) * size, limit: size } }, "a listing"),
      this.post("runAggregationQuery", { structuredAggregationQuery: { structuredQuery: { from, ...where },
        aggregations: [{ alias: "total", count: {} }] } }, "a listing count"),
    ]);
    const products = CardRows.parse(rows)
      .flatMap((r) => (r.document ? [ProductCardSchema.parse(JSON.parse(r.document.fields.card.stringValue))] : []));
    return { products, total: Number(Counted.parse(counted)[0]?.result?.aggregateFields.total.integerValue ?? 0) };
  }

  async categoryPage(category: string, cursor = "1"): Promise<CategoryPage> {
    const doc = `public_facets/${encodeURIComponent(category)}`;
    const [facets, chunk] = await Promise.all([this.required(doc, Facets),
      this.required(`${doc}/pages/${encodeURIComponent(cursor)}`, ListingChunk)]);
    return { ...chunk, facets };
  }

  organizations(): Promise<readonly OrgBrief[]> {
    return this.site ? this.site.organizations() : this.required("public_index/organizations", Organizations);
  }

  organization(slug: string): Promise<OrganizationView | null> {
    return this.json(`public_organizations/${encodeURIComponent(slug)}`, OrganizationViewSchema);
  }

  organizationViews(slugs: readonly string[]): Promise<readonly OrganizationView[]> {
    return this.views(slugs.map((slug) => `public_organizations/${slug}`), OrganizationViewSchema);
  }

  history(productId: string): Promise<HistoryView | null> {
    return this.json(`public_history/${encodeURIComponent(productId)}`, HistoryViewSchema);
  }

  news(): Promise<FeedPageView> {
    return this.required("public_index/news", FeedPageViewSchema);
  }

  article(slug: string): Promise<FeedItemView | null> {
    return this.json(`public_news/${encodeURIComponent(slug)}`, FeedItemViewSchema);
  }

  market(): Promise<MarketView> {
    return this.required("public_index/market", MarketViewSchema);
  }
}
