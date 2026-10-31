from pathlib import Path

import pytest

from visor.workspace import (
    WorkspaceResolutionError,
    file_uri_to_path,
    resolve_local_workspace,
    resolve_mcp_roots,
)


def make_project(path: Path, marker: str = "pyproject.toml") -> Path:
    path.mkdir(parents=True)
    (path / marker).write_text('[project]\nname = "fixture"\n')
    return path


def test_local_workspace_precedence(tmp_path):
    explicit = make_project(tmp_path / "explicit")
    environment = make_project(tmp_path / "environment")
    git_project = make_project(tmp_path / "git", ".git")
    nested = git_project / "src"
    nested.mkdir()

    assert resolve_local_workspace(
        explicit=str(explicit),
        environ={"WORKSPACE_ROOT": str(environment)},
        cwd=nested,
    ) == str(explicit.resolve())
    assert resolve_local_workspace(
        environ={"WORKSPACE_ROOT": str(environment)},
        cwd=nested,
    ) == str(environment.resolve())
    assert resolve_local_workspace(environ={}, cwd=nested) == str(git_project.resolve())


def test_local_workspace_rejects_unrecognized_cwd(tmp_path):
    with pytest.raises(WorkspaceResolutionError, match="No V.I.S.O.R. project"):
        resolve_local_workspace(environ={}, cwd=tmp_path)


def test_mcp_roots_accept_first_valid_file_project(tmp_path):
    invalid = tmp_path / "plain"
    invalid.mkdir()
    project = make_project(tmp_path / "project")

    class Root:
        def __init__(self, uri):
            self.uri = uri

    resolved = resolve_mcp_roots([Root(invalid.as_uri()), Root(project.as_uri())])
    assert resolved == str(project.resolve())


def test_file_uri_rejects_remote_hosts():
    assert file_uri_to_path("file://remote-host/project") is None


def test_implicit_home_workspace_is_rejected(tmp_path, monkeypatch):
    home = make_project(tmp_path / "home", ".git")
    monkeypatch.setattr("visor.workspace.Path.home", lambda: home)

    with pytest.raises(WorkspaceResolutionError, match="No V.I.S.O.R. project"):
        resolve_local_workspace(environ={}, cwd=home)
