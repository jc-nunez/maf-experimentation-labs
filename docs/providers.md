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
- **History stays client-side (`store=false`).** With `store=false`, the full history is sent on every model call. That survives server restarts, and long sessions don't hold memory on the server. SGLang also supports `SGLANG_STORE=true`: the server continues from `previous_response_id` and nothing is replayed. That works too, but sessions are lost when the server restarts.
- **Earlier reasoning is not replayed.** SGLang returns reasoning items without `encrypted_content`. Agent Framework (Python) refuses to replay reasoning without it ("Stateless replay cannot reconstruct reasoning item(s)…"). So the `sglang` provider strips reasoning from every request it sends (`SGLangResponsesClient`), along with the compaction flag that marks a message group as containing reasoning. This happens at the request layer because the harness's per-call history middleware re-injects history after any chat middleware runs. SGLang doesn't need the reasoning, live output and traces still show it, and the session history keeps it.
- **.NET compatibility fixes** (applied automatically by the `sglang` provider in `MafLabs.Hosting`):
  - SGLang sends `created_at` as a float. The OpenAI .NET SDK expects an integer and throws `FormatException`, so `SglangCompatPolicy` rewrites these timestamps while the response streams.
  - The .NET SDK sends `"strict": null` on tool definitions, which SGLang rejects, so the provider sets `strict: false` explicitly.
- **Debugging:** `MAFX_DEBUG=1` prints full Python tracebacks and .NET stack traces in error events.
- **Tool calling needs a parser.** SGLang must be started with a tool-call parser that matches the model (`--tool-call-parser …`), and with a reasoning parser if you want reasoning streamed separately. `mafx doctor` warns when the model answers without calling the test tool.
- **Chat Completions fallback.** If a Responses feature misbehaves, set `SGLANG_API=chat` to tell whether the problem is the model or the API layer.

The .NET host reads the same variables. In .NET, `azure-openai` supports API keys only for now, and `foundry` is not wired up yet.
