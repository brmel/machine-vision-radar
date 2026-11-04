import { useState, type ChangeEvent, type FC } from "react";
import type { StoredFile } from "../../../../domain/views.ts";
import { Field } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { useAdmin } from "../../model.ts";
import { useProblem } from "../../useLoad.tsx";

export const FileField: FC<{ onStored: (file: StoredFile) => void }> = ({ onStored }) => {
  const { editor } = useAdmin();
  const { t } = useI18n();
  const [stored, setStored] = useState<StoredFile | null>(null);
  const upload = useProblem("a media upload");
  const keep = (file: StoredFile) => {
    setStored(file);
    onStored(file);
  };
  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0];
    if (picked) void picked.arrayBuffer()
      .then((bytes) => editor.upload(bytes, picked.type || "application/octet-stream")).then(keep, upload.refuse);
  };
  return (
    <div className="space-y-1 md:col-span-2">
      <Field label={`${t("adminMediaFile")} *`}><input type="file" className="text-body" onChange={onPick} /></Field>
      {stored && <p
        className="text-caption font-mono break-all">sha256 {stored.sha256} · {stored.mime} · {stored.bytes} B</p>}
      {upload.alert}
    </div>
  );
};
