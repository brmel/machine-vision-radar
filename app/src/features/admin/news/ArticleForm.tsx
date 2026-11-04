import { useState, type ChangeEvent, type FC } from "react";
import type { FeedDeskRow } from "../../../domain/views.ts";
import { LANGUAGES } from "../../../domain/languages.ts";
import { Button, CONTROL, Field, TYPE, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useAdmin } from "../model.ts";
import { useSubmit } from "../useLoad.tsx";
import { NEW_ARTICLE, draftOf, fieldsOf, type ArticleFields } from "./article.ts";
import { SentenceFields } from "./SentenceFields.tsx";

export const ArticleForm: FC<{ row?: FeedDeskRow; onSaved: () => void }> = ({ row, onSaved }) => {
  const { news } = useAdmin();
  const { t, locale } = useI18n();
  const [fields, setFields] = useState<ArticleFields>(row ? fieldsOf(row) : NEW_ARTICLE);
  const [note, setNote] = useState("");
  const text = (part: "title" | "summary", code: string) => (event: ChangeEvent<HTMLInputElement>) =>
    setFields((f) => ({ ...f, [part]: { ...f[part], [code]: event.target.value } }));
  const sentence = (n: number, change: (s: ArticleFields["sentences"][number]) => ArticleFields["sentences"][number]) =>
    setFields((f) => ({ ...f, sentences: f.sentences.map((s, i) => (i === n ? change(s) : s)) }));
  const onSentence = (n: number) => (code: string) => (event: ChangeEvent<HTMLTextAreaElement>) =>
    sentence(n, (s) => ({ ...s, text: { ...s.text, [code]: event.target.value } }));
  const onCites = (n: number) => (event: ChangeEvent<HTMLInputElement>) =>
    sentence(n, (s) => ({ ...s, cites: event.target.value }));
  const onEvent = (part: "eventDate" | "eventSource") => (event: ChangeEvent<HTMLInputElement>) =>
    setFields((f) => ({ ...f, [part]: event.target.value }));
  const onNote = (event: ChangeEvent<HTMLTextAreaElement>) => setNote(event.target.value);
  const addSentence = () => setFields((f) => ({ ...f, sentences: [...f.sentences, { text: {}, cites: "" }] }));
  const save = () =>
    (row ? news.reviseArticle(row.id, draftOf(fields), note.trim()) : news.writeArticle(draftOf(fields)));
  const { busy, submit, alert } = useSubmit("an article", save, onSaved);
  const optional = (required: boolean) => (required ? undefined : t("adminNewsOptional"));

  return (
    <form onSubmit={submit} className="space-y-5 max-w-3xl" noValidate>
      <fieldset className="space-y-3">
        <legend className={`${TYPE.section} mb-2`}>{row ? t("adminNewsEditing", { title: localized(row.title, locale) })
          : t("adminNewsWrite")}</legend>
        {LANGUAGES.map((l) => (
          <div key={l.code} className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label={t("adminNewsTitleField", { language: l.label })} hint={optional(l.default)}>
              <input className={CONTROL} value={fields.title[l.code] ?? ""} onChange={text("title", l.code)}
                required={l.default} />
            </Field>
            <Field label={t("adminNewsSummaryField", { language: l.label })} hint={optional(l.default)}>
              <input className={CONTROL} value={fields.summary[l.code] ?? ""} onChange={text("summary", l.code)}
                required={l.default} />
            </Field>
          </div>
        ))}
      </fieldset>
      {fields.sentences.map((s, n) => (
        <SentenceFields key={n} n={n} sentence={s} optional={optional} onText={onSentence(n)} onCites={onCites(n)} />
      ))}
      <Button type="button" variant="outline" onClick={addSentence}>{t("adminNewsAddSentence")}</Button>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label={t("adminNewsEventDate")} hint={t("adminNewsOptional")}>
          <input className={`${CONTROL} font-mono`} value={fields.eventDate} onChange={onEvent("eventDate")} />
        </Field>
        <Field label={t("adminNewsEventSource")} hint={t("adminNewsOptional")}>
          <input className={`${CONTROL} font-mono`} value={fields.eventSource} onChange={onEvent("eventSource")} />
        </Field>
      </div>
      {row && <Field label={t("adminNewsRevisionNote")}><textarea className={CONTROL} rows={2} value={note}
        onChange={onNote} /></Field>}
      {alert}
      <Button type="submit" variant="primary" disabled={busy || Boolean(row && !note.trim())}>{row
        ? t("adminNewsSaveVersion") : t("adminNewsSave")}</Button>
    </form>
  );
};
