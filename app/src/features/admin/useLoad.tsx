import { useState, type FC, type FormEvent, type ReactNode } from "react";
import { RefusedChange } from "../../domain/ports/review/Review.ts";
import { AppLink, LoadingSkeleton, Pagination, StatePanel, formatNumber, prevented, useRead } from "../../ui/index.ts";
import { useI18n } from "../../shell/i18n/index.tsx";
import { usePagerLabels } from "../../shell/i18n/labels.ts";
import { logger } from "../../shell/logger.ts";
import { pageOf } from "../../domain/paths.ts";
import { useAdmin } from "./model.ts";

interface Loaded<T> {
  value: T | null;
  failed: boolean;
  reload: () => void;
  pending: ReactNode;
}

export function useLoad<T>(load: () => Promise<T>, key: string, skeleton = 3, level: 1 | 2 = 1): Loaded<T> {
  const { t } = useI18n();
  const [round, setRound] = useState(0);
  const reload = () => setRound((n) => n + 1);
  const read =
    useRead(load, `${key}#${round}`, (err) => logger.error("admin: a read failed", { page: "admin", key }, err));
  const pending = read.error ? <StatePanel tone="error" level={level} title={t("errorTitle")}
    retryLabel={t("errorRetry")} /> : <LoadingSkeleton label={t("loading")} count={skeleton} />;
  return { value: read.isLoading || read.error ? null : read.value, failed: read.error, reload, pending };
}

export type Paged<P> = Loaded<P> & { count: ReactNode; pager: ReactNode };

const ROWS = 20;

export const pageRows =
  <T,>(rows: readonly T[], page: number): readonly T[] => rows.slice((page - 1) * ROWS, page * ROWS);

export function usePaged<P extends { readonly total?: number }>(load: (cursor?: string) => Promise<P>, key: string,
  path: string, search: string,
                                                              skeleton = 3): Paged<P> {
  const { onNavigate } = useAdmin();
  const { t, locale } = useI18n();
  const page = pageOf(search);
  const list = useLoad(() => load(page > 1 ? String((page - 1) * ROWS) : undefined), `${key}?${search}`, skeleton, 2);
  const go = (to: number) => {
    const params = new URLSearchParams(search);
    if (to > 1) params.set("page", String(to));
    else params.delete("page");
    const query = params.toString();
    onNavigate(query ? `${path}?${query}` : path);
  };
  const total = list.value?.total ?? 0;
  const count = list.value
    ? <p className="text-caption text-muted">{t("adminInAll", { count: formatNumber(total, locale) })}</p> : null;
  return { ...list, count, pager: <Pager page={page} total={total} onPage={go} /> };
}

const refusalOf = (err: unknown, failed: string): readonly string[] =>
  (err instanceof RefusedChange ? [err.message, ...err.findings] : [failed]);

export function useProblem(what: string): { alert: ReactNode; say: (problem: readonly string[]) => void;
  refuse: (err: unknown) => void } {
  const { t } = useI18n();
  const [problem, say] = useState<readonly string[]>([]);
  const refuse = (err: unknown) => {
    logger.warn(`admin: ${what} was refused`, { page: "admin" }, err);
    say(refusalOf(err, t("adminFailed")));
  };
  const alert = problem.length > 0 && <ul role="alert" className="w-full text-caption text-danger">{problem.map((p) =>
    <li key={p} className="break-words">{p}</li>)}</ul>;
  return { alert, say, refuse };
}

export function useSubmit<T>(what: string, run: () => Promise<T>, done: (value: T) => void): { busy: boolean;
  submit: (event: FormEvent) => void; alert: ReactNode } {
  const [busy, setBusy] = useState(false);
  const { alert, say, refuse } = useProblem(what);
  const submit = prevented(() => {
    setBusy(true);
    say([]);
    return run().then(done, (err: unknown) => {
      refuse(err);
      setBusy(false);
    });
  });
  return { busy, submit, alert };
}

export const Pager: FC<{ page: number; total: number; onPage: (page: number) => void }> = ({ page, total, onPage }) => {
  const { t } = useI18n();
  const labels = usePagerLabels();
  const summaryText = (start: number, end: number, all: number) => t("paginationRows", { start, end, total: all });
  return <Pagination page={page} pageSize={ROWS} totalCount={total}
    onPageChange={onPage} {...labels} summaryText={summaryText} />;
};

export const AdminLink: FC<{ to: string; className: string; children: ReactNode }> = ({ to, className, children }) => {
  const { onNavigate } = useAdmin();
  return <AppLink href={`/admin${to}`} onOpen={() => onNavigate(to)} className={className}>{children}</AppLink>;
};
