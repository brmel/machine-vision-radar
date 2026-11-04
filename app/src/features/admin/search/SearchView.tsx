import type { FC } from "react";
import type { MessageKey } from "../../../shell/i18n/messages.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { prevented } from "../../../ui/index.ts";
import { useAdmin } from "../model.ts";
import { StatusView } from "./StatusView.tsx";
import { ConsoleView } from "./console/ConsoleView.tsx";
import { SettingsView } from "./settings/SettingsView.tsx";

const PAGES: readonly { path: string; label: MessageKey; page: FC<{ search: string }> }[] = [
  { path: "", label: "adminSearchNavIndex", page: StatusView },
  { path: "console", label: "adminSearchNavConsole", page: ConsoleView },
  { path: "settings", label: "adminSearchNavSettings", page: SettingsView },
];

export const SearchView: FC<{ item?: string; search: string }> = ({ item = "", search }) => {
  const { onNavigate } = useAdmin();
  const { t } = useI18n();
  const current = PAGES.find((p) => p.path === item) ?? PAGES[0];
  const follow = (to: string) => prevented(() => onNavigate(`/search${to ? `/${to}` : ""}`));
  const Page = current.page;
  return (
    <div className="space-y-6">
      <nav aria-label={t("adminSearchNavLabel")} className="flex flex-wrap gap-2">
        {PAGES.map((p) => (
          <a key={p.path} href={`/admin/search${p.path ? `/${p.path}` : ""}`}
            aria-current={p === current ? "page" : undefined} onClick={follow(p.path)}
            className={`px-3 py-1 rounded-chip text-caption font-medium border border-line ${p === current
              ? "bg-raised" : "text-fg-secondary hover:bg-raised"}`}>
            {t(p.label)}
          </a>
        ))}
      </nav>
      <Page search={search} />
    </div>
  );
};
