import { type FC } from "react";
import type { SourceView, SpecCell } from "../../domain/views.ts";
import { CELL, Table } from "../data/Table.tsx";
import { formatSpecValueText, specRowLabel, specValueLang, type SpecDefinitions,
  type SpecValueLabels } from "./specFormat.ts";
import { SourceChip } from "./SourceChip.tsx";

interface SpecRun {
  readonly title: string;
  readonly cells: readonly SpecCell[];
}

interface SpecTableProps {
  runs: readonly SpecRun[];
  sources: readonly SourceView[];
  specDefs: SpecDefinitions;
  labels: SpecValueLabels;
}

export const SpecTable: FC<SpecTableProps> = ({ runs, sources, specDefs, labels }) => {
  const sourceById = new Map(sources.map((s) => [s.id, s]));
  const row = (cell: SpecCell) => {
    const source = cell.source === undefined ? undefined : sourceById.get(cell.source);
    if (cell.source !== undefined && !source)
      throw new Error(`SpecTable: ${cell.key} cites missing source ${cell.source}`);
    return (
      <tr key={cell.key} className="hover:bg-sunken/60">
        <td className={`${CELL} w-2/5 text-caption text-muted`}>{specRowLabel(cell.key, specDefs, labels.locale)}</td>
        <td className={CELL}>
          <span lang={specValueLang(cell.value, labels.locale)}
            className={cell.value === undefined ? "italic text-muted" : "tabular-nums text-fg"}>
            {formatSpecValueText(cell.value, labels, "label")}
          </span>{" "}
          {source && <SourceChip source={source} locale={labels.locale} />}
        </td>
      </tr>
    );
  };
  return (
    <Table className="spec-table" groups={runs.map((run) => (
      <tbody key={run.title} className="divide-y divide-line-subtle border-t border-line first:border-t-0">
        <tr>
          <th scope="rowgroup" colSpan={2}
            className={`${CELL} bg-sunken text-left text-caption font-heading text-fg-secondary`}>{run.title}</th>
        </tr>
        {run.cells.map(row)}
      </tbody>
    ))} />
  );
};
