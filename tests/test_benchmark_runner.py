from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RUNNER = Path(__file__).parents[1] / "benchmarks" / "run.py"


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
    assert record["schema_version"] == 2
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
