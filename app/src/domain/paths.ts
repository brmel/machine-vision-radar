export const browsePath = (query: string): string => (query ? `/browse?${query}` : "/browse");
export const productPath = (slug: string): string => `/product/${encodeURIComponent(slug)}`;
export const isProductId = (slugOrId: string): boolean => /^prd_[0-9a-z]{10}$/.test(slugOrId);
export const vendorPath = (vendorSlug: string): string => `/vendor/${encodeURIComponent(vendorSlug)}`;
export const historyPath = (slug: string): string => `${productPath(slug)}/history`;
export const categoryPath = (categoryId: string): string => `/category/${encodeURIComponent(categoryId)}`;
export const hubPath = (path: string, productSlug: string): string => `/${path}/${encodeURIComponent(productSlug)}`;
export const NEWS_PATH = "/news";
export const articlePath = (slug: string): string => `${NEWS_PATH}/${encodeURIComponent(slug)}`;
export const familyComparePath = (slug: string): string => `/compare/${encodeURIComponent(slug)}`;
export const feedPath = (home: string, format: "atom" | "json"): string => `${home}/feed.${format}`;

export const pageCount = (total: number, size: number): number => Math.max(1, Math.ceil(total / size));

export function pageOf(search: string): number {
  const page = Number(new URLSearchParams(search).get("page") ?? "1");
  return Number.isInteger(page) && page > 1 ? page : 1;
}
