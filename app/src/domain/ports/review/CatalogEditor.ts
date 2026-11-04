import type { AdminModel, FieldDiff, HistoryPage, RecordRows, StoredFile } from "../../views.ts";
import type { JsonRecord } from "./Review.ts";

export type ListedKind = "Product" | "Organization" | "Document";

export interface EditedRecord {
  readonly record: JsonRecord;
  readonly related: readonly JsonRecord[];
}

export interface CatalogEditor {
  model(): Promise<AdminModel>;
  records(kind: ListedKind, query: string, cursor?: string, category?: string): Promise<RecordRows>;
  record(id: string): Promise<EditedRecord>;
  history(id: string, cursor?: string): Promise<HistoryPage>;
  diff(id: string, from: number, to: number): Promise<FieldDiff>;
  upload(bytes: ArrayBuffer, mime: string): Promise<StoredFile>;
}
