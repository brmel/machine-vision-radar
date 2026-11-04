import { type FC } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { pageCount } from "../../domain/paths.ts";
import { Button } from "../controls/Button.tsx";

interface PaginationProps {
  page: number;
  pageSize: number;
  totalCount: number;
  onPageChange: (newPage: number) => void;
  navLabel: string;
  previousLabel: string;
  nextLabel: string;
  pageLabel: (page: number, totalPages: number) => string;
  summaryText: (start: number, end: number, total: number) => string;
}

function getPaginationRange(page: number, totalPages: number): Array<number | "..."> {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  if (page <= 4) return [1, 2, 3, 4, 5, "...", totalPages];
  if (page >= totalPages - 3)
    return [1, "...", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
  return [1, "...", page - 1, page, page + 1, "...", totalPages];
}

export const Pagination: FC<PaginationProps> = ({ page: asked, pageSize, totalCount, onPageChange, navLabel,
  previousLabel, nextLabel, pageLabel, summaryText }) => {
  const totalPages = pageCount(totalCount, pageSize);
  if (totalPages <= 1) return null;
  const page = Math.min(asked, totalPages);
  const start = Math.min(totalCount, Math.max(1, (page - 1) * pageSize + 1));
  const end = Math.min(totalCount, page * pageSize);
  const pages = getPaginationRange(page, totalPages);
  return (
    <nav aria-label={navLabel} className="flex flex-col lg:flex-row items-center justify-between gap-3">
      <div className="text-caption font-mono tabular-nums text-muted">{summaryText(start, end, totalCount)}</div>
      <div className="flex flex-wrap items-center justify-center gap-1">
        <Button variant="outline" size="sm" onClick={() => onPageChange(page - 1)} disabled={page <= 1}
          aria-label={previousLabel}>
          <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
          <span className="hidden lg:inline">{previousLabel}</span>
        </Button>
        <div className="flex items-center gap-1 px-1">
          {pages.map((item, index) =>
            item === "..." ? (
              <span key={`ellipsis-${index}`} className="px-2 py-1 text-caption text-muted select-none"
                aria-hidden="true">…</span>
            ) : (
              <button key={item} type="button" onClick={() => onPageChange(item)}
                aria-current={item === page ? "page" : undefined} aria-label={pageLabel(item, totalPages)}
                className={`min-w-8 h-8 px-2 text-caption font-mono font-medium rounded-control transition-colors `
                  + `cursor-pointer tabular-nums flex items-center justify-center ${
                  item === page ? "bg-accent text-on-accent font-semibold shadow-control"
                    : "border border-transparent hover:border-line-strong text-fg-secondary hover:bg-raised"
                }`}>
                {item}
              </button>
            ),
          )}
        </div>
        <Button variant="outline" size="sm" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages}
          aria-label={nextLabel}>
          <span className="hidden lg:inline">{nextLabel}</span>
          <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
};
