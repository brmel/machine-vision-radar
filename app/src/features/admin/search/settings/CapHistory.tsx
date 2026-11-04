import type { FC } from "react";
import type { AiCapRow, HistoryPage } from "../../../../domain/views.ts";
import { Button, RowList, Section, formatDate } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { USE } from "../../model.ts";
import type { Paged } from "../../useLoad.tsx";

interface CapHistoryProps {
  use: AiCapRow["use"];
  history: Paged<HistoryPage>;
  onRevert: (proposal: string) => () => void;
}

export const CapHistory: FC<CapHistoryProps> = ({ use, history, onRevert }) => {
  const { t, locale } = useI18n();
  return (
    <Section sub title={t("adminCapsHistory", { use: t(USE[use]) })}>
      {history.value ? (
        <RowList ordered>
          {history.value.versions.length === 0 && <li className="p-3 text-caption">{t("adminSettingsNever")}</li>}
          {history.value.versions.map((v) => (
            <li key={v.version} className="p-3 text-caption flex flex-wrap items-center gap-2">
              <span>v{v.version} · {formatDate(v.recorded_at, locale)} · {v.actor}: {v.reason}</span>
              {v.proposal
                && <Button size="sm" variant="outline" onClick={onRevert(v.proposal)}>{t("adminCapsRevert")}</Button>}
            </li>
          ))}
        </RowList>
      ) : history.pending}
      {history.pager}
    </Section>
  );
};
