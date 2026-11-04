---
name: radar
description: Use to read the machineVisionRadar catalog or propose a change to it, instead of reading the store directly or reimplementing catalog logic. The agent CLI over validated products and vendors in the project's Firestore - search, ask with citations, fetch, compare, validate, propose - all machine-readable.
---

# radar — agent skill

`python -m radar <noun> <verb>`, run from the repo root, is an agent's way to read the catalog and propose changes.
Its contract, every command, and how it reaches the project or the emulators (`--project`, the token, `--yes`) are
docs/CLI.md; `radar --help` and `radar <noun> --help` list the commands.

## Where to start

- **Read:** `radar product search "<words>"` (the site's ranking, `--semantic` blends vectors in), `radar product get
  <id-or-slug>`, `radar product compare <id> <id>`, `radar org get <id-or-slug>`, `radar source search --url <text>`
  (cite a Source the catalog holds rather than propose it again), `radar catalog ask "<question>"` (cited, else refused).
- **Propose:** `radar product add|edit <changeset.json> --reason R`, `radar proposal submit <draft.json>`, then
  `radar proposal show <id>`; outside agents go through `radar mcp serve` (docs/MCP.md).

## Gotchas

- An agent proposes, never approves (AGENTS.md rule 11).
- Some commands spend on the project's AI caps (docs/CLI.md, Gotchas).
- Product ids are `prd_<id>`. Citing records in agents and models: [docs/LEGAL.md](../../../docs/LEGAL.md).
