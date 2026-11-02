#!/usr/bin/env python3
"""Prepare hidden-cause patch tasks and audit their initial V.I.S.O.R. context."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from benchmarks.context_coverage import context_files, score_gold_files
except ModuleNotFoundError:  # Direct script execution
    from context_coverage import context_files, score_gold_files

FIXTURE = Path(__file__).with_name("fixtures") / "adversarial_repo"
TASKS = [
    {
        "id": "hidden-invoice-rounding",
        "category": "hidden-cause-patch",
        "prompt": (
            "Invoice totals can be one cent too low for fractional line items. "
            "Fix the underlying cause, run python checks/check_invoice.py, and "
            "make the smallest justified change."
        ),
        "query": "invoice totals one cent low fractional line items",
        "gold_files": ["app/kernel/arithmetic.py"],
        "decoy_files": ["app/api/invoices.py"],
        "evidence": ["app/kernel/arithmetic.py", "settle"],
        "evaluator": {
            "command": ["python", "checks/check_invoice.py"],
            "timeout_seconds": 30,
            "require_gold_change": True,
        },
    },
    {
        "id": "hidden-webhook-signature",
        "category": "hidden-cause-patch",
        "prompt": (
            "A retried webhook keeps the stale signature header instead of the "
            "new signature. Fix the underlying cause, run "
            "python checks/check_webhook.py, and make the smallest justified change."
        ),
        "query": "retried webhook stale signature header new signature",
        "gold_files": ["app/kernel/collections.py"],
        "decoy_files": ["app/api/webhooks.py"],
        "evidence": ["app/kernel/collections.py", "put_unique"],
        "evaluator": {
            "command": ["python", "checks/check_webhook.py"],
            "timeout_seconds": 30,
            "require_gold_change": True,
        },
    },
    {
        "id": "hidden-session-permissions",
        "category": "hidden-cause-patch",
        "prompt": (
            "After switching accounts, a session can retain an old admin "
            "permission. Fix the underlying cause, run "
            "python checks/check_session.py, and make the smallest justified change."
        ),
        "query": "switching accounts session retains old admin permission",
        "gold_files": ["app/kernel/projection.py"],
        "decoy_files": ["app/api/sessions.py"],
        "evidence": ["app/kernel/projection.py", "project"],
        "evaluator": {
            "command": ["python", "checks/check_session.py"],
            "timeout_seconds": 30,
            "require_gold_change": True,
        },
    },
    {
        "id": "hidden-job-delay",
        "category": "hidden-cause-patch",
        "prompt": (
            "A background job retry schedule starts at twice the configured base "
            "delay. Fix the underlying cause, run python checks/check_jobs.py, "
            "and make the smallest justified change."
        ),
        "query": "background job retry schedule twice configured base delay",
        "gold_files": ["app/kernel/timing.py"],
        "decoy_files": ["app/api/jobs.py"],
        "evidence": ["app/kernel/timing.py", "span"],
        "evaluator": {
            "command": ["python", "checks/check_jobs.py"],
            "timeout_seconds": 30,
            "require_gold_change": True,
        },
    },
]


def _run(
    command: list[str],
    cwd: Path,
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def _json_output(value: str) -> dict[str, Any]:
    start = value.find("{")
    if start < 0:
        raise ValueError("command did not emit a JSON object")
    payload = json.loads(value[start:])
    if not isinstance(payload, dict):
        raise ValueError("command did not emit a JSON object")
    return payload


def _sanitize_context(value: Any, workspace: Path) -> Any:
    """Replace fixture-specific absolute roots before contexts are preserved."""
    if isinstance(value, dict):
        return {key: _sanitize_context(item, workspace) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_context(item, workspace) for item in value]
    if isinstance(value, str):
        return value.replace(f"{workspace}{os.sep}", "")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--contexts", type=Path, required=True)
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
        "GIT_AUTHOR_DATE": "2026-01-02T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-01-02T00:00:00Z",
    }
    subprocess.run(
        ["git", "commit", "-qm", "seed adversarial retrieval benchmark"],
        cwd=workspace,
        check=True,
        env=commit_env,
    )
    revision = _run(["git", "rev-parse", "HEAD"], workspace).stdout.strip()

    tasks = [{**definition, "revision": revision} for definition in TASKS]
    for task in tasks:
        baseline = _run(task["evaluator"]["command"], workspace, check=False)
        if baseline.returncode == 0:
            parser.error(f"fixture unexpectedly passes before patch: {task['id']}")

    args.contexts.mkdir(parents=True, exist_ok=True)
    cli = [sys.executable, "-m", "visor.cli", "--workspace", str(workspace)]
    retrieval_env = {**os.environ, "VISOR_RETRIEVAL_MODE": "lexical"}
    _run([*cli, "index"], workspace, env=retrieval_env)
    for task in tasks:
        completed = _run(
            [*cli, "context", task["query"], "--skill", "bug-fixer", "--json"],
            workspace,
            env=retrieval_env,
        )
        context = _json_output(completed.stdout)
        context = _sanitize_context(context, workspace)
        selected = context_files(context, workspace)
        coverage = score_gold_files(task["gold_files"], selected)
        selected_decoys = sorted(set(task["decoy_files"]) & set(selected))
        if not coverage["missing"]:
            parser.error(
                f"task is not adversarial; initial context includes every gold file: "
                f"{task['id']}"
            )
        if not selected_decoys:
            parser.error(
                f"task context does not include a declared decoy: {task['id']}"
            )
        task["prepared_initial_context_coverage"] = coverage
        task["prepared_selected_decoys"] = selected_decoys
        (args.contexts / f"{task['id']}.json").write_text(
            json.dumps(context, indent=2) + "\n", encoding="utf-8"
        )

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(
            {
                "version": 2,
                "benchmark": "adversarial-retrieval",
                "retrieval_mode": "lexical",
                "fixture_revision": revision,
                "tasks": tasks,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"workspace": str(workspace), "revision": revision, "tasks": len(tasks)}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
