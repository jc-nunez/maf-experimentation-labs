"""create_workspace, workspace_status and format_status on temp dirs with a bare origin."""

import subprocess

import pytest
import yaml
from repo_agent.guards import ActionLog, GuardError
from repo_agent.workspace import WorkspaceError, create_workspace, format_status, workspace_status


def test_create_workspace_layout(root, repos, file_allowlist):
    result = create_workspace("mafx", repos, allowlist=file_allowlist)

    ws = root.resolve() / "mafx"
    assert result["status"] == "created"
    assert (ws / "labs" / ".git").is_dir() and (ws / "labs" / "README.md").is_file()
    assert (ws / "worktrees").is_dir() and not any((ws / "worktrees").iterdir())
    config = yaml.safe_load((ws / ".repo-agent" / "config.yaml").read_text())
    assert config == {"project": "mafx", "repos": repos}
    entries = ActionLog(ws / ".repo-agent" / "actions.jsonl").entries()
    assert len(entries) == 1
    assert entries[0]["tool"] == "create_workspace" and entries[0]["caller"] == "mcp"
    assert entries[0]["argv"] == [["git", "clone", "--", repos[0]["url"], "labs"]]


def test_create_workspace_is_idempotent(root, repos, file_allowlist):
    create_workspace("mafx", repos, allowlist=file_allowlist)
    config = root / "mafx" / ".repo-agent" / "config.yaml"
    before = config.stat().st_mtime_ns

    again = create_workspace("mafx", repos, allowlist=file_allowlist)

    assert again["status"] == "unchanged" and "nothing changed" in again["message"]
    assert config.stat().st_mtime_ns == before
    assert len(ActionLog(root / "mafx" / ".repo-agent" / "actions.jsonl").entries()) == 1


def test_create_workspace_clones_only_https_by_default(root, repos):
    with pytest.raises(GuardError):
        create_workspace("mafx", repos)
    assert not (root / "mafx" / "labs").exists()


def test_create_workspace_refuses_bad_names(root, origin, file_allowlist):
    with pytest.raises(GuardError):
        create_workspace("../evil", [{"name": "labs", "url": origin}], allowlist=file_allowlist)
    with pytest.raises(GuardError):
        create_workspace("mafx", [{"name": "../evil", "url": origin}], allowlist=file_allowlist)


def test_create_workspace_failed_clone_is_logged(root, tmp_path, file_allowlist):
    with pytest.raises(WorkspaceError):
        create_workspace("mafx", [{"name": "labs", "url": f"file://{tmp_path}/nope.git"}], allowlist=file_allowlist)
    entries = ActionLog(root / "mafx" / ".repo-agent" / "actions.jsonl").entries()
    assert entries[-1]["result"].startswith("failed")


def test_status_of_a_fresh_workspace(root, repos, file_allowlist):
    create_workspace("mafx", repos, allowlist=file_allowlist)

    status = workspace_status("mafx")

    repo = status["repos"][0]
    assert repo["branch"] == "main" and repo["clean"] and repo["behind"] == 0 and repo["upstream"] == "origin/main"
    assert repo["last_commit"].endswith("initial commit")
    assert status["worktrees"] == [] and status["handoffs"] == [] and status["prs"] == []
    table = format_status(status).splitlines()
    assert table[1] == " REPOS      labs  main  ✓ clean  behind 0 (as of last fetch)"
    assert table[2:] == [" WORKTREES  none", " HANDOFFS   none", " PRS        none open"]


def test_status_shows_changes_worktrees_and_handoffs(root, repos, file_allowlist):
    create_workspace("mafx", repos, allowlist=file_allowlist)
    ws = root / "mafx"
    (ws / "labs" / "scratch.txt").write_text("wip\n")
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "bet/x", str(ws / "worktrees" / "x")], cwd=ws / "labs", check=True
    )
    (ws / "labs" / ".git" / "info" / "exclude").write_text(".handoffs/\n")  # as the real repo's .gitignore
    queue = ws / "labs" / ".handoffs"
    (queue / "done").mkdir(parents=True)
    (queue / "h003-mail.md").write_text("---\nid: h003\nstatus: draft     # waiting\n---\n# h003: mail\n")
    (queue / "done" / "h001-old.md").write_text("---\nid: h001\nstatus: done\n---\n")

    status = workspace_status("mafx")

    assert status["repos"][0]["changes"] == 1 and not status["repos"][0]["clean"]
    assert [w["branch"] for w in status["worktrees"]] == ["bet/x"]
    assert status["handoffs"] == [{"repo": "labs", "id": "h003", "status": "draft", "title": "h003: mail"}]
    table = format_status(status)
    assert "✗ 1 changed" in table and " HANDOFFS   h003 draft" in table and "bet/x" in table


def test_status_of_a_missing_workspace(root):
    status = workspace_status("mafx")
    assert status["exists"] is False
    assert "not created yet" in format_status(status)


def test_format_status_cuts_long_pr_titles():
    long_title = "feat(repo-agent): add start_worktree and finish_worktree with every precondition"
    status = {
        "exists": True,
        "workspace": "/tmp/ws",
        "repos": [],
        "worktrees": [],
        "handoffs": [],
        "prs": [
            {"repo": "labs", "number": 7, "headRefName": "bet/x", "title": long_title, "isDraft": False},
            {"repo": "labs", "number": 8, "headRefName": "bet/y", "title": "short", "isDraft": True},
        ],
        "errors": [],
    }

    prs = [line for line in format_status(status).splitlines() if "#" in line]

    title = prs[0].split("bet/x  ", 1)[1]
    assert len(title) == 60 and title.endswith("…") and long_title.startswith(title[:-1])
    assert prs[1].endswith("#8 bet/y  short  (draft)")
