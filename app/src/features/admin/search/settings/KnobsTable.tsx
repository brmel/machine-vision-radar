import type { FC } from "react";
import type { SearchField, SearchSettings } from "../../../../domain/views.ts";
import type { MessageKey } from "../../../../shell/i18n/messages.ts";
import { CELL, ROW_HEAD, formatNumber } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { AdminTable } from "../AdminTable.tsx";

type Knob = Exclude<keyof SearchSettings, "fields" | "model" | "stopwords">;

const KNOBS: Readonly<Record<Knob, readonly [MessageKey, MessageKey]>> = {
  whole_word: ["adminKnobWholeWord", "adminKnobWholeWordWhat"],
  pair_boost: ["adminKnobPairBoost", "adminKnobPairBoostWhat"], pair_window: ["adminKnobPairWindow",
    "adminKnobPairWindowWhat"], exact_boost: ["adminKnobExactBoost", "adminKnobExactBoostWhat"],
  relative_cut: ["adminKnobRelativeCut", "adminKnobRelativeCutWhat"],
  semantic_threshold: ["adminKnobSemanticThreshold", "adminKnobSemanticThresholdWhat"],
  rrf_k: ["adminKnobRrfK", "adminKnobRrfKWhat"], evidence: ["adminKnobEvidence", "adminKnobEvidenceWhat"],
};

const FIELD: Readonly<Record<SearchField["field"], MessageKey>> = {
  name: "adminName", vendor: "adminSearchFieldVendor", category: "adminSearchFieldCategory",
  tags: "adminSearchFieldTags", summary: "adminSearchFieldSummary", specs: "adminSpecs",
};

const isKnob = (entry: [string, unknown]): entry is [Knob, number] => typeof entry[1] === "number";

export const KnobsTable: FC<{ settings: SearchSettings }> = ({ settings }) => {
  const { t, locale } = useI18n();
  const rows: readonly (readonly [MessageKey, string, MessageKey])[] = [
    ["adminKnobFields",
      settings.fields.map((f) => `${t(FIELD[f.field])} ${formatNumber(f.weight, locale)}`).join(" · "),
      "adminKnobFieldsWhat"],
    ...Object.entries(settings).filter(isKnob)
      .map(([key, value]) => [KNOBS[key][0], formatNumber(value, locale), KNOBS[key][1]] as const),
    ["adminKnobStopwords", formatNumber(settings.stopwords.length, locale), "adminKnobStopwordsWhat"],
  ];
  return (
    <>
      <AdminTable columns={[["adminSettingsKnob"], ["adminSettingsValue"], ["adminSettingsWhat"]]}>
        {rows.map(([label, value, what]) => (
          <tr key={label}>
            <th scope="row" className={ROW_HEAD}>{t(label)}</th>
            <td className={`${CELL} tabular-nums`}>{value}</td>
            <td className={CELL}>{t(what)}</td>
          </tr>
        ))}
      </AdminTable>
      <p className="text-caption text-muted max-w-3xl">{t("adminSettingsKnobsWhat")}</p>
    </>
  );
};
