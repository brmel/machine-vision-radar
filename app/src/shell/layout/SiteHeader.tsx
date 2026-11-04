import { useState, type FC } from "react";
import { Menu, X } from "lucide-react";
import { AppLink, BrandLogo } from "../../ui/index.ts";
import { useI18n } from "../i18n/index.tsx";
import type { Route } from "../routing/routes.ts";
import { pathFromRoute } from "../routing/router.ts";
import { LanguageSwitcher } from "./LanguageSwitcher.tsx";
import { ThemeToggle } from "./ThemeToggle.tsx";

export interface NavItem {
  key: string;
  label: string;
  active: boolean;
  route: Route;
}

export const SiteHeader: FC<{ navItems: NavItem[];
  onNavigate: (route: Route) => void }> = ({ navItems, onNavigate }) => {
  const { t } = useI18n();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const toggleMenu = () => setMobileMenuOpen((open) => !open);
  const link = (item: NavItem, className: string, close: boolean) => (
    <AppLink key={item.key} href={pathFromRoute(item.route)} className={className}
      onOpen={() => {
        if (close) setMobileMenuOpen(false);
        onNavigate(item.route);
      }}>
      {item.label}
    </AppLink>
  );
  return (
    <header className="sticky top-0 z-40 w-full border-b border-line bg-chrome/90 backdrop-blur-md">
      <div className="max-w-page mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-2 sm:gap-8">
        <div className="shrink-0">
          <BrandLogo onHome={() => onNavigate({ name: "home" })} />
        </div>

        <nav className="hidden lg:flex items-center gap-6 text-body font-medium text-muted">
          {navItems.map((item) => link(item, `py-1 border-b-2 whitespace-nowrap transition-colors ${item.active
            ? "border-accent text-fg font-semibold" : "border-transparent hover:text-fg"}`, false))}
        </nav>

        <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
          <button
            type="button"
            onClick={toggleMenu}
            aria-expanded={mobileMenuOpen}
            aria-label={t("navMenuAriaLabel")}
            className="lg:hidden p-1.5 text-fg-secondary hover:text-fg transition-colors cursor-pointer"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" aria-hidden="true" />
              : <Menu className="w-5 h-5" aria-hidden="true" />}
          </button>
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>

      {mobileMenuOpen && (
        <nav className="lg:hidden border-t border-line bg-chrome">
          <div className="max-w-page mx-auto px-4 sm:px-6 py-1 flex flex-col">
            {navItems.map((item) =>
              link(item, `px-2 py-2.5 text-body border-b border-line-subtle last:border-0 transition-colors `
                + `${item.active ? "text-fg font-semibold" : "text-muted font-medium"}`, true))}
          </div>
        </nav>
      )}
    </header>
  );
};
