"""start_worktree / finish_worktree on a temp workspace whose repo clones a local bare origin."""

import subprocess

import pytest
from repo_agent.guards import ActionLog
from repo_agent.workspace import create_workspace, workspace_status
from repo_agent.worktree import WorktreeError, finish_worktree, start_worktree


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def write_handoff(labs, handoff_id="h900", status="ready", branch="test/h900-demo"):
    queue = labs / ".handoffs"
    queue.mkdir(exist_ok=True)
    file = queue / f"{handoff_id}-demo.md"
    file.write_text(
        f"---\nid: {handoff_id}\nstatus: {status}   # comment\nbranch: {branch}\n---\n# {handoff_id}: demo\n"
    )
    return file


@pytest.fixture
def ws(root, repos, file_allowlist):
    """The mafx workspace with labs cloned, a .env in labs, and .env/.handoffs ignored as in the real repo."""
    create_workspace("mafx", repos, allowlist=file_allowlist)
    ws = root.resolve() / "mafx"
    (ws / "labs" / ".git" / "info" / "exclude").write_text(".env\n.handoffs/\n")
    (ws / "labs" / ".env").write_text("MAF_PROVIDER=mock\n")
    return ws


@pytest.fixture
def start(file_allowlist):
    return lambda handoff_id="h900": start_worktree(handoff_id, "mafx", allowlist=file_allowlist)


@pytest.fixture
def finish(file_allowlist):
    return lambda handoff_id="h900": finish_worktree(handoff_id, "mafx", allowlist=file_allowlist)


def actions(ws):
    return ActionLog(ws / ".repo-agent" / "actions.jsonl").entries()


# ------------------------------------------------------------------------------------------------- start


def test_start_creates_the_worktree_on_a_new_branch_from_origin_main(ws, start):
    write_handoff(ws / "labs")

    result = start()

    path = ws / "worktrees" / "h900"
    assert result["status"] == "started" and result["worktree"] == str(path)
    assert git("branch", "--show-current", cwd=path) == "test/h900-demo"
    assert git("rev-parse", "HEAD", cwd=path) == git("rev-parse", "origin/main", cwd=ws / "labs")
    assert (path / ".env").read_text() == "MAF_PROVIDER=mock\n"
    assert result["next"] == f'cd {path} && claude "/handoff h900"'
    assert [w["branch"] for w in workspace_status("mafx")["worktrees"]] == ["test/h900-demo"]
    entry = actions(ws)[-1]
    assert entry["tool"] == "start_worktree" and entry["result"].startswith("started")
    assert ["git", "worktree", "add", str(path), "-b", "test/h900-demo", "origin/main"] in entry["argv"]


def test_start_reuses_an_existing_branch(ws, start):
    write_handoff(ws / "labs")
    git("branch", "test/h900-demo", "origin/main", cwd=ws / "labs")

    result = start()

    assert "existing branch test/h900-demo" in result["changes"][0]
    assert git("branch", "--show-current", cwd=ws / "worktrees" / "h900") == "test/h900-demo"


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        (lambda labs: None, "not in the handoff queue"),
        (lambda labs: write_handoff(labs, status="draft"), "h900 is draft, not ready"),
        (lambda labs: write_handoff(labs, branch="--force"), "invalid branch"),
        (lambda labs: (write_handoff(labs), (labs / "README.md").write_text("dirty\n")), "uncommitted change"),
        (lambda labs: (write_handoff(labs), (labs.parent / "worktrees" / "h900").mkdir()), "already exists"),
    ],
)
def test_start_refuses_and_changes_nothing(ws, start, setup, reason):
    setup(ws / "labs")
    before = actions(ws)

    with pytest.raises(WorktreeError, match=reason):
        start()

    assert actions(ws) == before
    assert git("branch", "--list", "test/h900-demo", cwd=ws / "labs") == ""


@pytest.mark.parametrize("handoff_id", ["../x", "h1/..", "x900", "h"])
def test_start_refuses_invalid_ids(ws, start, handoff_id):
    with pytest.raises(WorktreeError, match="invalid handoff id"):
        start(handoff_id)


# ------------------------------------------------------------------------------------------------ finish


