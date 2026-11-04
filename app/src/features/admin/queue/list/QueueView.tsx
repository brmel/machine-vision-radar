import { useState, type ChangeEvent, type FC } from "react";
import type { QueueFilter } from "../../../../domain/ports/review/Review.ts";
import type { FilesOn, ProposalView } from "../../../../domain/views.ts";
import { PageHeader, RowList, StatePanel } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { ACTOR, STATUS, leftWaiting, useAdmin } from "../../model.ts";
import { AdminLink, usePaged, useProblem } from "../../useLoad.tsx";
import { Decision } from "../Decision.tsx";
import { QueueFilters } from "./QueueFilters.tsx";
import { QueueItem } from "./QueueItem.tsx";

const isStatus = (v: string | null): v is ProposalView["status"] => v !== null && Object.hasOwn(STATUS, v);
const isActor = (v: string | null): v is ProposalView["actor_kind"] => v !== null && Object.hasOwn(ACTOR, v);

function filterOf(params: URLSearchParams, events: readonly FilesOn[]): QueueFilter {
  const status = params.get("status") ?? "suggested";
  const actor = params.get("actor");
  const filesOn = events.find((e) => e === params.get("files_on"));
  return { ...(isStatus(status) ? { status } : {}), ...(filesOn ? { filesOn } : {}),
           ...(isActor(actor) ? { actorKind: actor } : {}),
           ...(params.get("author") ? { author: params.get("author") ?? "" } : {}) };
}

const allIn = (chosen: ReadonlySet<string>, ids: readonly string[]): boolean => ids.length > 0
  && ids.every((id) => chosen.has(id));

const withAll = (chosen: ReadonlySet<string>, ids: readonly string[]): ReadonlySet<string> =>
  new Set(allIn(chosen, ids) ? [...chosen].filter((id) => !ids.includes(id)) : [...chosen, ...ids]);

export const QueueView: FC<{ search: string }> = ({ search }) => {
  const { review, model, onNavigate } = useAdmin();
  const { t, plural } = useI18n();
  const params = new URLSearchParams(search);
  const filter = filterOf(params, model.kinds.map((k) => k.files_on));
  const list = usePaged((cursor) => review.queue(filter, cursor), "queue", "/queue", search);
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const { alert, say } = useProblem("approving the chosen proposals");
  const listed = list.value?.proposals ?? [];

  const setParam = (key: string) => (event: ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
    const changed = new URLSearchParams(search);
    changed.delete("page");
    if (event.target.value) changed.set(key, event.target.value);
    else changed.delete(key);
    setChosen(new Set());
    onNavigate(`/queue?${changed}`);
  };
  const toggle = (id: string) => () =>
    setChosen((c) => new Set(c.has(id) ? [...c].filter((x) => x !== id) : [...c, id]));
  const waiting = listed.filter((p) => p.status === "suggested").map((p) => p.id);
  const toggleAll = () => setChosen((c) => withAll(c, waiting));
  const approveChosen = async (note: string) => {
    say([]);
    const outcome = await review.decide({ decision: "approve", target: { proposals: [...chosen] }, note });
    setChosen(new Set());
    list.reload();
    say(leftWaiting(outcome, t));
  };

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <PageHeader title={t("adminQueueTitle")} />
        {list.count}
        <AdminLink to="/queue/log" className="ml-auto text-body underline">{t("adminLogTitle")}</AdminLink>
      </div>
      <QueueFilters params={params} filter={filter} onParam={setParam} />
      {!list.value ? list.pending
        : listed.length === 0 ? <StatePanel tone="empty" title={t("adminQueueEmpty")} />
        : (
          <RowList>
            {waiting.length > 0 && (
              <li className="flex items-center gap-3 px-3 py-2 bg-raised">
                <input id="queue-all" type="checkbox" className="h-5 w-5" checked={allIn(chosen, waiting)}
                  onChange={toggleAll} />
                <label htmlFor="queue-all" className="text-caption text-muted">{t("adminChooseAll")}</label>
              </li>
            )}
            {listed.map((p) => <QueueItem key={p.id} proposal={p} chosen={chosen.has(p.id)} onToggle={toggle(p.id)} />)}
          </RowList>
        )}
      {list.pager}
      {alert}
      {chosen.size > 0 && <Decision actions={[{ label: plural("adminApproveChosenOne", "adminApproveChosenOther",
        chosen.size), run: approveChosen, primary: true }]} />}
    </section>
  );
};
