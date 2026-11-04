import { type FC } from "react";
import { Button } from "../controls/Button.tsx";
import { TYPE } from "../theme/typography.ts";

interface Common {
  title: string;
  description?: string;
  level?: 1 | 2;
}

type StatePanelProps =
  | (Common & { tone: "empty"; action?: { label: string; onClick: () => void } })
  | (Common & {
      tone: "error";
      retryLabel: string;
    });

const BOXES = { empty: "border-dashed border-line-strong bg-sunken/50",
  error: "border-danger-line bg-danger-bg/50" } as const;

export const StatePanel: FC<StatePanelProps> = (props) => {
  const { tone, title, description, level = 2 } = props;
  const Heading = level === 1 ? "h1" : "h2";
  const action = props.tone === "error" ? { label: props.retryLabel, onClick: () => window.location.reload() }
    : props.action;
  return (
    <div role={tone === "error" ? "alert" : undefined}
      className={`flex flex-col items-center gap-2 p-5 text-center rounded-card border ${BOXES[tone]}`}>
      <Heading className={level === 1 ? TYPE.title : TYPE.section}>{title}</Heading>
      {description && <p className="text-body text-muted max-w-md">{description}</p>}
      {action && (
        <Button variant={tone === "error" ? "primary" : "secondary"} size="sm" onClick={action.onClick}
          className="mt-2">
          {action.label}
        </Button>
      )}
    </div>
  );
};
