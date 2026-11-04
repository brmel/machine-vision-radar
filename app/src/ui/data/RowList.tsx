import type { FC, ReactNode } from "react";

const FRAME = "divide-y divide-line border border-line rounded-control";

export const RowList: FC<{ ordered?: boolean; label?: string; children: ReactNode }> = ({ ordered, label,
  children }) => (ordered
  ? <ol aria-label={label} className={FRAME}>{children}</ol>
  : <ul aria-label={label} className={FRAME}>{children}</ul>);
