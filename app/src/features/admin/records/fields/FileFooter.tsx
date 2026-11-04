import type { ChangeEvent, FC, ReactNode } from "react";
import { Button, CONTROL, Field } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";

export const FileFooter: FC<{ reason: string; onReason: (reason: string) => void; alert: ReactNode }> = ({ reason,
  onReason, alert }) => {
  const { t } = useI18n();
  return (
    <>
      <Field label={`${t("adminReason")} *`}><textarea className={CONTROL} rows={2} value={reason}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onReason(e.target.value)} /></Field>
      {alert}
      <Button type="submit" variant="primary">{t("adminFile")}</Button>
    </>
  );
};