def test_finish_merged_branch_removes_worktree_branch_and_moves_handoff(ws, start, finish):
    file = write_handoff(ws / "labs")
    start()

    result = finish()

    assert result["branch_state"] == "merged"
    assert not (ws / "worktrees" / "h900").exists()
    assert git("branch", "--list", "test/h900-demo", cwd=ws / "labs") == ""
    assert not file.exists() and (ws / "labs" / ".handoffs" / "done" / file.name).is_file()
    assert actions(ws)[-1]["tool"] == "finish_worktree"
    assert workspace_status("mafx")["worktrees"] == []


def test_finish_pushed_but_unmerged_branch_keeps_the_branch(ws, start, finish):
    file = write_handoff(ws / "labs")
    start()
    path = ws / "worktrees" / "h900"
    (path / "work.txt").write_text("work\n")
    git("add", "work.txt", cwd=path)
    git("commit", "-q", "-m", "work", cwd=path)
    git("push", "-q", "origin", "test/h900-demo", cwd=path)

    result = finish()

    assert result["branch_state"] == "pushed"
    assert not path.exists()
    assert git("branch", "--list", "test/h900-demo", cwd=ws / "labs").endswith("test/h900-demo")
    assert file.exists()  # not merged: the handoff stays in the queue


def test_finish_refuses_unpushed_commits(ws, start, finish):
    write_handoff(ws / "labs")
    start()
    path = ws / "worktrees" / "h900"
    (path / "work.txt").write_text("work\n")
    git("add", "work.txt", cwd=path)
    git("commit", "-q", "-m", "work", cwd=path)

    with pytest.raises(WorktreeError, match="not merged into origin/main and not pushed"):
        finish()
    git("push", "-q", "origin", "test/h900-demo", cwd=path)
    (path / "more.txt").write_text("more\n")
    git("add", "more.txt", cwd=path)
    git("commit", "-q", "-m", "more", cwd=path)
    with pytest.raises(WorktreeError, match="1 commit"):
        finish()
    assert path.is_dir()


def test_finish_refuses_a_dirty_worktree(ws, start, finish):
    write_handoff(ws / "labs")
    start()
    (ws / "worktrees" / "h900" / "scratch.txt").write_text("wip\n")

    with pytest.raises(WorktreeError, match="uncommitted change"):
        finish()
    assert (ws / "worktrees" / "h900").is_dir()


def test_finish_refuses_a_missing_or_foreign_worktree(ws, finish):
    with pytest.raises(WorktreeError, match="there is no worktree"):
        finish()
    (ws / "worktrees" / "h900").mkdir()
    with pytest.raises(WorktreeError, match="not a git worktree"):
        finish()


def test_finish_refuses_a_done_collision_before_any_write(ws, start, finish):
    file = write_handoff(ws / "labs")
    start()
    (ws / "labs" / ".handoffs" / "done").mkdir()
    (ws / "labs" / ".handoffs" / "done" / file.name).write_text("older copy\n")
    before = actions(ws)

    with pytest.raises(WorktreeError, match="already exists; move h900-demo.md by hand"):
        finish()

    assert (ws / "worktrees" / "h900").is_dir()
    assert git("branch", "--list", "test/h900-demo", cwd=ws / "labs").endswith("test/h900-demo")
    assert file.exists()
    assert actions(ws) == before


# ------------------------------------------------------------------------------------------- link safety


def test_start_refuses_a_symlinked_handoff(ws, start):
    queue = ws / "labs" / ".handoffs"
    queue.mkdir()
    real = ws / "labs" / "h900.txt"
    real.write_text("---\nid: h900\nstatus: ready\nbranch: test/h900-demo\n---\n")
    (queue / "h900-demo.md").symlink_to(real)

    with pytest.raises(WorktreeError, match="symbolic link"):
        start()


def test_start_never_overwrites_an_env_the_branch_tracks(ws, start):
    labs = ws / "labs"
    git("checkout", "-q", "-b", "test/h900-demo", cwd=labs)
    (labs / ".env").unlink()
    (labs / ".env").symlink_to(labs / "README.md")
    git("add", "-f", ".env", cwd=labs)
    git("commit", "-q", "-m", "tracked env link", cwd=labs)
    git("checkout", "-q", "main", cwd=labs)
    (labs / ".env").write_text("MAF_PROVIDER=mock\n")
    write_handoff(labs)

    result = start()

    assert "the worktree already has one" in result["warnings"][0]
    assert (labs / "README.md").read_text() == "labs\n"


def test_start_copies_env_readable_by_the_owner_only(ws, start):
    write_handoff(ws / "labs")
    start()
    assert (ws / "worktrees" / "h900" / ".env").stat().st_mode & 0o777 == 0o600
