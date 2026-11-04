import { useState, type ChangeEvent, type FC } from "react";
import type { ReportInbox } from "../../../domain/ports/review/ReportInbox.ts";
import { Button, CONTROL, Field, prevented } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { logger } from "../../../shell/logger.ts";

type Sent = "idle" | "sending" | "filed" | "counted" | "failed";
const SAID = { filed: "reportFiled", counted: "reportCounted", failed: "reportFailed" } as const;

export const ReportError: FC<{ inbox: ReportInbox; subject: string }> = ({ inbox, subject }) => {
  const { t } = useI18n();
  const { protection } = inbox;
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sent, setSent] = useState<Sent>("idle");
  const toggle = () => {
    if (!open) inbox.prepare().catch((err: unknown) =>
      logger.warn("product page: the report form's protection did not load", { product: subject }, err));
    setOpen(!open);
  };
  const onMessage = (event: ChangeEvent<HTMLTextAreaElement>) => setMessage(event.target.value);
  const onSource = (event: ChangeEvent<HTMLInputElement>) => setSourceUrl(event.target.value);
  const send = async () => {
    setSent("sending");
    try {
      setSent(await inbox.report({ subject, message: message.trim(),
        ...(sourceUrl.trim() ? { sourceUrl: sourceUrl.trim() } : {}) }));
      setMessage("");
      setSourceUrl("");
    } catch (err) {
      logger.warn("product page: an error report was not filed", { product: subject }, err);
      setSent("failed");
    }
  };
  const submit = prevented(send);
  return (
    <section className="pt-4 border-t border-line space-y-3" aria-label={t("reportErrorAction")}>
      <Button variant="ghost" size="sm" aria-expanded={open} onClick={toggle}>
        {t("reportErrorAction")}
      </Button>
      {open && (
        <form onSubmit={submit} className="space-y-3 max-w-2xl">
          <Field label={t("reportMessage")} hint={t("reportHint")}>
            <textarea className={CONTROL} rows={3} maxLength={2000} required value={message} onChange={onMessage} />
          </Field>
          <Field label={t("reportSource")}>
            <input type="url" className={CONTROL} maxLength={500} placeholder="https://" value={sourceUrl}
              onChange={onSource} />
          </Field>
          <Button type="submit" variant="primary"
            disabled={!message.trim() || sent === "sending"}>{t("reportSend")}</Button>
          {protection && (
            <p className="text-caption text-fg-secondary">
              {t("reportProtection", { name: protection.name, owner: protection.owner }).split(/[[\]]/)
                .map((part, i) => (i % 2 ? <a key={part} href={protection.links[(i - 1) / 2]} target="_blank"
                  rel="noopener noreferrer" className="underline hover:text-fg">{part}</a> : part))}
            </p>
          )}
        </form>
      )}
      {sent !== "idle" && sent !== "sending" && <p role="status"
        className={sent === "failed" ? "text-danger text-caption" : "text-caption"}>{t(SAID[sent])}</p>}
    </section>
  );
};
