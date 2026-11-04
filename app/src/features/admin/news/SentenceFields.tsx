import type { ChangeEvent, FC } from "react";
import { LANGUAGES } from "../../../domain/languages.ts";
import { CONTROL, Field } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import type { ArticleFields } from "./article.ts";

interface Props {
  n: number;
  sentence: ArticleFields["sentences"][number];
  optional: (required: boolean) => string | undefined;
  onText: (code: string) => (event: ChangeEvent<HTMLTextAreaElement>) => void;
  onCites: (event: ChangeEvent<HTMLInputElement>) => void;
}

export const SentenceFields: FC<Props> = ({ n, sentence, optional, onText, onCites }) => {
  const { t } = useI18n();
  return (
    <fieldset className="space-y-2 rounded-control border border-line p-3">
      {LANGUAGES.map((l) => (
        <Field key={l.code} label={t("adminNewsSentence", { n: n + 1, language: l.label })}
          hint={optional(l.default)}>
          <textarea className={CONTROL} rows={2} value={sentence.text[l.code] ?? ""} onChange={onText(l.code)}
            required={l.default} />
        </Field>
      ))}
      <Field label={t("adminNewsCitesField", { n: n + 1 })}>
        <input className={`${CONTROL} font-mono`} value={sentence.cites} onChange={onCites} required />
      </Field>
    </fieldset>
  );
};
