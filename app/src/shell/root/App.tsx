import { useState, useMemo, useEffect, type ComponentProps, type FC } from "react";
import { HttpAskApi } from "../../adapters/search/HttpAskApi.ts";
import { HttpProductSearch } from "../../adapters/search/HttpProductSearch.ts";
import { FilesCatalogRepository } from "../../adapters/read-model/files.ts";
import { HttpReportInbox, type AppCheckConfig } from "../../adapters/review/HttpReportInbox.ts";
import type { CatalogRepository } from "../../domain/ports/CatalogRepository.ts";
import { CompareTray } from "../../features/compare/CompareTray.tsx";
import { useComparedIds } from "../../features/compare/useComparedIds.ts";
import { LoadingSkeleton, RegistryProvider, StatePanel, useRead } from "../../ui/index.ts";
import { NO_REGISTRY } from "../../ui/specs/RegistryContext.tsx";
import { ThemeProvider } from "../layout/ThemeProvider.tsx";
import { I18nProvider, useI18n } from "../i18n/index.tsx";
import { SiteHeader, type NavItem } from "../layout/SiteHeader.tsx";
import { SiteFooter } from "../layout/SiteFooter.tsx";
import { STATIC_ROUTES, browseRoute, pathFromRoute } from "../routing/router.ts";
import { browseQuery } from "../../domain/filtering/filterUrl.ts";
import { RouteView, type Navigation } from "../routing/RouteView.tsx";
import { useRoute } from "../routing/useRoute.ts";
import { buildHomeHeadMeta, buildStaticHeadMeta } from "../seo/seo.ts";
import { setCanonical, syncDocumentHead, syncNotFoundHead } from "../seo/documentHead.ts";
import { SITE_ORIGIN } from "../seo/siteOrigin.ts";
import { logger } from "../logger.ts";
import type { Start } from "./start.ts";

declare const __FIRESTORE_DOCS__: string;

async function readModel(): Promise<CatalogRepository> {
  const { FirestoreCatalogRepository } = await import("../../adapters/read-model/firestore.ts");
  return new FirestoreCatalogRepository(__FIRESTORE_DOCS__,
    import.meta.env.PROD ? new FilesCatalogRepository() : undefined);
}

function appCheck(): AppCheckConfig | null {
  const env = import.meta.env;
  const [apiKey, projectId, appId, siteKey] =
    [env.VITE_FIREBASE_API_KEY, env.VITE_FIREBASE_PROJECT_ID, env.VITE_FIREBASE_APP_ID, env.VITE_APPCHECK_SITE_KEY];
  return apiKey && projectId && appId && siteKey ? { apiKey, projectId, appId, siteKey } : null;
}

type Ports = { start: Start; repository?: CatalogRepository };

function useHeadSync(route: ReturnType<typeof useRoute>["route"], t: ReturnType<typeof useI18n>["t"]) {
  useEffect(() => {
    if (["category", "hub", "product-detail", "vendor-detail", "news", "article"].includes(route.name)) return;
    if (route.name === "not-found") return syncNotFoundHead(t("notFoundTitle"));
    if (route.name === "admin") return syncNotFoundHead(t("navAdmin"));
    const path = pathFromRoute(route);
    const canonicalUrl = `${SITE_ORIGIN}${path}`;
    if (route.name === "product-history") return setCanonical(canonicalUrl);
    const fixed = STATIC_ROUTES.find((r) => r.path === path.split("?")[0]);
    syncDocumentHead(fixed ? buildStaticHeadMeta(canonicalUrl, SITE_ORIGIN, t(fixed.title), t(fixed.description))
      : { ...buildHomeHeadMeta(SITE_ORIGIN, t("heroSubtitle")), canonicalUrl });
  }, [route, t]);
}

