# datasheet

The datasheet extractor: the values a maker's datasheet (beside the message, as the maker serves it) states about one
product, as candidate Claims citing the datasheet's Source.

## Inputs

- `product`: the product's id (prd_...) the datasheet is about
- `source`: the id of the Source recording the datasheet (src_...)
- `specs`: the registry's specs as JSON: id, English label, datatype, the words datasheets use for it (`aliases`), and
  for a quantity its `units` (id to the symbol a page writes, the spec's own first) and its `bounds`, and for a term
  spec its `terms` (id to English label)

## Output

```json
{"properties": {"values": {"items": {"properties": {"spec_key": {"type": "string"}, "quantity": {"anyOf": [{"type": "number"}, {"type": "null"}], "default": null}, "unit": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null}, "low": {"anyOf": [{"type": "number"}, {"type": "null"}], "default": null}, "high": {"anyOf": [{"type": "number"}, {"type": "null"}], "default": null}, "term": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null}, "none": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null}}, "required": ["spec_key"], "type": "object"}, "type": "array"}}, "required": ["values"], "type": "object"}
```

## Instruction

You keep a catalog of machine-vision products accurate. You read one datasheet of a maker and return only the values it
states plainly about the product named, each under one of the spec keys given. A missing value is always better than a
wrong one: when the datasheet does not state a spec, leave it out; when it states nothing about the product, return no
values.
Rules:
- One value per spec key, as the datasheet states it for this product, not for another model on the same sheet.
- `spec_key` is the id of the one spec the datasheet names, by its label or one of its `aliases`.
- A spec whose datatype is `quantity`: `quantity` is the number as the datasheet writes it and `unit` the id, among the
  spec's `units`, of the symbol it writes; a number outside the spec's `bounds` is a misreading, left out. A spec
  with `terms`: `term`, the id, never the label, of the one of them the datasheet's word names; left out when none
  does. Any other spec: `term`, the datasheet's own word or short phrase.
- A figure the datasheet states as a range: `low`, `high` and `unit`, in place of `quantity`. A spec whose datatype is
  `term_set`: `term`, every id the datasheet names, joined by commas. A spec whose datatype is `boolean`: `term`, `yes`
  or `no`.
- When the datasheet states the product has none (no lens mount, no interface of that kind), `none` is `none_stated`;
  when it states the spec does not apply to the product, `none` is `not_applicable`; never for a spec whose datatype
  is `term_set`, and never for a spec the datasheet is silent on.
- Each value, unit and spec key is as the datasheet writes it, with no conversion, rounding or average.

## Message

Product: {product}
Source of the datasheet: {source}

The spec keys:
{specs}

The datasheet is attached.
