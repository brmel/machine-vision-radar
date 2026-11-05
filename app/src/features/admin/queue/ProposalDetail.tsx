import { useState, type ChangeEvent, type FC } from "react";
import type { Review } from "../../../domain/ports/review/Review.ts";
import type { FieldChangeView, ProposalView } from "../../../domain/views.ts";
import { CONTROL, Field, Section, formatDate } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import type { MessageKey } from "../../../shell/i18n/messages.ts";
import { AdminLink, useLoad } from "../useLoad.tsx";
import { changeDrafts } from "../records/drafts.ts";
import { DiffTable } from "./DiffTable.tsx";
import { Decision, type Action } from "./Decision.tsx";
import { ProposalHeader } from "./ProposalHeader.tsx";
import { useAdmin } from "../model.ts";

function flatten(value: unknown, prefix = "", out = new Map<string, string>()): Map<string, string> {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    for (const [key, inner] of Object.entries(value)) flatten(inner, prefix ? `${prefix}.${key}` : key, out);
  } else if (prefix) {
    out.set(prefix, JSON.stringify(value));
  }
  return out;
}

function diffRows(before?: string, after?: string): FieldChangeView[] {
  const [a, b] = [flatten(before ? JSON.parse(before) : {}), flatten(after ? JSON.parse(after) : {})];
  return [...new Set([...a.keys(), ...b.keys()])]
    .sort()
    .filter((path) => a.get(path) !== b.get(path))
    .map((path) =>
      ({ path, ...(a.has(path) ? { before: a.get(path) } : {}), ...(b.has(path) ? { after: b.get(path) } : {}) }));
}

function actionsFor(review: Review, p: ProposalView, changeset: string | null, t: (key: MessageKey) => string,
    done: () => void): Action[] {
  const on = (decision: "approve" | "reject" | "retract") => (note: string) =>
    review.decide({ decision, target: { proposals: [p.id] }, note }).then(done);
  if (p.status === "approved") return [{ label: t("adminRetract"), run: on("retract") }];
  if (p.status !== "suggested") return [];
  const save = async (note: string) => {
    await review.decide({ decision: "edit", proposal: p.id, changes: changeDrafts(changeset ?? ""), note });
    done();
  };
  const approve: Action[] = p.changeset ? [{ label: t("adminApprove"), run: on("approve"), primary: true }] : [];
  const edit: Action[] = changeset !== null ? [{ label: t("adminSaveEdit"), run: save }] : [];
  return [...approve, { label: t("adminReject"), run: on("reject") }, ...edit];
}

const changesetText = (p: ProposalView, edited: string | null): string => edited
  ?? JSON.stringify(JSON.parse(p.changeset ?? '{"changes": []}'), null, 2);

export const ProposalDetail: FC<{ id: string }> = ({ id }) => {
  const { review } = useAdmin();
  const { t, locale } = useI18n();
  const loaded = useLoad(() => review.proposal(id), `proposal/${id}`);
  const [changeset, setChangeset] = useState<string | null>(null);
  const p = loaded.value;
  if (!p) return loaded.pending;
  const done = () => {
    setChangeset(null);
    loaded.reload();
  };
  const onChangeset = (event: ChangeEvent<HTMLTextAreaElement>) => setChangeset(event.target.value);
  const actions = actionsFor(review, p, changeset, t, done);
  const changes = p.changes ?? [];
  return (
    <article className="space-y-4">
      <ProposalHeader proposal={p} />
      {p.bundle && (
        <p className="text-body">
          {t("adminBundleOf")}: <AdminLink to={`/queue/bundles/${p.bundle}`}
            className="font-mono underline">{p.bundle}</AdminLink>
        </p>
      )}
      <Section id="proposal-changes" title={t("adminChanges")}>
        {changes.length === 0 ? <p className="text-body text-muted">{t("adminNoChange")}</p> : changes.map((c) => (
          <DiffTable key={c.entity} title={`${c.entity} · ${t(!c.before ? "adminDiffNew" : !c.after
            ? "adminDiffWithdrawn" : "adminDiffChanged")}`}
            heads={[t("adminDiffBefore"), t("adminDiffAfter")]} rows={diffRows(c.before, c.after)} />
        ))}
      </Section>
      {p.sources.length > 0
        && <p className="text-caption">{t("tabSources")}: <span
          className="font-mono">{p.sources.join(", ")}</span></p>}
      {p.edits.length > 0 && (
        <Section title={t("adminEdits")}>
          <ul className="text-caption space-y-1">{p.edits.map((e) =>
            <li key={e.at}>{formatDate(e.at, locale)} · {e.actor}: {e.note}</li>)}</ul>
        </Section>
      )}
      {p.status === "suggested" && (
        <Field label={t("adminChangeset")} hint={t("adminChangesetHint")}>
          <textarea className={`${CONTROL} font-mono text-caption`} rows={10} value={changesetText(p, changeset)}
            onChange={onChangeset} />
        </Field>
      )}
      {actions.length > 0 && <Decision actions={actions} />}
    </article>
  );
};
