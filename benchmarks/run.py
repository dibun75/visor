#!/usr/bin/env python3
"""Run one reproducible coding-agent benchmark cell."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import signal
import subprocess
import time
from pathlib import Path
from typing import Any


def load_task(manifest: Path, task_id: str) -> dict[str, Any]:
    tasks = json.loads(manifest.read_text(encoding="utf-8"))["tasks"]
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise ValueError(f"Task {task_id!r} is not present in {manifest}.")


def _as_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def _changed_files(workspace: Path) -> list[str]:
    tracked = subprocess.run(
        ["git", "-C", str(workspace), "diff", "--name-only", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "-C", str(workspace), "ls-files", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    names = set(tracked + untracked)
    return sorted(
        path
        for path in names
        if "__pycache__" not in Path(path).parts and not path.endswith(".pyc")
    )


def _signal_process_group(process: subprocess.Popen[str], sig: int) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        return


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
) -> tuple[int, str, str, bool, bool]:
    """Run a command in its own session so an interrupt can stop its children."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode or 0, stdout or "", stderr or "", False, False
    except subprocess.TimeoutExpired as exc:
        _signal_process_group(process, signal.SIGTERM)
        try:
            extra_out, extra_err = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            _signal_process_group(process, signal.SIGKILL)
            extra_out, extra_err = process.communicate()
        stdout = _as_text(exc.stdout) + _as_text(extra_out)
        stderr = _as_text(exc.stderr) + _as_text(extra_err)
        return 124, stdout, stderr, True, False
    except KeyboardInterrupt:
        _signal_process_group(process, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            _signal_process_group(process, signal.SIGKILL)
            stdout, stderr = process.communicate()
        return 130, stdout or "", stderr or "", False, True


def _run_evaluator(task: dict[str, Any], workspace: Path) -> dict[str, Any] | None:
    evaluator = task.get("evaluator")
    if evaluator is None:
        return None
    command = evaluator.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(part, str) and part for part in command)
    ):
        raise ValueError("task evaluator.command must be a non-empty string list")
    timeout = float(evaluator.get("timeout_seconds", 120))
    if timeout <= 0:
        raise ValueError("task evaluator.timeout_seconds must be greater than zero")
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(workspace), env["PYTHONPATH"]]
        if env.get("PYTHONPATH")
        else [str(workspace)]
    )
    exit_code, stdout, stderr, timed_out, _interrupted = _run_command(
        command,
        cwd=workspace,
        env=env,
        timeout=timeout,
    )
    return {
        "command": command,
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "duration_seconds": time.monotonic() - started,
        "timed_out": timed_out,
        "interrupted": _interrupted,
        "changed_files": _changed_files(workspace),
        "stdout": stdout,
        "stderr": stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
    record: dict[str, Any] = {
        "schema_version": 3,
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
    interrupted = False
    if args.dry_run:
        record.update({"dry_run": True, "exit_code": None, "duration_seconds": 0})
    else:
        started = time.monotonic()
        exit_code, stdout, stderr, timed_out, interrupted = _run_command(
            command,
            cwd=workspace,
            env={**os.environ, "VISOR_BENCHMARK_CONDITION": args.condition},
            timeout=args.timeout,
        )
        record.update(
            {
                "exit_code": exit_code,
                "duration_seconds": time.monotonic() - started,
                "stdout": stdout,
                "stderr": stderr,
            }
        )
        if timed_out:
            record["timed_out"] = True
        if interrupted:
            record["interrupted"] = True
        try:
            evaluation = _run_evaluator(task, workspace)
        except ValueError as exc:
            parser.error(str(exc))
        if evaluation is not None:
            if evaluation.pop("interrupted", False):
                interrupted = True
                record["interrupted"] = True
                record["exit_code"] = 130
            record["evaluation"] = evaluation
            record["patch_success"] = bool(
                record["exit_code"] == 0 and evaluation["passed"]
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if interrupted:
        raise KeyboardInterrupt
    return 0 if args.dry_run or record["exit_code"] == 0 else record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
