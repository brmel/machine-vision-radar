import type { ChangeEvent, FC } from "react";
import type { CapChange } from "../../../../domain/ports/review/SearchAdmin.ts";
import { CONTROL, Field } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";

const LIMITS =
  [["month_cad", "adminCapsMonth"], ["day_calls", "adminCapsDay"], ["client_calls", "adminCapsClient"]] as const;

export const CapLimits: FC<{ change: CapChange;
  onLimit: (key: keyof CapChange) => (event: ChangeEvent<HTMLInputElement>) => void }> = ({ change, onLimit }) => {
  const { t } = useI18n();
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {LIMITS.map(([key, label]) => (
        <Field key={key} label={t(label)}>
          <input className={CONTROL} type="number" min={0} step={key === "month_cad" ? "any" : 1}
            value={change[key] ?? ""} onChange={onLimit(key)} />
        </Field>
      ))}
    </div>
  );
};
