from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from benchmarks.run_pilot import Cell, completed_successfully

RUNNER = Path(__file__).parents[1] / "benchmarks" / "run.py"

PILOT = Path(__file__).parents[1] / "benchmarks" / "run_pilot.py"


def _workspace(tmp_path: Path) -> tuple[Path, str]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", workspace], check=True)
    subprocess.run(
        ["git", "-C", workspace, "config", "user.email", "benchmark@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", workspace, "config", "user.name", "Benchmark Test"],
        check=True,
    )
    (workspace / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", workspace, "add", "README.md"], check=True)
    subprocess.run(["git", "-C", workspace, "commit", "-qm", "fixture"], check=True)
    revision = subprocess.run(
        ["git", "-C", workspace, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return workspace, revision


def _manifest(tmp_path: Path, revision: str, prompt: str) -> Path:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [
                    {
                        "id": "p01",
                        "category": "test",
                        "prompt": prompt,
                        "revision": revision,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _run(
    tmp_path: Path,
    workspace: Path,
    manifest: Path,
    command: str,
    *extra: str,
    condition: str = "native",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = tmp_path / "result.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--manifest",
            str(manifest),
            "--task",
            "p01",
            "--agent",
            "codex",
            "--condition",
            condition,
            "--workspace",
            str(workspace),
            "--command",
            command,
            "--model",
            "test-model",
            "--client-version",
            "test-client",
            "--run-id",
            "r1",
            "--output",
            str(output),
            *extra,
        ],
        capture_output=True,
        text=True,
    )
    return completed, output


def test_prompt_is_not_evaluated_by_a_shell(tmp_path: Path) -> None:
    workspace, revision = _workspace(tmp_path)
    marker = workspace / "shell-injection"
    prompt = f'"; touch {marker}; echo "'
    manifest = _manifest(tmp_path, revision, prompt)
    command = f'{sys.executable} -c "import sys; print(sys.argv[1])" "{{prompt}}"'

    completed, output = _run(tmp_path, workspace, manifest, command)

    assert completed.returncode == 0, completed.stderr
    assert not marker.exists()
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["schema_version"] == 3
    assert record["stdout"].strip() == prompt
    assert isinstance(record["command"], list)


def test_workspace_revision_must_match_manifest(tmp_path: Path) -> None:
    workspace, _ = _workspace(tmp_path)
    manifest = _manifest(tmp_path, "0" * 40, "prompt")

    completed, output = _run(tmp_path, workspace, manifest, "true", "--dry-run")

    assert completed.returncode == 2
    assert "does not match task revision" in completed.stderr
    assert not output.exists()


def test_timeout_is_recorded(tmp_path: Path) -> None:
    workspace, revision = _workspace(tmp_path)
    manifest = _manifest(tmp_path, revision, "prompt")
    command = (
        f'{sys.executable} -c "import time; '
        "print('partial', flush=True); time.sleep(2)\""
    )

    completed, output = _run(
        tmp_path,
        workspace,
        manifest,
        command,
        "--timeout",
        "0.2",
    )

    assert completed.returncode == 124
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["exit_code"] == 124
    assert record["timed_out"] is True
    assert "partial" in record["stdout"]


def test_visor_context_is_explicit_and_redacted_from_command(tmp_path: Path) -> None:
    workspace, revision = _workspace(tmp_path)
    manifest = _manifest(tmp_path, revision, "prompt")
    context_file = tmp_path / "context.txt"
    context_file.write_text("private context", encoding="utf-8")
    command = f'{sys.executable} -c "import sys; print(sys.argv[1])" "{{context}}"'

    completed, output = _run(
        tmp_path,
        workspace,
        manifest,
        command,
        "--context-file",
        str(context_file),
        condition="visor",
    )

    assert completed.returncode == 0, completed.stderr
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["stdout"].strip() == "private context"
    assert "private context" not in json.dumps(record["command"])
    assert "<VISOR_CONTEXT>" in json.dumps(record["command"])
    assert record["context_sha256"]


def test_patch_evaluator_records_machine_verified_success(tmp_path: Path) -> None:
    workspace, _ = _workspace(tmp_path)
    (workspace / "check_patch.py").write_text(
        "from pathlib import Path\n"
        "raise SystemExit(0 if Path('fixed.txt').read_text() == 'fixed' else 1)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", workspace, "add", "check_patch.py"], check=True)
    subprocess.run(
        ["git", "-C", workspace, "commit", "-qm", "add evaluator"], check=True
    )
    revision = subprocess.run(
        ["git", "-C", workspace, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = _manifest(tmp_path, revision, "fix the seeded bug")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["tasks"][0]["evaluator"] = {
        "command": [sys.executable, "check_patch.py"],
        "timeout_seconds": 10,
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    fixer = tmp_path / "fixer.py"
    fixer.write_text(
        "import pathlib, sys\n"
        "pathlib.Path(sys.argv[1], 'fixed.txt').write_text('fixed')\n",
        encoding="utf-8",
    )

    completed, output = _run(
        tmp_path,
        workspace,
        manifest,
        f"{sys.executable} {fixer} {{workspace}}",
    )

    assert completed.returncode == 0, completed.stderr
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["patch_success"] is True
    assert record["evaluation"]["passed"] is True
    assert record["evaluation"]["changed_files"] == ["fixed.txt"]


def test_pilot_dry_run_writes_all_four_cells(tmp_path: Path) -> None:
    workspace, revision = _workspace(tmp_path)
    manifest = _manifest(tmp_path, revision, "prompt")
    contexts = tmp_path / "contexts"
    contexts.mkdir()
    (contexts / "p01.json").write_text("context", encoding="utf-8")
    results = tmp_path / "results"

    completed = subprocess.run(
        [
            sys.executable,
            str(PILOT),
            "--manifest",
            str(manifest),
            "--workspace",
            str(workspace),
            "--worktrees",
            str(tmp_path / "worktrees"),
            "--contexts",
            str(contexts),
            "--results",
            str(results),
            "--repeats",
            "1",
            "--concurrency",
            "2",
            "--codex-command",
            "true {prompt} {context}",
            "--codex-model",
            "codex-test",
            "--codex-client-version",
            "codex-test",
            "--claude-command",
            "true {prompt} {context}",
            "--claude-model",
            "claude-test",
            "--claude-client-version",
            "claude-test",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    records = list(results.glob("p01-*.json"))
    assert len(records) == 4
    plan = json.loads((results / "plan.json").read_text(encoding="utf-8"))
    assert len(plan["cells"]) == 4
    assert plan["isolated_worktrees"] is True
    assert len(list((tmp_path / "worktrees").iterdir())) == 4


def test_completed_successfully_supports_resume(tmp_path: Path) -> None:
    cell = Cell("p01", "codex", "native", "r1")
    assert not completed_successfully(tmp_path, cell)
    path = tmp_path / "p01-codex-native-r1.json"
    path.write_text('{"exit_code": 1}', encoding="utf-8")
    assert not completed_successfully(tmp_path, cell)
    path.write_text('{"exit_code": 0}', encoding="utf-8")
    assert completed_successfully(tmp_path, cell)


def test_process_group_signal_stops_the_child() -> None:
    import os
    import signal

    from benchmarks.run import _signal_process_group

    process = subprocess.Popen(
        ["sleep", "30"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _signal_process_group(process, signal.SIGTERM)
        process.wait(timeout=5)
        assert process.returncode is not None
        assert not os.path.exists(f"/proc/{process.pid}")
    finally:
        if process.poll() is None:
            process.kill()


def test_fixture_checks_import_and_fail_until_the_seeded_bug_is_fixed(
    tmp_path: Path,
) -> None:
    import shutil

    fixture = Path(__file__).parents[1] / "benchmarks" / "fixtures" / "patch_repo"
    workspace = tmp_path / "fixture"
    shutil.copytree(fixture, workspace)
    discount = subprocess.run(
        [sys.executable, "checks/check_discounts.py"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    assert discount.returncode != 0
    assert "ModuleNotFoundError" not in discount.stderr
    source = workspace / "app" / "discounts.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "total * (1 - percent)", "total * (1 - percent / 100)"
        ),
        encoding="utf-8",
    )
    fixed = subprocess.run(
        [sys.executable, "checks/check_discounts.py"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    assert fixed.returncode == 0, fixed.stderr
