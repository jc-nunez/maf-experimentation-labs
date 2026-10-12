"""Path guard, command allowlist and action log."""

import subprocess

import pytest
from repo_agent.git import Runner
from repo_agent.guards import ActionLog, GuardError, PathGuard, default_allowlist, is_branch, workspace_dir


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "workspaces" / "mafx"
    root.mkdir(parents=True)
    return root


@pytest.mark.parametrize("path", ["/etc", "..", "../other", "../mafx-evil", "sub/../../escape"])
def test_path_guard_refuses_paths_outside_the_workspace(ws, path):
    with pytest.raises(GuardError):
        PathGuard(ws).check(ws / path if not path.startswith("/") else path)


def test_path_guard_refuses_symlink_escape(ws, tmp_path):
    (ws / "link").symlink_to(tmp_path)
    with pytest.raises(GuardError):
        PathGuard(ws).check(ws / "link" / "secret")


def test_path_guard_allows_workspace_paths(ws):
    guard = PathGuard(ws)
    assert guard.check(ws) == ws.resolve()
    assert guard.check(ws / "repo" / "file") == (ws / "repo" / "file").resolve()


@pytest.mark.parametrize("project", ["../etc", "a/b", "", "UPPER", "-x"])
def test_workspace_dir_refuses_bad_project_names(tmp_path, project):
    with pytest.raises(GuardError):
        workspace_dir(project, tmp_path)


def test_workspace_dir_uses_env_root(tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_AGENT_ROOT", str(tmp_path))
    assert workspace_dir("mafx") == tmp_path.resolve() / "mafx"


@pytest.mark.parametrize(
    "argv",
    [
        ["git", "push", "--force"],
        ["git", "push"],
        ["git", "reset", "--hard"],
        ["git", "status"],
        ["git", "status", "--porcelain=v2", "--branch", "--ignored"],
        ["git", "clone", "git@github.com:x/y.git", "y"],
        ["git", "clone", "file:///tmp/origin.git", "y"],
        ["git", "clone", "https://github.com/x/y.git", "--upload-pack=evil"],
        ["gh", "pr", "merge", "1"],
        ["gh", "pr", "list", "--state", "open", "--json", "number;rm -rf"],
        ["rm", "-rf", "/"],
        ["git", "worktree", "remove", "--force", "worktrees/h1"],
        ["git", "worktree", "remove", "-f", "worktrees/h1"],
        ["git", "worktree", "add", "--force", "worktrees/h1", "b"],
        ["git", "worktree", "add", "worktrees/h1", "-B", "b", "origin/main"],
        ["git", "worktree", "add", "worktrees/h1", "--detach"],
        ["git", "branch", "-D", "b"],
        ["git", "branch", "-d", "--force", "b"],
        ["git", "branch", "-d", "-f"],
        ["git", "fetch", "origin", "--prune", "--force"],
        ["git", "rev-parse", "--verify", "--quiet", "a..b"],
        ["git", "rev-list", "--count", "main..b"],
        ["git", "rev-list", "--count", "origin/a..b"],
        ["git", "rev-list", "--count", "origin/b...b"],
        ["uv", "sync"],
        ["uv", "run", "anything"],
    ],
)
def test_allowlist_refuses_commands_not_on_the_list(argv):
    with pytest.raises(GuardError):
        default_allowlist().match(argv)


def test_allowlist_accepts_default_commands():
    allow = default_allowlist()
    assert allow.match(["git", "clone", "--", "https://github.com/x/y.git", "y"]) == ["y"]
    assert allow.match(["git", "status", "--porcelain=v2", "--branch"]) == []
    assert allow.match(["gh", "pr", "list", "--state", "open", "--json", "number,title"]) == []
    assert allow.match(["git", "worktree", "add", "worktrees/h1", "-b", "bet/002-s02", "origin/main"]) == [
        "worktrees/h1"
    ]
    assert allow.match(["git", "worktree", "add", "worktrees/h1", "bet/002-s02"]) == ["worktrees/h1"]
    assert allow.match(["git", "worktree", "remove", "worktrees/h1"]) == ["worktrees/h1"]
    assert allow.match(["git", "branch", "-d", "bet/002-s02"]) == []
    assert allow.match(["git", "rev-list", "--count", "origin/bet/x..bet/x"]) == []
    assert allow.match(["uv", "sync", "--all-packages"]) == []


@pytest.mark.parametrize("name", ["-D", "--force", "a..b", "", "a b", "a;b", "a~1", "a^", "a:b"])
def test_is_branch_refuses_options_ranges_and_odd_characters(name):
    assert not is_branch(name)


def test_runner_refuses_before_executing(ws, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(subprocess, "run", boom)
    runner = Runner(PathGuard(ws), default_allowlist())
    with pytest.raises(GuardError):
        runner.run(["git", "push", "--force"], ws)
    with pytest.raises(GuardError):
        runner.run(["git", "clone", "--", "https://github.com/x/y.git", "../outside"], ws)
    with pytest.raises(GuardError):
        runner.run(["git", "status", "--porcelain=v2", "--branch"], ws.parent)


def test_runner_runs_allowlisted_command(ws):
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    result = Runner(PathGuard(ws), default_allowlist()).run(["git", "status", "--porcelain=v2", "--branch"], ws)
    assert result.ok and "# branch.head" in result.stdout


def test_action_log_appends_jsonl(tmp_path):
    log = ActionLog(tmp_path / ".repo-agent" / "actions.jsonl")
    log.append(caller="mcp", tool="create_workspace", argv=[["git", "clone", "u", "d"]], result="created")
    entries = log.entries()
    assert len(entries) == 1
    assert entries[0]["caller"] == "mcp" and entries[0]["tool"] == "create_workspace"
    assert set(entries[0]) == {"time", "caller", "tool", "argv", "result"}
