import { type ChangeEvent, type FC } from "react";
import type { TermRef } from "../../../../domain/views.ts";
import { CONTROL, Field, localized } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";

export const TermSelect: FC<{ label: string; terms: readonly TermRef[]; value: string;
  onChange: (value: string) => void; empty?: boolean }> = ({ label, terms, value, onChange, empty = true }) => {
  const { locale } = useI18n();
  const pick = (event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value);
  return (
    <Field label={label}>
      <select className={CONTROL} value={value} onChange={pick}>
        {empty && <option value="">—</option>}
        {terms.map((o) => <option key={o.id} value={o.id}>{localized(o.label, locale)}</option>)}
      </select>
    </Field>
  );
};
