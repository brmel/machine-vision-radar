import type { FC } from "react";
import type { IndexStatus } from "../../../domain/views.ts";
import { RowList, Section, formatDate, formatNumber } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

export const IndexDetails: FC<{ status: IndexStatus }> = ({ status }) => {
  const { t, locale } = useI18n();
  return (
    <Section title={t("adminSearchRuns")}>
      <RowList ordered>
        {status.runs.map((r) => (
          <li key={`${r.at}-${r.correlation_id}`} className="p-3 text-caption space-y-0.5">
            <p><span className="font-medium">{t(r.action === "update" ? "adminSearchUpdate"
              : "adminSearchRebuild")}</span> · {formatDate(r.at, locale)} · {r.actor}</p>
            <p className={r.error ? "text-danger break-words" : "text-muted"}>
              {r.error ? t("adminSearchRunFailed", { error: r.error })
                : t("adminSearchRunDone", { products: formatNumber(r.products, locale),
                  embedded: formatNumber(r.embedded, locale), removed: formatNumber(r.removed, locale) })}
            </p>
          </li>
        ))}
      </RowList>
    </Section>
  );
};
