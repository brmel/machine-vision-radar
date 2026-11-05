import { type ChangeEvent, type FC, type ReactNode } from "react";
import type { Json } from "../../../../domain/ports/review/Review.ts";
import type { FieldShape, TermRef } from "../../../../domain/views.ts";
import type { Language } from "../../../../domain/languages.ts";
import { CONTROL, Field, localized } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { logger } from "../../../../shell/logger.ts";
import type { MessageKey } from "../../../../shell/i18n/messages.ts";
import { terms, useAdmin } from "../../model.ts";
import { isRecord, partialDate, text } from "../drafts.ts";
import { TermSelect } from "./TermSelect.tsx";

interface Props {
  field: FieldShape;
  value: Json | undefined;
  onChange: (name: string, value: Json | undefined) => void;
  disabled?: boolean;
}

const texts = (value: Json | undefined): Readonly<Record<string, string>> =>
  isRecord(value) ? Object.fromEntries(Object.entries(value).map(([k, v]) => [k, text(v)])) : {};

function typedJson(typed: string): Json | undefined {
  if (!typed.trim()) return undefined;
  try {
    return JSON.parse(typed);
  } catch (err) {
    logger.warn("admin: a JSON field does not parse; the validator says why", { page: "admin" }, err);
    return typed;
  }
}

interface Render {
  label: string;
  value: Json | undefined;
  set: (next: Json | undefined) => void;
  options: readonly TermRef[];
  values: readonly string[];
  locale: string;
  locales: readonly Language[];
  t: (key: MessageKey) => string;
  disabled?: boolean;
}

const RENDER: Readonly<Record<FieldShape["input"], (r: Render) => ReactNode>> = {
  term: (r) =>
    <TermSelect label={r.label} terms={r.options} value={text(r.value)} onChange={(v) => r.set(v || undefined)} />,
  terms: (r) => (
    <Field label={r.label} hint={r.t("adminManyHint")}>
      <select multiple className={`${CONTROL} h-32`} value={Array.isArray(r.value) ? r.value.map(text) : []}
        disabled={r.disabled}
        onChange={(e: ChangeEvent<HTMLSelectElement>) => r.set([...e.target.selectedOptions].map((o) => o.value))}>
        {r.options.map((o) => <option key={o.id} value={o.id}>{localized(o.label, r.locale)}</option>)}
      </select>
    </Field>
  ),
  localized: (r) => {
    const change = (code: string) => (e: ChangeEvent<HTMLTextAreaElement>) => {
      const kept = Object.entries({ ...texts(r.value), [code]: e.target.value }).filter(([, v]) => v.trim());
      r.set(kept.length ? Object.fromEntries(kept) : undefined);
    };
    return (
      <fieldset className="space-y-2">
        <legend className="text-caption font-medium text-fg-secondary">{r.label}</legend>
        {r.locales.map((l) => (
          <Field key={l.code} label={l.name}>
            <textarea className={CONTROL} rows={2} lang={l.code} value={texts(r.value)[l.code] ?? ""}
              onChange={change(l.code)} disabled={r.disabled} />
          </Field>
        ))}
      </fieldset>
    );
  },
  date: (r) => (
    <Field label={r.label} hint={r.t("adminDateHint")}>
      <input className={CONTROL} defaultValue={text(texts(r.value).value)}
        onBlur={(e) => r.set(partialDate(e.target.value) ?? undefined)} disabled={r.disabled} />
    </Field>
  ),
  flag: (r) => (
    <label className="flex items-center gap-2 text-body">
      <input type="checkbox" className="h-5 w-5" checked={r.value === true} onChange={(e) => r.set(e.target.checked)}
        disabled={r.disabled} />
      {r.label}
    </label>
  ),
  number: (r) => (
    <Field label={r.label}>
      <input type="number" className={CONTROL} value={text(r.value)}
        onChange={(e) => r.set(e.target.value === "" ? undefined : Number(e.target.value))} disabled={r.disabled} />
    </Field>
  ),
  text: (r) => <Field label={r.label}><input className={CONTROL} value={text(r.value)}
    onChange={(e) => r.set(e.target.value || undefined)} disabled={r.disabled} /></Field>,
  choice: (r) => (
    <Field label={r.label}>
      <select className={CONTROL} value={text(r.value)} onChange={(e) => r.set(e.target.value || undefined)}
        disabled={r.disabled}>
        <option value="">—</option>
        {r.values.map((v) => <option key={v} value={v}>{v}</option>)}
      </select>
    </Field>
  ),
  json: (r) => (
    <Field label={r.label} hint={r.t("adminJsonHint")}>
      <textarea className={`${CONTROL} font-mono`} rows={3}
        defaultValue={r.value === undefined ? "" : JSON.stringify(r.value)}
        onBlur={(e) => r.set(typedJson(e.target.value))} disabled={r.disabled} />
    </Field>
  ),
};

export const FieldInput: FC<Props> = ({ field, value, onChange, disabled }) => {
  const { model } = useAdmin();
  const { t, locale, locales } = useI18n();
  const options = terms(model, field.vocabulary);
  const set = (next: Json | undefined) => onChange(field.name, next);
  const label = `${localized(field.label, locale)}${field.optional ? "" : " *"}`;
  return <>{RENDER[field.input]({ label, value, set, options, values: field.values, locale, locales, t, disabled })}</>;
};
