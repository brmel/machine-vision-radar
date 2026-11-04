import { type FC, type ReactNode, useEffect, useState } from "react";
import type { CatalogRepository } from "../../../domain/ports/CatalogRepository.ts";
import type { SearchEvent } from "../../../domain/ports/AskApi.ts";
import type { ProductSearch } from "../../../domain/ports/ProductSearch.ts";
import { withoutFilters, withQuery } from "../../../domain/filtering/filterTransitions.ts";
import { ReadState } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useReadStateLabels } from "../../../shell/i18n/labels.ts";
import { useBrowse } from "../hooks/useBrowse.ts";
import { useProductSearch } from "../hooks/useProductSearch.ts";
import { CatalogSearch } from "../components/CatalogSearch.tsx";
import { AppliedFilters } from "./AppliedFilters.tsx";
import { buildHubHeadMeta, categoryHub } from "../../../shell/seo/hubs.ts";
import { syncDocumentHead } from "../../../shell/seo/documentHead.ts";
import { SITE_ORIGIN } from "../../../shell/seo/siteOrigin.ts";
import { appliedFilters } from "../hooks/browseFilters.ts";
import { encodeFilters } from "../../../domain/filtering/filterUrl.ts";
import { FacetSidebar } from "../facets/FacetSidebar.tsx";
import { BrowseHeader } from "./BrowseHeader.tsx";
import { BrowseResults } from "./BrowseResults.tsx";
import { FiltersToggle } from "./FiltersToggle.tsx";

interface CategoryBrowserProps {
  repository: CatalogRepository;
  productSearch: ProductSearch;
  onCounted: (event: SearchEvent) => void;
  query: string;
  onNavigate: (query: string, replace: boolean) => void;
  onSelectProduct: (productSlug: string) => void;
  onSelectVendor: (vendorSlug: string) => void;
  onToggleCompare: (productId: string) => void;
  comparedIds: string[];
  news: (about: string) => ReactNode;
}

export const CategoryBrowser: FC<CategoryBrowserProps> = ({ repository, productSearch, onCounted, query,
  onNavigate, onSelectProduct, onSelectVendor, onToggleCompare, comparedIds, news }) => {
  const { t, locale } = useI18n();
  const states = useReadStateLabels();
  const rank = useProductSearch(productSearch, onCounted);
  const { index, view, searched, error, change } = useBrowse(repository, rank, query, onNavigate);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const hub = index?.categories.find((c) => c.id === view?.filters.category);
  useEffect(() => {
    if (hub && view) syncDocumentHead(buildHubHeadMeta(categoryHub(hub, view.products), SITE_ORIGIN));
  }, [hub, view]);

  if (error || !index || !view) {
    return (
      <div className="space-y-3">
        <BrowseHeader hub={hub} />
        <ReadState failed={Boolean(error)} skeleton={{ count: 6 }} level={2}
          labels={{ ...states, errorTitle: t(error === "search" ? "searchErrorTitle" : "errorTitle") }} />
      </div>
    );
  }

  const f = view.filters;
  const open = (slug: string) => {
    if (f.q) onCounted("result_click");
    onSelectProduct(slug);
  };
  const chips = appliedFilters(f, view.categoryFacets, index, t, locale).map((chip) => ({ key: chip.key,
    label: t("appliedFilter", { facet: chip.facet, option: chip.option }), onRemove: () => change(chip.next) }));
  const toggleFilters = () => setMobileFiltersOpen((shown) => !shown);

  return (
    <div className="w-full space-y-3">
      <BrowseHeader hub={hub} view={view} byMeaning={searched === "meaning"} change={change} />
      <CatalogSearch value={f.q} onSearch={(words) => onNavigate(encodeFilters(withQuery(f, words)), true)} />
      <AppliedFilters chips={chips} onClearAll={() => change(withoutFilters(f))} />
      <div className="flex flex-col md:flex-row items-start gap-4 lg:gap-6">
        <FiltersToggle open={mobileFiltersOpen} active={chips.length} onToggle={toggleFilters} />
        <FacetSidebar
          className={mobileFiltersOpen
            ? "fixed inset-0 z-50 overflow-y-auto bg-page px-4 pt-4 md:static md:z-auto md:overflow-visible md:p-0"
              : "hidden md:block"}
          view={view} categories={index.categories} onChange={change} onDone={() => setMobileFiltersOpen(false)} />
        <BrowseResults hub={hub} view={view} change={change} onOpen={open} onSelectVendor={onSelectVendor}
          onToggleCompare={onToggleCompare} comparedIds={comparedIds} />
      </div>
      {hub && news(hub.id)}
    </div>
  );
};
