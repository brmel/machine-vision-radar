import { useState, type FC } from "react";
import type { EntityShape } from "../../../domain/views.ts";
import { PageHeader, Section, Segmented, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useAdmin } from "../model.ts";
import { useLoad } from "../useLoad.tsx";
import { Decision } from "../queue/Decision.tsx";
import { HistoryTab } from "./HistoryTab.tsx";
import { RecordForm } from "./RecordForm.tsx";
import { RelatedRecords } from "./RelatedRecords.tsx";

interface Props {
  shape: EntityShape;
  id: string;
  tab?: string;
  search: string;
}

export const RecordView: FC<Props> = ({ shape, id, tab, search }) => {
  const { editor, review, onNavigate } = useAdmin();
  const { t, locale } = useI18n();
  const [thumbnailPick, setThumbnailPick] = useState<string | null>(null);
  const isNew = id === "new";
  const history = tab === "history";
  const loaded =
    useLoad(() => (isNew || history ? Promise.resolve(null) : editor.record(id)), `record/${id}/${tab}`, 4, 2);
  const toProposal = (proposal: string) => onNavigate(`/queue/${proposal}`);
  const remove = (reason: string) => review.submit({ filesOn: "retract", subject: id, reason })
    .then((p) => toProposal(p.id));
  const tabs = [{ id: "edit", label: t("adminEdit"), path: `/records/${id}` },
    { id: "history", label: t("adminHistory"), path: `/records/${id}/history` }];
  const label = localized(shape.label, locale);
  if (isNew) {
    return (
      <article className="space-y-4">
        <PageHeader title={t("adminNewOf", { kind: label })} />
        <RecordForm key={`${shape.id}?${search}`} kind={shape.id} existing={null} given={search} onFiled={toProposal} />
      </article>
    );
  }
  const named = loaded.value?.related.find((r) => r.subject === id && r.is_primary === true)?.value;
  return (
    <article className="space-y-4">
      <PageHeader title={String(named ?? loaded.value?.record.name ?? id)}>
        <p className="text-caption text-muted">{label} · <span className="font-mono">{id}</span></p>
      </PageHeader>
      <Segmented look="tab" label={t("adminRecordTabs")} value={history ? "history" : "edit"} options={tabs}
        onChange={(next) => onNavigate(next === "history" ? tabs[1].path : tabs[0].path)} />
      {history ? <HistoryTab id={id} search={search} onFiled={toProposal} /> : !loaded.value ? loaded.pending : (
        <>
          <RecordForm key={id} kind={shape.id} existing={loaded.value} onFiled={toProposal}
            thumbnailPick={thumbnailPick} />
          <RelatedRecords id={id} kind={shape.id} related={loaded.value.related} onUseThumbnail={setThumbnailPick} />
          <Section title={t("adminDelete")} note={t("adminDeleteHint")}>
            <Decision noteLabel={t("adminReason")} actions={[{ label: t("adminDelete"), run: remove }]} />
          </Section>
        </>
      )}
    </article>
  );
};
