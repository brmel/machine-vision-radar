import { type ChangeEvent, type FC } from "react";
import type { JsonRecord } from "../../../../domain/ports/review/Review.ts";
import { CONTROL, Field, TYPE } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { entity, terms, useAdmin } from "../../model.ts";
import type { SourceChoice } from "../drafts.ts";
import { TermSelect } from "./TermSelect.tsx";

const NEW: SourceChoice = { type: "", url: "", title: "" };

export const SourceFields: FC<{ sources: readonly JsonRecord[]; source: SourceChoice;
  onChange: (source: SourceChoice) => void }> = ({ sources, source, onChange }) => {
  const { model } = useAdmin();
  const { t } = useI18n();
  const pick = (event: ChangeEvent<HTMLSelectElement>) =>
    onChange(event.target.value ? { existing: event.target.value } : NEW);
  const part = (key: "type" | "url" | "title") => (value: string) =>
    onChange("existing" in source ? source : { ...source, [key]: value });
  const typed = (key: "url" | "title") => (event: ChangeEvent<HTMLInputElement>) => part(key)(event.target.value);
  const types = terms(model, entity(model, "Source").fields.find((f) => f.name === "type")?.vocabulary);
  return (
    <fieldset className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <legend className={`${TYPE.section} mb-2`}>{t("adminSource")}</legend>
      <Field label={`${t("adminSourceCited")} *`}>
        <select className={CONTROL} value={"existing" in source ? source.existing : ""} onChange={pick}>
          {sources.map((s) =>
            <option key={String(s.id)} value={String(s.id)}>{String(s.title ?? s.url ?? s.id)}</option>)}
          <option value="">{t("adminSourceNew")}</option>
        </select>
      </Field>
      {!("existing" in source) && (
        <>
          <TermSelect label={`${t("adminSourceType")} *`} terms={types} value={source.type} onChange={part("type")} />
          <Field label={t("adminSourceUrl")}><input type="url" className={CONTROL} value={source.url}
            onChange={typed("url")} /></Field>
          <Field label={t("adminSourceTitle")}><input className={CONTROL} value={source.title}
            onChange={typed("title")} /></Field>
        </>
      )}
    </fieldset>
  );
};
