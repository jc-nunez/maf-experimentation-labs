"""Offline fixtures: a bare origin with one commit on main, and a temporary workspaces root."""

import subprocess

import pytest
from repo_agent.guards import slice1_allowlist

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
}


def git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture(autouse=True)
def git_identity(monkeypatch):
    for key, value in GIT_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def origin(tmp_path):
    """file:// URL of a bare repo whose main has one commit."""
    bare = tmp_path / "origin" / "labs.git"
    seed = tmp_path / "seed"
    git("init", "-q", "--bare", "-b", "main", str(bare))
    git("init", "-q", "-b", "main", str(seed))
    (seed / "README.md").write_text("labs\n")
    git("add", ".", cwd=seed)
    git("commit", "-q", "-m", "initial commit", cwd=seed)
    git("push", "-q", str(bare), "main", cwd=seed)
    return f"file://{bare}"


@pytest.fixture
def root(tmp_path, monkeypatch):
    path = tmp_path / "workspaces"
    monkeypatch.setenv("REPO_AGENT_ROOT", str(path))
    return path


@pytest.fixture
def repos(origin):
    return [{"name": "labs", "url": origin, "default_branch": "main"}]


@pytest.fixture
def file_allowlist():
    """The slice 1 allowlist, also accepting file:// URLs so tests can clone the local bare origin."""
    return slice1_allowlist(("https", "file"))
