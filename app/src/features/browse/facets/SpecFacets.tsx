import type { FC } from "react";
import type { FacetView } from "../../../domain/views.ts";
import type { BrowseFilters } from "../../../domain/filtering/filterUrl.ts";
import { facetLabel, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { toggleOption, withRange, withoutSpec } from "../../../domain/filtering/filterTransitions.ts";
import { FacetGroup } from "./FacetGroup.tsx";
import { RangeFacet } from "./RangeFacet.tsx";

interface SpecFacetsProps {
  facets: readonly FacetView[];
  filters: BrowseFilters;
  onChange: (next: BrowseFilters) => void;
}

export const SpecFacets: FC<SpecFacetsProps> = ({ facets, filters: f, onChange }) => {
  const { t, locale } = useI18n();
  return (
    <div role="group" aria-label={t("tabSpecs")} className="space-y-3 pt-2 border-t border-line-subtle">
      {facets.map((facet) =>
        facet.kind === "number" ? (
          <RangeFacet
            key={facet.spec_key}
            facet={facet}
            range={f.ranges[facet.spec_key]}
            onRange={(range) => onChange(withRange(f, facet.spec_key, range))}
          />
        ) : (
          <FacetGroup key={facet.spec_key} title={facetLabel(facet, locale)}
            hint={facet.description && localized(facet.description, locale)}
            onReset={() => onChange(withoutSpec(f, facet.spec_key))}
            options={facet.options.map((opt) => ({ id: opt.id, label: localized(opt.label, locale), count: opt.count,
              on: (f.specs[facet.spec_key] ?? []).includes(opt.id),
              onClick: () => onChange(toggleOption(f, facet.spec_key, opt.id)) }))} />
        ),
      )}
    </div>
  );
};
