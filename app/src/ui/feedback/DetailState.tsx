import type { FC, ReactNode } from "react";
import { ReadState, type ReadStateLabels } from "./ReadState.tsx";
import { StatePanel } from "./StatePanel.tsx";

export interface DetailStateLabels extends ReadStateLabels {
  missing: string;
}

interface DetailStateProps {
  failed: boolean;
  loading: boolean;
  trail: ReactNode;
  labels: DetailStateLabels;
  skeleton: { count: number; type?: "card" | "row" };
}

export const DetailState: FC<DetailStateProps> = ({ failed, loading, trail, labels, skeleton }) => (
  <div className="space-y-3">
    {trail}
    {loading || failed ? <ReadState failed={!loading && failed} labels={labels} skeleton={skeleton} />
      : <StatePanel tone="empty" level={1} title={labels.missing} />}
  </div>
);
