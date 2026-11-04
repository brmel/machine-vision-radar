import { type FC } from "react";
import { Button } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";

interface CompareTrayProps {
  count: number;
  onCompare: () => void;
  onClear: () => void;
}

export const CompareTray: FC<CompareTrayProps> = ({ count, onCompare, onClear }) => {
  const { t } = useI18n();
  return (
    <div className={"dark fixed inset-x-4 bottom-4 sm:inset-x-auto sm:right-6 sm:bottom-6 z-40 "
      + "motion-safe:animate-rise flex items-center justify-between gap-3 p-3 bg-page text-fg rounded-card "
      + "shadow-overlay border border-line"}>
      <span className="text-caption font-mono tabular-nums">{t("compareTrayCount", { count })}</span>
      <div className="flex items-center gap-3">
        <Button variant="primary" size="sm" onClick={onCompare}>
          {t("compareAction")}
        </Button>
        <button type="button" onClick={onClear}
          className="text-fg-secondary hover:text-fg text-caption underline cursor-pointer">
          {t("searchClear")}
        </button>
      </div>
    </div>
  );
};
