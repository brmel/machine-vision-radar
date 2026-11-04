import { useState, type ChangeEvent, type FC } from "react";
import type { AskAnswer } from "../../../../domain/views.ts";
import type { MessageKey } from "../../../../shell/i18n/messages.ts";
import { Button, CONTROL, Field, prevented } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { useAdmin } from "../../model.ts";
import { AdminLink } from "../../useLoad.tsx";

const REFUSED: Readonly<Record<NonNullable<AskAnswer["reason"]>, MessageKey>> = {
  off_topic: "adminRefusedOffTopic", not_enough_evidence: "adminRefusedEvidence", limit: "askLimit",
  unavailable: "askUnavailable",
};

export const AskConsole: FC<{ onFail: (err: unknown) => void }> = ({ onFail }) => {
  const { search } = useAdmin();
  const { t, locale, locales } = useI18n();
  const [question, setQuestion] = useState("");
  const [site, setSite] = useState(locale);
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const onQuestion = (event: ChangeEvent<HTMLInputElement>) => setQuestion(event.target.value);
  const onSite = (event: ChangeEvent<HTMLSelectElement>) => setSite(event.target.value);
  const ask = prevented(() => {
    setAnswer(null);
    search.ask(question, site).then(setAnswer, onFail);
  });
  return (
    <>
      <form onSubmit={ask} className="space-y-3">
        <Field label={t("adminConsoleQuestion")}><input className={CONTROL} value={question} onChange={onQuestion}
          required /></Field>
        <Field label={t("adminConsoleSite")} className="max-w-xs">
          <select className={CONTROL} value={site} onChange={onSite}>{locales.map((l) =>
            <option key={l.code} value={l.code}>{l.name}</option>)}</select>
        </Field>
        <Button type="submit">{t("askAction")}</Button>
      </form>
      {answer && (
        <div aria-label={t("adminConsoleAnswer")} role="region" className="space-y-2 text-body">
          {answer.refused && <p>{t(REFUSED[answer.reason ?? "not_enough_evidence"])}</p>}
          {!answer.refused && !answer.needs && <p>{answer.answer}</p>}
          {answer.needs?.map((n) => <p key={n.need}><strong>{n.need}: </strong>{n.answer || t("askNeedUnmet")}</p>)}
          {answer.citations.length > 0 && (
            <ul aria-label={t("askCited")} className="text-caption">
              {answer.citations.map((c) => (
                <li key={`${c.product}-${c.source ?? ""}`}>
                  <AdminLink to={`/records/${c.product}`}
                    className="font-mono underline">{c.product}</AdminLink>{c.source && ` · ${c.source}`}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  );
};
