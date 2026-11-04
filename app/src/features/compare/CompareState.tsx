import type { FC } from "react";
import { PageHeader, ReadState, StatePanel } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { useReadStateLabels } from "../../shell/i18n/labels.ts";

export const CompareState: FC<{ isLoading: boolean; error: boolean; onBrowseMore: () => void }> = ({ isLoading, error,
  onBrowseMore }) => {
  const { t } = useI18n();
  const states = useReadStateLabels();
  return (
    <div className="space-y-3">
      <PageHeader title={t("compareTitle")} lead={t("compareSubtitle")} />
      {isLoading || error ? (
        <ReadState failed={!isLoading && error} labels={states} skeleton={{ count: 3, type: "row" }} level={2} />
      ) : (
        <StatePanel tone="empty" title={t("compareEmptyTitle")}
          action={{ label: t("addProductsToCompare"), onClick: onBrowseMore }} />
      )}
    </div>
  );
};
