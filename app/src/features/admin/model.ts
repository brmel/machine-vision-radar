import { createContext, useContext } from "react";
import type { CatalogEditor, ListedKind } from "../../domain/ports/review/CatalogEditor.ts";
import type { JsonRecord, Review } from "../../domain/ports/review/Review.ts";
import type { SearchAdmin } from "../../domain/ports/review/SearchAdmin.ts";
import type { NewsAdmin } from "../../domain/ports/review/NewsAdmin.ts";
import type { AgentsAdmin } from "../../domain/ports/review/agents/AgentsAdmin.ts";
import type { ResearchAdmin } from "../../domain/ports/review/agents/ResearchAdmin.ts";
import type { AdminModel, AgentTokenView, AiCapRow, DecisionOutcome, EntityShape, FilesOn, LogEntryView, ProposalView,
  ResearchLine, ResearchRunView, Risk, TermRef } from "../../domain/views.ts";
import type { MessageKey } from "../../shell/i18n/messages.ts";
import { kindOf as modelKindOf } from "../../domain/views.ts";
import { localized } from "../../ui/index.ts";

export interface Admin {
  review: Review;
  editor: CatalogEditor;
  search: SearchAdmin;
  news: NewsAdmin;
  agents: AgentsAdmin;
  research: ResearchAdmin;
  model: AdminModel;
  onNavigate: (path: string) => void;
}

export const AdminContext = createContext<Admin | null>(null);

export function useAdmin(): Admin {
  const admin = useContext(AdminContext);
  if (!admin) throw new Error("an admin view renders inside AdminView, which provides the admin");
  return admin;
}

export const STATUS: Readonly<Record<ProposalView["status"], MessageKey>> = {
  suggested: "adminStatusSuggested", approved: "adminStatusApproved", rejected: "adminStatusRejected",
  retracted: "adminStatusRetracted",
};
export const ACTOR: Readonly<Record<ProposalView["actor_kind"], MessageKey>> = { human: "adminActorHuman",
  agent: "adminActorAgent", import: "adminActorImport" };
export const ACTION: Readonly<Record<LogEntryView["action"], MessageKey>> = {
  submit: "adminActionSubmit", edit: "adminActionEdit", approve: "adminActionApprove", reject: "adminActionReject",
  retract: "adminActionRetract",
};
export const SCOPE: Readonly<Record<AgentTokenView["scope"], MessageKey>> = { read: "adminAgentsScopeRead",
  propose: "adminAgentsScopePropose" };
export const RUN_STATUS = {
  running: ["adminResearchRunning", "info"], done: ["adminResearchDone", "positive"],
  partial: ["adminResearchPartial", "info"], blocked: ["adminResearchBlocked", "warning"],
  cancelled: ["adminResearchCancelled", "neutral"], capped: ["adminResearchCapped", "warning"],
  failed: ["adminResearchFailed", "warning"],
} as const satisfies Readonly<Record<ResearchRunView["status"], readonly [MessageKey, string]>>;
export const STEP: Readonly<Record<ResearchLine["step"], MessageKey>> = {
  read: "adminResearchStepRead", skipped: "adminResearchStepSkipped", filed: "adminResearchStepFiled",
  media: "adminResearchStepMedia", datasheet: "adminResearchStepDatasheet", rejected: "adminResearchStepRejected",
  ended: "adminResearchStepEnded",
};
export const RISK = {
  withdraws: ["adminRiskWithdraws", "warning"], changes: ["adminRiskChanges", "info"],
  adds: ["adminRiskAdds", "neutral"],
} as const satisfies Readonly<Record<Risk, readonly [MessageKey, string]>>;
export const USE: Readonly<Record<AiCapRow["use"], MessageKey>> = {
  all: "adminUseAll", ask: "adminUseAsk", research: "adminUseResearch", datasheet: "adminUseDatasheet",
  draft: "adminUseDraft",
};

export function kindLabel(model: AdminModel, filesOn: FilesOn, locale: string): string {
  const found = model.kinds.find((k) => k.files_on === filesOn);
  return found ? localized(found.label, locale) : filesOn;
}

export const leftWaiting =
  (outcome: DecisionOutcome, t: (key: MessageKey, params: Record<string, string>) => string): string[] => [
  ...outcome.refused.map((r) => t("adminLeftRefused", { id: r.proposal.id, findings: r.findings.join("; ") })),
  ...outcome.held.map((h) => t("adminLeftHeld", { id: h.proposal.id, waits: h.waits_on.join(", ") })),
];

export function terms(model: AdminModel, vocabulary: string | undefined): readonly TermRef[] {
  return (vocabulary && model.vocabularies[vocabulary]?.terms) || [];
}

export function entity(model: AdminModel, name: string): EntityShape {
  const found = model.entities.find((e) => e.id === name);
  if (!found) throw new Error(`the admin model has no entity ${name}`);
  return found;
}

export const claimMethods = (model: AdminModel): readonly TermRef[] =>
  terms(model, entity(model, "Claim").fields.find((f) => f.name === "method")?.vocabulary);

export const isKind = (kind: string) => (r: JsonRecord): boolean => modelKindOf(String(r.id)) === kind;

export const recordPath = (model: AdminModel, id: string): string
  | null => (model.entities.some((e) => e.id === modelKindOf(id)) ? `/records/${id}` : null);

export const SECTIONS: Readonly<Record<string, { kind: ListedKind; label: MessageKey }>> = {
  products: { kind: "Product", label: "adminProducts" }, organizations: { kind: "Organization",
    label: "adminOrganizations" }, media: { kind: "Document", label: "adminMedia" },
};
