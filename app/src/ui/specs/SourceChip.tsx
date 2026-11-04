import { type FC } from "react";
import type { SourceView } from "../../domain/views.ts";
import { formatDate, localized } from "./specFormat.ts";

interface SourceChipProps {
  source: SourceView;
  locale: string;
}

export const SourceChip: FC<SourceChipProps> = ({ source, locale }) => {
  const text = <><span className="whitespace-nowrap">{localized(source.type.label, locale)} ·</span>{" "}
    <span className="whitespace-nowrap">{formatDate(source.retrieved_at, locale)}</span></>;
  const className = "source-chip inline-block max-w-full rounded-chip bg-sunken px-1 text-micro leading-4 text-muted";
  if (!source.url) {
    return <span className={className} data-source-id={source.id}>{text}</span>;
  }
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      title={source.title ?? source.url}
      data-source-id={source.id}
      className={`${className} hover:text-fg hover:underline`}
    >
      {text}
    </a>
  );
};
