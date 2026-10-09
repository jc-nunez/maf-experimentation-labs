# Shared tools

Tools reusable across projects. Each is a self-contained package with a `tool.yaml` that projects reference:

```yaml
# projects/<p>/project.yaml
tools:
  - { name: web-fetch, kind: ref, ref: tools/python/web-fetch }
```

- `tools/python/<name>/`: Python package (`pyproject.toml`, `src/<pkg>/tool.py`, `tool.yaml`). It is a uv workspace member, so `uv sync --all-packages` installs it.
- `tools/mcp/<name>/`: standalone MCP servers that any agent can use (`kind: mcp` in a manifest).
- `tools/dotnet/<Name>/`: .NET class libraries with `AIFunction`s that .NET projects reference.

An entry can point to a single tool or to a list of tools (a *tool pack*); one manifest reference then attaches
all of them.

| Package | Tools | Config |
|---|---|---|
| `python/web-search` | `web_search` (SearXNG JSON API), `fetch_url` (page → markdown via trafilatura; blocks non-public addresses) | `SEARXNG_URL`, `WEB_FETCH_ALLOW_PRIVATE` |

Create one with `mafx new tool <project> <name> --shared`.
