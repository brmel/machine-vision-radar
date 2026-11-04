import { useState, type ChangeEvent, type FC } from "react";
import { Button, CONTROL, Field } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useProblem } from "../useLoad.tsx";

export interface Action {
  label: string;
  run: (note: string) => Promise<unknown>;
  primary?: boolean;
}

export const Decision: FC<{ actions: readonly Action[]; noteLabel?: string }> = ({ actions, noteLabel }) => {
  const { t } = useI18n();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const { alert, say, refuse } = useProblem("a decision");
  const onNote = (event: ChangeEvent<HTMLTextAreaElement>) => setNote(event.target.value);
  const decide = (action: Action) => () => {
    setBusy(true);
    say([]);
    return action.run(note.trim()).then(() => setNote(""), refuse).finally(() => setBusy(false));
  };
  return (
    <div className="space-y-2 rounded-control border border-line p-3">
      <Field label={noteLabel ?? t("adminNote")}>
        <textarea className={CONTROL} rows={2} value={note} onChange={onNote} />
      </Field>
      <div className="flex flex-wrap gap-2">
        {actions.map((a) => (
          <Button key={a.label} variant={a.primary ? "primary" : "outline"} disabled={busy || !note.trim()}
            onClick={decide(a)}>{a.label}</Button>
        ))}
      </div>
      {alert}
    </div>
  );
};
