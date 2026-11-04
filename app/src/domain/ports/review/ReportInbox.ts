export interface ErrorReport {
  readonly subject: string;
  readonly message: string;
  readonly sourceUrl?: string;
}

export interface Protection {
  readonly name: string;
  readonly owner: string;
  readonly links: readonly [privacy: string, terms: string];
}

export interface ReportInbox {
  readonly protection: Protection | null;
  prepare(): Promise<void>;
  report(report: ErrorReport): Promise<"filed" | "counted">;
}
