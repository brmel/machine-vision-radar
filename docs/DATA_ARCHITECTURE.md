# Data architecture

The catalog's data: entities, value types, invariants and how the model changes. The executable definition is
`contracts/model/` and the data's `data/registry/`; [contracts/AGENTS.md](../contracts/AGENTS.md) maps them
and the files `radar model generate` writes from them. The validator (`radar/domain/validation/`) enforces the invariants on every
write (the `CatalogWriter`), on the store (`radar store validate`) and on a catalog folder (`radar model validate`).
The store, the read model and the read and write paths: [SYSTEM.md](SYSTEM.md); search and every AI use:
[SEARCH.md](SEARCH.md).

**The interface** is one object, `Model` (`radar/domain/model/model.py`), holding the schema and the registry; the
wiring loads it once and every caller takes it.

- `Model.parse(raw, kind, where)`: the one edge parser of records, JSON in and the generated `kind` out, or a
  `ParseError` naming the path.
- `Model.check(catalog, scope, today)`: every `Rule` (`radar/domain/validation/rule.py`) on the catalog, returning an
  immutable `Verdict` of `Finding`s (rule, entity, message, `Severity` error or warning). The `scope` is `Whole()`
  for the store (`store validate`) and a folder `model validate` reads, else `Part()`: a write's neighborhood, a
  catalog `store load` seeds, a catalog file or the registry alone.
- `parse_changeset(raw, model)` (`radar/domain/model/history/changeset.py`): a changeset's JSON into a `Changeset`
  whose `PutEntity` holds a parsed entity, its version left for the writer to number; a record that does not parse is
  a `record_parse` finding. The domain hands changes on as entities, and `as_record` turns one back into a record only
  to be stored, compared or shown.
- A refused write raises `InvalidChangeset`, which holds findings only.

## 1. Principles

1. **Technology-neutral:** machine-vision concepts, independent of databases, wire formats or UI state.
2. **Provenance** ([AGENTS.md](../AGENTS.md) rule 11): every entity with `source_refs` cites at least one public
   Source, and a Change cites one when it sets a sourced fact. A record's identity and classification (names,
   identifiers, slug, category, tags, country, summary, links) is curated, not a sourced fact. Unknown values are
   omitted, never defaulted; dates carry their precision, with no invented day or month.
3. **Sparse facts:** a product stores only the facts it has, as typed claims on registry specs; no table of nulls.

## 2. Value types

`contracts/model/value_types.json` defines every value type (fields, patterns, the registry a field draws from) and
every enum a field names by type, which `model generate` emits once per runtime. Among them: EntityId (§8); Instant
(UTC, `Z`, from the clock); LocalizedText (`en` required, the fallback); PartialDate (a value and its `precision`:
year, half, quarter, month or day); Quantity and Range (numbers in a registry unit); and ClaimValue, one tagged variant:
`quantity` or `range` for a quantity spec, `term`, `terms`, `boolean`, `string`, or, for any spec but a term set,
`none` with the reason a source gives (an `absence_reasons` term), which the page shows, coverage counts and facets
leave out. Optional fields are omitted when unknown; `null` is rejected.

## 3. Entities and topology

```
Organization ──OrgRelation (valid-time)── Organization
Organization 1──* ProductOrgRole *──1 Product
Product[family] 1──* Product[model] 1──* Product[variant]
Product *──1 Category 1──1 CategoryProfile ──> SpecDefinition, SpecGroup
Product | Organization 1──* Claim *──1 SpecDefinition
Product | Organization 1──* Name, Identifier, AltName
Product 1──* ProductVersion, Offering, LifecycleEvent, ObservedStatus
Product | ProductVersion *──Relation (valid-time)──* Product | ProductVersion
sourced entity *──1..* Source 0..1── Document *──1..* Product | ProductVersion | Organization
Every entity 1──* Change (transaction-time history; `version` counts them)
```

### 3.1 Entities

