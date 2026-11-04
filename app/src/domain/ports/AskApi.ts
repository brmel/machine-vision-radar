import type { AskAnswer } from "../views.ts";

export type SearchEvent = "search" | "zero_result" | "result_click";

export interface AskApi {
  ask(question: string, locale: string): Promise<AskAnswer>;
  count(event: SearchEvent): Promise<void>;
}
