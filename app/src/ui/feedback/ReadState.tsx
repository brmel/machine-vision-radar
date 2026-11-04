import type { FC } from "react";
import { LoadingSkeleton } from "./LoadingSkeleton.tsx";
import { StatePanel } from "./StatePanel.tsx";

export interface ReadStateLabels {
  loading: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
}

interface ReadStateProps {
  failed: boolean;
  labels: ReadStateLabels;
  skeleton: { count: number; type?: "card" | "row" };
  level?: 1 | 2;
}

export const ReadState: FC<ReadStateProps> = ({ failed, labels, skeleton, level = 1 }) =>
  failed
    ? <StatePanel tone="error" level={level} title={labels.errorTitle} description={labels.errorDescription}
      retryLabel={labels.retry} />
    : <LoadingSkeleton label={labels.loading} count={skeleton.count} type={skeleton.type} />;
