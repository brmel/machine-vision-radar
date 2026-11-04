import type { BundleView, DecisionOutcome, FilesOn, LogPage, ProposalPage, ProposalView } from "../../views.ts";

export type Json = string | number | boolean | null | readonly Json[] | { readonly [key: string]: Json };
export type JsonRecord = { readonly [field: string]: Json };

export type ChangeDraft =
  | { readonly op: "put"; readonly entity: JsonRecord; readonly reason: string;
    readonly source_refs: readonly string[] }
  | { readonly op: "retract"; readonly id: string; readonly reason: string; readonly source_refs: readonly string[] };

export type Draft =
  | { readonly filesOn: Extract<FilesOn, "create" | "update">; readonly reason: string; readonly subject: string;
    readonly changes: readonly ChangeDraft[] }
  | { readonly filesOn: "retract"; readonly reason: string; readonly subject: string }
  | { readonly filesOn: "rollback"; readonly reason: string; readonly subject: string; readonly to: number };

type Target = { readonly proposals: readonly string[] } | { readonly bundle: string };

export type Decision =
  | { readonly decision: "approve" | "reject" | "retract"; readonly target: Target; readonly note: string }
  | { readonly decision: "edit"; readonly proposal: string; readonly changes: readonly ChangeDraft[];
    readonly note: string };

export interface QueueFilter {
  readonly status?: ProposalView["status"];
  readonly filesOn?: FilesOn;
  readonly actorKind?: ProposalView["actor_kind"];
  readonly author?: string;
  readonly bundle?: string;
}

export class RefusedChange extends Error {
  constructor(message: string, readonly findings: readonly string[]) {
    super(message);
  }
}

export interface Review {
  queue(filter: QueueFilter, cursor?: string): Promise<ProposalPage>;
  proposal(id: string): Promise<ProposalView>;
  bundle(run: string): Promise<BundleView>;
  submit(draft: Draft): Promise<ProposalView>;
  decide(decision: Decision): Promise<DecisionOutcome>;
  log(actor?: string, cursor?: string): Promise<LogPage>;
}
