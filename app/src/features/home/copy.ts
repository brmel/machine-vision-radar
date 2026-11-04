import type { MessageKey } from "../../shell/i18n/messages.ts";
import type { CategoryEntry, TermEntry } from "../../domain/views.ts";
import { localized } from "../../ui/specs/specFormat.ts";
import { BRAND_CONFIG, type RoleAddress } from "../../ui/theme/brand.ts";

export interface TermCount {
  readonly term: TermEntry;
  readonly products: number;
}

export const pipeline = (stages: readonly TermEntry[], domains: readonly TermEntry[],
    categories: readonly CategoryEntry[]): { stages: TermCount[]; domains: TermCount[] } => {
  const sum = (holds: (c: CategoryEntry) => boolean): number =>
    categories.reduce((n, c) => n + (holds(c) ? c.products : 0), 0);
  return {
    stages: stages.map((term) => ({ term, products: sum((c) => c.pipeline.includes(term.id)) })),
    domains: domains.map((term) => ({ term, products: sum((c) => c.domain === term.id) }))
      .filter((d) => d.products > 0),
  };
};

export const domainList = (domains: readonly TermEntry[], locale: string): string =>
  new Intl.ListFormat(locale, { type: "conjunction" }).format(domains.map((d) => localized(d.label, locale)));

export const PRINCIPLES = [["principleNotPublished", "principleNotPublishedDesc"],
  ["principleProvenance", "principleProvenanceDesc"], ["principleIndependent", "principleIndependentDesc"]] as const;

interface Section {
  heading: MessageKey;
  text: MessageKey;
  link?: { label: MessageKey; href: string };
}

interface LegalPage {
  title: MessageKey;
  lead: MessageKey;
  sections: readonly Section[];
  role: RoleAddress["role"];
}

export const LEGAL_PAGES: Readonly<Record<"terms" | "privacy", LegalPage>> = {
  terms: {
    title: "termsTitle", lead: "termsPageDescription", role: "corrections", sections: [
      { heading: "termsSourcesTitle", text: "termsSources" },
      { heading: "termsLicenceTitle", text: "termsLicence",
        link: { label: "termsLicenceLink", href: BRAND_CONFIG.licence.url } },
      { heading: "termsMediaTitle", text: "termsMedia" },
      { heading: "termsCorrectionsTitle", text: "termsCorrections" },
    ],
  },
  privacy: {
    title: "privacyTitle", lead: "privacyPageDescription", role: "privacy", sections: [
      { heading: "privacyBrowserTitle", text: "privacyBrowser" },
      { heading: "privacyCountsTitle", text: "privacyCounts" },
      { heading: "navAsk", text: "privacyAsk" },
      { heading: "privacyReportTitle", text: "privacyReport" },
      { heading: "navAdmin", text: "privacyAdmin" },
      { heading: "privacyProvidersTitle", text: "privacyProviders" },
      { heading: "privacyRequestsTitle", text: "privacyRequests" },
    ],
  },
};

export const mcpEndpoint = (origin: string): string => `${origin}/api/mcp`;

export const mcpClients = (origin: string): readonly (readonly [MessageKey, string])[] => [
  ["agentsClientClaudeCode",
    `claude mcp add --transport http mvradar ${mcpEndpoint(origin)} --header "Authorization: Bearer <token>"`],
  ["agentsClientCursor", JSON.stringify({ mcpServers: { mvradar: { url: mcpEndpoint(origin),
    headers: { Authorization: "Bearer <token>" } } } }, null, 2)],
];
