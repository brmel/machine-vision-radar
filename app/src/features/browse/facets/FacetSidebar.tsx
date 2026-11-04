import { type FC, useState } from "react";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import type { CategoryEntry } from "../../../domain/views.ts";
import type { BrowseView } from "../../../domain/filtering/browseView.ts";
import type { BrowseFilters } from "../../../domain/filtering/filterUrl.ts";
import { Button, localized, useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { withCategory, withDomain, withStage } from "../../../domain/filtering/filterTransitions.ts";
import { FacetGroup } from "./FacetGroup.tsx";
import { SpecFacets } from "./SpecFacets.tsx";

interface FacetSidebarProps {
  view: BrowseView;
  categories: readonly CategoryEntry[];
  onChange: (next: BrowseFilters) => void;
  onDone: () => void;
  className: string;
}

const TOP_FACETS = 3;

export const FacetSidebar: FC<FacetSidebarProps> = ({ view, categories, onChange, onDone, className }) => {
  const { t, plural, locale } = useI18n();
  const { pipeline_stages: stages, domains: allDomains } = useRegistry();
  const [showAll, setShowAll] = useState(true);
  const f = view.filters;
  const shown = (counts: Readonly<Record<string, number>>, id: string, active: boolean) => active
    || (counts[id] ?? 0) > 0;
  const domainLabel = (id: string) => localized(allDomains.find((d) => d.id === id)?.label ?? { en: id }, locale);
  const domains = allDomains.filter(({ id }) => shown(view.domainCounts, id, f.domain === id));
  const shownStages = stages.filter(({ id }) => shown(view.stageCounts, id, f.stage === id));
  const visibleCategories = categories.filter(
    (c) => (!f.domain || c.domain === f.domain) && shown(view.categoryCounts, c.id, f.category === c.id)
  );
  const facets = showAll ? view.facets : view.facets.slice(0, TOP_FACETS);

  return (
    <aside className={`w-full md:w-60 space-y-3 shrink-0 ${className}`}>
      <div className="flex items-center justify-between pb-2 border-b border-line">
        <h2 className="text-body font-heading text-fg">{t("filtersTitle")}</h2>
        <button type="button" onClick={onDone} aria-label={t("filtersClose")}
          className="md:hidden -my-2 -mr-3 p-3 text-fg-secondary hover:text-fg cursor-pointer">
          <X className="w-5 h-5" aria-hidden="true" />
        </button>
      </div>

      <FacetGroup title={t("filterByDomain")} onReset={() => onChange(withDomain(f, null, categories))}
        options={domains.map(({ id, label }) =>
          ({ id, label: localized(label, locale), count: view.domainCounts[id], on: f.domain === id,
          onClick: () => onChange(withDomain(f, f.domain === id ? null : id, categories)) }))} />

      <FacetGroup title={t("filterByPipeline")} onReset={() => onChange(withStage(f, null, categories))}
        options={shownStages.map(({ id, label }) =>
          ({ id, label: localized(label, locale), count: view.stageCounts[id], on: f.stage === id,
          onClick: () => onChange(withStage(f, f.stage === id ? null : id, categories)) }))} />

      {visibleCategories.length > 0 && (
        <FacetGroup title={t("filterByCategory")} onReset={() => onChange(withCategory(f, null, categories))}
          options={visibleCategories.map((cat) => ({ id: cat.id, label: localized(cat.label, locale),
            count: view.categoryCounts[cat.id] ?? 0, on: f.category === cat.id,
            onClick: () => onChange(withCategory(f, f.category === cat.id ? null : cat.id, categories)),
            title: localized(cat.description, locale), section: f.domain ? undefined : domainLabel(cat.domain) }))} />
      )}

      {facets.length > 0 && <SpecFacets facets={facets} filters={f} onChange={onChange} />}

      {view.facets.length > TOP_FACETS && (
        <Button variant="ghost" size="sm" onClick={() => setShowAll((open) => !open)}
          className={"w-full justify-between text-caption text-muted border border-dashed border-line "
            + "hover:border-line-hover"}>
          <span>{showAll ? t("fewerFilters") : `${t("moreFilters")} (${view.facets.length - TOP_FACETS})`}</span>
          {showAll ? <ChevronUp className="w-3.5 h-3.5" aria-hidden="true" />
            : <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" />}
        </Button>
      )}

      <div className="md:hidden sticky bottom-0 pt-2 pb-4 bg-page">
        <Button variant="primary" onClick={onDone} className="w-full justify-center">
          {plural("filtersShowOne", "filtersShowOther", view.resultCount)}
        </Button>
      </div>
    </aside>
  );
};
