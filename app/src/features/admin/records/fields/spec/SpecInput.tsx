import { type ChangeEvent, type FC, type ReactNode } from "react";
import type { Json, JsonRecord } from "../../../../../domain/ports/review/Review.ts";
import type { AdminModel, SpecShape } from "../../../../../domain/views.ts";
import { CONTROL, Field, localized } from "../../../../../ui/index.ts";
import { useI18n } from "../../../../../shell/i18n/index.tsx";
import type { MessageKey } from "../../../../../shell/i18n/messages.ts";
import { terms, useAdmin } from "../../../model.ts";
import { isRecord } from "../../drafts.ts";
import { TermSelect } from "../TermSelect.tsx";

const record = (value: Json | null | undefined): JsonRecord => (isRecord(value) ? value : {});
const str = (value: Json | undefined): string =>
  (typeof value === "string" || typeof value === "number" ? String(value) : "");

interface Render {
  label: string;
  spec: SpecShape;
  value: JsonRecord;
  put: (value: Json | null) => void;
  model: AdminModel;
  locale: string;
  t: (key: MessageKey, params?: Readonly<Record<string, string | number>>) => string;
}

function quantity(r: Render): ReactNode {
  const q = record(r.value.quantity ?? r.value.range);
  const [from, to, unit] = [str(q.value ?? q.min), str(q.max), str(q.unit) || (r.spec.unit ?? "")];
  const units = Object.entries(r.model.units).filter(([, u]) => u.dimension === r.spec.dimension);
  const put = (low: string, high: string, measured: string) =>
    r.put(low === "" ? null : high === "" ? { quantity: { value: Number(low), unit: measured } }
      : { range: { min: Number(low), max: Number(high), unit: measured } });
  const input = (label: string, value: string, onChange: (v: string) => void) => (
    <Field label={label} className="flex-1">
      <input type="number" step="any" className={CONTROL} value={value}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)} />
    </Field>
  );
  return (
    <div className="flex gap-2 items-end">
      {input(r.label, from, (v) => put(v, to, unit))}
      {input(r.t("adminRangeTo"), to, (v) => put(from, v, unit))}
      <div className="w-24 shrink-0">
        <select aria-label={r.t("adminFieldPart", { field: r.label, part: r.t("adminUnit") })} className={CONTROL}
          value={unit} onChange={(e) => put(from, to, e.target.value)}>
          {units.map(([id, u]) => <option key={id} value={id}>{u.symbol}</option>)}
        </select>
      </div>
    </div>
  );
}

const RENDER: { readonly [D in SpecShape["datatype"]]: (r: Render) => ReactNode } = {
  quantity,
  term: (r) => <TermSelect label={r.label} terms={terms(r.model, r.spec.vocabulary)} value={str(r.value.term)}
    onChange={(v) => r.put(v ? { term: v } : null)} />,
  term_set: (r) => (
    <Field label={r.label}>
      <select multiple className={`${CONTROL} h-28`} value={Array.isArray(r.value.terms) ? r.value.terms.map(str) : []}
        onChange={(e) => r.put(e.target.selectedOptions.length
          ? { terms: [...e.target.selectedOptions].map((o) => o.value) } : null)}>
        {terms(r.model, r.spec.vocabulary)
          .map((o) => <option key={o.id} value={o.id}>{localized(o.label, r.locale)}</option>)}
      </select>
    </Field>
  ),
  boolean: (r) => (
    <Field label={r.label}>
      <select className={CONTROL} value={r.value.boolean === undefined ? "" : String(r.value.boolean)}
        onChange={(e) => r.put(e.target.value ? { boolean: e.target.value === "true" } : null)}>
        <option value="">—</option>
        <option value="true">{r.t("yesValue")}</option>
        <option value="false">{r.t("noValue")}</option>
      </select>
    </Field>
  ),
  string: (r) => (
    <Field label={r.label}>
      <input className={CONTROL} value={str(r.value.string)}
        onChange={(e) => r.put(e.target.value ? { string: e.target.value } : null)} />
    </Field>
  ),
};

export const SpecInput: FC<{ specKey: string; label: string; value: Json | null | undefined;
  onChange: (value: Json | null) => void }> = ({ specKey, label, value, onChange }) => {
  const { model } = useAdmin();
  const { t, locale } = useI18n();
  const spec = model.specs[specKey];
  if (!spec) return null;
  const none = model.none_datatypes.includes(spec.datatype) && (
    <TermSelect label={t("adminFieldPart", { field: label, part: t("adminNoneBecause") })}
      terms={terms(model, model.none_vocabulary)}
      value={str(record(value).none)} onChange={(v) => onChange(v ? { none: v } : null)} />
  );
  return <>{RENDER[spec.datatype]({ label, spec, value: record(value), put: onChange, model, locale, t })}{none}</>;
};
