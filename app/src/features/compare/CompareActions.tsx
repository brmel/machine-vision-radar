import type { FC } from "react";
import { Button } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";

interface CompareActionsProps {
  onlyDifferences: boolean;
  onToggleDifferences: () => void;
  onClear: () => void;
  onBrowseMore: () => void;
}

export const CompareActions: FC<CompareActionsProps> = ({ onlyDifferences, onToggleDifferences, onClear,
  onBrowseMore }) => {
  const { t } = useI18n();
  return (
    <>
      <label className="flex items-center gap-2 text-caption font-medium text-fg-secondary cursor-pointer">
        <input type="checkbox" checked={onlyDifferences} onChange={onToggleDifferences}
          className="rounded-chip border-line-strong accent-focus cursor-pointer" />
        <span>{t("onlyDifferencesToggle")}</span>
      </label>
      <Button variant="ghost" size="sm" onClick={onClear}>{t("clearAllCompare")}</Button>
      <Button variant="secondary" size="sm" onClick={onBrowseMore}>{t("addProductsToCompare")}</Button>
    </>
  );
};
