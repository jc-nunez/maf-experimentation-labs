"""Runners: execute one turn of an agent or workflow and yield trajectory events."""

from __future__ import annotations

import contextlib
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from . import events as ev
from .manifest import AgentSpec, Project, WorkflowSpec
from .providers import ProviderInfo, create_chat_client
from .runtime import HostContext, agent_tools, build_agent, build_workflow, effective_effort
from .trace import TraceWriter


class Runner:
    """Common interface used by the CLI for every runtime (in-process or subprocess)."""

    kind: str = "agent"
    target: str = ""
    info: dict[str, Any]

    async def start(self) -> None: ...

    async def close(self) -> None: ...

    def turn(self, text: str) -> AsyncIterator[dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError

    async def reset(self) -> None: ...

    async def set_effort(self, effort: str | None) -> None:
        """Override the reasoning effort for the following turns (None restores the configured default)."""
        raise NotImplementedError(f"{type(self).__name__} does not support changing the reasoning effort")

    def describe(self) -> dict[str, Any]:
        return self.info


class AgentRunner(Runner):
    kind = "agent"

    def __init__(self, ctx: HostContext, spec: AgentSpec) -> None:
        self.ctx = ctx
        self.spec = spec
        self.target = f"{ctx.project.name}/{spec.name}"
        self.agent: Any = None
        self.session: Any = None
        self.tools: list[Any] = []
        self.effort_override: str | None = ctx.reasoning_effort
        self._stack = contextlib.AsyncExitStack()
        self.info = {
            "target": self.target,
            "kind": "agent",
            "runtime": spec.runtime,
            "provider": ctx.provider.provider,
            "model": ctx.provider.model,
            "api": ctx.provider.api,
        }

    async def start(self) -> None:
        self.agent = build_agent(self.spec, self.ctx)
        for tool in agent_tools(self.spec, self.ctx):
            if hasattr(tool, "__aenter__"):  # MCP tools need a live connection
                tool = await self._stack.enter_async_context(tool)
            self.tools.append(tool)
        await self.reset()
        options = getattr(self.agent, "default_options", {}) or {}
        tool_names = [getattr(t, "name", str(t)) for t in [*(options.get("tools") or []), *self.tools]]
        self.info.update(
            agent_name=getattr(self.agent, "name", None), tools=tool_names, instructions=options.get("instructions")
        )
        self._update_effort_info()

    def _update_effort_info(self) -> None:
        self.info["effort"] = self.effort_override or effective_effort(self.agent) or "default"

    async def set_effort(self, effort: str | None) -> None:
        self.effort_override = effort
        self._update_effort_info()

    async def reset(self) -> None:
        self.session = self.agent.create_session()

    async def close(self) -> None:
        await self._stack.aclose()

    async def turn(self, text: str) -> AsyncIterator[dict[str, Any]]:
        started = time.perf_counter()
        tr = ev.UpdateTranslator()
        try:
            options = {"reasoning": {"effort": self.effort_override}} if self.effort_override else None
            stream = self.agent.run(text, stream=True, session=self.session, tools=self.tools or None, options=options)
            async for update in stream:
                for e in tr.translate(update):
                    yield e
            for e in tr.finish():
                yield e
        except Exception as exc:  # noqa: BLE001 - surfaced as an event
            for e in tr.finish():
                yield e
            yield ev.event(ev.ERROR, message=f"{type(exc).__name__}: {exc}")
            yield _turn_completed(tr, started, ok=False)
            return
        yield _turn_completed(tr, started)


class WorkflowRunner(Runner):
    """Each turn runs the workflow once. Pending ``request_info`` prompts are answered by the next turn."""

    kind = "workflow"

    def __init__(self, ctx: HostContext, spec: WorkflowSpec) -> None:
        self.ctx = ctx
        self.spec = spec
        self.target = f"{ctx.project.name}/{spec.name}"
        self.workflow: Any = None
        self.pending: list[str] = []
        self.info = {
            "target": self.target,
            "kind": "workflow",
            "runtime": spec.runtime,
            "provider": ctx.provider.provider,
            "model": ctx.provider.model,
            "api": ctx.provider.api,
            # Workflows set effort per agent in their factory; --effort reaches them via context.reasoning_effort.
            "effort": ctx.reasoning_effort or "per-agent",
        }

    async def start(self) -> None:
        await self.reset()
        try:
            executors = [getattr(e, "id", str(e)) for e in self.workflow.get_executors_list()]
        except Exception:  # noqa: BLE001
            executors = []
        self.info.update(executors=executors)

    async def reset(self) -> None:
        self.workflow = build_workflow(self.spec, self.ctx)
        self.pending = []

    async def turn(self, text: str) -> AsyncIterator[dict[str, Any]]:
        started = time.perf_counter()
        totals = ev.UpdateTranslator()
        translators: dict[str, ev.UpdateTranslator] = {}
        outputs: list[Any] = []
        self._output_executors: list[str] = []
        ok = True
        try:
            if self.pending:
                responses = {request_id: text for request_id in self.pending}
                self.pending = []
                stream = self.workflow.run(responses=responses, stream=True)
            else:
                stream = self.workflow.run(text, stream=True)
            async for wf_event in stream:
                for e in self._translate(wf_event, translators, outputs):
                    yield e
        except Exception as exc:  # noqa: BLE001
            ok = False
            yield ev.event(ev.ERROR, message=f"{type(exc).__name__}: {exc}")
        for tr in translators.values():
            for e in tr.finish():
                yield e
            totals.input_tokens += tr.input_tokens
            totals.output_tokens += tr.output_tokens
            totals.model_calls += tr.model_calls
            totals.tool_calls += tr.tool_calls
        streamed = [translators[x].text for x in self._output_executors if x in translators]
        if outputs:
            totals.text_parts = ["\n\n".join(_output_text(o) for o in outputs)]
        elif streamed:
            totals.text_parts = ["\n\n".join(streamed)]
        done = _turn_completed(totals, started, ok=ok)
        done["outputs"] = [ev.to_jsonable(o) for o in outputs]
        done["pending_requests"] = list(self.pending)
        yield done

    def _translate(
        self, wf_event: Any, translators: dict[str, ev.UpdateTranslator], outputs: list[Any]
    ) -> list[dict[str, Any]]:
        etype = getattr(wf_event, "type", None)
        executor_id = getattr(wf_event, "executor_id", None)
        data = getattr(wf_event, "data", None)

        if data is not None and type(data).__name__ in ("AgentResponseUpdate", "ChatResponseUpdate"):
            key = executor_id or "?"
            tr = translators.setdefault(key, ev.UpdateTranslator(executor_id))
            if etype == "output" and key not in self._output_executors:
                self._output_executors.append(key)
            return tr.translate(data)

        if etype == "executor_invoked":
            return [ev.event(ev.EXECUTOR_STARTED, executor_id=executor_id, input=_preview(data))]
        if etype == "executor_completed":
            out = []
            if executor_id in translators:
                out.extend(translators[executor_id].finish())
            out.append(ev.event(ev.EXECUTOR_COMPLETED, executor_id=executor_id))
            return out
        if etype == "executor_failed":
            return [ev.event(ev.ERROR, executor_id=executor_id, message=_error_message(wf_event, data))]
        if etype == "output":
            outputs.append(data)
            return [ev.event(ev.WORKFLOW_OUTPUT, executor_id=executor_id, data=ev.to_jsonable(data))]
        if etype == "request_info":
            request_id = getattr(wf_event, "request_id", None)
            if request_id:
                self.pending.append(request_id)
            return [
                ev.event(ev.REQUEST_INFO, request_id=request_id, executor_id=executor_id, data=ev.to_jsonable(data))
            ]
        if etype in ("warning", "error", "failed"):
            kind = ev.WARNING if etype == "warning" else ev.ERROR
            return [ev.event(kind, executor_id=executor_id, message=_error_message(wf_event, data))]
        return []


def _error_message(wf_event: Any, data: Any) -> str:
    details = getattr(wf_event, "details", None)
    if details is not None and getattr(details, "message", None):
        return f"{getattr(details, 'error_type', 'Error')}: {details.message}"
    return str(details or data)


def _preview(value: Any, limit: int = 500) -> Any:
    if value is not None and " object at 0x" in repr(value):
        return type(value).__name__
    value = ev.to_jsonable(value)
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def _output_text(value: Any) -> str:
    if hasattr(value, "text"):
        return str(value.text)
    if isinstance(value, list):
        return "\n".join(_output_text(v) for v in value)
    return value if isinstance(value, str) else str(ev.to_jsonable(value))


def _turn_completed(tr: ev.UpdateTranslator, started: float, ok: bool = True) -> dict[str, Any]:
    return ev.event(
        ev.TURN_COMPLETED,
        ok=ok,
        text=tr.text,
        duration_s=round(time.perf_counter() - started, 3),
        input_tokens=tr.input_tokens,
        output_tokens=tr.output_tokens,
        model_calls=tr.model_calls,
        tool_calls=tr.tool_calls,
    )


# --------------------------------------------------------------------------------------------- setup


def create_runner(
    project: Project,
    name: str | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    workspace_root: Path | None = None,
    default_provider: str | None = None,
    reasoning_effort: str | None = None,
) -> Runner:
    """Create an in-process runner (python / declarative runtimes)."""
    name = name or project.default_target()
    kind, spec = project.find(name)
    if kind == "tools":
        raise ValueError(f"'{name}' is a tool; use `mafx tool run` to call it directly")
    from .providers import resolve_provider

    client, info = create_chat_client(resolve_provider(provider, default_provider), model)
    ctx = HostContext(
        project=project, client=client, provider=info, workspace_root=workspace_root, reasoning_effort=reasoning_effort
    )
    if kind == "agents":
        return AgentRunner(ctx, spec)  # type: ignore[arg-type]
    return WorkflowRunner(ctx, spec)  # type: ignore[arg-type]


class RecordingRunner(Runner):
    """Wraps a runner and writes every event to ``<runs>/<run-id>/trace.jsonl``."""

    def __init__(self, inner: Runner, runs_dir: Path, mode: str) -> None:
        self.inner = inner
        self.kind = inner.kind
        self.target = inner.target
        self.run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.trace = TraceWriter(runs_dir / self.run_id)
        self.mode = mode

    @property
    def info(self) -> dict[str, Any]:  # type: ignore[override]
        return {**self.inner.info, "run_id": self.run_id, "trace": str(self.trace.path)}

    async def start(self) -> None:
        await self.inner.start()
        self.trace.write(ev.event(ev.RUN_STARTED, mode=self.mode, **self.info))

    async def reset(self) -> None:
        await self.inner.reset()
        self.trace.write(ev.event("session_reset"))

    async def close(self) -> None:
        await self.inner.close()
        self.trace.close()

    async def set_effort(self, effort: str | None) -> None:
        await self.inner.set_effort(effort)
        self.trace.write(ev.event("effort_changed", effort=effort or "default"))

    async def turn(self, text: str) -> AsyncIterator[dict[str, Any]]:
        self.trace.write(ev.event("user_message", text=text))
        async for e in self.inner.turn(text):
            self.trace.write(e)
            yield e


__all__ = ["AgentRunner", "WorkflowRunner", "RecordingRunner", "Runner", "create_runner", "ProviderInfo"]
