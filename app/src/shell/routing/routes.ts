export type Route =
  | { name: "home" }
  | { name: "browse"; query: string }
  | { name: "category"; category: string; query: string }
  | { name: "product-detail"; productId: string }
  | { name: "product-history"; productId: string }
  | { name: "vendor-detail"; vendorSlug: string; page: number }
  | { name: "hub"; path: string; slug: string; page: number }
  | { name: "search"; ask: string }
  | { name: "compare"; query: string; family?: string }
  | { name: "news"; query: string }
  | { name: "article"; slug: string }
  | { name: "market" }
  | { name: "about" }
  | { name: "agents" }
  | { name: "terms" }
  | { name: "privacy" }
  | { name: "admin"; path: string }
  | { name: "not-found"; path: string };
