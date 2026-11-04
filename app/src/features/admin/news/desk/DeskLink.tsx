import type { FC } from "react";
import type { FeedDeskRow } from "../../../../domain/views.ts";
import { localized } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { AdminLink } from "../../useLoad.tsx";

export const DeskLink: FC<{ row: FeedDeskRow }> = ({ row }) => {
  const { locale } = useI18n();
  return <AdminLink to={`/news/${encodeURIComponent(row.id)}`}
    className="flex-1 min-w-0 underline break-words">{localized(row.title, locale)}</AdminLink>;
};
