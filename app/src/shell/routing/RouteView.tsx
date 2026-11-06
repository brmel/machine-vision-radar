import { Suspense, type FC, useCallback } from "react";
import type { ProductView, RegistryView } from "../../domain/views.ts";
import type { CatalogRepository } from "../../domain/ports/CatalogRepository.ts";
import type { AskApi, SearchEvent } from "../../domain/ports/AskApi.ts";
import type { ProductSearch } from "../../domain/ports/ProductSearch.ts";
import type { ReportInbox } from "../../domain/ports/review/ReportInbox.ts";
import type { BrowseFilters } from "../../domain/filtering/filterUrl.ts";
import type { Route } from "./routes.ts";
import { browseRoute, categoryQuery, pathFromRoute } from "./router.ts";
import { CategoryBrowser } from "../../features/browse/page/CategoryBrowser.tsx";
import { MarketView } from "../../features/browse/page/MarketView.tsx";
import { ComponentHub } from "../../features/browse/components/ComponentHub.tsx";
import { ProductDetailView } from "../../features/product-detail/components/ProductDetailView.tsx";
import { ProductHistory } from "../../features/product-detail/history/ProductHistory.tsx";
import { VendorDetailView } from "../../features/vendor-detail/VendorDetailView.tsx";
import { AskView } from "../../features/ask/AskView.tsx";
import { CompareView } from "../../features/compare/CompareView.tsx";
import type { useComparedIds } from "../../features/compare/useComparedIds.ts";
import { HomeView } from "../../features/home/landing/HomeView.tsx";
import { AboutView } from "../../features/home/AboutView.tsx";
import { AgentsView } from "../../features/home/AgentsView.tsx";
import { LegalView } from "../../features/home/LegalView.tsx";
import { NotFoundView } from "../../features/home/NotFoundView.tsx";
import { NewsView } from "../../features/home/news/NewsView.tsx";
import { ArticleView } from "../../features/home/news/ArticleView.tsx";
import { RecentNews } from "../../features/home/news/RecentNews.tsx";
import { LazyAdminSection as AdminSection } from "../admin/flags.ts";
import { LoadingSkeleton } from "../../ui/index.ts";
import { useI18n } from "../i18n/index.tsx";
import { logger } from "../logger.ts";

export interface Navigation {
  navigate: (route: Route, replace?: boolean) => void;
  home: () => void;
  browse: (filters?: Partial<BrowseFilters>) => void;
  product: (productId: string) => void;
  history: (productId: string) => void;
  vendor: (vendorSlug: string) => void;
  article: (slug: string) => void;
}

export const RouteView: FC<{
  route: Route;
  go: Navigation;
  repository: CatalogRepository;
  prerendered: ProductView | null;
  productSearch: ProductSearch;
  answers: AskApi;
  reports: ReportInbox;
  registry: RegistryView;
  homeSearchQuery: string;
  onHomeSearchQueryChange: (query: string) => void;
  compare: ReturnType<typeof useComparedIds>;
}> = ({ route, go, repository, prerendered, productSearch, answers, reports, registry, homeSearchQuery,
  onHomeSearchQueryChange, compare }) => {
  const { t } = useI18n();
  const { comparedIds, setComparedIds, toggleCompare } = compare;
  const recent = (about: string) => <RecentNews repository={repository} about={about} onOpen={go.article} />;
  const cards = { repository, onSelectProduct: go.product, onSelectVendor: go.vendor, onToggleCompare: toggleCompare,
    comparedIds, news: recent };
  const count = useCallback((event: SearchEvent) => {
    answers.count(event).catch((err: unknown) => logger.warn("search: a counter was not added", { event }, err));
  }, [answers]);
  switch (route.name) {
    case "home":
      return (
        <HomeView
          registry={registry}
          query={homeSearchQuery}
          onQueryChange={onHomeSearchQueryChange}
          onSearch={(q) => go.browse({ q })}
          onBrowse={go.browse}
          onNews={() => go.navigate({ name: "news", query: "" })}
          onMarket={() => go.navigate({ name: "market" })}
          onArticle={go.article}
        />
      );
    case "browse":
    case "category":
      return (
        <CategoryBrowser
          {...cards}
          productSearch={productSearch}
          onCounted={count}
          query={route.name === "category" ? categoryQuery(route) : route.query}
          onNavigate={(query, replace) => go.navigate(browseRoute(query), replace)}
        />
      );
    case "hub":
      return (
        <ComponentHub
          repository={repository}
          path={route.path}
          slug={route.slug}
          page={route.page}
          onPage={(page) => go.navigate({ ...route, page })}
          onSelectProduct={go.product}
          onSelectVendor={go.vendor}
          onSelectCategory={(category) => go.browse({ category })}
          onMissing={() => go.navigate({ name: "not-found", path: pathFromRoute(route) }, true)}
          news={recent}
        />
      );
    case "product-detail":
      return (
        <ProductDetailView
          repository={repository}
          reports={reports}
          productId={route.productId}
          prerendered={prerendered}
          onBrowse={() => go.browse()}
          onSelectProduct={go.product}
          onOpenHistory={go.history}
          onSelectVendor={go.vendor}
          onSelectDomain={(domain) => go.browse({ domain })}
          onSelectCategory={(category) => go.browse({ category })}
          onOpenHub={(path, slug) => go.navigate({ name: "hub", path, slug, page: 1 })}
          onToggleCompare={toggleCompare}
          comparedIds={comparedIds}
          onCompareFamily={(family) => go.navigate({ name: "compare", query: "", family })}
        />
      );
    case "product-history":
      return <ProductHistory repository={repository} productId={route.productId} onBrowse={() => go.browse()}
        onSelectProduct={go.product} />;
    case "vendor-detail":
      return (
        <VendorDetailView
          {...cards}
          vendorSlug={route.vendorSlug}
          page={route.page}
          onPage={(page) => go.navigate({ ...route, page })}
          onBrowse={() => go.browse()}
        />
      );
    case "search":
      return (
        <AskView
          repository={repository}
          answers={answers}
          question={route.ask}
          onAsk={(ask) => go.navigate({ name: "search", ask })}
          onSelectProduct={go.product}
        />
      );
    case "compare":
      return (
        <CompareView
          repository={repository}
          comparedIds={comparedIds}
          onComparedIdsChange={setComparedIds}
          query={route.query}
          family={route.family}
          onQueryChange={(query, family) => go.navigate({ name: "compare", query, ...(family ? { family } : {}) })}
          onSelectProduct={go.product}
          onBrowseMore={() => go.browse()}
        />
      );
    case "news":
      return <NewsView repository={repository} query={route.query}
        onQuery={(query) => go.navigate({ name: "news", query })} onOpen={go.article} />;
    case "article":
      return (
        <ArticleView repository={repository} slug={route.slug} onNews={() => go.navigate({ name: "news", query: "" })}
          onProduct={go.product} onVendor={go.vendor} />
      );
    case "market":
      return <MarketView repository={repository} onCategory={(category) => go.browse({ category })}
        onVendor={go.vendor} />;
    case "about":
      return <AboutView />;
    case "agents":
      return <AgentsView />;
    case "terms":
    case "privacy":
      return <LegalView page={route.name} />;
    case "admin":
      return AdminSection ? (
        <Suspense fallback={<LoadingSkeleton label={t("loading")} count={2} />}>
          <AdminSection path={route.path}
            onNavigate={(path, replace) => go.navigate({ name: "admin", path }, replace)} />
        </Suspense>
      ) : null;
    case "not-found":
      return <NotFoundView path={route.path} onHome={go.home} />;
  }
};
