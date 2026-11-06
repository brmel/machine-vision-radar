# Connecting an agent over MCP

One MCP server lets the outside agents the founder issues a token to read the catalog and propose changes to it. Only
the founder approves, at `/admin/queue` or with `radar proposal approve`; no tool approves, edits the catalog or
publishes.

## Where

- **HTTP:** `POST https://<site>/api/mcp` (live: `https://mvradar.web.app/api/mcp`), the streamable HTTP transport,
  stateless: one JSON-RPC 2.0 message a request, one `application/json` body an answer, a notification 202 and no
  body. No session and no stream: any method but `POST` answers 405.
- **Up?** `GET https://<site>/api/health` answers 200 with the release, the deployed commit and the search index's
  version; a directory's check or an agent's retry reads it, never the MCP route.
- **stdio,** on the founder's machine: `MVR_AGENT_TOKEN=mvr_… python -m radar mcp serve`, one message a line in and
  one answer a line out, on the emulators' store, or the project's with `--project <id> --yes` ([CLI.md](CLI.md)).

Both go through `handle` in `radar/adapters/web/mcp.py`. Its methods: `initialize` (protocol `2025-11-25` or
`2025-06-18`), `ping`, `tools/list`, `tools/call`.

## The token

The founder issues each agent its own named token, with a scope, an expiry and limits, from `/admin/agents` or:

```
radar agent-token create "Grok Bot" --scope propose --expires YYYY-MM-DD
```

The token, `mvr_` and 32 hex characters, is shown once; the store keeps only its sha256. The agent sends it on every
request as `Authorization: Bearer mvr_…`. The agent's name is who it is: its proposals carry that name and the token's
id, and every token issued under the name sees them.

## Configuring a client

A client that connects to remote servers takes the URL and the header; the public `/agents` page gives the setup for
Claude Code and Cursor:

```json
{"mcpServers": {"mvradar": {"url": "https://mvradar.web.app/api/mcp", "headers": {"Authorization": "Bearer mvr_…"}}}}
```

A client that runs local servers only uses stdio, from the repo root:

```json
{"mcpServers": {"mvradar": {"command": "python3", "args": ["-m", "radar", "mcp", "serve"],
                            "env": {"MVR_AGENT_TOKEN": "mvr_…"}}}}
```

`app/tests/e2e/emulator/mcp.spec.ts` connects with the protocol's TypeScript client (`@modelcontextprotocol/sdk`).

## The tools

| Tool | Scope | CLI command | Answers |
|---|---|---|---|
| `search_products` | `read` | `product search` | products ranked for a query as the site ranks them |
| `get_product` | `read` | `product get` | one product as its page shows it, with each spec's label and unit |
| `search_sources` | `read` | `source search` | Sources and media Documents by address, vendor, type and date |
| `submit_proposal` | `propose` | `proposal submit` | the proposal filed for the founder's review |
| `list_my_proposals` | `propose` | `proposal list --actor-kind agent --author <name>` | its own proposals |
| `get_proposal_status` | `propose` | `proposal show` | one of its proposals: status, founder's note, changes |

`propose` covers `read`. `tools/list` lists the tools the token's scope allows, each with its title, its input and
output JSON Schemas and its `readOnlyHint`/`destructiveHint` (generated from `contracts/model/tools.json`; only
`submit_proposal` writes). Each answer is in `structuredContent` and, as JSON text, in `content`; the CLI command prints
the same JSON, `product search` without the `hits` wrapper.

`submit_proposal`'s `changeset` is JSON text: `{"changes": [{"op": "put", "entity": {…}, "reason": "…",
"source_refs": ["src_…"]}]}`. Every change is the agent's (`actor_kind: agent`, with its token's id). It is validated
as the CLI validates it, after these merges:

- a new product the catalog holds, by its vendor and a name, or a part number of a scheme marked `names_product`, in
  any case and spacing, is that product: its records take the held product's id, its own product record and the
  matching name or number are dropped, and it is filed as an edit (its reason says so); with no vendor, another
  vendor, or two held products answering, it is filed as new;
- a proposal that creates a held product, by its id, is filed as an edit of it;
- a record that says only what the catalog says is dropped; a proposal left with nothing is refused;
- a record one of the agent's open proposals puts already, compared but for its id, version and provenance, is
  dropped, and so is every record that names it; a proposal left with only its Sources is refused, naming those
  proposals;
- the same proposal filed again counts one more report.

## Limits

Each token has its own, set when it is issued (the defaults are `Limits` in `radar/domain/review/agents/tokens.py`),
counted in the store (`agent_usage`) by the UTC clock:

- **requests a minute:** every message, a notification too;
- **proposals a day:** every `submit_proposal` call, filed, merged or refused.

Over a limit, the request is refused until the next minute or day: HTTP 429 with `Retry-After` in seconds and the
JSON-RPC error `-32002` with the same seconds in `data.retry_after`; over stdio, the same error line.

## Errors

| HTTP | JSON-RPC | When |
|---|---|---|
| 400 | `-32700` | the body is not JSON |
| 400 | `-32600` | not one JSON-RPC 2.0 request or notification (a batch, say) |
| 401 | `-32001` | the token is refused: no such token, revoked, expired, or a tool outside its scope |
| 429 | `-32002` | over a limit, with `data.retry_after` |
| 200 | `-32601` | no such method |
| 200 | `-32602` | no such tool |
| 405 | | any method but `POST` |

A tool that cannot answer returns a result with `isError: true` and the reason as its text: arguments outside its
schema, naming the field (`limit: 0 is less than the minimum of 1`); a change the validator refuses, with its findings;
a change that cites no source (only a Source, a media file or a kind another screen owns need none); another agent's
proposal (`prp_… is not a proposal of Muse's`); a proposal the merges leave empty.

Each call is logged with the agent's name, the tool, its correlation id (shared with its proposal and the audit log),
the outcome and the latency; never the token.
