"""Utilities for scoring initial benchmark context against predeclared gold files."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_repo_path(value: str, workspace: Path | None = None) -> str:
    """Return a stable POSIX repository-relative path when possible."""
    path = Path(value)
    if workspace is not None:
        try:
            path = path.resolve().relative_to(workspace.resolve())
        except (OSError, ValueError):
            pass
    return path.as_posix().lstrip("./")


def context_files(payload: dict[str, Any], workspace: Path | None = None) -> list[str]:
    """Extract unique file paths, preserving their first context order."""
    files: list[str] = []
    for node in payload.get("context", []):
        value = node.get("file_path") if isinstance(node, dict) else None
        if not isinstance(value, str) or not value:
            continue
        normalized = normalize_repo_path(value, workspace)
        if normalized not in files:
            files.append(normalized)
    return files


def score_gold_files(
    gold_files: list[str], selected_files: list[str]
) -> dict[str, Any]:
    """Score gold-file coverage in an initial ordered file selection."""
    gold = [normalize_repo_path(path) for path in gold_files]
    selected = [normalize_repo_path(path) for path in selected_files]
    hits = [path for path in gold if path in selected]
    missing = [path for path in gold if path not in selected]
    ranks = {path: selected.index(path) + 1 for path in hits}
    return {
        "gold_files": gold,
        "selected_files": selected,
        "hits": hits,
        "missing": missing,
        "recall": len(hits) / len(gold) if gold else None,
        "ranks": ranks,
    }
