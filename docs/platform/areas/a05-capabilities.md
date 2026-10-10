# A5 Capabilities

Map: [platform map](../map.md) · Maturity: **Partial** · Review: [2026-10-10](../../reviews/2026-10-10-state-review.md)

## Purpose
Tools agents can call: function tools, tool packs, shared tools, MCP, OpenAPI, harness tools.

## Current state
| Capability | Python / where | Status | .NET |
|---|---|---|---|
| Function tools | projects | Built | Built (code registration) |
| Tool packs and shared tools (`kind: ref`) | `runtime.py`, `tools/` | Built | Missing |
| Web search and fetch | `tools/python/web-search` | Built | Missing |
| MCP (stdio, http, websocket) | `runtime.py` | Partial | Missing |
| OpenAPI | `manifest.py` | Stub | Missing |
| Harness tools | MAF | Built | Built |

## Gaps
- Shared tools are Python only (.NET agents have no web tools)
- MCP: no auth headers or env in the manifest; no MCP server in the repo
- OpenAPI kind is a stub
- fetch_url extraction blocks the event loop (F8); no proxy support (F9)

## Features
Requirements live at feature level: `docs/platform/features/<area>-<feature>.md` (created when we drill in).

| ID | Feature | What it does | Python | .NET | Requirements |
|---|---|---|---|---|---|
| A5.F1 | Function tools and packs | `@tool`, one entry for several tools | Built | Built (code) | not yet |
| A5.F2 | Shared tools by reference | `kind: ref` packages under `tools/` | Built | Missing | not yet |
| A5.F3 | MCP tools | stdio, http, websocket servers; auth and secrets for personal and business systems | Partial | Missing | not yet |
| A5.F4 | OpenAPI tools | tools from an OpenAPI spec | Stub | Missing | not yet |
| A5.F5 | Web tools | search and safe fetch | Built | Missing | not yet |
| A5.F6 | Harness tools | todos, modes, file memory, file access | Built | Built | not yet |

## Items
| ID | Item | Stage |
|---|---|---|
| | | |

## Decisions
| ID | Decision | Date | Item |
|---|---|---|---|
| | | | |
