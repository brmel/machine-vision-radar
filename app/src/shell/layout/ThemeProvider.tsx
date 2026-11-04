import { createContext, useContext, useState, useEffect, type FC, type ReactNode } from "react";
import { save } from "../root/preferences.ts";

export type ThemePreference = "light" | "dark" | "system";

export const THEME_KEY = "machineVisionRadar.themePreference";

interface ThemeContextValue {
  preference: ThemePreference;
  setPreference: (pref: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function resolveTheme(pref: ThemePreference): "light" | "dark" {
  if (pref !== "system") return pref;
  if (typeof window.matchMedia !== "function") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyThemeToDOM(theme: "light" | "dark"): void {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
}

export const ThemeProvider: FC<{ children: ReactNode; initial: ThemePreference }> = ({ children, initial }) => {
  const [preference, setPreferenceState] = useState<ThemePreference>(initial);

  const setPreference = (newPref: ThemePreference) => {
    setPreferenceState(newPref);
    save(THEME_KEY, newPref, "theme preference not saved");
    applyThemeToDOM(resolveTheme(newPref));
  };

  useEffect(() => {
    applyThemeToDOM(resolveTheme(preference));
    if (preference !== "system" || typeof window.matchMedia !== "function") return;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (e: MediaQueryListEvent) => applyThemeToDOM(e.matches ? "dark" : "light");
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [preference]);

  return <ThemeContext.Provider value={{ preference, setPreference }}>{children}</ThemeContext.Provider>;
};

export const useTheme = (): ThemeContextValue => {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
};
