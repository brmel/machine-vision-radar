import { type FC } from "react";
import { X } from "lucide-react";
import { Chip } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

interface AppliedFilterChip {
  readonly key: string;
  readonly label: string;
  readonly onRemove: () => void;
}

export const AppliedFilters: FC<{ chips: readonly AppliedFilterChip[]; onClearAll: () => void }> = ({ chips,
  onClearAll }) => {
  const { t } = useI18n();
  return chips.length === 0 ? null : (
    <div role="group" aria-label={t("appliedFiltersLabel")} className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <Chip key={chip.key} active label={chip.label} aria-label={t("removeFilter", { label: chip.label })}
          onClick={chip.onRemove}>
          <X className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
        </Chip>
      ))}
      <button type="button" onClick={onClearAll}
        className="text-caption font-medium text-fg-secondary underline hover:text-fg cursor-pointer">
        {t("clearAll")}
      </button>
    </div>
  );
};
