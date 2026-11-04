import { useEffect, useState, type FC } from "react";
import type { EditedRecord } from "../../../domain/ports/review/CatalogEditor.ts";
import type { Json, JsonRecord } from "../../../domain/ports/review/Review.ts";
import type { StoredFile } from "../../../domain/views.ts";
import { TYPE, prevented } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { claimMethods, entity, isKind, useAdmin } from "../model.ts";
import { useProblem } from "../useLoad.tsx";
import { FILLED, changesOf, chosenSource, claimsOf, instant, namesSource, newRecord, type NewProduct,
  type SourceChoice } from "./drafts.ts";
import { FieldInput } from "./fields/FieldInput.tsx";
import { FileField } from "./fields/FileField.tsx";
import { FileFooter } from "./fields/FileFooter.tsx";
import { NewProductFields } from "./fields/NewProductFields.tsx";
import { SourceFields } from "./fields/SourceFields.tsx";
import { SpecFields } from "./fields/spec/SpecFields.tsx";

interface Props {
  kind: string;
  existing: EditedRecord | null;
  given?: string;
  onFiled: (proposal: string) => void;
  thumbnailPick?: string | null;
}

export const RecordForm: FC<Props> = ({ kind, existing, given, onFiled, thumbnailPick }) => {
  const { model, review } = useAdmin();
  const { t } = useI18n();
  const shape = entity(model, kind);
  const related = existing?.related ?? [];
  const [record, setRecord] =
    useState<JsonRecord>(() => existing?.record ?? newRecord(shape, new URLSearchParams(given)));
  const [product, setProduct] = useState<NewProduct>({ name: "", org: "", role: "" });
  const [specs, setSpecs] = useState<Readonly<Record<string, Json | null>>>({});
  const [method, setMethod] = useState(() => claimMethods(model)[0]?.id ?? "");
  const [picked, setSource] = useState<SourceChoice | null>(null);
  const [reason, setReason] = useState("");
  const { alert, say, refuse } = useProblem("a proposal");
  const id = String(record.id);
  const newProduct = !existing && kind === "Product";
  const profile = typeof record.category === "string" ? model.profiles[record.category] : undefined;
  const upload = !existing && shape.provenance === "file";
  const cites = !shape.provenance;
  const sources = related.filter(isKind("Source"));
  const source = chosenSource(picked, record);

  useEffect(() => {
    if (thumbnailPick) setRecord((r) => ({ ...r, thumbnail: thumbnailPick }));
  }, [thumbnailPick]);

  const onField = (field: string, value: Json | undefined) =>
    setRecord((r) => (value === undefined ? Object.fromEntries(Object.entries(r).filter(([k]) => k !== field))
      : { ...r, [field]: value }));
  const onStored = (file: StoredFile) =>
    setRecord((r) => ({ ...r, mime: file.mime, bytes: file.bytes, sha256: file.sha256, fetched_at: instant() }));
  const onSpec = (key: string, value: Json | null) => setSpecs((s) => ({ ...s, [key]: value }));
  const file = async () => {
    if (!reason.trim() || (cites && !namesSource(source))) return say([t("adminNeedReasonSource")]);
    const draft = { record, product: newProduct ? product : null, specs, method, source: cites ? source : null,
      reason: reason.trim() };
    await review.submit({ filesOn: existing ? "update" : "create", reason: reason.trim(), subject: id,
      changes: changesOf(model, kind, draft, existing) })
      .then((proposal) => onFiled(proposal.id), refuse);
  };
  const submit = prevented(file);

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      <fieldset className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <legend className={`${TYPE.section} mb-2`}>{t("adminRecord")}</legend>
        {shape.fields.filter((f) => !FILLED.includes(f.name)).map((f) => (
          <FieldInput key={f.name} field={f} value={record[f.name]} onChange={onField}
            disabled={f.name === "slug" && existing !== null} />
        ))}
        {upload && <FileField onStored={onStored} />}
      </fieldset>
      {newProduct && <NewProductFields product={product} onChange={setProduct} />}
      {profile && <SpecFields profile={profile} held={claimsOf(related, id)} set={specs} onChange={onSpec}
        method={method} onMethod={setMethod} />}
      {cites && <SourceFields sources={sources} source={source} onChange={setSource} />}
      <FileFooter reason={reason} onReason={setReason} alert={alert} />
    </form>
  );
};