`contracts/model/entities.json` defines each entity: its id prefix, its collection, its label, its fields, whether it
is `internal` (never published: AltName, EvalQuery, and AiCap, an AI use's model and caps) and whether it is
`provenance` (a Source; a Document, one kept file of any kind with its `rights`, [SYSTEM.md](SYSTEM.md) §2): a change
to a provenance record cites no source. Every entity carries `version`, from 1, the count of its Changes; a Change's
`version` is the one it produces.

- **Names.** An AltName is still a search term: the product view's `aliases`, in the page's data and never displayed,
  carry the product's and its vendor's AltNames and non-primary Names, which the search index matches as the name.
- **Lifecycle.** A LifecycleEvent has a `type`, a `state`, a date, sources, and optional `caused_by`, `revised_by` and
  `successor`; an ObservedStatus is a status a source states without a date. The displayed status is derived, never
  stored: the newest event in an `occurred` state whose type `sets_status`, else the ObservedStatus.
- **News.** A FeedItem is a news article. A draft is a proposal in the review queue; approving it publishes it, and
  review sets `published_at` from its clock (the field is `set_on_approval`). `authorship` says who wrote it: `human`,
  `template` (feed.json's rules, from the change log) or `ai_draft` (the article model, from one catalog record only);
  an `ai_draft` article's page and the feeds say it was drafted with AI and reviewed on its `published_at`.
- **Files kept.** Only a file whose type a `document_kinds` term lists is kept ([SYSTEM.md](SYSTEM.md) §2). Firmware
  and CAD files are not: no kind lists their types, so a release's download page is cited as a Source and the
  ProductVersion carries the release.

## 4. Versions vs. Changes: the world vs. us

- **ProductVersion is the world:** a vendor's release (firmware, software, a model's weights), with its own claims,
  offerings and lifecycle events; claims that depend on it use `applies_to_versions`.
- **Change is us:** a record's append-only, transaction-time history, one event per write: the `version` it produces,
  `recorded_at`, `actor_kind` (`human`, `agent`, `import`), `actor`, `reason`, a `patch` of field-path ops (version
  1's creates the entity), `source_refs`, an optional `proposal` and the `correlation_id`. Replaying the patches gives
  the stored entity (`radar/domain/model/history/`, through the `ChangeLog` and `VersionStore` ports).
- **World time vs. system time:** `valid_from` / `valid_to` say when a fact was true in the world; `recorded_at` when
  the catalog recorded it.

## 5. Registry, taxonomy and sparse specs

`data/registry/` holds the units, dimensions, specs, spec groups, categories, profiles and vocabularies
(shapes in `registry_types.json`) and three settings files typed in `views.json`: `search.json`
([SEARCH.md](SEARCH.md)), `feed.json` (the news desk's rules) and `ai.json` (the models an AI use may run, their
prices, each use's default model and caps). A new spec, category, term or language is a registry change only (recipes:
[contracts/AGENTS.md](../contracts/AGENTS.md)).

- **SpecDefinition:** one `datatype`: `quantity`, `term`, `term_set`, `boolean` or `string` (a name never translated,
  such as a sensor's model; no free text). A quantity names its `dimension` and its `unit`, the one pages state and
  filter it in, its plausible `bounds`, and may say which way is `better` (`higher` or `lower`) so a comparison marks
  the better value. A claim states a number in any unit of the dimension, as its source did; the read model publishes
  it in the spec's unit, rounded to its `precision`, so the browser converts nothing. A term or term-set spec names
  its `vocabulary`. A spec may carry a `description` (what is measured, under what convention), `aliases` (the words
  datasheets use; search and the extraction prompts read them) and `external` ids in other standards' dictionaries
  (identifiers, never definitions).
- **Claims:** a fact with several values is one term-set claim; any other spec has one value ranked first per subject.
- **Units:** a unit has the `symbol` pages show, its dimension, its UCUM code (`ucum`) and a `factor`: a value in the
  dimension's canonical unit (factor 1) is the value in this unit times the factor; a test checks each against pint.
- **Terms:** what a term means is a mark on it, never a branch in code: an identifier scheme's `pattern`,
  `gs1_check` and `names_product`, a role's `vendor_for_view` (a product's vendor is the organization of the role
  ranked first), a relation type's `from_side` and `to_side`, a lifecycle state's `occurred`. The Term type in
  `value_types.json` states every mark.
- **Relations:** a Relation's `basis` is `asserted` (a source says so) or `derived` (computed).

### 5.1 Layers and the category tree

Three concerns stay apart: **SpecDefinitions** (the global attribute catalog), **CategoryProfiles** (per category,
which specs a page shows, must publish and filters on) and **navigation** (the `domains` and the ordered
`pipeline_stages` vocabularies). A product belongs to **exactly one leaf category**. A category has a dotted id
(`imaging.cameras.area_scan`), a domain, its pipeline stages, a glyph and one profile; one whose products others use
as components names a `component_hub` (a path and a relation type), and each product so used gets a hub page listing
those that use it. The read model carries all of it, so a new category, domain or stage needs no code change.

### 5.2 CategoryProfile

A profile lists its category's own specs and the spec groups it takes (`spec_groups.json`: sets such as an image
sensor's); the registry puts the groups' specs after the profile's own detail ones and refuses a spec named twice. A
product may take more groups (`Product.spec_groups`, a smart camera's compute), whose specs it may claim and its page
shows.

- `core`: the distinguishing specs, on cards and first on the product page and in a comparison; `detail`: the
  profile's other specs, each row a group gives naming its group.
- `versions`, `offerings`: the ProductVersion and Offering fields a page shows.
- `facets`: the specs a category page filters on, in the spec's unit, the kind read off the datatype (term: one
  option, term set: several, quantity: a range, boolean: yes or no); a listing shows those its products publish, the
  most published first.
- `required`: the specs a product must state; every other spec is optional. A product missing one is a warning in a
  whole catalog, `quality coverage` counts them per category, and its page is `noindex` and out of the sitemap.
- `axis_dependent_keys`: specs a family's variants may vary along their declared axes.

### 5.3 Category rules

- Barcode verifiers and print-grading instruments are `imaging.code_readers`, told apart by specs
  (`grading_standards`) and capability terms.
- Thermal and thermographic cameras are one category, `imaging.thermal_cameras`; spectral bands are specs
  (`spectral_range`, `sensor_technology`, `thermal_sensitivity_netd`) and tags (`swir`).
- A SWIR area-scan or line-scan camera stays in its camera category; its band is its `spectral_range`.
- Vision software capabilities are term-set specs, not categories. The `ai_stack` group (methods, tasks, model
  formats, inference hardware, APIs) is taken by every category whose products build or run models; a product can
  take it through `spec_groups`. An AI agent that builds or runs a vision application belongs to its role's category,
  with `agentic` among its methods and its configuration style, and `model_context_protocol` among its APIs when it
  speaks MCP.
- **New tech enters as a tag**, and becomes a category or profile only when its products need a spec shape no profile
  can express.

### 5.4 The anti-overfit rule

Categories are pipeline roles; technologies are vocabulary terms and specs. Every vision system does the same six
things: illuminate → acquire → transport → process → decide → act. Roles change on decade timescales; sensing
principles, AI paradigms and interfaces change yearly and live one level down. `imaging.cameras.3d` is one category,
and stereo, structured light, ToF, triangulation or lidar are values of its `principle` spec; an event-based camera is
an area-scan camera with the `event_based` tag. The test for a proposed category: "Will this still be a distinct
product kind in 20 years?" If not, it is a term or a tag. History is first-class: discontinued products keep their
records, and vocabularies keep older terms (analog, FireWire, USB2) so a 2005 camera records as faithfully as a
current one.

### 5.5 Scope and boundaries

**In scope:** anything whose primary function is in the vision pipeline above, plus laser marking and laser
projection/guidance systems (`systems.laser_marking`), which vision vendors sell and which close the mark-and-verify
loop. **Out of scope:** mobile robots and drones, standalone robot arms, safety laser scanners, optical micrometers,
generic IPCs/COMs/SOMs without AI acceleration or vision interfaces, life-science instruments (streak cameras,
confocal microscopy), process equipment other than laser marking, bare ISP chips, licensable vision-processor IP,
non-vision developer tools, robotics platforms where vision is incidental, generic IoT/AI platforms, RF/mmWave radar
and other non-optical sensing, pure distributors, discrete photodetectors, HMIs and panel PCs, document AI, and
broadcast capture unless marketed for machine vision. **Boundaries:**

- Bare sensor modules → `imaging.sensors`; board-level camera engines → the camera category with the `board_level`
  tag; finished cameras → the camera category.
- A turnkey cell that bundles a robot is `systems.vision_systems` (tags `turnkey`, `robot_ready`).
- `compute.edge_ai` needs AI acceleration or explicit vision interfaces; controllers with trigger, lighting or machine
  I/O are `compute.vision_controllers`.
- Pushbroom hyperspectral → `imaging.cameras.line_scan` + `hyperspectral`; snapshot hyperspectral →
  `imaging.cameras.area_scan` + `hyperspectral`; point and benchtop instruments → `imaging.spectrometers`.
- A scientific camera is an area-scan camera; "smart" needs on-device processing and is a tag.
- A vendor with services only gets an organization record and no products.

## 6. Validation

Parsing (`Model.parse`, driven by the model schema) rejects a wrong shape before any rule
runs: an unknown or missing field, a wrong type, a bad id, an enum value outside its list, a LocalizedText without
`en` or with empty text, NaN or Infinity, a number below its minimum (a Claim `rank` below 1), too few items (empty
`source_refs` where one is required). The rules (`radar/domain/validation/rules/`) then check:

- **registry_integrity:** a quantity spec has a known dimension and a unit of it, and only a quantity takes those,
  `better`, `bounds` (min below max) and `precision`; only a term or term-set spec names a vocabulary, a known one; a
  dimension's canonical unit is one of its units with factor 1, and no two of its units share a UCUM code; each category
  has one profile, with valid keys, a core spec and facets on term, term-set, quantity or boolean specs, and every spec
  is in a profile's core or detail; every vocabulary is used; every registry field bound to a registry holds its ids; a
  component hub has a path of its own, free of the site's routes, and a known relation; in a vocabulary no two terms
  share a label or alias, and a description (in every language) or a relation side one term gives, every term gives;
  `proposal_kinds` files each event once; ai.json sets each AI use once, each on one of its models but all uses together
  on none; version schemes match the orderings in `radar/domain/model/versions.py`.
- **vocabularies:** every registry-bound field of a record holds an id of that registry.
- **no_filler_text:** no placeholder or marketing filler in a text field: the `placeholders` and `anywhere` patterns of
  `data/no_filler.json`, which the site's slop guard also reads.
- **entity_ids:** an id carries its entity's prefix and is unique; no Identifier appears twice, and each is the whole
  of its scheme's `pattern`, passes the GS1 check digit where the scheme has `gs1_check`, and names a kind of subject
  in its scheme's `subjects`.
- **unique:** no two records of a kind hold one value in a field marked `unique` (a slug, a Source's `url`: one URL,
  one Source; a Document's `sha256`: one file, one Document), each holder named; and no Change replaces a field marked
  `permanent` (a slug, a Document's `sha256`), a value that never changes once set. `radar source dedupe` merges a
  URL's extra Sources through review.
- **countries:** an organization's `country` is an assigned ISO 3166-1 alpha-2 code.
- **references:** every reference resolves to an entity of a kind its `refs` allow (a Change may still name a record
  withdrawn since, if recorded while it existed); a product's thumbnail is an image Document about it under public
  rights; a Document of a kind marked `version` names a ProductVersion.
- **category_and_roles:** every product has a ProductOrgRole, names an organization in a role once, and has a slug of
  §8's shape; in a whole catalog (`store validate`, or `model validate` on a folder), an empty category is a warning,
  a coverage gap.
- **variant_axes:** a variant has a parent and differs from it only on its axes and the profile's
  `axis_dependent_keys`.
- **versions:** a product's versions order by their scheme; a version-scoped claim targets its own subject and matches
  a version.
- **ai_caps:** an AiCap's id is keyed on its use, so each use has one; its model is one ai.json lists, and all uses
  together run none.
- **claim_values:** the value is a variant the spec's datatype takes, its unit measures the spec's dimension, its
  numbers sit inside the spec's bounds, a range runs from its min up to its max, its terms come from the spec's
  vocabulary, each once, and a spec but a term set has one value ranked first per subject; a relation's qualifiers are
  keyed by spec and pass the same checks.
- **claim_profile:** a product's claims use specs of its category's profile, groups included, or of the spec groups it
  takes; in a whole catalog, a product with no claim of a spec its profile marks `required` is a warning.
- **dates:** a PartialDate matches its precision; no date or Instant is in the future, except fields marked
  `future_allowed` and a LifecycleEvent in an `expected` state with a published cited Source, flagged for revision
  once its date passes.
- **lifecycle:** an event in a `superseded` state names its reviser (same product and type) in `revised_by`; only an
  event of a type marked `names_successor` names a successor, which has a relation of a type marked `succeeds` to the
  product.
- **source_integrity:** a Source carries a URL or a Document.
- **source_preference:** a quantity claim backed only by an inherited record may not outrank a datasheet claim.
- **document_integrity:** [SYSTEM.md](SYSTEM.md) §2.
- **changes:** an entity's change versions run 1..n without gaps, n its stored `version`; the patches replay to the
  stored entity (or to nothing after a retraction); a change that sets a sourced fact cites a source; a `proposal` has
  the proposal id shape.
- **feed:** an article's `cites` is exactly what its sentences cite (so withdrawing one finds the article, and
  **references** refuses it while cited), and its `event_source` is among them; `event_date` and `event_source` come
  together; `revised_at` only once published; the byline is feed.json's, the brand's, never a personal name; a slug is
  lowercase words joined by hyphens, an address under /news/.

## 7. Evolving the model

The model and the registry change in place; there are no dataset releases, and the Change log keeps who changed
what. No code keeps an earlier shape ([AGENTS.md](../AGENTS.md) rule 10). A registry entry carries no status: it is
removed once nothing uses it (no record, fixture, code or other entry), after a changeset moves the records holding
it. The registry lives with the data, in `data/registry/`; `radar model generate` lays out its JSON with the
contracts', and `--check` fails on a file off that layout.

## 8. Permanent ids

Product and organization ids and slugs are permanent, so no URL ever needs a redirect: a record leaves the read model
only through a retract Change, and `entities.json` marks slugs `unique` and `permanent`, which rule `unique` checks.

- **Ids** are `<prefix>_` + 10 lowercase Crockford base32 characters, opaque, kept by the store as they are. A new one
  is keyed on what makes the record that one, a Document's on its file's sha256 for example (`keyed` in
  `radar/domain/model/history/ids.py`: 50 bits of the sha256 of `<prefix>:<key>`).
- **Slugs** are stored, never recomputed: a product's is `<maker>__<product>`, the maker part its maker's slug or a
  short form of it; an organization's is its name in lowercase with every run of other characters turned into `-`.

## 9. The current source

The read model shows one source per value: among the sources its claims cite, the one whose type has the first
`preference` in the `source_types` vocabulary, then the newest `retrieved_at`, then the smallest id. The store keeps
every citation; past sources belong to the product's History view.
