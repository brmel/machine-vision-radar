import type { FC } from "react";
import { SlidersHorizontal, ChevronDown, ChevronUp } from "lucide-react";
import { Badge } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

export const FiltersToggle: FC<{ open: boolean; active: number;
  onToggle: () => void }> = ({ open, active, onToggle }) => {
  const { t } = useI18n();
  const Chevron = open ? ChevronUp : ChevronDown;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className={"md:hidden w-full inline-flex items-center justify-between px-3 py-2 bg-surface border border-line "
        + "rounded-card text-body font-medium text-fg cursor-pointer"}
    >
      <span className="inline-flex items-center gap-2">
        <SlidersHorizontal className="w-4 h-4 text-muted" aria-hidden="true" />
        <span>{t("filtersToggleLabel")}</span>
        {active > 0 && <Badge tone="accent">{active}</Badge>}
      </span>
      <Chevron className="w-4 h-4 text-muted" aria-hidden="true" />
    </button>
  );
};
