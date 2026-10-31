#!/usr/bin/env python3
"""Materialize the deterministic patch fixture, manifest, and V.I.S.O.R. contexts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).with_name("fixtures") / "patch_repo"
TASKS = [
    {
        "id": "patch-discount",
        "category": "patch-correctness",
        "prompt": (
            "Fix the percentage discount calculation while preserving its validation. "
            "Run python checks/check_discounts.py and make the smallest justified change."
        ),
        "query": "fix percentage discount calculation validation",
        "evidence": ["app/discounts.py", "apply_discount"],
        "evaluator": {
            "command": ["python", "checks/check_discounts.py"],
            "timeout_seconds": 30,
        },
    },
    {
        "id": "patch-retry",
        "category": "patch-correctness",
        "prompt": (
            "Fix the exponential retry schedule so the first delay equals the base. "
            "Run python checks/check_retry.py and make the smallest justified change."
        ),
        "query": "fix exponential retry first delay base",
        "evidence": ["app/retry.py", "retry_delays"],
        "evaluator": {
            "command": ["python", "checks/check_retry.py"],
            "timeout_seconds": 30,
        },
    },
    {
        "id": "patch-paths",
        "category": "patch-correctness",
        "prompt": (
            "Fix filesystem containment so sibling paths with the same prefix are rejected. "
            "Run python checks/check_paths.py and make the smallest justified change."
        ),
        "query": "fix filesystem containment sibling path prefix",
        "evidence": ["app/paths.py", "is_within"],
        "evaluator": {
            "command": ["python", "checks/check_paths.py"],
            "timeout_seconds": 30,
        },
    },
]


def _run(
    command: list[str], cwd: Path, *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=check, capture_output=True, text=True)


def _json_output(value: str) -> dict[str, Any]:
    start = value.find("{")
    if start < 0:
        raise ValueError("command did not emit a JSON object")
    return json.loads(value[start:])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--contexts", type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if workspace.exists() and any(workspace.iterdir()):
        parser.error(f"workspace must be absent or empty: {workspace}")
    if workspace.exists():
        workspace.rmdir()
    shutil.copytree(FIXTURE, workspace)

    _run(["git", "init", "-q"], workspace)
    _run(["git", "config", "user.email", "benchmark@example.com"], workspace)
    _run(["git", "config", "user.name", "V.I.S.O.R. Benchmark"], workspace)
    _run(["git", "add", "."], workspace)
    commit_env = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
    }
    subprocess.run(
        ["git", "commit", "-qm", "seed patch benchmark"],
        cwd=workspace,
        check=True,
        env=commit_env,
    )
    revision = _run(["git", "rev-parse", "HEAD"], workspace).stdout.strip()

    tasks = []
    for definition in TASKS:
        task = {**definition, "revision": revision}
        baseline = _run(task["evaluator"]["command"], workspace, check=False)
        if baseline.returncode == 0:
            parser.error(f"fixture unexpectedly passes before patch: {task['id']}")
        tasks.append(task)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(
            {"version": 1, "fixture_revision": revision, "tasks": tasks}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )

    if args.contexts is not None:
        args.contexts.mkdir(parents=True, exist_ok=True)
        cli = [sys.executable, "-m", "visor.cli", "--workspace", str(workspace)]
        _run([*cli, "index"], workspace)
        for task in tasks:
            completed = _run(
                [*cli, "context", task["query"], "--skill", "bug-fixer", "--json"],
                workspace,
            )
            context = _json_output(completed.stdout)
            (args.contexts / f"{task['id']}.json").write_text(
                json.dumps(context, indent=2) + "\n", encoding="utf-8"
            )

    print(
        json.dumps(
            {"workspace": str(workspace), "revision": revision, "tasks": len(tasks)}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
