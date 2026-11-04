import { type FC, useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { Button, Chip, SearchInput, TYPE, prevented } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import type { AskApi } from "../../domain/ports/AskApi.ts";
import type { CatalogRepository } from "../../domain/ports/CatalogRepository.ts";
import { AnswerArea } from "./AnswerArea.tsx";
import { useAsk } from "./useAsk.ts";

interface AskViewProps {
  repository: CatalogRepository;
  answers: AskApi;
  question: string;
  onAsk: (question: string) => void;
  onSelectProduct: (slug: string) => void;
}

const EXAMPLES = ["askExample1", "askExample2", "askExample3"] as const;

export const AskView: FC<AskViewProps> = ({ repository, answers, question, onAsk, onSelectProduct }) => {
  const { t, locale } = useI18n();
  const state = useAsk(answers, repository, question, locale);
  const [draft, setDraft] = useState(question);
  useEffect(() => setDraft(question), [question]);
  const submit = prevented(() => {
    if (draft.trim()) onAsk(draft.trim());
  });
  return (
    <div className={`mx-auto w-full max-w-2xl space-y-5 ${question ? "" : "pt-[10vh] sm:pt-[18vh]"}`}>
      <header className="flex flex-col items-center gap-3 text-center">
        <span className="flex size-12 items-center justify-center rounded-full bg-accent text-on-accent shadow-field">
          <Sparkles className="size-6" aria-hidden="true" />
        </span>
        <h1 className={TYPE.title}>{t("askTitle")}</h1>
        <p className="text-body text-fg-secondary">{t("askSubtitle")}</p>
      </header>
      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <SearchInput value={draft} onChange={(e) => setDraft(e.target.value)} onClear={() => setDraft("")}
          maxLength={300} aria-label={t("askTitle")} placeholder={t("askPlaceholder")}
          clearLabel={t("ariaClearInput")} />
        <Button type="submit" variant="primary" size="lg"
          disabled={!draft.trim() || state.phase === "loading"}>{t("askAction")}</Button>
      </form>
      {!question && (
        <ul aria-label={t("askExamplesLabel")} className="flex flex-wrap justify-center gap-2">
          {EXAMPLES.map((key) =>
            <li key={key}><Chip active={false} label={t(key)} onClick={() => onAsk(t(key))} /></li>)}
        </ul>
      )}
      <AnswerArea state={state} onSelectProduct={onSelectProduct} />
    </div>
  );
};
