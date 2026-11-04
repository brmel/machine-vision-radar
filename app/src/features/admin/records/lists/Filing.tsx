import { useState, type FC } from "react";
import type { JsonRecord } from "../../../../domain/ports/review/Review.ts";
import { prevented } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { claimMethods, useAdmin } from "../../model.ts";
import { useProblem } from "../../useLoad.tsx";
import { chosenSource, type SourceChoice } from "../drafts.ts";
import { FileFooter } from "../fields/FileFooter.tsx";
import { SourceFields } from "../fields/SourceFields.tsx";
import { TermSelect } from "../fields/TermSelect.tsx";

interface FilingProps {
  sources: readonly JsonRecord[];
  onFile: (method: string, source: SourceChoice, reason: string) => Promise<readonly string[]>;
}

export const Filing: FC<FilingProps> = ({ sources, onFile }) => {
  const { model } = useAdmin();
  const { t } = useI18n();
  const methods = claimMethods(model);
  const [method, setMethod] = useState(methods[0]?.id ?? "");
  const [picked, setSource] = useState<SourceChoice | null>(null);
  const [reason, setReason] = useState("");
  const { alert, say, refuse } = useProblem("a grid proposal");
  const source = chosenSource(picked, {});
  const file = () => onFile(method, source, reason.trim()).then(say, refuse);
  return (
    <form onSubmit={prevented(file)} className="space-y-5" noValidate>
      <TermSelect label={t("adminMethod")} terms={methods} value={method} onChange={setMethod} empty={false} />
      <SourceFields sources={sources} source={source} onChange={setSource} />
      <FileFooter reason={reason} onReason={setReason} alert={alert} />
    </form>
  );
};
