import { type FC } from "react";
import type { SourceView } from "../../../domain/views.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { CELL, StatePanel, Table, formatDate, localized, sourceLinkText } from "../../../ui/index.ts";

interface SourcesListProps {
  sources: readonly SourceView[];
}

export const SourcesList: FC<SourcesListProps> = ({ sources }) => {
  const { t, locale } = useI18n();
  if (sources.length === 0) return <StatePanel tone="empty" title={t("noSourcesAvailable")} />;
  return (
    <div className="space-y-2">
      <p className="text-caption text-muted">{t("sourcesDescription")}</p>
      <Table columns={[{ head: t("sourceType") }, { head: t("sourceDate") }, { head: t("sourceUrl") }]}
        className="sources-table text-caption">
        {sources.map((src) => (
          <tr key={src.id} id={src.id} className="hover:bg-sunken/60">
            <td className={`${CELL} text-fg`}>{localized(src.type.label, locale)}</td>
            <td className={`${CELL} tabular-nums text-muted whitespace-nowrap`}>{formatDate(src.retrieved_at,
              locale)}</td>
            <td className={CELL}>
              {src.url ? (
                <a href={src.url} target="_blank" rel="noopener noreferrer"
                  className="wrap-anywhere text-fg-secondary hover:text-fg underline">{sourceLinkText(src)}</a>
              ) : (
                <span>{src.title ?? t("unknownValue")}</span>
              )}
            </td>
          </tr>
        ))}
      </Table>
    </div>
  );
};
