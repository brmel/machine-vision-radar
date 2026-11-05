import type { FC } from "react";
import { LoadingSkeleton, StatePanel } from "../../ui/index.ts";
import { useI18n } from "../i18n/index.tsx";
import type { MessageKey } from "../i18n/messages.ts";

interface ReadStateProps {
  failed: boolean;
  skeleton: { count: number; type?: "card" | "row" };
  level?: 1 | 2;
  title?: MessageKey;
}

export const ReadState: FC<ReadStateProps> = ({ failed, skeleton, level = 1, title = "errorTitle" }) => {
  const { t } = useI18n();
  return failed
    ? <StatePanel tone="error" level={level} title={t(title)} description={t("catalogLoadErrorDesc")}
      retryLabel={t("errorRetry")} />
    : <LoadingSkeleton label={t("loading")} count={skeleton.count} type={skeleton.type} />;
};
