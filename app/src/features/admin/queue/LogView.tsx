import type { ChangeEvent, FC } from "react";
import { CONTROL, Field, PageHeader, RowList, StatePanel, formatInstant } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { ACTION, ACTOR, useAdmin } from "../model.ts";
import { AdminLink, usePaged } from "../useLoad.tsx";

export const LogView: FC<{ search: string }> = ({ search }) => {
  const { review, onNavigate } = useAdmin();
  const { t, plural, locale } = useI18n();
  const actor = new URLSearchParams(search).get("actor") ?? undefined;
  const list = usePaged((cursor) => review.log(actor, cursor), "log", "/queue/log", search);
  const onActor = (event: ChangeEvent<HTMLInputElement>) =>
    onNavigate(event.target.value ? `/queue/log?actor=${encodeURIComponent(event.target.value)}` : "/queue/log");
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <PageHeader title={t("adminLogTitle")} />
        {list.count}
        <AdminLink to="/queue" className="ml-auto text-body underline">{t("adminQueueTitle")}</AdminLink>
      </div>
      <Field label={t("adminFilterActorName")} className="max-w-sm">
        <input className={CONTROL} defaultValue={actor ?? ""} onBlur={onActor} />
      </Field>
      {!list.value ? list.pending
        : list.value.entries.length === 0 ? <StatePanel tone="empty" title={t("adminLogEmpty")} />
        : (
          <RowList ordered>
            {list.value.entries.map((e) => (
              <li key={`${e.at}-${e.proposal}-${e.action}`} className="p-3 text-body space-y-0.5">
                <p>
                  <span className="font-medium">{t(ACTION[e.action])}</span> ·{" "}
                  <AdminLink to={`/queue/${e.proposal}`} className="font-mono underline">{e.proposal}</AdminLink>
                </p>
                <p className="text-caption text-muted">
                  <time dateTime={e.at}>{formatInstant(e.at,
                    locale)}</time> · {e.actor} ({t(ACTOR[e.actor_kind])}){e.changes.length > 0
                      && ` · ${plural("adminChangesOne", "adminChangesOther", e.changes.length)}`}
                </p>
                {e.note && <p className="text-caption break-words">{e.note}</p>}
              </li>
            ))}
          </RowList>
        )}
      {list.pager}
    </section>
  );
};
