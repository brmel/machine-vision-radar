import { useMemo } from "react";
import { MAX_COMPARED } from "../../domain/compare.ts";
import type { SpecValueLabels } from "../../ui/specs/specFormat.ts";
import type { DetailStateLabels } from "../../ui/feedback/DetailState.tsx";
import type { ReadStateLabels } from "../../ui/feedback/ReadState.tsx";
import { useI18n } from "./index.tsx";

export function useValueLabels(): SpecValueLabels {
  const { t, locale } = useI18n();
  return useMemo(() => ({ unknown: t("unknownValue"), yes: t("yesValue"), no: t("noValue"), locale }), [t, locale]);
}

export function usePagerLabels() {
  const { t } = useI18n();
  return {
    navLabel: t("paginationLabel"),
    previousLabel: t("paginationPrevious"),
    nextLabel: t("paginationNext"),
    pageLabel: (page: number, totalPages: number) => t("paginationPage", { page, totalPages }),
    summaryText: (start: number, end: number, total: number) => t("paginationSummary", { start, end, total }),
  };
}

export function useReadStateLabels(): ReadStateLabels {
  const { t } = useI18n();
  return { loading: t("loading"), errorTitle: t("errorTitle"), errorDescription: t("catalogLoadErrorDesc"),
    retry: t("errorRetry") };
}

export function useDetailStateLabels(missing: string): DetailStateLabels {
  return { ...useReadStateLabels(), missing };
}

export function useCompareControl(comparedIds: readonly string[], onToggle: (productId: string) => void) {
  const { t } = useI18n();
  return (id: string) => ({
    label: comparedIds.includes(id) ? t("inCompareAction") : t("compareAction"),
    pressed: comparedIds.includes(id),
    disabled: !comparedIds.includes(id) && comparedIds.length >= MAX_COMPARED,
    onToggle: () => onToggle(id),
  });
}
