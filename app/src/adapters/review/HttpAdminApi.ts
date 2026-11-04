import { z } from "zod";
import type { CatalogEditor, ListedKind } from "../../domain/ports/review/CatalogEditor.ts";
import type { CapChange, SearchAdmin } from "../../domain/ports/review/SearchAdmin.ts";
import type { ArticleDraft, NewsAdmin } from "../../domain/ports/review/NewsAdmin.ts";
import type { AgentsAdmin, TokenRequest } from "../../domain/ports/review/agents/AgentsAdmin.ts";
import type { ResearchAdmin, ResearchScope } from "../../domain/ports/review/agents/ResearchAdmin.ts";
import { RefusedChange, type Decision, type Draft, type Json, type JsonRecord, type QueueFilter,
  type Review } from "../../domain/ports/review/Review.ts";
import type { AiCapRow } from "../../domain/views.ts";
import {
  AdminModelSchema, AdminRecordSchema, AgentTokenListSchema, AgentTokenViewSchema, AiCapsSchema, AskAnswerSchema,
  BundleViewSchema, DecisionOutcomeSchema, FeedDeskRowSchema, FeedDeskSchema, FeedShareSchema, FieldDiffSchema,
  HistoryPageSchema, IndexSettingsSchema, IndexStatusSchema, IssuedTokenSchema, LogPageSchema, ProposalPageSchema,
  ProposalViewSchema, RecordRowsSchema, ResearchRunListSchema, ResearchRunViewSchema, SearchHitsSchema,
  StoredFileSchema, WeeklyCountsSchema,
} from "../generated-views-zod.ts";

const Refusal = z.object({ error: z.string(), findings: z.array(z.string()).optional() });
const Proposals = z.object({ proposals: z.array(ProposalViewSchema) }).transform((answer) => answer.proposals);
const JsonValue: z.ZodType<Json> = z.lazy(() =>
  z.union([z.string(), z.number(), z.boolean(), z.null(), z.array(JsonValue), z.record(z.string(), JsonValue)]));
const RecordJson = z.record(z.string(), JsonValue);

const parsed = (text: string): JsonRecord => RecordJson.parse(JSON.parse(text));

const paged = (cursor?: string, params: Readonly<Record<string, string | undefined>> = {}): string => {
  const query = new URLSearchParams(Object.entries({ ...params, cursor })
    .filter((entry): entry is [string, string] => Boolean(entry[1]))).toString();
  return query ? `?${query}` : "";
};

export class HttpAdminApi implements Review, CatalogEditor, SearchAdmin, NewsAdmin, AgentsAdmin, ResearchAdmin {
  constructor(private readonly token: () => Promise<string | null>) {}

