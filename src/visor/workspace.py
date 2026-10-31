"""Workspace discovery and validation for CLI and MCP entry points."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse


PROJECT_MARKERS = {
    ".git",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    ".sln",
}


class WorkspaceResolutionError(RuntimeError):
    """Raised when no safe project workspace can be identified."""


def canonicalize_workspace(path: str | os.PathLike[str]) -> str:
    """Return a canonical absolute path without requiring it to be a project."""
    return os.path.abspath(os.path.realpath(os.fspath(path)))


def is_project_dir(path: str | os.PathLike[str]) -> bool:
    """Return whether *path* exists and contains a recognized project marker."""
    candidate = Path(canonicalize_workspace(path))
    return candidate.is_dir() and any(
        (candidate / marker).exists() for marker in PROJECT_MARKERS
    )


def validate_workspace(path: str | os.PathLike[str], source: str) -> str:
    """Validate an explicit workspace and return its canonical form."""
    candidate = canonicalize_workspace(path)
    if not os.path.isdir(candidate):
        raise WorkspaceResolutionError(
            f"{source} workspace does not exist: {candidate}"
        )
    if not is_project_dir(candidate):
        markers = ", ".join(sorted(PROJECT_MARKERS))
        raise WorkspaceResolutionError(
            f"{source} workspace is not a recognized project: {candidate}. "
            f"Expected one of: {markers}."
        )
    return candidate


def find_git_root(start: str | os.PathLike[str]) -> str | None:
    """Find a Git worktree root by walking upward from *start*."""
    candidate = Path(canonicalize_workspace(start))
    if not candidate.is_dir():
        return None
    for directory in (candidate, *candidate.parents):
        if (directory / ".git").exists():
            return str(directory)
    return None


def _safe_implicit_workspace(path: str) -> str | None:
    """Reject a home directory even when it happens to contain project markers."""
    candidate = canonicalize_workspace(path)
    return None if candidate == canonicalize_workspace(Path.home()) else candidate


def resolve_local_workspace(
    *,
    explicit: str | None = None,
    environ: dict[str, str] | os._Environ[str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
) -> str:
    """Resolve non-MCP sources in their required precedence order."""
    env = os.environ if environ is None else environ
    current = canonicalize_workspace(cwd or os.getcwd())

    if explicit:
        return validate_workspace(explicit, "Explicit")

    env_workspace = env.get("WORKSPACE_ROOT")
    if env_workspace:
        return validate_workspace(env_workspace, "WORKSPACE_ROOT")

    git_root = find_git_root(current)
    if git_root:
        safe_git_root = _safe_implicit_workspace(git_root)
        if safe_git_root:
            return safe_git_root

    if is_project_dir(current):
        safe_current = _safe_implicit_workspace(current)
        if safe_current:
            return safe_current

    raise WorkspaceResolutionError(
        "No V.I.S.O.R. project workspace could be resolved. Start the MCP server "
        "inside a Git/project directory, pass --workspace PATH, or set WORKSPACE_ROOT."
    )


def file_uri_to_path(uri: str) -> str | None:
    """Convert a local file URI to a filesystem path."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    if parsed.netloc not in ("", "localhost"):
        return None
    path = unquote(parsed.path)
    if os.name == "nt" and len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return canonicalize_workspace(path)


def resolve_mcp_roots(roots: Iterable[object]) -> str:
    """Return the first valid local project advertised by an MCP client."""
    rejected: list[str] = []
    for root in roots:
        uri = str(getattr(root, "uri", ""))
        path = file_uri_to_path(uri)
        if path and is_project_dir(path):
            return path
        if uri:
            rejected.append(uri)

    detail = f" Advertised roots: {', '.join(rejected)}." if rejected else ""
    raise WorkspaceResolutionError(
        "The MCP client did not provide a valid local project root." + detail
    )
