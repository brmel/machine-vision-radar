import type { AskApi } from "../../domain/ports/AskApi.ts";
import type { CatalogRepository } from "../../domain/ports/CatalogRepository.ts";
import type { AskAnswer, ProductView } from "../../domain/views.ts";
import { useRead } from "../../ui/index.ts";
import { logger } from "../../shell/logger.ts";

export type AskState =
  | { readonly phase: "idle" | "loading" | "unreachable" }
  | { readonly phase: "done"; readonly answer: AskAnswer; readonly cited: ReadonlyMap<string, ProductView> };

export function useAsk(api: AskApi, repository: CatalogRepository, question: string, locale: string): AskState {
  const read = useRead(async () => {
    if (!question.trim()) return null;
    const answer = await api.ask(question, locale);
    const views = await repository.products([...new Set(answer.citations.map((c) => c.product))]);
    return { answer, cited: new Map(views.map((v) => [v.id, v])) };
  }, `ask:${locale}:${question}`, (err) => logger.error("ask: no answer", { locale }, err));
  if (!question.trim()) return { phase: "idle" };
  if (read.error) return { phase: "unreachable" };
  return read.isLoading || !read.value ? { phase: "loading" } : { phase: "done", ...read.value };
}
