import type { ArticleDraft } from "../../../domain/ports/review/NewsAdmin.ts";
import type { FeedDeskRow, LocalizedText } from "../../../domain/views.ts";
import { partialDate } from "../records/drafts.ts";

type Texts = Readonly<Record<string, string>>;

export interface ArticleFields {
  readonly title: Texts;
  readonly summary: Texts;
  readonly sentences: readonly { readonly text: Texts; readonly cites: string }[];
  readonly eventDate: string;
  readonly eventSource: string;
}

export const NEW_ARTICLE: ArticleFields = { title: {}, summary: {}, sentences: [{ text: {}, cites: "" }], eventDate: "",
  eventSource: "" };

export const fieldsOf = (row: FeedDeskRow): ArticleFields => ({
  title: row.title,
  summary: row.summary,
  sentences: row.body.map((s) => ({ text: s.text, cites: s.cites.join(", ") })),
  eventDate: row.event_date?.value ?? "",
  eventSource: row.event_source ?? "",
});

const written = (texts: Texts): LocalizedText => {
  const kept = Object.entries(texts).map(([code, text]) => [code, text.trim()]).filter(([, text]) => text);
  // Justification (typed boundary): the default language's text is required; the API refuses an article without it.
  return Object.fromEntries(kept) as LocalizedText;
};

export function draftOf(fields: ArticleFields): ArticleDraft {
  const date = partialDate(fields.eventDate);
  const source = fields.eventSource.trim();
  return {
    title: written(fields.title),
    summary: written(fields.summary),
    body: fields.sentences.map((s) =>
      ({ text: written(s.text), cites: s.cites.split(",").map((c) => c.trim()).filter(Boolean) })),
    ...(date ? { event_date: date } : {}),
    ...(source ? { event_source: source } : {}),
  };
}
