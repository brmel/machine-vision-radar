import { type FC } from "react";
import { StatePanel } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";

interface NotFoundViewProps {
  path: string;
  onHome: () => void;
}

export const NotFoundView: FC<NotFoundViewProps> = ({ path, onHome }) => {
  const { t } = useI18n();
  return (
    <StatePanel
      tone="empty"
      level={1}
      title={t("notFoundTitle")}
      description={path ? t("notFoundDescription", { path }) : t("notFoundPage")}
      action={{ label: t("notFoundBackHome"), onClick: onHome }}
    />
  );
};
