import type { FC, ReactNode } from "react";
import { StatePanel } from "../../ui/index.ts";
import { ReadState } from "./ReadState.tsx";

interface DetailStateProps {
  failed: boolean;
  loading: boolean;
  trail: ReactNode;
  missing: string;
  skeleton: { count: number; type?: "card" | "row" };
}

export const DetailState: FC<DetailStateProps> = ({ failed, loading, trail, missing, skeleton }) => (
  <div className="space-y-3">
    {trail}
    {loading || failed ? <ReadState failed={!loading && failed} skeleton={skeleton} />
      : <StatePanel tone="empty" level={1} title={missing} />}
  </div>
);
