import type { FC } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import type { FeedDeskRow } from "../../../../domain/views.ts";
import { Badge, Button, localized } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import type { MessageKey } from "../../../../shell/i18n/messages.ts";
import { DeskLink } from "./DeskLink.tsx";

const AUTHORSHIP: Readonly<Record<FeedDeskRow["authorship"], MessageKey>> = { human: "adminNewsHuman",
  template: "adminNewsTemplate", ai_draft: "adminNewsAiDraft" };

interface DraftListProps {
  drafts: readonly FeedDeskRow[];
  onMove: (row: FeedDeskRow, position: number) => () => void;
}

export const DraftList: FC<DraftListProps> = ({ drafts, onMove }) => {
  const { t, locale } = useI18n();
  return (
    <ol className="divide-y divide-line">
      {drafts.map((row, n) => (
        <li key={row.id} className="flex flex-wrap items-center gap-2 py-2">
          <span className="w-6 font-mono text-caption tabular-nums">{n + 1}</span>
          <DeskLink row={row} />
          <Badge>{t(AUTHORSHIP[row.authorship])}</Badge>
          <Button variant="ghost" size="sm" disabled={n === 0} onClick={onMove(row, n)}
            aria-label={t("adminNewsUp", { title: localized(row.title, locale) })}>
            <ArrowUp className="w-4 h-4" aria-hidden="true" />
          </Button>
          <Button variant="ghost" size="sm" disabled={n === drafts.length - 1} onClick={onMove(row, n + 2)}
            aria-label={t("adminNewsDown", { title: localized(row.title, locale) })}>
            <ArrowDown className="w-4 h-4" aria-hidden="true" />
          </Button>
        </li>
      ))}
    </ol>
  );
};
