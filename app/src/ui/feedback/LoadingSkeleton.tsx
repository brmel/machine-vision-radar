import { type FC } from "react";
import { Card } from "../page/Card.tsx";

interface LoadingSkeletonProps {
  label: string;
  count: number;
  type?: "card" | "row";
}

const BAR = "bg-raised-hover rounded-chip";

export const LoadingSkeleton: FC<LoadingSkeletonProps> = ({ label, count, type = "card" }) => {
  const items = Array.from({ length: count }, (_, i) => i);
  return (
    <div role="status" aria-busy="true"
      className={type === "row" ? "divide-y divide-line" : "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"}>
      <span className="sr-only">{label}</span>
      {items.map((i) =>
        type === "row" ? (
          <div key={i} aria-hidden="true" className="py-3 px-4 flex items-center justify-between gap-4 animate-pulse">
            <div className={`h-4 w-1/3 ${BAR}`} />
            <div className={`h-4 w-1/2 ${BAR}`} />
          </div>
        ) : (
          <Card key={i} aria-hidden="true" className="space-y-3 animate-pulse">
            <div className={`h-3 w-20 ${BAR}`} />
            <div className={`h-5 w-3/4 ${BAR}`} />
            <div className={`h-3 w-full ${BAR}`} />
            <div className={`h-3 w-2/3 ${BAR}`} />
          </Card>
        ),
      )}
    </div>
  );
};
