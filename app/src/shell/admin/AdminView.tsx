import { useEffect, type FC, type ReactNode } from "react";
import { kindOf, type AdminModel } from "../../domain/views.ts";
import { Button, StatePanel, prevented } from "../../ui/index.ts";
import { useI18n } from "../i18n/index.tsx";
import { useAuth } from "./AuthContext.tsx";
import { useLoad } from "../../features/admin/useLoad.tsx";
import { AdminContext, SECTIONS, type Admin } from "../../features/admin/model.ts";
import { QueueView } from "../../features/admin/queue/list/QueueView.tsx";
import { ProposalDetail } from "../../features/admin/queue/ProposalDetail.tsx";
import { BundleView } from "../../features/admin/queue/bundle/BundleView.tsx";
import { LogView } from "../../features/admin/queue/LogView.tsx";
import { RecordsView } from "../../features/admin/records/lists/RecordsView.tsx";
import { GridView } from "../../features/admin/records/lists/GridView.tsx";
import { RecordView } from "../../features/admin/records/RecordView.tsx";
import { SearchView } from "../../features/admin/search/SearchView.tsx";
import { NewsDesk } from "../../features/admin/news/desk/NewsDesk.tsx";
import { ArticlePage } from "../../features/admin/news/ArticlePage.tsx";
import { AgentsView } from "../../features/admin/agents/AgentsView.tsx";
import { ResearchView } from "../../features/admin/agents/ResearchView.tsx";
import { RunPage } from "../../features/admin/agents/RunPage.tsx";

interface AdminViewProps {
  api: Admin["review"] & Admin["editor"] & Admin["search"] & Admin["news"] & Admin["agents"] & Admin["research"];
  path: string;
  onNavigate: (path: string, replace?: boolean) => void;
}

const queuePage = (item: string | undefined, extra: string | undefined, search: string): ReactNode => {
  if (item === "log") return <LogView search={search} />;
  if (item === "bundles" && extra) return <BundleView run={extra} />;
  return item ? <ProposalDetail id={item} /> : <QueueView search={search} />;
};

export const AdminView: FC<AdminViewProps> = ({ api, path, onNavigate }) => {
  const { t } = useI18n();
  const { user, signOut } = useAuth();
  const leave = () => void signOut();
  const [pathname, search = ""] = path.split("?");
  const [section = "", item, extra] = pathname.split("/").filter(Boolean).map(decodeURIComponent);
  const model = useLoad(() => api.model(), "model");
  const catalog = Object.hasOwn(SECTIONS, section) || section === "records";
  useEffect(() => {
    if (!section) onNavigate("/queue", true);
  }, [section, onNavigate]);

  const nav = [
    { key: "queue", label: t("adminNavQueue"), path: "/queue", active: section === "queue" },
    { key: "catalog", label: t("adminNavCatalog"), path: "/products", active: catalog },
    { key: "grid", label: t("adminNavGrid"), path: "/grid", active: section === "grid" },
    { key: "search", label: t("adminNavSearch"), path: "/search", active: section === "search" },
    { key: "news", label: t("adminNavNews"), path: "/news", active: section === "news" },
    { key: "agents", label: t("adminNavAgents"), path: "/agents", active: section === "agents" },
    { key: "research", label: t("adminNavResearch"), path: "/research", active: section === "research" },
  ];
  const follow = (to: string) => prevented(() => onNavigate(to));
  const notFound = <StatePanel tone="empty" level={1} title={t("notFoundTitle")} />;
  const recordPage = (admin: AdminModel) => {
    if (Object.hasOwn(SECTIONS, section)) return item ? notFound : <RecordsView section={section} search={search} />;
    const shape = admin.entities.find((e) => e.id === (item === "new" ? extra : kindOf(item ?? "")));
    return item && shape ? <RecordView shape={shape} id={item} tab={extra} search={search} /> : notFound;
  };
  const page = () => {
    if (!model.value) return model.pending;
    const sections: Readonly<Record<string, ReactNode>> = {
      queue: queuePage(item, extra, search),
      grid: <GridView search={search} />,
      search: <SearchView item={item} search={search} />,
      news: item ? <ArticlePage id={item} /> : <NewsDesk search={search} />, agents: <AgentsView search={search} />,
      research: item === "runs" && extra ? <RunPage id={extra} /> : <ResearchView search={search} />,
    };
    const pageOf = catalog ? recordPage(model.value) : sections[section] ?? notFound;
    return <AdminContext.Provider value={{ review: api, editor: api, search: api, news: api, agents: api, research: api,
      model: model.value, onNavigate }}>{pageOf}</AdminContext.Provider>;
  };

  return (
    <div className="space-y-6">
      <nav aria-label={t("adminNavLabel")} className="flex flex-wrap items-center gap-2 border-b border-line pb-3">
        {nav.map((n) => (
          <a key={n.key} href={`/admin${n.path}`} aria-current={n.active ? "page" : undefined} onClick={follow(n.path)}
            className={`px-3 py-1.5 rounded-chip text-body font-medium ${n.active ? "bg-inverse text-on-inverse"
              : "text-fg-secondary hover:bg-raised"}`}>
            {n.label}
          </a>
        ))}
        <span className="ml-auto text-caption text-muted break-all">{user?.email ?? ""}</span>
        <Button variant="ghost" size="sm" onClick={leave}>{t("authSignOut")}</Button>
      </nav>
      {page()}
    </div>
  );
};
