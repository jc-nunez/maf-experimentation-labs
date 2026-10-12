"""Workspaces: ``~/workspaces/<project>/`` with the main checkouts, ``worktrees/`` and ``.repo-agent/``.

``create_workspace`` writes; ``workspace_status`` and ``format_status`` only read.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from repo_agent.git import Runner
from repo_agent.guards import ActionLog, Allowlist, GuardError, PathGuard, default_allowlist, workspace_dir

STATE_DIR = ".repo-agent"
CONFIG = "config.yaml"
ACTIONS = "actions.jsonl"
WORKTREES = "worktrees"
REPO_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")

DEFAULT_REPOS: dict[str, list[dict[str, str]]] = {
    "mafx": [
        {
            "name": "maf-experimentation-labs",
            "url": "https://github.com/jc-nunez/maf-experimentation-labs.git",
            "default_branch": "main",
        }
    ],
}


class WorkspaceError(RuntimeError):
    pass


def _config_path(ws: Path) -> Path:
    return ws / STATE_DIR / CONFIG


def load_config(ws: Path) -> dict[str, Any] | None:
    path = _config_path(ws)
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None


def _check_repo(repo: dict[str, Any]) -> dict[str, str]:
    name = str(repo.get("name") or "")
    if not REPO_NAME.match(name) or name in (STATE_DIR, WORKTREES):
        raise GuardError(f"invalid repo name '{name}'")
    if not repo.get("url"):
        raise WorkspaceError(f"repo '{name}' has no url")
    return {"name": name, "url": str(repo["url"]), "default_branch": str(repo.get("default_branch") or "main")}


# ------------------------------------------------------------------------------------------------- write


def create_workspace(
    project: str = "mafx",
    repos: list[dict[str, Any]] | None = None,
    *,
    root: Path | None = None,
    caller: str = "mcp",
    allowlist: Allowlist | None = None,
) -> dict[str, Any]:
    """Create the workspace folders, write the config and clone missing repos. Idempotent."""
    ws = workspace_dir(project, root)
    guard = PathGuard(ws)
    runner = Runner(guard, allowlist or default_allowlist())
    existed = ws.is_dir()

    config = load_config(ws) or {"project": project, "repos": []}
    known = {r["name"] for r in config["repos"]}
    wanted = repos if repos is not None else DEFAULT_REPOS.get(project, [])
    added = [_check_repo(r) for r in wanted if r.get("name") not in known]
    if not config["repos"] and not added:
        raise WorkspaceError(f"no repos given for workspace '{project}'")

    changes: list[str] = []
    for folder in (ws, ws / WORKTREES, ws / STATE_DIR):
        if not guard.check(folder).is_dir():
            folder.mkdir(parents=True)
            changes.append(f"created {folder.relative_to(ws.parent)}/")
    if added:
        config["repos"] = [*config["repos"], *added]
        _config_path(ws).write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        changes.append(f"wrote {STATE_DIR}/{CONFIG}")

    commands: list[list[str]] = []
    for repo in (_check_repo(r) for r in config["repos"]):
        dest = guard.check(ws / repo["name"])
        if (dest / ".git").exists():
            continue
        if dest.exists():
            raise WorkspaceError(f"{dest} exists but is not a git checkout; move it away first")
        argv = ["git", "clone", "--", repo["url"], repo["name"]]
        commands.append(argv)
        result = runner.run(argv, ws)
        if not result.ok:
            ActionLog(ws / STATE_DIR / ACTIONS).append(
                caller=caller, tool="create_workspace", argv=commands, result=f"failed: {result.stderr.strip()}"
            )
            raise WorkspaceError(f"git clone {repo['url']} failed: {result.stderr.strip()}")
        changes.append(f"cloned {repo['name']}")

    if not changes:
        return {"status": "unchanged", "workspace": str(ws), "message": "workspace already exists; nothing changed"}
    status = "updated" if existed else "created"
    ActionLog(ws / STATE_DIR / ACTIONS).append(
        caller=caller, tool="create_workspace", argv=commands, result=f"{status}: {'; '.join(changes)}"
    )
    return {"status": status, "workspace": str(ws), "changes": changes}


# -------------------------------------------------------------------------------------------------- read


def workspace_status(project: str = "mafx", *, root: Path | None = None) -> dict[str, Any]:
    """Repos (branch, clean, behind/ahead as of last fetch), worktrees, handoff queue and open PRs."""
    ws = workspace_dir(project, root)
    config = load_config(ws)
    if config is None:
        return {"project": project, "workspace": str(ws), "exists": False}
    guard = PathGuard(ws)
    runner = Runner(guard, default_allowlist())
    status: dict[str, Any] = {
        "project": project,
        "workspace": str(ws),
        "exists": True,
        "repos": [],
        "worktrees": [],
        "handoffs": [],
        "prs": [],
        "errors": [],
    }
    for repo in (_check_repo(r) for r in config["repos"]):
        path = guard.check(ws / repo["name"])
        if not (path / ".git").exists():
            status["repos"].append({"name": repo["name"], "missing": True})
            continue
        status["repos"].append({"name": repo["name"], **_repo_state(runner, path)})
        status["worktrees"] += [{"repo": repo["name"], **w} for w in _worktrees(runner, path)]
        status["handoffs"] += [{"repo": repo["name"], **h} for h in _handoffs(guard, path / ".handoffs")]
        prs, error = _open_prs(runner, path, repo["url"])
        status["prs"] += [{"repo": repo["name"], **p} for p in prs]
        if error:
            status["errors"].append(f"{repo['name']}: pull requests unavailable ({error})")
    return status


def _repo_state(runner: Runner, path: Path) -> dict[str, Any]:
    result = runner.run(["git", "status", "--porcelain=v2", "--branch"], path)
    if not result.ok:
        return {"error": result.stderr.strip()}
    state: dict[str, Any] = {"branch": None, "upstream": None, "ahead": 0, "behind": 0, "changes": 0}
    for line in result.stdout.splitlines():
        if line.startswith("# branch.head "):
            state["branch"] = line.split(" ", 2)[2]
        elif line.startswith("# branch.upstream "):
            state["upstream"] = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            ahead, behind = line.split()[2:4]
            state["ahead"], state["behind"] = int(ahead), -int(behind)
        elif line and not line.startswith("#"):
            state["changes"] += 1
    state["clean"] = state["changes"] == 0
    log = runner.run(["git", "log", "-1", "--format=%h %cs %s"], path)
    state["last_commit"] = log.stdout.strip() if log.ok else None
    return state


def _worktrees(runner: Runner, path: Path) -> list[dict[str, Any]]:
    result = runner.run(["git", "worktree", "list", "--porcelain"], path)
    if not result.ok:
        return []
    blocks = [b for b in result.stdout.strip().split("\n\n") if b.strip()]
    worktrees = []
    for block in blocks[1:]:  # the first entry is the main checkout itself
        fields = dict((line.split(" ", 1) + [""])[:2] for line in block.splitlines())
        branch = fields.get("branch", "").removeprefix("refs/heads/") or "(detached)"
        worktrees.append({"path": fields.get("worktree", ""), "branch": branch, "prunable": "prunable" in fields})
    return worktrees


_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _handoffs(guard: PathGuard, queue: Path) -> list[dict[str, Any]]:
    """Handoffs waiting in the queue (``.handoffs/*.md``; ``done/`` and ``parked/`` are not listed)."""
    if not queue.is_dir():
        return []
    items = []
    for file in sorted(guard.check(queue).glob("h*.md")):
        text = guard.check(file).read_text(encoding="utf-8", errors="replace")
        match = _FRONTMATTER.match(text)
        meta = {}
        if match:
            for line in match.group(1).splitlines():
                key, _, value = line.partition(":")
                meta[key.strip()] = value.split("#", 1)[0].strip()
        title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), "")
        items.append(
            {"id": meta.get("id") or file.stem.split("-", 1)[0], "status": meta.get("status", "?"), "title": title}
        )
    return items


def _open_prs(runner: Runner, path: Path, url: str) -> tuple[list[dict[str, Any]], str | None]:
    if not url.startswith("https://github.com/"):
        return [], None
    result = runner.run(["gh", "pr", "list", "--state", "open", "--json", "number,title,headRefName,isDraft"], path)
    if not result.ok:
        return [], (result.stderr.strip().splitlines() or ["gh failed"])[0]
    return json.loads(result.stdout or "[]"), None


# ------------------------------------------------------------------------------------------------ render


def _home(path: str) -> str:
    home = str(Path.home())
    return "~" + path[len(home) :] if path == home or path.startswith(home + "/") else path


def format_status(status: dict[str, Any]) -> str:
    """The status table shown by the MCP tool and the agent."""
    if not status.get("exists"):
        return f" WORKSPACE  {_home(status['workspace'])}  (not created yet: call create_workspace)"
    rows: list[tuple[str, list[str]]] = [("WORKSPACE", [_home(status["workspace"])])]

    repos = []
    for r in status["repos"]:
        if r.get("missing"):
            repos.append(f"{r['name']}  missing (call create_workspace)")
        elif r.get("error"):
            repos.append(f"{r['name']}  error: {r['error']}")
        else:
            clean = "✓ clean" if r["clean"] else f"✗ {r['changes']} changed"
            sync = f"behind {r['behind']}" + (f" ahead {r['ahead']}" if r["ahead"] else "")
            sync = f"{sync} (as of last fetch)" if r["upstream"] else "no upstream"
            repos.append(f"{r['name']}  {r['branch']}  {clean}  {sync}")
    rows.append(("REPOS", repos or ["none"]))
    many = len(status["repos"]) > 1

    def prefix(item: dict[str, Any]) -> str:
        return f"{item['repo']}  " if many else ""

    rows.append(
        (
            "WORKTREES",
            [
                f"{prefix(w)}{w['branch']}  {_home(w['path'])}" + ("  prunable" if w["prunable"] else "")
                for w in status["worktrees"]
            ]
            or ["none"],
        )
    )
    rows.append(("HANDOFFS", [f"{prefix(h)}{h['id']} {h['status']}" for h in status["handoffs"]] or ["none"]))
    prs = [
        f"{prefix(p)}#{p['number']} {p['headRefName']}  {p['title']}" + ("  (draft)" if p.get("isDraft") else "")
        for p in status["prs"]
    ]
    rows.append(("PRS", prs or ["none open"]))
    if status["errors"]:
        rows.append(("NOTES", status["errors"]))

    lines = []
    for label, values in rows:
        for i, value in enumerate(values):
            lines.append(f" {label if i == 0 else '':<9}  {value}")
    return "\n".join(lines)
