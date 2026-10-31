"""Filesystem containment helpers."""

from pathlib import Path


def is_within(root: str | Path, candidate: str | Path) -> bool:
    root_path = Path(root).resolve()
    candidate_path = Path(candidate).resolve()
    return str(candidate_path).startswith(str(root_path))