  private async call<T>(schema: z.ZodType<T>, path: string, body?: unknown): Promise<T> {
    const token = await this.token();
    const res = await fetch(`/api/admin/${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if ([400, 422, 429].includes(res.status)) {
      const refusal = Refusal.parse(await res.json());
      throw new RefusedChange(refusal.error, refusal.findings ?? []);
    }
    if (!res.ok) {
      const body = await res.text();
      const said = Refusal.safeParse(body.startsWith("{") ? JSON.parse(body) : null);
      throw new Error(said.success ? said.data.error : `admin API: ${path} answered HTTP ${res.status}`);
    }
    return schema.parse(await res.json());
  }

  queue(filter: QueueFilter, cursor?: string) {
    const query = { status: filter.status, files_on: filter.filesOn, actor_kind: filter.actorKind,
      author: filter.author, bundle: filter.bundle };
    return this.call(ProposalPageSchema, `proposals${paged(cursor, query)}`);
  }
  proposal(id: string) { return this.call(ProposalViewSchema, `proposals/${encodeURIComponent(id)}`); }
  bundle(run: string) { return this.call(BundleViewSchema, `bundles/${encodeURIComponent(run)}`); }
  submit(draft: Draft) {
    const { filesOn, ...fields } = draft;
    const body = "changes" in fields
      ? { reason: fields.reason, subject: fields.subject, changeset: { changes: fields.changes } } : fields;
    return this.call(ProposalViewSchema, "proposals", { files_on: filesOn, ...body });
  }
  decide(decision: Decision) {
    const body = decision.decision === "edit"
      ? { decision: decision.decision, proposal: decision.proposal, changeset: { changes: decision.changes },
        note: decision.note }
      : { decision: decision.decision, note: decision.note, ...decision.target };
    return this.call(DecisionOutcomeSchema, "decisions", body);
  }
  log(actor?: string, cursor?: string) { return this.call(LogPageSchema, `log${paged(cursor, { actor })}`); }
  model() { return this.call(AdminModelSchema, "model"); }
  records(kind: ListedKind, query: string, cursor?: string, category?: string) {
    return this.call(RecordRowsSchema, `records?${new URLSearchParams({ kind, q: query, ...(cursor ? { cursor } : {}),
      ...(category ? { category } : {}) })}`);
  }
  async record(id: string) {
    const found = await this.call(AdminRecordSchema, `records/${encodeURIComponent(id)}`);
    return { record: parsed(found.record), related: found.related.map(parsed) };
  }
  history(id: string, cursor?: string) {
    return this.call(HistoryPageSchema, `records/${encodeURIComponent(id)}/history${paged(cursor)}`);
  }
  diff(id: string, from: number, to: number) {
    return this.call(FieldDiffSchema, `records/${encodeURIComponent(id)}/diff?from=${from}&to=${to}`);
  }
  status() { return this.call(IndexStatusSchema, "search/status"); }
  run(action: "update" | "rebuild") { return this.call(IndexStatusSchema, `search/${action}`, {}); }
  settings() { return this.call(IndexSettingsSchema, "search/settings"); }
  query(q: string, semantic: boolean) {
    return this.call(SearchHitsSchema, `search/query?${new URLSearchParams({ q, semantic: String(semantic) })}`);
  }
  ask(question: string, locale: string) { return this.call(AskAnswerSchema, "search/ask", { question, locale }); }
  caps() { return this.call(AiCapsSchema, "search/caps"); }
  setCap(use: AiCapRow["use"], change: CapChange, reason: string) {
    return this.call(ProposalViewSchema, "search/caps", { use, ...change, reason });
  }
  capHistory(use: AiCapRow["use"], cursor?: string) {
    return this.call(HistoryPageSchema, `search/caps/${use}/history${paged(cursor)}`);
  }
  weekly() { return this.call(WeeklyCountsSchema, "search/weekly"); }
  newsDesk(cursor?: string) { return this.call(FeedDeskSchema, `news${paged(cursor)}`); }
  article(id: string) { return this.call(FeedDeskRowSchema, `news/${encodeURIComponent(id)}`); }
  writeArticle(article: ArticleDraft) { return this.call(ProposalViewSchema, "news", { article }); }
  draftArticle(item: string) { return this.call(ProposalViewSchema, "news/draft", { item }); }
  reviseArticle(id: string, article: ArticleDraft, note: string) {
    return this.call(ProposalViewSchema, `news/${encodeURIComponent(id)}/edit`, { article, note });
  }
  moveDraft(id: string, position: number) {
    return this.call(Proposals, `news/${encodeURIComponent(id)}/move`, { position });
  }
  publishNext(note: string) { return this.call(ProposalViewSchema, "news/publish", { note }); }
  publishTemplated(note: string) { return this.call(Proposals, "news/approve", { note }); }
  retractArticle(id: string, note: string) {
    return this.call(ProposalViewSchema, `news/${encodeURIComponent(id)}/retract`, { note });
  }
  shareText(id: string, locale: string) {
    return this.call(FeedShareSchema, `news/${encodeURIComponent(id)}/share?${new URLSearchParams({ locale })}`);
  }
  agentTokens(cursor?: string) { return this.call(AgentTokenListSchema, `agents${paged(cursor)}`); }
  issueToken(request: TokenRequest) {
    return this.call(IssuedTokenSchema, "agents",
      { name: request.name, scope: request.scope, expires: request.expires, ...request.limits });
  }
  revokeToken(id: string) { return this.call(AgentTokenViewSchema, `agents/${encodeURIComponent(id)}/revoke`, {}); }
  researchRuns(cursor?: string) { return this.call(ResearchRunListSchema, `research${paged(cursor)}`); }
  researchRun(id: string) { return this.call(ResearchRunViewSchema, `research/${encodeURIComponent(id)}`); }
  startResearch(scope: ResearchScope) { return this.call(ResearchRunViewSchema, "research", scope); }
  cancelResearch(id: string) {
    return this.call(ResearchRunViewSchema, `research/${encodeURIComponent(id)}/cancel`, {});
  }
  upload(bytes: ArrayBuffer, mime: string) {
    let binary = "";
    new Uint8Array(bytes).forEach((b) => (binary += String.fromCharCode(b)));
    return this.call(StoredFileSchema, "media", { mime, content: btoa(binary) });
  }
}
