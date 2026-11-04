import type { FacetView } from "../../../domain/views.ts";
import type { BrowseIndex } from "../../../domain/filtering/browseView.ts";
import type { BrowseFilters } from "../../../domain/filtering/filterUrl.ts";
import { toggleOption, withCategory, withRange } from "../../../domain/filtering/filterTransitions.ts";
import type { MessageKey } from "../../../shell/i18n/messages.ts";
import { facetLabel, formatNumber, localized, termLabel } from "../../../ui/index.ts";

interface AppliedFilter {
  readonly key: string;
  readonly facet: string;
  readonly option: string;
  readonly next: BrowseFilters;
}

function optionName(facet: FacetView, id: string, locale: string): string {
  const option = facet.options.find((o) => o.id === id);
  if (!option) throw new Error(`browse: ${facet.spec_key}=${id} is not in the read model`);
  return localized(option.label, locale);
}

const boundName = (facet: FacetView, bound: "min" | "max", value: number, locale: string): string =>
  `${bound === "min" ? "≥" : "≤"} ${formatNumber(value, locale)}${facet.unit ? ` ${facet.unit}` : ""}`;

function facetOf(f: BrowseFilters, categoryFacets: readonly FacetView[], specKey: string): FacetView {
  const facet = categoryFacets.find((x) => x.spec_key === specKey);
  if (!facet) throw new Error(`appliedFilters: ${specKey} is not a facet of ${f.category}`);
  return facet;
}

export function appliedFilters(f: BrowseFilters, categoryFacets: readonly FacetView[], index: BrowseIndex,
    t: (key: MessageKey) => string, locale: string): AppliedFilter[] {
  const chips: AppliedFilter[] = [];
  if (f.domain) chips.push({ key: "domain", facet: t("filterByDomain"),
    option: termLabel(index.domains, f.domain, locale), next: { ...f, domain: null, page: 1 } });
  if (f.stage) chips.push({ key: "stage", facet: t("filterByPipeline"),
    option: termLabel(index.pipeline_stages, f.stage, locale), next: { ...f, stage: null, page: 1 } });
  if (f.category) chips.push({ key: "category", facet: t("filterByCategory"),
    option: termLabel(index.categories, f.category, locale), next: withCategory(f, null, []) });
  for (const [specKey, ids] of Object.entries(f.specs)) {
    const facet = facetOf(f, categoryFacets, specKey);
    chips.push(...ids.map((id) => ({ key: `${specKey}=${id}`, facet: facetLabel(facet, locale),
      option: optionName(facet, id, locale), next: toggleOption(f, specKey, id) })));
  }
  for (const [specKey, range] of Object.entries(f.ranges)) {
    const facet = facetOf(f, categoryFacets, specKey);
    for (const bound of ["min", "max"] as const) {
      const value = range[bound];
      if (value !== undefined)
        chips.push({ key: `${specKey}_${bound}`, facet: facetLabel(facet, locale), option: boundName(facet, bound,
          value, locale), next: withRange(f, specKey, { ...range, [bound]: undefined }) });
    }
  }
  return chips;
}
