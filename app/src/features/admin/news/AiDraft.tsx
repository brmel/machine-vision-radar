import { useState, type ChangeEvent, type FC } from "react";
import { Button, CONTROL, Field } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useAdmin } from "../model.ts";
import { useSubmit } from "../useLoad.tsx";

export const AiDraft: FC<{ onDrafted: () => void }> = ({ onDrafted }) => {
  const { news } = useAdmin();
  const { t } = useI18n();
  const [item, setItem] = useState("");
  const onItem = (event: ChangeEvent<HTMLInputElement>) => setItem(event.target.value);
  const { busy, submit: draft, alert } = useSubmit("an AI draft", () => news.draftArticle(item.trim()), onDrafted);
  return (
    <form onSubmit={draft} className="flex flex-wrap items-end gap-2">
      <Field label={t("adminNewsDraftItem")}><input className={`${CONTROL} font-mono`} value={item} onChange={onItem}
        required /></Field>
      <Button type="submit" variant="outline" disabled={busy || !item.trim()}>{t("adminNewsDraftWithAi")}</Button>
      {alert}
    </form>
  );
};
