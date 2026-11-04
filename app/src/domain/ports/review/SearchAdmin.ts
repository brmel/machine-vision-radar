import type { AiCapRow, AiCaps, AiUse, AskAnswer, HistoryPage, IndexSettings, IndexStatus, ProposalView, SearchHits,
  WeeklyCounts } from "../../views.ts";

export type CapChange = Partial<Omit<AiUse, "use">>;

export interface SearchAdmin {
  status(): Promise<IndexStatus>;
  run(action: "update" | "rebuild"): Promise<IndexStatus>;
  settings(): Promise<IndexSettings>;
  query(q: string, semantic: boolean): Promise<SearchHits>;
  ask(question: string, locale: string): Promise<AskAnswer>;
  caps(): Promise<AiCaps>;
  setCap(use: AiCapRow["use"], change: CapChange, reason: string): Promise<ProposalView>;
  capHistory(use: AiCapRow["use"], cursor?: string): Promise<HistoryPage>;
  weekly(): Promise<WeeklyCounts>;
}
