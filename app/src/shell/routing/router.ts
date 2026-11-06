import type { Route } from "./routes.ts";
import { NEWS_PATH, articlePath, browsePath, categoryPath, familyComparePath, historyPath, hubPath, pageOf,
  productPath, vendorPath } from "../../domain/paths.ts";
import type { MessageKey } from "../i18n/messages.ts";
import { ENABLE_ADMIN } from "../admin/flags.ts";

export const STATIC_ROUTES = [
  { path: "/browse", file: "browse.html", title: "catalogTitle", description: "catalogDescription" },
  { path: "/search", file: "search.html", title: "askTitle", description: "askDescription" },
  { path: "/compare", file: "compare.html", title: "compareTitle", description: "compareDescription" },
  { path: "/market", file: "market.html", title: "marketTitle", description: "marketDescription" },
  { path: "/about", file: "about.html", title: "navAbout", description: "aboutPageDescription" },
  { path: "/agents", file: "agents.html", title: "agentsPageTitle", description: "agentsPageDescription" },
  { path: "/terms", file: "terms.html", title: "termsTitle", description: "termsPageDescription" },
  { path: "/privacy", file: "privacy.html", title: "privacyTitle", description: "privacyPageDescription" },
] as const satisfies readonly { path: string; file: string; title: MessageKey; description: MessageKey }[];

export function browseRoute(query: string): Route {
  const pairs = query.split("&").filter(Boolean);
  const named = pairs.find((p) => p.startsWith("category="));
  if (!named) return { name: "browse", query };
  return { name: "category", category: decodeURIComponent(named.slice("category=".length)),
    query: pairs.filter((p) => p !== named).join("&") };
}

export const categoryQuery = (route: { category: string; query: string }): string =>
  [`category=${encodeURIComponent(route.category)}`, route.query].filter(Boolean).join("&");

const queryOf = (search: string): string => search.replace(/^\?/, "");
const withQuery = (path: string, query: string): string => (query ? `${path}?${query}` : path);
const withPage = (path: string, page: number): string => (page > 1 ? `${path}?page=${page}` : path);

const EXACT = new Map<string, (search: string) => Route>([
  ["/", () => ({ name: "home" })],
  ["/browse", (search) => browseRoute(queryOf(search))],
  ["/search", (search) => ({ name: "search", ask: new URLSearchParams(search).get("ask") ?? "" })],
  ["/compare", (search) => ({ name: "compare", query: queryOf(search) })],
  ["/market", () => ({ name: "market" })],
  ["/about", () => ({ name: "about" })],
  ["/agents", () => ({ name: "agents" })],
  ["/terms", () => ({ name: "terms" })],
  ["/privacy", () => ({ name: "privacy" })],
  [NEWS_PATH, (search) => ({ name: "news", query: queryOf(search) })],
]);

function categoryRoute(rest: string, search: string): Route | null {
  const category = decodeURIComponent(rest).trim();
  return !category || category.includes("/") ? null : { name: "category", category, query: queryOf(search) };
}

function productRoute(rest: string): Route | null {
  const [rawId, tail, ...more] = rest.split("/");
  const productId = decodeURIComponent(rawId).trim();
  if (!productId || more.length > 0 || (tail !== undefined && tail !== "history")) return null;
  return tail === "history" ? { name: "product-history", productId } : { name: "product-detail", productId };
}

function vendorRoute(rest: string, search: string): Route | null {
  const vendorSlug = decodeURIComponent(rest).trim();
  return vendorSlug ? { name: "vendor-detail", vendorSlug, page: pageOf(search) } : null;
}

function compareRoute(rest: string, search: string): Route | null {
  const family = decodeURIComponent(rest).trim();
  return !family || family.includes("/") ? null : { name: "compare", query: queryOf(search), family };
}

function articleRoute(rest: string): Route | null {
  const slug = decodeURIComponent(rest).trim();
  return !slug || slug.includes("/") ? null : { name: "article", slug };
}

const PREFIXED: readonly (readonly [string, (rest: string, search: string) => Route | null])[] = [
  ["/category/", categoryRoute],
  ["/product/", productRoute],
  ["/vendor/", vendorRoute],
  ["/compare/", compareRoute],
  [`${NEWS_PATH}/`, articleRoute],
];

export function routeFromPath(pathname: string, search = ""): Route {
  const cleanPath = pathname.replace(/\/+$/, "") || "/";
  const exact = EXACT.get(cleanPath);
  if (exact) return exact(search);
  const prefixed = PREFIXED.find(([prefix]) => cleanPath.startsWith(prefix));
  if (prefixed) return prefixed[1](cleanPath.slice(prefixed[0].length), search)
    ?? { name: "not-found", path: pathname };
  if (ENABLE_ADMIN && (cleanPath === "/admin" || cleanPath.startsWith("/admin/"))) {
    return { name: "admin", path: `${cleanPath.slice("/admin".length)}${search}` };
  }
  const parts = cleanPath.split("/").filter(Boolean);
  return parts.length === 2 ? { name: "hub", path: parts[0], slug: decodeURIComponent(parts[1]), page: pageOf(search) }
    : { name: "not-found", path: pathname };
}

type RouteByName = { [K in Route["name"]]: Extract<Route, { name: K }> };

const PATHS: { [K in keyof RouteByName]: (route: RouteByName[K]) => string } = {
  home: () => "/",
  browse: (route) => browsePath(route.query),
  category: (route) => withQuery(categoryPath(route.category), route.query),
  "product-detail": (route) => productPath(route.productId),
  "product-history": (route) => historyPath(route.productId),
  "vendor-detail": (route) => withPage(vendorPath(route.vendorSlug), route.page),
  hub: (route) => withPage(hubPath(route.path, route.slug), route.page),
  search: (route) => (route.ask ? `/search?ask=${encodeURIComponent(route.ask)}` : "/search"),
  compare: (route) => withQuery(route.family ? familyComparePath(route.family) : "/compare", route.query),
  market: () => "/market",
  about: () => "/about",
  agents: () => "/agents",
  terms: () => "/terms",
  privacy: () => "/privacy",
  news: (route) => withQuery(NEWS_PATH, route.query),
  article: (route) => articlePath(route.slug),
  admin: (route) => (ENABLE_ADMIN ? `/admin${route.path}` : "/404"),
  "not-found": (route) => route.path,
};

export function pathFromRoute<K extends keyof RouteByName>(route: RouteByName[K] & { name: K }): string {
  return PATHS[route.name](route);
}
