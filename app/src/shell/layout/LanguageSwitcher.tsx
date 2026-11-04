import { type FC } from "react";
import { Segmented } from "../../ui/index.ts";
import { useI18n } from "../i18n/index.tsx";

export const LanguageSwitcher: FC = () => {
  const { locale, setLocale, locales, t } = useI18n();
  return (
    <Segmented label={t("ariaLanguageSelection")} value={locale} onChange={setLocale}
      options={locales.map((loc) => ({ id: loc.code, label: loc.label, title: loc.name, lang: loc.code }))} />
  );
};
