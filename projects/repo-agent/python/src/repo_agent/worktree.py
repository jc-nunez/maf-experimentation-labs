"""Worktree start / finish for a handoff: ``<workspace>/worktrees/<handoff id>`` on the handoff's branch.

Both functions check every precondition before the first write and raise ``WorktreeError`` with the reason when one
fails. Every write is logged in ``.repo-agent/actions.jsonl``. Nothing is ever forced: a dirty or unpushed worktree is
refused, and branches are deleted only with ``git branch -d`` (git refuses unmerged ones itself).

``uv sync`` builds the branch's own packages, so it runs that branch's build code: start only handoffs you trust
(the user approves every call). File operations never follow a symbolic link.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from repo_agent.git import Result, Runner
from repo_agent.guards import ActionLog, Allowlist, PathGuard, default_allowlist, is_branch, workspace_dir
from repo_agent.workspace import ACTIONS, STATE_DIR, WORKTREES, _check_repo, load_config, read_handoff

HANDOFF_ID = re.compile(r"^h[0-9]{1,6}$")
QUEUE = ".handoffs"
DONE = "done"


class WorktreeError(RuntimeError):
    """A precondition failed or a git step failed; the message says which."""


@dataclass
class _Ctx:
    """One call: the workspace, its guards, and the commands run so far (for the action log)."""

    ws: Path
    guard: PathGuard
    runner: Runner
    log: ActionLog
    caller: str
    tool: str
    commands: list[list[str]] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)

    def run(self, argv: list[str], cwd: Path) -> Result:
        self.commands.append(argv)
        return self.runner.run(argv, cwd)

    def must(self, argv: list[str], cwd: Path) -> Result:
        """Run a step that has to succeed; a failure is logged with everything done so far, then raised."""
        result = self.run(argv, cwd)
        if not result.ok:
            reason = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            self.write_log(f"failed at '{' '.join(argv)}': {reason}")
            raise WorktreeError(f"'{' '.join(argv)}' failed: {reason}")
        return result

    def write_log(self, result: str) -> None:
        self.log.append(caller=self.caller, tool=self.tool, argv=self.commands, result=result)


def _context(project: str, root: Path | None, caller: str, tool: str, allowlist: Allowlist | None) -> _Ctx:
    ws = workspace_dir(project, root)
    guard = PathGuard(ws)
    return _Ctx(
        ws, guard, Runner(guard, allowlist or default_allowlist()), ActionLog(ws / STATE_DIR / ACTIONS), caller, tool
    )


def _repos(ctx: _Ctx, project: str) -> list[Path]:
    config = load_config(ctx.ws)
    if config is None:
        raise WorktreeError(f"workspace '{project}' does not exist (call create_workspace)")
    return [ctx.guard.check(ctx.ws / _check_repo(r)["name"]) for r in config["repos"]]


def _check_id(handoff_id: str) -> str:
    if not HANDOFF_ID.match(handoff_id):
        raise WorktreeError(f"invalid handoff id '{handoff_id}' (expected h followed by digits, e.g. h007)")
    return handoff_id


def _find_handoff(ctx: _Ctx, repos: list[Path], handoff_id: str, folder: str = "") -> tuple[Path, Path] | None:
    """(repo, handoff file) for ``<repo>/.handoffs/[folder/]<id>-*.md``; None if absent, error if ambiguous."""
    found = []
    for repo in repos:
        queue = repo / QUEUE / folder
        if queue.is_dir():
            files = [*queue.glob(f"{handoff_id}-*.md"), *queue.glob(f"{handoff_id}.md")]
            for f in files:
                if f.is_symlink():  # move and read the queue entry itself, never what a link points at
                    raise WorktreeError(f"{f} is a symbolic link; replace it with the handoff file")
                found.append((repo, ctx.guard.check(f)))
    if len(found) > 1:
        raise WorktreeError(f"{handoff_id} is ambiguous: {', '.join(str(f) for _, f in found)}")
    return found[0] if found else None


def _changes(ctx: _Ctx, path: Path) -> int:
    result = ctx.must(["git", "status", "--porcelain=v2", "--branch"], path)
    return sum(1 for line in result.stdout.splitlines() if line and not line.startswith("#"))


def _ref_exists(ctx: _Ctx, repo: Path, ref: str) -> bool:
    return ctx.run(["git", "rev-parse", "--verify", "--quiet", ref], repo).ok


# ------------------------------------------------------------------------------------------------- start


def start_worktree(
    handoff_id: str,
    project: str = "mafx",
    *,
    root: Path | None = None,
    caller: str = "mcp",
    allowlist: Allowlist | None = None,
) -> dict[str, Any]:
    """Create ``worktrees/<id>`` for a ready handoff, copy ``.env``, run ``uv sync``; return the path and next step.

    Refuses when the handoff is missing or not ``ready``, its branch is invalid, the main checkout is dirty, or the
    worktree already exists. A new branch starts from ``origin/main`` (after a fetch); an existing one is reused.
    """
    ctx = _context(project, root, caller, "start_worktree", allowlist)
    repos = _repos(ctx, project)
    found = _find_handoff(ctx, repos, _check_id(handoff_id))
    if found is None:
        raise WorktreeError(f"{handoff_id} is not in the handoff queue")
    repo, file = found
    meta = read_handoff(file)
    if meta.get("status") != "ready":
        raise WorktreeError(f"{handoff_id} is {meta.get('status') or 'missing a status'}, not ready")
    branch = meta.get("branch", "")
    if not is_branch(branch):
        raise WorktreeError(f"{handoff_id} has an invalid branch '{branch}'")
    if changes := _changes(ctx, repo):
        raise WorktreeError(f"{repo.name} has {changes} uncommitted change(s); commit or stash them first")
    path = ctx.guard.check(ctx.ws / WORKTREES / handoff_id)
    if path.exists():
        raise WorktreeError(f"{path} already exists")

    ctx.must(["git", "fetch", "origin", "--prune"], repo)
    if _ref_exists(ctx, repo, f"refs/heads/{branch}") or _ref_exists(ctx, repo, f"refs/remotes/origin/{branch}"):
        ctx.must(["git", "worktree", "add", str(path), branch], repo)
        ctx.changes.append(f"worktree {path} on existing branch {branch}")
    else:
        ctx.must(["git", "worktree", "add", str(path), "-b", branch, "origin/main"], repo)
        ctx.changes.append(f"worktree {path} on new branch {branch} from origin/main")

    warnings = []
    copied = _copy_env(ctx, repo / ".env", path / ".env")
    if copied:
        (ctx.changes if copied == "copied .env" else warnings).append(copied)
    if (path / "pyproject.toml").is_file():
        result = ctx.run(["uv", "sync", "--all-packages"], path)
        if result.ok:
            ctx.changes.append("uv sync done")
        else:  # the worktree is usable; the agent in it can sync again
            warnings.append(f"uv sync failed: {(result.stderr.strip().splitlines() or ['?'])[-1]}")

    ctx.write_log("started: " + "; ".join(ctx.changes + warnings))
    return {
        "status": "started",
        "handoff": handoff_id,
        "repo": repo.name,
        "branch": branch,
        "worktree": str(path),
        "changes": ctx.changes,
        "warnings": warnings,
        "next": f'cd {path} && claude "/handoff {handoff_id}"',
    }


# ------------------------------------------------------------------------------------------------ finish


def finish_worktree(
    handoff_id: str,
    project: str = "mafx",
    *,
    root: Path | None = None,
    caller: str = "mcp",
    allowlist: Allowlist | None = None,
) -> dict[str, Any]:
    """Remove ``worktrees/<id>`` when it is clean, then (after a fetch):

    - branch merged into ``origin/main``: delete it (``-d``) and move the handoff to ``.handoffs/done/``;
    - not merged but every commit pushed: keep the branch (R19);
    - otherwise refuse and change nothing.
    """
    ctx = _context(project, root, caller, "finish_worktree", allowlist)
    repos = _repos(ctx, project)
    path = ctx.guard.check(ctx.ws / WORKTREES / _check_id(handoff_id))
    if not path.is_dir():
        raise WorktreeError(f"there is no worktree {path}")
    repo, branch = _owner(ctx, repos, path)
    if changes := _changes(ctx, path):
        raise WorktreeError(f"{path} has {changes} uncommitted change(s); commit and push or discard them first")

    ctx.must(["git", "fetch", "origin", "--prune"], repo)
    merged = ctx.run(["git", "merge-base", "--is-ancestor", branch, "origin/main"], repo)
    if merged.returncode not in (0, 1):
        ctx.must(merged.argv, repo)  # a real error, not an answer: log and raise it
    if merged.ok:
        move = _done_target(ctx, repos, handoff_id)  # refuse a done/ collision before the first write
        ctx.must(["git", "worktree", "remove", str(path)], repo)
        ctx.changes.append(f"removed {path}")
        deleted = ctx.run(["git", "branch", "-d", branch], repo)
        warnings = [] if deleted.ok else [f"branch {branch} kept: {deleted.stderr.strip()}"]
        if deleted.ok:
            ctx.changes.append(f"deleted branch {branch} (merged into origin/main)")
        if move:
            ctx.changes.append(_move_to_done(ctx, *move))
        ctx.write_log("finished: " + "; ".join(ctx.changes + warnings))
        return _finished(ctx, handoff_id, branch, path, "merged", warnings)

    if not _ref_exists(ctx, repo, f"refs/remotes/origin/{branch}"):
        raise WorktreeError(f"{branch} is not merged into origin/main and not pushed; push it or merge it first")
    ahead = ctx.must(["git", "rev-list", "--count", f"origin/{branch}..{branch}"], repo).stdout.strip()
    if ahead != "0":
        raise WorktreeError(f"{branch} has {ahead} commit(s) not pushed to origin; push them first")
    ctx.must(["git", "worktree", "remove", str(path)], repo)
    ctx.changes.append(f"removed {path}; kept branch {branch} (pushed, not merged)")
    ctx.write_log("finished: " + "; ".join(ctx.changes))
    return _finished(ctx, handoff_id, branch, path, "pushed", [])


def _owner(ctx: _Ctx, repos: list[Path], path: Path) -> tuple[Path, str]:
    """The repo whose worktree list contains ``path``, and the branch checked out there."""
    for repo in repos:
        result = ctx.must(["git", "worktree", "list", "--porcelain"], repo)
        for block in result.stdout.strip().split("\n\n"):
            fields = dict((line.split(" ", 1) + [""])[:2] for line in block.splitlines())
            if fields.get("worktree") and Path(fields["worktree"]).resolve() == path:
                branch = fields.get("branch", "").removeprefix("refs/heads/")
                if not is_branch(branch):
                    raise WorktreeError(f"{path} is not on a branch (detached HEAD); check it out by hand")
                return repo, branch
    raise WorktreeError(f"{path} is not a git worktree of this workspace; remove it by hand")


def _copy_env(ctx: _Ctx, source: Path, target: Path) -> str | None:
    """Copy the main checkout's ``.env`` into a new worktree: never through a link, never over an existing file
    (a branch may track its own ``.env``), readable by the owner only."""
    if not source.is_file():
        return None
    if source.is_symlink():
        return ".env not copied: the main checkout's .env is a symbolic link"
    if target.exists() or target.is_symlink():
        return ".env not copied: the worktree already has one"
    data = ctx.guard.check(source).read_bytes()
    fd = os.open(ctx.guard.check(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return "copied .env"


def _done_target(ctx: _Ctx, repos: list[Path], handoff_id: str) -> tuple[Path, Path] | None:
    """(handoff file, its path in ``done/``) after every check, without writing; None if there is nothing to move."""
    found = _find_handoff(ctx, repos, handoff_id)
    if found is None:  # already in done/ (the /handoff command moves it) or never queued
        return None
    _, file = found
    if (file.parent / DONE).is_symlink():
        raise WorktreeError(f"{file.parent / DONE} is a symbolic link; move {file.name} by hand")
    target = ctx.guard.check(file.parent / DONE / file.name)
    if target.exists() or target.is_symlink():
        raise WorktreeError(f"{target} already exists; move {file.name} by hand")
    return file, target


def _move_to_done(ctx: _Ctx, file: Path, target: Path) -> str:
    ctx.guard.check(target.parent).mkdir(exist_ok=True)
    file.rename(target)
    return f"moved {file.name} to {QUEUE}/{DONE}/"


def _finished(ctx: _Ctx, handoff_id: str, branch: str, path: Path, how: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "status": "finished",
        "handoff": handoff_id,
        "branch": branch,
        "worktree": str(path),
        "branch_state": how,
        "changes": ctx.changes,
        "warnings": warnings,
    }


def format_result(result: dict[str, Any]) -> str:
    """The reply shown by the MCP tools and the agent: what changed, then the next step."""
    lines = [f"{result['handoff']}: {result['status']} ({result['worktree']})"]
    lines += [f"- {c}" for c in result["changes"]]
    lines += [f"- warning: {w}" for w in result["warnings"]]
    if result.get("next"):
        lines += ["", f"Next: {result['next']}"]
    return "\n".join(lines)
