import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";
import { ENTITY_KINDS } from "../../src/domain/views.ts";
import { AdminModelSchema } from "../../src/adapters/generated-views-zod.ts";
import { changesOf, chosenSource, newRecord } from "../../src/features/admin/records/drafts.ts";

const model =
  AdminModelSchema.parse(JSON.parse(readFileSync(join(process.env.MVR_E2E_FIXTURE ?? "", "admin-model.json"), "utf8")));
const prefix = (kind: string): string =>
  (ENTITY_KINDS as Record<string, { prefix: string } | undefined>)[kind]?.prefix ?? "";

it("starts a new record of every kind added from a parent's page naming that parent", () => {
  const added = model.entities.flatMap((shape) =>
    shape.fields.filter((f) => f.refs.length > 0 && f.name !== "source_refs").map((field) => ({ shape, field })));
  expect(added.length).toBeGreaterThan(0);
  for (const { shape, field } of added) {
    const parent = `${prefix(field.refs[0])}_0000000000`;
    const record = newRecord(shape, new URLSearchParams({ [field.name]: parent }));
    expect(record, `${shape.id}.${field.name}`)
      .toMatchObject({ id: expect.stringMatching(new RegExp(`^${shape.prefix}_`)),
        [field.name]: field.type === "array" ? [parent] : parent });
  }
});

it("cites the source chosen on every change, and keeps a record's own sources beside it", () => {
  for (const shape of model.entities.filter((e) => !e.provenance)) {
    const sourced = shape.fields.some((f) => f.name === "source_refs");
    const record = { id: `${shape.prefix}_0000000001`, ...(sourced ? { source_refs: ["src_000000000a"] } : {}) };
    const draft = { record, product: null, specs: {}, method: "", source: { existing: "src_000000000b" },
      reason: "Seen" };
    expect(changesOf(model, shape.id, draft, null), shape.id).toEqual([
      { op: "put", entity: sourced ? { ...record, source_refs: ["src_000000000a", "src_000000000b"] } : record,
        reason: "Seen", source_refs: ["src_000000000b"] },
    ]);
  }
});

it("lets an edit drop one of a record's sources: unless another is picked, the change cites one the record "
  + "keeps", () => {
  for (const shape of model.entities.filter((e) => e.fields.some((f) => f.name === "source_refs"))) {
    const before = { id: `${shape.prefix}_0000000001`, source_refs: ["src_000000000a", "src_000000000b"] };
    const record = { ...before, source_refs: ["src_000000000b"] };
    const draft = { record, product: null, specs: {}, method: "", source: chosenSource(null, record), reason: "Seen" };
    expect(changesOf(model, shape.id, draft, { record: before, related: [] }), shape.id)
      .toEqual([{ op: "put", entity: record, reason: "Seen", source_refs: ["src_000000000b"] }]);
  }
});
