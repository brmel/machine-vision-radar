import { type ChangeEvent, type FC } from "react";
import { CONTROL, Field, TYPE } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { entity, terms, useAdmin } from "../../model.ts";
import type { NewProduct } from "../drafts.ts";
import { TermSelect } from "./TermSelect.tsx";

export const NewProductFields: FC<{ product: NewProduct; onChange: (product: NewProduct) => void }> = ({ product,
  onChange }) => {
  const { model } = useAdmin();
  const { t } = useI18n();
  const typed = (key: "name" | "org") => (event: ChangeEvent<HTMLInputElement>) =>
    onChange({ ...product, [key]: event.target.value });
  const onRole = (role: string) => onChange({ ...product, role });
  const roles = terms(model, entity(model, "ProductOrgRole").fields.find((f) => f.name === "role")?.vocabulary);
  return (
    <fieldset className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <legend className={`${TYPE.section} mb-2`}>{t("adminMaker")}</legend>
      <Field label={`${t("adminName")} *`}><input className={CONTROL} value={product.name}
        onChange={typed("name")} /></Field>
      <Field label={`${t("adminMakerOrg")} *`}><input className={CONTROL} value={product.org}
        onChange={typed("org")} /></Field>
      <TermSelect label={`${t("adminMakerRole")} *`} terms={roles} value={product.role} onChange={onRole} />
    </fieldset>
  );
};
