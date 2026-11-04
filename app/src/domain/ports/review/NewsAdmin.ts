import type { FeedDesk, FeedDeskRow, FeedShare, ProposalView } from "../../views.ts";

export type ArticleDraft = Pick<FeedDeskRow, "title" | "summary" | "body" | "event_date" | "event_source">;

export interface NewsAdmin {
  newsDesk(cursor?: string): Promise<FeedDesk>;
  article(id: string): Promise<FeedDeskRow>;
  writeArticle(article: ArticleDraft): Promise<ProposalView>;
  draftArticle(item: string): Promise<ProposalView>;
  reviseArticle(id: string, article: ArticleDraft, note: string): Promise<ProposalView>;
  moveDraft(id: string, position: number): Promise<readonly ProposalView[]>;
  publishNext(note: string): Promise<ProposalView>;
  publishTemplated(note: string): Promise<readonly ProposalView[]>;
  retractArticle(id: string, note: string): Promise<ProposalView>;
  shareText(id: string, locale: string): Promise<FeedShare>;
}
