# Host contract and event protocol

Every host (Python `maf_labs_host`, .NET `MafLabs.Hosting`) accepts the same arguments:

```
<host> [target] [-p PROMPT|-] [--output text|json|jsonl] [--provider P] [--model M] [--stdio] [--list] [--quiet]
```

- `-p`: run one turn and exit. In `text` mode the answer goes to stdout and the trajectory to stderr. Exit code 0 on success, 1 if the turn failed, 2 for configuration errors.
- `--stdio`: JSON Lines protocol, used by mafx for out-of-process hosts.
  - In: `{"type":"user","text":"…"}`, `{"type":"reset"}`, `{"type":"exit"}`
  - Out: `{"type":"ready","info":{…}}`, then the events of each turn, ending with `turn_completed`; `reset_done` after a reset.

## Events
All events have `type` and `ts` (unix seconds). Events produced inside a workflow also carry `executor_id`.

| type | fields |
|---|---|
| `reasoning_delta` | `text` |
| `text_delta` | `text` |
| `tool_call` | `call_id`, `name`, `arguments` (object) |
| `tool_result` | `call_id`, `result`, `error`, `duration_s` |
| `usage` | `input_tokens`, `output_tokens` (one per model call) |
| `executor_started` / `executor_completed` | `executor_id`, `input` (preview) |
| `workflow_output` | `data` |
| `request_info` | `request_id`, `data` (a workflow asks for input; the next user message answers it) |
| `warning` / `error` | `message` |
| `turn_completed` | `ok`, `text`, `duration_s`, `input_tokens`, `output_tokens`, `model_calls`, `tool_calls` (+ `outputs`, `pending_requests` for workflows) |

Trace files add `run_started` (target, runtime, provider, model, mode, run_id), `user_message` and `session_reset`.
