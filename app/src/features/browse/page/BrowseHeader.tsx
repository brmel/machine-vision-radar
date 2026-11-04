import { type FC } from "react";
import { Sparkles } from "lucide-react";
import type { CategoryEntry } from "../../../domain/views.ts";
import type { BrowseView } from "../../../domain/filtering/browseView.ts";
import type { BrowseFilters } from "../../../domain/filtering/filterUrl.ts";
import { withLayout, withSort } from "../../../domain/filtering/filterTransitions.ts";
import { PageHeader, Segmented, localized, specRowLabel, useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { SortSelect } from "../components/SortSelect.tsx";

interface BrowseHeaderProps {
  hub: CategoryEntry | undefined;
  view?: BrowseView;
  byMeaning?: boolean;
  change?: (next: BrowseFilters) => void;
}

export const BrowseHeader: FC<BrowseHeaderProps> = ({ hub, view, byMeaning = false, change }) => {
  const { t, plural, locale } = useI18n();
  const { spec_definitions: specs } = useRegistry();
  const f = view?.filters;
  const column = f?.column ? t(f.column.desc ? "sortColumnDesc" : "sortColumnAsc",
    { column: specRowLabel(f.column.key, specs, locale) }) : undefined;
  return (
    <PageHeader
      title={hub ? localized(hub.label, locale) : t("catalogTitle")}
      lead={hub && localized(hub.description, locale)}
      count={view && (
        <span role="status" aria-live="polite">
          {plural("productCountOne", "productCountOther", view.resultCount)}
          {byMeaning && <> · <Sparkles className="inline size-3.5 align-[-2px]" aria-hidden="true" /> {t(
            "searchClosestLabel")}</>}
        </span>
      )}
      actions={f && change && (
        <>
          {hub && (
            <Segmented label={t("layoutLabel")} value={f.layout} onChange={(layout) => change(withLayout(f, layout))}
              options={[{ id: "cards", label: t("layoutCards") }, { id: "table", label: t("layoutTable") }]} />
          )}
          <SortSelect value={f.sort} relevance={f.q !== ""} column={column}
            onChange={(sort) => change(withSort(f, sort))} />
        </>
      )}
    />
  );
};
