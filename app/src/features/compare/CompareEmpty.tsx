import type { FC } from "react";
import { StatePanel } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { ReadState } from "../../shell/layout/ReadState.tsx";

interface CompareEmptyProps {
  loading: boolean;
  failed: boolean;
  missing: boolean;
  onBrowseMore: () => void;
}

export const CompareEmpty: FC<CompareEmptyProps> = ({ loading, failed, missing, onBrowseMore }) => {
  const { t } = useI18n();
  if (loading || failed) return <ReadState failed={failed} skeleton={{ count: 3, type: "row" }} level={2} />;
  return (
    <StatePanel tone="empty" title={missing ? t("productNotFound") : t("compareEmptyTitle")}
      action={{ label: t("addProductsToCompare"), onClick: onBrowseMore }} />
  );
};
