import { type FC, type ReactNode } from "react";

export interface Fact {
  readonly key: string;
  readonly label: ReactNode;
  readonly value: ReactNode;
  readonly lang?: string;
}

const LAYOUTS = {
  inline: { list: "inline", pair: "inline-block max-w-full break-words mr-3", term: "inline text-muted",
    value: "inline text-fg-secondary tabular-nums" },
  grid: { list: "grid grid-cols-[max-content_1fr] gap-x-3 gap-y-0.5", pair: "contents", term: "text-muted",
    value: "min-w-0 break-words text-fg" },
} as const;

export const Facts: FC<{ facts: readonly Fact[]; layout: keyof typeof LAYOUTS; className?: string }> = ({ facts, layout,
  className = "" }) => {
  const look = LAYOUTS[layout];
  return (
    <dl className={`${look.list} ${className}`}>
      {facts.map((fact) => (
        <div key={fact.key} className={look.pair}>
          <dt className={look.term}>{fact.label}</dt>{" "}
          <dd lang={fact.lang} className={look.value}>{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
};
