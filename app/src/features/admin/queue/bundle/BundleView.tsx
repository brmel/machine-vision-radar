import { useState, type FC } from "react";
import { PageHeader, RowList, StatePanel } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { leftWaiting, useAdmin } from "../../model.ts";
import { AdminLink, useLoad, useProblem } from "../../useLoad.tsx";
import { Decision, type Action } from "../Decision.tsx";
import { BundleItem } from "./BundleItem.tsx";

export const BundleView: FC<{ run: string }> = ({ run }) => {
  const { review } = useAdmin();
  const { t, plural } = useI18n();
  const bundle = useLoad(() => review.bundle(run), `bundle/${run}`);
  const [left, setLeft] = useState<ReadonlySet<string>>(new Set());
  const { alert, say } = useProblem("a bundle's decision");
  if (!bundle.value) return bundle.pending;
  const { members } = bundle.value;
  const waiting = members.filter((m) => m.proposal.status === "suggested");
  const toggle = (id: string) => () => setLeft((l) => new Set(l.has(id) ? [...l].filter((x) => x !== id) : [...l, id]));
  const approve = async (note: string) => {
    if (left.size > 0) await review.decide({ decision: "reject", target: { proposals: [...left] }, note });
    say(leftWaiting(await review.decide({ decision: "approve", target: { bundle: run }, note }), t));
  };
  const reject = async (note: string) => {
    await review.decide({ decision: "reject", target: { bundle: run }, note });
  };
  const reloaded = (act: Action["run"]): Action["run"] => (note) => {
    say([]);
    return act(note).finally(() => {
      setLeft(new Set());
      bundle.reload();
    });
  };
  const actions: Action[] = [
    { label: left.size > 0 ? plural("adminApproveRestOne", "adminApproveRestOther", left.size)
      : t("adminApproveBundle"), run: reloaded(approve), primary: true },
    { label: t("adminRejectBundle"), run: reloaded(reject) },
  ];
  const research = `/research/runs/${run}`;
  return (
    <article className="space-y-4">
      <PageHeader title={t("adminBundleTitle", { count: members.length })}>
        <p className="text-caption"><AdminLink to={research}
          className="font-mono underline break-all">{run}</AdminLink></p>
      </PageHeader>
      {members.length === 0 ? <StatePanel tone="empty" title={t("adminBundleEmpty")} /> : (
        <RowList ordered>
          {members.map((m) => (
            <BundleItem key={m.proposal.id} member={m} left={left.has(m.proposal.id)}
              onToggle={toggle(m.proposal.id)} />
          ))}
        </RowList>
      )}
      {alert}
      {waiting.length > 0 && <Decision actions={actions} />}
    </article>
  );
};
