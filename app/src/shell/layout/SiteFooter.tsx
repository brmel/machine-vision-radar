import type { FC } from "react";
import { BRAND_CONFIG } from "../../ui/theme/brand.ts";
import { BrandLinks } from "../../ui/theme/BrandLinks.tsx";
import { AppLink } from "../../ui/controls/AppLink.tsx";
import { useI18n } from "../i18n/index.tsx";
import { pathFromRoute } from "../routing/router.ts";
import type { MessageKey } from "../i18n/messages.ts";

declare const __APP_VERSION__: string;

type FooterPage = "about" | "agents" | "terms" | "privacy";
const PAGES: readonly (readonly [FooterPage, MessageKey])[] =
  [["about", "footerAbout"], ["terms", "termsTitle"], ["privacy", "privacyTitle"]];
const LINK = "hover:underline text-fg-secondary";

export const SiteFooter: FC<{ onOpen: (page: FooterPage) => void }> = ({ onOpen }) => {
  const { t } = useI18n();
  return (
    <footer className="border-t border-line bg-chrome py-4 text-caption text-muted transition-colors">
      <div className={"max-w-page mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between "
        + "gap-4"}>
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
          <span className="font-semibold text-fg">{BRAND_CONFIG.wordmark}</span>
          <span>{t("footerNote")}</span>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-caption font-mono">
          <span>{t("footerVersion", { version: __APP_VERSION__ })}</span>
          {PAGES.map(([page, label]) => (
            <AppLink key={page} href={pathFromRoute({ name: page })} onOpen={() => onOpen(page)}
              className={LINK}>{t(label)}</AppLink>
          ))}
          <a href={BRAND_CONFIG.licence.url} rel="license noopener noreferrer" target="_blank"
            className={LINK}>{t("footerLicence", { licence: BRAND_CONFIG.licence.name })}</a>
          <AppLink href={pathFromRoute({ name: "agents" })} onOpen={() => onOpen("agents")}
            className={LINK}>{t("footerAgents")}</AppLink>
        </div>
        <BrandLinks label={t("contactLabel")} profiles={BRAND_CONFIG.profiles} className="justify-center" />
      </div>
    </footer>
  );
};
