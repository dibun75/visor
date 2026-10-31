#!/usr/bin/env python3
"""Run one reproducible coding-agent benchmark cell.

The harness does not invoke an agent provider itself. Callers supply an exact
command template, making credentials, model selection, and client versions
explicit in the saved run configuration rather than implicit in this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import os
import shlex
import subprocess
import time
from pathlib import Path


def load_task(manifest: Path, task_id: str) -> dict:
    tasks = json.loads(manifest.read_text(encoding="utf-8"))["tasks"]
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise ValueError(f"Task {task_id!r} is not present in {manifest}.")


def _as_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one paired benchmark cell")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--agent", choices=("codex", "claude-code"), required=True)
    parser.add_argument("--condition", choices=("native", "visor"), required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--command", required=True, help="Template using {prompt} and {workspace}"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--client-version", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--context-file", type=Path)
    args = parser.parse_args()

    task = load_task(args.manifest, args.task)
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        parser.error(f"Workspace does not exist: {workspace}")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    expected_revision = task.get("revision")
    if not expected_revision:
        parser.error(f"Task {args.task!r} does not declare an immutable revision")
    actual_revision = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual_revision != expected_revision:
        parser.error(
            f"Workspace revision {actual_revision} does not match task revision "
            f"{expected_revision}"
        )
    if args.condition == "visor" and args.context_file is None:
        parser.error("--context-file is required for the visor condition")
    if args.condition == "visor" and not (
        "{context}" in args.command or "{context_file}" in args.command
    ):
        parser.error("visor command must use {context} or {context_file}")
    if args.condition == "native" and args.context_file is not None:
        parser.error("--context-file is not allowed for the native condition")
    context_path = args.context_file.resolve() if args.context_file else None
    context = context_path.read_text(encoding="utf-8") if context_path else ""
    values = {
        "prompt": task["prompt"],
        "workspace": workspace,
        "context": context,
        "context_file": context_path or "",
    }
    command = [part.format(**values) for part in shlex.split(args.command)]
    recorded_command = [
        part.replace(context, "<VISOR_CONTEXT>") if context else part
        for part in command
    ]
    record = {
        "schema_version": 2,
        "task": task,
        "agent": args.agent,
        "condition": args.condition,
        "model": args.model,
        "workspace": str(workspace),
        "command": recorded_command,
        "timeout_seconds": args.timeout,
        "client_version": args.client_version,
        "run_id": args.run_id,
        "machine": platform.platform(),
        "python_version": platform.python_version(),
        "context_sha256": hashlib.sha256(context.encode()).hexdigest()
        if context
        else None,
        "started_at_epoch": time.time(),
    }
    if args.dry_run:
        record.update({"dry_run": True, "exit_code": None, "duration_seconds": 0})
    else:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                timeout=args.timeout,
                cwd=workspace,
                text=True,
                capture_output=True,
                env={**os.environ, "VISOR_BENCHMARK_CONDITION": args.condition},
            )
            record.update(
                {
                    "exit_code": completed.returncode,
                    "duration_seconds": time.monotonic() - started,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
        except subprocess.TimeoutExpired as exc:
            record.update(
                {
                    "exit_code": 124,
                    "duration_seconds": time.monotonic() - started,
                    "stdout": _as_text(exc.stdout),
                    "stderr": _as_text(exc.stderr),
                    "timed_out": True,
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0 if args.dry_run or record["exit_code"] == 0 else record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
