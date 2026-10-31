#!/usr/bin/env python3
"""Run the randomized paired Codex/Claude diagnostic or patch pilot."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cell:
    task: str
    agent: str
    condition: str
    run_id: str


def output_path(results: Path, cell: Cell) -> Path:
    return results / f"{cell.task}-{cell.agent}-{cell.condition}-{cell.run_id}.json"


def completed_successfully(results: Path, cell: Cell) -> bool:
    path = output_path(results, cell)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return record.get("exit_code") == 0


def build_cells(task_ids: list[str], repeats: int, seed: int) -> list[Cell]:
    cells = [
        Cell(task, agent, condition, f"r{repeat}")
        for repeat in range(1, repeats + 1)
        for task in task_ids
        for agent in ("codex", "claude-code")
        for condition in ("native", "visor")
    ]
    random.Random(seed).shuffle(cells)
    return cells


def _cell_name(cell: Cell) -> str:
    return f"{cell.task}-{cell.agent}-{cell.condition}-{cell.run_id}"


def prepare_worktrees(
    source: Path, destination: Path, cells: list[Cell], revision: str
) -> dict[Cell, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    mapping = {}
    for cell in cells:
        workspace = (destination / _cell_name(cell)).resolve()
        if workspace.exists():
            removed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "worktree",
                    "remove",
                    "--force",
                    str(workspace),
                ],
                capture_output=True,
                text=True,
            )
            if workspace.exists():
                if removed.returncode != 0 and not (workspace / ".git").exists():
                    shutil.rmtree(workspace)
                else:
                    raise ValueError(f"worktree already exists: {workspace}")
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "worktree",
                "add",
                "--detach",
                str(workspace),
                revision,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        mapping[cell] = workspace
    return mapping


def _run_cell(
    args: argparse.Namespace, cell: Cell, workspace: Path
) -> tuple[Cell, int]:
    agent_key = "codex" if cell.agent == "codex" else "claude"
    command = getattr(args, f"{agent_key}_{cell.condition}_command") or getattr(
        args, f"{agent_key}_command"
    )
    model = getattr(args, f"{agent_key}_model")
    client_version = getattr(args, f"{agent_key}_client_version")
    output = output_path(args.results, cell)
    invocation = [
        sys.executable,
        str(Path(__file__).with_name("run.py")),
        "--manifest",
        str(args.manifest),
        "--task",
        cell.task,
        "--agent",
        cell.agent,
        "--condition",
        cell.condition,
        "--workspace",
        str(workspace),
        "--command",
        command,
        "--model",
        model,
        "--client-version",
        client_version,
        "--run-id",
        cell.run_id,
        "--timeout",
        str(args.timeout),
        "--output",
        str(output),
    ]
    if cell.condition == "visor":
        invocation.extend(["--context-file", str(args.contexts / f"{cell.task}.json")])
    if args.dry_run:
        invocation.append("--dry-run")
    completed = subprocess.run(invocation)
    return cell, completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--worktrees", type=Path)
    parser.add_argument("--contexts", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--codex-command")
    parser.add_argument("--codex-native-command")
    parser.add_argument("--codex-visor-command")
    parser.add_argument("--claude-command")
    parser.add_argument("--claude-native-command")
    parser.add_argument("--claude-visor-command")
    parser.add_argument("--codex-model", required=True)
    parser.add_argument("--codex-client-version", required=True)
    parser.add_argument("--claude-model", required=True)
    parser.add_argument("--claude-client-version", required=True)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip cells whose existing result has exit_code 0",
    )
    args = parser.parse_args()

    for agent in ("codex", "claude"):
        shared = getattr(args, f"{agent}_command")
        native = getattr(args, f"{agent}_native_command")
        visor = getattr(args, f"{agent}_visor_command")
        if not shared and not (native and visor):
            parser.error(
                f"provide --{agent}-command or both condition-specific commands"
            )

    if args.repeats < 1 or args.concurrency < 1 or args.timeout <= 0:
        parser.error("repeats, concurrency, and timeout must be greater than zero")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task_ids = [task["id"] for task in manifest["tasks"]]
    revisions = {task.get("revision") for task in manifest["tasks"]}
    if len(revisions) != 1 or None in revisions:
        parser.error("all pilot tasks must declare the same immutable revision")
    revision = revisions.pop()
    missing = [
        task for task in task_ids if not (args.contexts / f"{task}.json").is_file()
    ]
    if missing:
        parser.error(f"missing context files: {', '.join(missing)}")

    args.results.mkdir(parents=True, exist_ok=True)
    all_cells = build_cells(task_ids, args.repeats, args.seed)
    cells = (
        [cell for cell in all_cells if not completed_successfully(args.results, cell)]
        if args.resume
        else all_cells
    )
    if args.worktrees:
        try:
            workspaces = prepare_worktrees(
                args.workspace.resolve(), args.worktrees.resolve(), cells, revision
            )
        except (ValueError, subprocess.CalledProcessError) as exc:
            parser.error(str(exc))
    else:
        workspaces = {cell: args.workspace.resolve() for cell in cells}

    plan = {
        "schema_version": 2,
        "seed": args.seed,
        "repeats": args.repeats,
        "concurrency": args.concurrency,
        "resume": args.resume,
        "revision": revision,
        "isolated_worktrees": bool(args.worktrees),
        "cells": [cell.__dict__ for cell in all_cells],
        "scheduled_cells": [cell.__dict__ for cell in cells],
    }
    (args.results / "plan.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8"
    )

    failures = 0
    executor = ThreadPoolExecutor(max_workers=args.concurrency)
    futures = {
        executor.submit(_run_cell, args, cell, workspaces[cell]): cell for cell in cells
    }
    try:
        completed_count = 0
        for future in as_completed(futures):
            cell, returncode = future.result()
            completed_count += 1
            failures += returncode != 0
            print(
                f"[{completed_count}/{len(cells)}] {cell.task} {cell.agent} "
                f"{cell.condition} {cell.run_id}: exit {returncode}",
                flush=True,
            )
    except KeyboardInterrupt:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        print(
            "Interrupted. Child benchmark processes were asked to stop.",
            file=sys.stderr,
        )
        return 130
    executor.shutdown(wait=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
