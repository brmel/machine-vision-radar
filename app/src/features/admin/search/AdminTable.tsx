import type { FC, ReactNode } from "react";
import type { MessageKey } from "../../../shell/i18n/messages.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { Table } from "../../../ui/index.ts";

type Column = readonly [MessageKey, string?];

export const AdminTable: FC<{ columns: readonly Column[]; caption?: string; children: ReactNode }> = ({ columns,
  caption, children }) => {
  const { t } = useI18n();
  return <Table caption={caption} className="text-caption"
    columns={columns.map(([key, head]) => ({ head: t(key), className: head }))}>{children}</Table>;
};
