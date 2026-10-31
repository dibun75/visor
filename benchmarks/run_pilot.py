#!/usr/bin/env python3
"""Run the randomized paired Codex/Claude diagnostic pilot."""

from __future__ import annotations

import argparse
import json
import random
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


def _run_cell(args: argparse.Namespace, cell: Cell) -> tuple[Cell, int]:
    agent_key = "codex" if cell.agent == "codex" else "claude"
    command = getattr(args, f"{agent_key}_command")
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
        str(args.workspace),
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
    parser.add_argument("--contexts", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--codex-command", required=True)
    parser.add_argument("--codex-model", required=True)
    parser.add_argument("--codex-client-version", required=True)
    parser.add_argument("--claude-command", required=True)
    parser.add_argument("--claude-model", required=True)
    parser.add_argument("--claude-client-version", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip cells whose existing result has exit_code 0",
    )
    args = parser.parse_args()

    if args.repeats < 1 or args.concurrency < 1 or args.timeout <= 0:
        parser.error("repeats, concurrency, and timeout must be greater than zero")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task_ids = [task["id"] for task in manifest["tasks"]]
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
    plan = {
        "schema_version": 1,
        "seed": args.seed,
        "repeats": args.repeats,
        "concurrency": args.concurrency,
        "resume": args.resume,
        "cells": [cell.__dict__ for cell in all_cells],
        "scheduled_cells": [cell.__dict__ for cell in cells],
    }
    (args.results / "plan.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8"
    )

    failures = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {executor.submit(_run_cell, args, cell): cell for cell in cells}
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
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
