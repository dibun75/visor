from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from benchmarks.analyze import aggregate, classify_outcome
from benchmarks.context_coverage import context_files, score_gold_files
from benchmarks.run import _run_evaluator

ROOT = Path(__file__).parents[1]
PREPARE = ROOT / "benchmarks" / "prepare_adversarial_pilot.py"


def test_context_coverage_normalizes_absolute_workspace_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    payload = {
        "context": [
            {"file_path": str(workspace / "app" / "api" / "jobs.py")},
            {"file_path": str(workspace / "app" / "api" / "jobs.py")},
        ]
    }

    selected = context_files(payload, workspace)
    coverage = score_gold_files(["app/kernel/timing.py"], selected)

    assert selected == ["app/api/jobs.py"]
    assert coverage["recall"] == 0.0
    assert coverage["missing"] == ["app/kernel/timing.py"]


def test_outcomes_distinguish_recovery_wrong_location_and_loud_failure() -> None:
    initial = {"missing": ["app/kernel/timing.py"], "recall": 0.0}
    common = {
        "gold_files": ["app/kernel/timing.py"],
        "decoy_files": ["app/api/jobs.py"],
        "initial_context": initial,
    }

    assert (
        classify_outcome(
            exit_code=0,
            patch_success=True,
            changed_files=["app/kernel/timing.py"],
            **common,
        )
        == "recovered_beyond_initial_context"
    )
    assert (
        classify_outcome(
            exit_code=0,
            patch_success=False,
            changed_files=["app/api/jobs.py"],
            **common,
        )
        == "plausible_wrong_location"
    )
    assert (
        classify_outcome(
            exit_code=2,
            patch_success=False,
            changed_files=[],
            **common,
        )
        == "loud_failure"
    )


def test_aggregate_reports_outcomes_by_agent_and_condition() -> None:
    rows = []
    for condition, outcome in (
        ("native", "recovered_beyond_initial_context"),
        ("visor", "plausible_wrong_location"),
    ):
        rows.append(
            {
                "agent": "codex",
                "condition": condition,
                "task": "hidden-job-delay",
                "run_id": "r1",
                "exit_code": 0,
                "duration_seconds": 1.0,
                "evidence_recall": 0.0,
                "initial_gold_recall": 0.0 if condition == "visor" else None,
                "patch_success": condition == "native",
                "outcome": outcome,
            }
        )

    report = aggregate(rows)

    assert report["outcomes_by_cell"]["codex:native"] == {
        "recovered_beyond_initial_context": 1
    }
    assert report["outcomes_by_cell"]["codex:visor"] == {"plausible_wrong_location": 1}
    assert report["cells"]["codex:visor"]["median_initial_gold_recall"] == 0.0
    assert report["patch_transitions"]["codex"] == {"native_only": 1}


def test_preparer_proves_every_task_omits_gold_and_includes_a_decoy(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"
    contexts = tmp_path / "contexts"
    completed = subprocess.run(
        [
            sys.executable,
            str(PREPARE),
            "--workspace",
            str(tmp_path / "workspace"),
            "--manifest",
            str(manifest),
            "--contexts",
            str(contexts),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["benchmark"] == "adversarial-retrieval"
    assert len(payload["tasks"]) == 4
    for task in payload["tasks"]:
        coverage = task["prepared_initial_context_coverage"]
        assert coverage["recall"] == 0.0
        assert coverage["missing"] == task["gold_files"]
        assert task["prepared_selected_decoys"]
        assert (contexts / f"{task['id']}.json").is_file()


def test_evaluator_rejects_a_passing_workaround_in_the_decoy_file(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "app" / "api").mkdir(parents=True)
    (workspace / "app" / "kernel").mkdir(parents=True)
    (workspace / "checks").mkdir()
    (workspace / "app" / "api" / "jobs.py").write_text("value = 1\n")
    (workspace / "app" / "kernel" / "timing.py").write_text("value = 1\n")
    (workspace / "checks" / "check.py").write_text("print('passes')\n")
    subprocess.run(["git", "init", "-q", workspace], check=True)
    subprocess.run(["git", "-C", workspace, "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            workspace,
            "-c",
            "user.name=Benchmark Test",
            "-c",
            "user.email=benchmark@example.com",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    (workspace / "app" / "api" / "jobs.py").write_text("value = 2\n")
    task = {
        "gold_files": ["app/kernel/timing.py"],
        "evaluator": {
            "command": [sys.executable, "checks/check.py"],
            "require_gold_change": True,
        },
    }

    result = _run_evaluator(task, workspace)

    assert result is not None
    assert result["behavioral_check_passed"] is True
    assert result["passed"] is False
    assert result["missing_required_changed_files"] == ["app/kernel/timing.py"]
