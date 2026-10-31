from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from benchmarks.analyze import aggregate

ANALYZER = Path(__file__).parents[1] / "benchmarks" / "analyze.py"


def _record(agent: str, condition: str, stdout: str, duration: float) -> dict:
    return {
        "task": {
            "id": "p01",
            "evidence": ["workspace.py", "resolve_local_workspace"],
        },
        "agent": agent,
        "condition": condition,
        "run_id": "r1",
        "exit_code": 0,
        "duration_seconds": duration,
        "stdout": stdout,
    }


def test_analyzer_extracts_provider_usage_and_pairs_results(tmp_path: Path) -> None:
    codex_stdout = "\n".join(
        [
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": "workspace.py resolve_local_workspace",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 100,
                        "cached_input_tokens": 20,
                        "output_tokens": 30,
                    },
                }
            ),
        ]
    )
    claude_stdout = json.dumps(
        {
            "result": "workspace.py",
            "usage": {
                "input_tokens": 40,
                "cache_read_input_tokens": 10,
                "output_tokens": 15,
            },
            "total_cost_usd": 0.02,
        }
    )
    records = [
        _record("codex", "native", codex_stdout, 20),
        _record("codex", "visor", codex_stdout, 15),
        _record("claude-code", "native", claude_stdout, 12),
        _record("claude-code", "visor", claude_stdout, 10),
    ]
    inputs = []
    plan = tmp_path / "plan.json"
    plan.write_text('{"schema_version": 1}', encoding="utf-8")
    for index, record in enumerate(records):
        path = tmp_path / f"{index}.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        inputs.append(path)
    output = tmp_path / "summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(ANALYZER),
            *(str(path) for path in inputs),
            str(plan),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["skipped_inputs"] == ["plan.json"]
    assert report["aggregate"]["cells"]["codex:native"]["input_tokens"] == 100
    assert report["aggregate"]["cells"]["claude-code:native"]["cost_usd"] == 0.02
    assert report["aggregate"]["paired"]["codex"] == {
        "pairs": 1,
        "median_duration_delta_seconds": -5.0,
        "median_evidence_recall_delta": 0.0,
    }
    codex = next(
        row
        for row in report["records"]
        if row["agent"] == "codex" and row["condition"] == "native"
    )
    assert codex["evidence_recall"] == 1.0


def test_aggregate_excludes_failed_records() -> None:
    failed = {
        "agent": "codex",
        "condition": "native",
        "task": "p01",
        "run_id": "r1",
        "exit_code": 1,
        "duration_seconds": 1.0,
        "evidence_recall": 0.0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
    }
    summary = aggregate([failed])
    assert summary["successful_records"] == 0
    assert summary["failed_records"] == 1
    assert summary["cells"] == {}
