# Host contract and event protocol

Every host (Python `maf_labs_host`, .NET `MafLabs.Hosting`) accepts the same arguments:

```
<host> [target] [-p PROMPT|-] [--output text|json|jsonl] [--provider P] [--model M] [--stdio] [--list] [--quiet]
```

- `-p`: run one turn and exit. In `text` mode the answer goes to stdout and the trajectory to stderr. Exit code 0 on success, 1 if the turn failed, 2 for configuration errors.
- `--stdio`: JSON Lines protocol, used by mafx for out-of-process hosts.
  - In: `{"type":"user","text":"…"}`, `{"type":"approve","decisions":{"<request_id>":"approve|deny|always|always_args"}}`, `{"type":"set_effort","effort":"low"}`, `{"type":"reset"}`, `{"type":"exit"}`
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
| `approval_request` | `request_id`, `call_id`, `name`, `arguments` (a tool call is waiting for approval) |
| `approval_decision` | `request_id`, `name`, `decision` (emitted when an `approve` continues the turn) |
| `warning` / `error` | `message` |
| `turn_completed` | `ok`, `text`, `duration_s`, `input_tokens`, `output_tokens`, `model_calls`, `tool_calls`, `pending_approvals` (+ `outputs`, `pending_requests` for workflows) |

## Tool approvals
Some tools pause the turn until a person decides. Examples: the harness file-access writes, or tools declared with `approval_mode="always_require"`.

1. The host emits `approval_request` events and ends the turn with a non-empty `pending_approvals`.
2. The client answers with `approve`. The decision for each request is one of:
   - `approve`: run this call.
   - `deny`: the agent is told the call was rejected. Requests left out of the message are also denied.
   - `always`: approve this tool for the rest of the session.
   - `always_args`: approve this tool with these exact arguments for the rest of the session.
3. The host continues the same turn. It may ask again until nothing is pending.

How each client decides:
- **`mafx` interactive:** asks for each request (`y`, `a`, `A`, `n`).
- **`mafx -p`:** denies unless `--allow-all-tools` or `--allow-tool NAME` is given.
- **A standalone host with `-p`:** approves with `--allow-all-tools`, denies otherwise.

Trace files add `run_started` (target, runtime, provider, model, mode, run_id), `user_message` and `session_reset`.
