import type { ChangeEvent, FC } from "react";
import type { QueueFilter } from "../../../../domain/ports/review/Review.ts";
import { CONTROL, Field } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { ACTOR, STATUS, kindLabel, useAdmin } from "../../model.ts";

type QueueParam = "status" | "files_on" | "actor" | "author";

interface QueueFiltersProps {
  params: URLSearchParams;
  filter: QueueFilter;
  onParam: (key: QueueParam) => (event: ChangeEvent<HTMLSelectElement | HTMLInputElement>) => void;
}

export const QueueFilters: FC<QueueFiltersProps> = ({ params, filter, onParam }) => {
  const { model } = useAdmin();
  const { t, locale } = useI18n();
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Field label={t("adminFilterStatus")}>
        <select className={CONTROL} value={params.get("status") ?? "suggested"} onChange={onParam("status")}>
          {Object.entries(STATUS).map(([s, label]) => <option key={s} value={s}>{t(label)}</option>)}
          <option value="all">{t("adminFilterAll")}</option>
        </select>
      </Field>
      <Field label={t("adminFilterKind")}>
        <select className={CONTROL} value={filter.filesOn ?? ""} onChange={onParam("files_on")}>
          <option value="">{t("adminFilterAll")}</option>
          {model.kinds.map((k) =>
            <option key={k.id} value={k.files_on}>{kindLabel(model, k.files_on, locale)}</option>)}
        </select>
      </Field>
      <Field label={t("adminFilterActor")}>
        <select className={CONTROL} value={params.get("actor") ?? ""} onChange={onParam("actor")}>
          <option value="">{t("adminFilterAll")}</option>
          {Object.entries(ACTOR).map(([a, label]) => <option key={a} value={a}>{t(label)}</option>)}
        </select>
      </Field>
      <Field label={t("adminFilterAuthor")}>
        <input className={CONTROL} defaultValue={params.get("author") ?? ""} onBlur={onParam("author")} />
      </Field>
    </div>
  );
};
