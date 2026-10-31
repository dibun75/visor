#!/usr/bin/env python3
"""Run one reproducible coding-agent benchmark cell.

The harness does not invoke an agent provider itself. Callers supply an exact
command template, making credentials, model selection, and client versions
explicit in the saved run configuration rather than implicit in this script.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def load_task(manifest: Path, task_id: str) -> dict:
    tasks = json.loads(manifest.read_text(encoding="utf-8"))["tasks"]
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise ValueError(f"Task {task_id!r} is not present in {manifest}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one paired benchmark cell")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--agent", choices=("codex", "claude-code"), required=True)
    parser.add_argument("--condition", choices=("native", "visor"), required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--command", required=True, help="Template using {prompt} and {workspace}")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    task = load_task(args.manifest, args.task)
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        parser.error(f"Workspace does not exist: {workspace}")
    command = args.command.format(prompt=task["prompt"], workspace=workspace)
    record = {
        "schema_version": 1,
        "task": task,
        "agent": args.agent,
        "condition": args.condition,
        "model": args.model,
        "workspace": str(workspace),
        "command": command,
        "started_at_epoch": time.time(),
    }
    if args.dry_run:
        record.update({"dry_run": True, "exit_code": None, "duration_seconds": 0})
    else:
        started = time.monotonic()
        completed = subprocess.run(
            command, shell=True, cwd=workspace, text=True, capture_output=True,
            env={**os.environ, "VISOR_BENCHMARK_CONDITION": args.condition},
        )
        record.update({
            "exit_code": completed.returncode,
            "duration_seconds": time.monotonic() - started,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0 if args.dry_run or record["exit_code"] == 0 else record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
