import { type FC, type ReactNode } from "react";

interface Column {
  readonly head: ReactNode;
  readonly className?: string;
  readonly sort?: "ascending" | "descending" | "none";
}

export const CELL = "px-3 py-1.5 align-top";
export const NUM = "text-right tabular-nums whitespace-nowrap";
export const ROW_HEAD = `${CELL} text-left font-normal text-muted`;

interface TableProps {
  columns?: readonly Column[];
  label?: string;
  caption?: string;
  className?: string;
  children?: ReactNode;
  groups?: ReactNode;
}

export const Table: FC<TableProps> = ({ columns, label, caption, className = "", children, groups }) => (
  <div className="scroll-cue overflow-x-auto rounded-card border border-line">
    <table aria-label={label} className={`w-full border-collapse text-left text-body ${className}`}>
      {caption && <caption
        className={`${CELL} text-left text-caption text-muted border-b border-line`}>{caption}</caption>}
      {columns && (
        <thead>
          <tr className="border-b border-line bg-sunken text-caption text-muted">
            {columns.map((column, n) => (
              <th key={n} scope="col" aria-sort={column.sort}
                className={`${CELL} font-medium ${column.className ?? ""}`}>{column.head}</th>
            ))}
          </tr>
        </thead>
      )}
      {groups ?? <tbody className="divide-y divide-line-subtle">{children}</tbody>}
    </table>
  </div>
);
