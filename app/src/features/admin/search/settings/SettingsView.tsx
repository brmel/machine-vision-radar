import type { FC } from "react";
import type { AiCapRow } from "../../../../domain/views.ts";
import { PageHeader, Section, formatNumber } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { useAdmin } from "../../model.ts";
import { useLoad } from "../../useLoad.tsx";
import { UsesTable } from "./UsesTable.tsx";
import { ModelsTable } from "./ModelsTable.tsx";
import { UseForm } from "./UseForm.tsx";
import { KnobsTable } from "./KnobsTable.tsx";

export const SettingsView: FC<{ search: string }> = ({ search }) => {
  const { search: admin } = useAdmin();
  const { t, locale } = useI18n();
  const caps = useLoad(() => admin.caps(), "search-caps");
  const index = useLoad(() => admin.settings(), "search-settings", 2, 2);
  if (!caps.value) return caps.pending;
  const asked = new URLSearchParams(search).get("use");
  const use: AiCapRow["use"] = caps.value.uses.find((r) => r.use === asked)?.use ?? "ask";
  return (
    <div className="space-y-8">
      <PageHeader title={t("adminSettingsTitle")} />
      <p className="text-body max-w-3xl">{t("adminSettingsIntro")}</p>
      <Section id="settings-ai" title={t("adminSettingsAi")}>
        <UsesTable caps={caps.value} />
        <ModelsTable caps={caps.value} />
        <UseForm key={use} caps={caps.value} use={use} search={search} onSaved={caps.reload} />
      </Section>
      <Section id="settings-search" title={t("adminSettingsSearch")}>
        {index.value ? (
          <>
            <p className="text-body break-words">
              {index.value.current
                ? t("adminSettingsEmbedder", { model: index.value.current.model_id,
                  dimension: formatNumber(index.value.current.dimension, locale) })
                : t("adminSearchNoIndex")}
            </p>
            <p className="text-caption text-muted max-w-3xl">{t("adminSettingsEmbedderWhat")} <code
              className="font-mono">radar index rebuild</code></p>
            <KnobsTable settings={index.value.search} />
          </>
        ) : index.pending}
      </Section>
    </div>
  );
};
