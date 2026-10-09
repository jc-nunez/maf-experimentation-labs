# Providers

Choose one with `--provider` or `MAF_PROVIDER`. The default comes from `defaults.provider` in `maf-labs.yaml`. Configure providers in `.env` (template: `.env.example`).

| Provider | Client | Settings |
|---|---|---|
| `sglang` (default) | `OpenAIChatClient` (Responses API), or `OpenAIChatCompletionClient` with `SGLANG_API=chat` | `SGLANG_BASE_URL`, `SGLANG_MODEL`, `SGLANG_API_KEY`, `SGLANG_API`, `SGLANG_STORE` |
| `openai` | `OpenAIChatClient` | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| `azure-openai` | `OpenAIChatClient(azure_endpoint=…)`; API key or Entra ID (`uv sync --extra azure`) | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY` |
| `foundry` | `FoundryChatClient` (`uv sync --extra foundry`) | `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL` |
| `mock` | offline deterministic client | none |

## SGLang notes
- **History stays client-side (`store=false`).** The Responses client normally relies on server-side storage (`previous_response_id`), which self-hosted servers usually don't fully support. With `store=false`, the full history is sent on every turn. Set `SGLANG_STORE=true` only if your server supports stored responses.
- **Tool calling needs a parser.** SGLang must be started with a tool-call parser that matches the model (`--tool-call-parser …`), and with a reasoning parser if you want reasoning streamed separately. `mafx doctor` warns when the model answers without calling the test tool.
- **Chat Completions fallback.** If a Responses feature misbehaves, set `SGLANG_API=chat` to tell whether the problem is the model or the API layer.

The .NET host reads the same variables. In .NET, `azure-openai` supports API keys only for now, and `foundry` is not wired up yet.