const RadarApp: FC<Ports> = ({ start, repository: injectedReader }) => {
  const { t } = useI18n();
  const productSearch = useMemo(() => new HttpProductSearch(), []);
  const answers = useMemo(() => new HttpAskApi(), []);
  const reports = useMemo(() => new HttpReportInbox(appCheck()), []);

  const { route, navigate } = useRoute(start.route);
  const compare = useComparedIds(route.name === "compare", start.compared);
  useHeadSync(route, t);

  const { value: loaded, error: loadError } = useRead(async () => {
    const repository = injectedReader ?? (await readModel());
    return { repository, registry: await repository.registry() };
  }, "registry", (err) => logger.error("the read model registry failed to load", { page: "shell" }, err));
  const [homeSearchQuery, setHomeSearchQuery] = useState("");

  const go: Navigation = {
    navigate,
    home: () => navigate({ name: "home" }),
    browse: (filters = {}) => navigate(browseRoute(browseQuery(filters))),
    product: (productId) => navigate({ name: "product-detail", productId }),
    history: (productId) => navigate({ name: "product-history", productId }),
    vendor: (vendorSlug) => navigate({ name: "vendor-detail", vendorSlug, page: 1 }),
    article: (slug) => navigate({ name: "article", slug }),
  };
  const toCompare = () => navigate({ name: "compare", query: "" });
  const showTray = compare.comparedIds.length > 0 && !["compare", "admin"].includes(route.name);

  const navItems: NavItem[] = [
    { key: "home", label: t("navHome"), active: route.name === "home", route: { name: "home" } },
    { key: "browse", label: t("navBrowse"), active: ["browse", "category"].includes(route.name),
      route: browseRoute(browseQuery({})) },
    { key: "ask", label: t("navAsk"), active: route.name === "search", route: { name: "search", ask: "" } },
    { key: "news", label: t("navNews"), active: ["news", "article"].includes(route.name),
      route: { name: "news", query: "" } },
    { key: "about", label: t("navAbout"), active: route.name === "about", route: { name: "about" } },
  ];

  return (
    <RegistryProvider value={loaded?.registry ?? NO_REGISTRY}>
    <div className={`min-h-screen flex flex-col bg-page text-fg transition-colors ${showTray ? "pb-24" : ""}`}>
      <a
        href="#main-content"
        className={"sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 "
          + "focus:rounded-control focus:bg-accent focus:text-on-accent focus:font-semibold focus:text-body"}
      >
        {t("skipToMainContent")}
      </a>
      <SiteHeader navItems={navItems} onNavigate={navigate} />

      <main id="main-content" className="flex-1 max-w-page w-full mx-auto px-4 sm:px-6 lg:px-8 py-4">
        {loadError ? (
          <StatePanel tone="error" level={1} title={t("errorTitle")} description={t("catalogLoadErrorDesc")}
            retryLabel={t("errorRetry")} />
        ) : !loaded ? (
          <LoadingSkeleton label={t("loading")} count={4} />
        ) : (
          <RouteView
            route={route}
            go={go}
            repository={loaded.repository}
            prerendered={start.prerendered}
            productSearch={productSearch}
            answers={answers}
            reports={reports}
            registry={loaded.registry}
            homeSearchQuery={homeSearchQuery}
            onHomeSearchQueryChange={setHomeSearchQuery}
            compare={compare}
          />
        )}
      </main>

      {showTray && (
        <CompareTray count={compare.comparedIds.length} onCompare={toCompare} onClear={compare.clearCompare} />
      )}

      <SiteFooter onOpen={(name) => navigate({ name })} />
    </div>
    </RegistryProvider>
  );
};

const App: FC<Ports & Omit<ComponentProps<typeof I18nProvider>, "children"
  | "preferred">> = ({ languages, messages, ...ports }) => (
  <ThemeProvider initial={ports.start.theme}>
    <I18nProvider preferred={ports.start.preferred} languages={languages} messages={messages}>
      <RadarApp {...ports} />
    </I18nProvider>
  </ThemeProvider>
);

export default App;
