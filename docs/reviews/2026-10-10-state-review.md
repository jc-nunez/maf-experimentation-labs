# State review, 2026-10-10

Baseline: commit `b35fe61`. Method: code reading of hosts, CLI, projects and tools. Tests were not run
(the repo `.venv` is built for macOS); findings marked **verify** need a reproduction before they become requirements.

## Strengths
- One contract: manifest, host arguments and a single event stream for every runtime.
- Offline first: the mock provider exercises tool loops, approvals and workflows without a model.
- Safety is deliberate: approvals never default to approve, untrusted text is escaped, `fetch_url` checks the
  resolved and the connected address, and the global mafx only re-executes into trusted workspaces.

## Findings

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| F1 | High | Ctrl+C during a .NET turn desyncs the session. The client stops reading, the .NET host keeps streaming, and the next turn reads the old turn's events and `turn_completed`. The protocol has no `cancel` message. | `cli/src/mafx/interactive.py:254-262`, `cli/src/mafx/dotnet.py:136-155` |
| F2 | High (verify) | Workflow failures reported through events (`executor_failed`, `failed`) do not set `ok=False`; only exceptions do. `-p` could exit 0 on a failed workflow. | `libs/python/maf_labs_host/src/maf_labs_host/runner.py:216-217, 258-272` |
| F3 | Medium (verify) | Sending a new message instead of answering pending approvals leaves an unanswered approval request in the session; the next model call may be rejected. | `runner.py:101-102, 152` |
| F4 | Medium | .NET host parity: no `--allow-tool`; an unknown approval decision throws and ends the host (Python answers with an error); `approve` with nothing pending runs an empty message (Python errors); a mistyped target runs the only agent; `minimal` maps to low. | `HostOptions.cs`, `MafLabsHost.cs:92, 171, 266-273`, `Providers.cs:148` |
| F5 | Medium | Harness file memory is scoped per session: `.mafx/memory/harness-lab/<session-id>/watchlist.md` exists once per run, so the claw watchlist does not survive a new `mafx run`. | `.mafx/memory/harness-lab/*/`, `harness_lab/agents/claw.py:112` |
| F6 | Low (verify) | `_fail` inside the async `main` raises `typer.Exit`, which the generic `except Exception` catches and reports a second time. | `cli/src/mafx/main.py:131, 151-154` |
| F7 | Low | A project `.env` overrides variables set in the shell (`override=True`), so `MAF_PROVIDER=mock mafx run ...` can be ignored. | `workspace.py:70` |
| F8 | Low | `fetch_url` runs trafilatura extraction on the event loop; the overall deadline cannot interrupt it. | `tools/python/web-search/src/web_search/tools.py:254` |
| F9 | Low | `fetch_url` ignores proxies (`trust_env=False`) by design; it will not work behind a corporate proxy. Document it. | `tools.py:228` |
| F10 | Info | `doctor` labels "reasoning streamed" from `model_calls`, which counts usage events, not reasoning. | `main.py:385` |
| F11 | Hygiene | `projects/harness-lab/.mafx/` holds run data from before paths were workspace-rooted (gitignored). | |

## Coverage gaps
No tests for interrupt handling, .NET protocol edge cases (bad decision, approve with nothing pending), workflow
failure exit codes, or approvals inside workflows. No CI.

## Candidate backlog items
Captured in `docs/inbox.md`.
