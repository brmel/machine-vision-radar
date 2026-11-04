import { type FC } from "react";
import { useI18n } from "../../shell/i18n/index.tsx";
import { CitedProducts } from "./CitedProducts.tsx";
import { SolvedNeeds } from "./SolvedNeeds.tsx";
import type { AskState } from "./useAsk.ts";

const REFUSALS = { off_topic: "askRefused", not_enough_evidence: "askRefused", limit: "askLimit",
  unavailable: "askUnavailable" } as const;

export const AnswerArea: FC<{ state: AskState; onSelectProduct: (slug: string) => void }> = ({ state,
  onSelectProduct }) => {
  const { t } = useI18n();
  if (state.phase !== "done") return (
    <div aria-live="polite" className="text-body">
      {state.phase === "loading" && <p className="text-muted">{t("askLoading")}</p>}
      {state.phase === "unreachable" && <p role="note" className="text-warning">{t("askUnavailable")}</p>}
    </div>
  );
  const { answer, cited } = state;
  if (answer.refused) return (
    <div aria-live="polite" className="text-body">
      <p className="ask-refusal font-medium text-fg">{t(REFUSALS[answer.reason ?? "not_enough_evidence"])}</p>
    </div>
  );
  return (
    <div aria-live="polite" className="text-body space-y-2">
      {answer.needs ? <SolvedNeeds needs={answer.needs} cited={cited} onSelectProduct={onSelectProduct} /> : (
        <>
          <p className="ask-answer text-fg leading-relaxed">{answer.answer}</p>
          <div className="space-y-1.5">
            <h3 className="text-caption font-heading text-fg-secondary">{t("askCited")}</h3>
            <CitedProducts citations={answer.citations} cited={cited} onSelectProduct={onSelectProduct} />
          </div>
        </>
      )}
      <p className="text-caption text-muted">{t("askNote")}</p>
    </div>
  );
};
