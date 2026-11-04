import { type FC } from "react";
import type { Json, JsonRecord } from "../../../../../domain/ports/review/Review.ts";
import type { SectionKeys } from "../../../../../domain/views.ts";
import { localized } from "../../../../../ui/index.ts";
import { useI18n } from "../../../../../shell/i18n/index.tsx";
import { claimMethods, useAdmin } from "../../../model.ts";
import { TermSelect } from "../TermSelect.tsx";
import { SpecInput } from "./SpecInput.tsx";

interface Props {
  profile: SectionKeys;
  held: Readonly<Record<string, JsonRecord>>;
  set: Readonly<Record<string, Json | null>>;
  onChange: (key: string, value: Json | null) => void;
  method: string;
  onMethod: (method: string) => void;
}

export const SpecFields: FC<Props> = ({ profile, held, set, onChange, method, onMethod }) => {
  const { model } = useAdmin();
  const { t, locale } = useI18n();
  const row = (key: string) => (
    <div key={key}>
      <SpecInput specKey={key} label={localized(model.specs[key]?.label ?? {}, locale)}
        value={key in set ? set[key] : held[key]?.value} onChange={(v) => onChange(key, v)} />
    </div>
  );
  return (
    <fieldset className="space-y-3">
      <legend className="text-section font-semibold">{t("adminSpecs")}</legend>
      <TermSelect label={t("adminMethod")} terms={claimMethods(model)} value={method} onChange={onMethod}
        empty={false} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{profile.core.map(row)}</div>
      {profile.detail.length > 0 && (
        <details className="space-y-3">
          <summary className="cursor-pointer text-body font-medium">{t("adminMoreSpecs")}</summary>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">{profile.detail.map(row)}</div>
        </details>
      )}
    </fieldset>
  );
};
