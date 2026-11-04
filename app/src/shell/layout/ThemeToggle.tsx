import { type FC } from "react";
import { Sun, Moon, Laptop } from "lucide-react";
import { Segmented } from "../../ui/index.ts";
import { useTheme, type ThemePreference } from "./ThemeProvider.tsx";
import { useI18n } from "../i18n/index.tsx";

export const ThemeToggle: FC = () => {
  const { preference, setPreference } = useTheme();
  const { t } = useI18n();
  return (
    <Segmented<ThemePreference> label={t("themeToggle")} value={preference} onChange={setPreference} options={[
      { id: "light", label: t("themeLight"), icon: Sun },
      { id: "system", label: t("themeSystem"), icon: Laptop },
      { id: "dark", label: t("themeDark"), icon: Moon },
    ]} />
  );
};
