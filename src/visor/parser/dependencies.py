"""Normalize parser dependency edges into workspace-scoped file identities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".cxx",
    ".hpp",
    ".cs",
}

_INDEX_NAMES = (
    "__init__.py",
    "index.ts",
    "index.tsx",
    "index.js",
    "index.jsx",
    "mod.rs",
    "lib.rs",
)


def canonical_file(path: str | os.PathLike[str]) -> str:
    return str(Path(path).resolve())


def _existing_source(path: Path) -> list[Path]:
    if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS:
        return [path.resolve()]
    if path.is_dir():
        indexed = [path / name for name in _INDEX_NAMES if (path / name).is_file()]
        if indexed:
            return [candidate.resolve() for candidate in indexed]
        return sorted(
            candidate.resolve()
            for candidate in path.iterdir()
            if candidate.is_file() and candidate.suffix.lower() in SOURCE_EXTENSIONS
        )
    if path.suffix:
        return []
    return [
        candidate.resolve()
        for extension in SOURCE_EXTENSIONS
        if (candidate := path.with_suffix(extension)).is_file()
    ]


def _raw_path_variants(
    raw_target: str, source_file: Path, workspace_root: Path
) -> list[Path]:
    raw = raw_target.strip().strip("'\"<>")
    variants: list[Path] = []

    if raw.startswith(("./", "../")):
        variants.append(source_file.parent / raw)
    elif raw.startswith(".") and source_file.suffix == ".py":
        relative = raw.lstrip(".").replace(".", "/")
        variants.append(source_file.parent / relative)
    elif raw.startswith(("crate::", "self::", "super::")):
        rust_parts = raw.replace("::", "/").split("/")
        while rust_parts and rust_parts[0] in {"crate", "self", "super"}:
            rust_parts.pop(0)
        for end in range(len(rust_parts), 0, -1):
            variants.append(workspace_root / "src" / Path(*rust_parts[:end]))
    else:
        variants.append(source_file.parent / raw)
        variants.append(workspace_root / raw)
        dotted = raw.replace("::", "/").replace(".", "/")
        variants.append(workspace_root / dotted)
        parts = [part for part in dotted.split("/") if part]
        for start in range(1, len(parts)):
            variants.append(workspace_root / Path(*parts[start:]))

    return variants


def resolve_import_target(
    source_file: str, raw_target: str, workspace_root: str
) -> list[str]:
    """Resolve an import/include to canonical workspace files, if possible."""
    source = Path(source_file).resolve()
    root = Path(workspace_root).resolve()
    matches: list[Path] = []

    for variant in _raw_path_variants(raw_target, source, root):
        matches.extend(_existing_source(variant))

    if not matches:
        raw = raw_target.strip().strip("'\"<>")
        suffixes = {
            raw.replace("::", "/").replace(".", "/"),
            "/".join(raw.replace("::", "/").split("/")[-2:]),
        }
        for candidate in root.rglob("*"):
            if (
                not candidate.is_file()
                or candidate.suffix.lower() not in SOURCE_EXTENSIONS
            ):
                continue
            relative = candidate.relative_to(root).as_posix()
            relative_without_extension = relative[: -len(candidate.suffix)]
            if any(
                relative_without_extension.endswith(suffix)
                for suffix in suffixes
                if suffix
            ):
                matches.append(candidate.resolve())

    unique = sorted(
        {
            match
            for match in matches
            if match != source and (root == match.parent or root in match.parents)
        }
    )
    return [str(match) for match in unique]


def _unresolved_kind(source_file: str, raw_target: str) -> str:
    raw = raw_target.strip()
    suffix = Path(source_file).suffix.lower()
    if raw.startswith("<") and raw.endswith(">"):
        return "external"
    if raw.startswith(("./", "../", ".")):
        return "unresolved"
    if raw.startswith(("crate::", "self::", "super::")):
        return "unresolved"
    if suffix in {".c", ".h", ".cpp", ".cc", ".cxx", ".hpp"}:
        return "unresolved"
    return "external"


def normalize_edges(
    *,
    source_file: str,
    parser_edges: Iterable[dict[str, str]],
    workspace_root: str,
    db_client: Any,
) -> list[dict[str, str]]:
    """Return canonical edge rows with explicit resolution metadata."""
    source = canonical_file(source_file)
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()

    for edge in parser_edges:
        relation = edge["type"].upper()
        raw_target = edge["to"].strip()
        targets: list[str] = []
        target_symbol = ""
        ambiguous = False

        if relation == "IMPORTS":
            candidates = resolve_import_target(source, raw_target, workspace_root)
            if len(candidates) == 1:
                targets = candidates
            elif len(candidates) > 1:
                ambiguous = True
        elif relation == "CALLS":
            target_symbol = raw_target
            rows = db_client.conn.execute(
                "SELECT DISTINCT file_path FROM code_nodes "
                "WHERE name = ? AND file_path != ?",
                (raw_target, source),
            ).fetchall()
            candidates = sorted({canonical_file(row[0]) for row in rows})
            if len(candidates) == 1:
                targets = candidates

        if targets:
            for target in targets:
                key = (
                    source,
                    target,
                    relation,
                    raw_target,
                    target_symbol,
                    "internal",
                )
                if key not in seen:
                    seen.add(key)
                    normalized.append(
                        {
                            "from": source,
                            "to": target,
                            "type": relation,
                            "raw_target": raw_target,
                            "target_symbol": target_symbol,
                            "resolution": "internal",
                        }
                    )
        else:
            resolution = (
                "unresolved"
                if ambiguous
                else _unresolved_kind(source, raw_target)
                if relation == "IMPORTS"
                else "unresolved"
            )
            key = (
                source,
                raw_target,
                relation,
                raw_target,
                target_symbol,
                resolution,
            )
            if key not in seen:
                seen.add(key)
                normalized.append(
                    {
                        "from": source,
                        "to": raw_target,
                        "type": relation,
                        "raw_target": raw_target,
                        "target_symbol": target_symbol,
                        "resolution": resolution,
                    }
                )

    return normalized
