import { type FC } from "react";
import { ArrowUpDown } from "lucide-react";
import { SORTS, type BrowseSort } from "../../../domain/filtering/filterUrl.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

export const SortSelect: FC<{ value: BrowseSort; relevance: boolean; column?: string;
  onChange: (sort: BrowseSort) => void }> = ({ value, relevance, column, onChange }) => {
  const { t } = useI18n();
  const label = { relevance: t("sortRelevance"), name: t("sortNameAsc"), "name-desc": t("sortNameDesc"),
    vendor: t("sortVendor") };
  return (
    <label className="flex items-center gap-2">
      <ArrowUpDown className="w-4 h-4 text-muted shrink-0" aria-hidden="true" />
      <span className={"sr-only sm:not-sr-only text-caption text-muted font-medium "
        + "whitespace-nowrap"}>{t("sortLabel")}</span>
      <select
        value={column ? "column" : value}
        onChange={(e) => onChange(SORTS.find((s) => s === e.target.value) ?? "name")}
        className={"text-caption bg-surface border border-line-strong rounded-control px-2.5 py-1.5 text-fg "
          + "cursor-pointer"}
      >
        {column && <option value="column">{column}</option>}
        {SORTS.filter((s) => relevance || s !== "relevance").map((s) => (
          <option key={s} value={s}>
            {label[s]}
          </option>
        ))}
      </select>
    </label>
  );
};
