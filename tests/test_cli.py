"""Tests for the visor CLI interface."""

import subprocess
import sys


class TestCLIBasics:
    """Test CLI entry points and help output."""

    def test_version_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "V.I.S.O.R." in result.stdout
        assert "0.0.0" not in result.stdout  # Should not be dev version

    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Context Intelligence Engine" in result.stdout

    def test_no_command_shows_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0  # exits with error
        assert (
            "usage:" in result.stdout.lower()
            or "usage:" in result.stderr.lower()
            or "Context Intelligence Engine" in result.stdout
        )

    def test_init_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert "init" in result.stdout

    def test_context_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert "context" in result.stdout

    def test_fix_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert "fix" in result.stdout

    def test_explain_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert "explain" in result.stdout

    def test_trace_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert "trace" in result.stdout

    def test_drift_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert "drift" in result.stdout


def _run_cli(*args, cwd, visor_home):
    import os

    env = dict(os.environ)
    env["VISOR_HOME"] = str(visor_home)
    env.pop("VISOR_RETRIEVAL_MODE", None)
    env.pop("WORKSPACE_ROOT", None)
    return subprocess.run(
        [sys.executable, "-m", "visor.cli", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
        timeout=120,
    )


def _make_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (project / "app.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    return project


class TestDoctorAndStatus:
    """Check the JSON printed by `visor doctor` and `visor status`."""

    def test_doctor_reports_readiness_fields(self, tmp_path):
        import json
        import os

        project = _make_project(tmp_path)
        result = _run_cli(
            "--workspace",
            str(project),
            "doctor",
            cwd=project,
            visor_home=tmp_path / "home",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert set(data) == {
            "workspace",
            "index_ready",
            "retrieval_mode",
            "semantic_dependencies_available",
            "recommendation",
        }
        assert os.path.realpath(data["workspace"]) == os.path.realpath(project)
        assert data["index_ready"] is False
        assert data["retrieval_mode"] in {"lexical", "semantic"}
        assert isinstance(data["semantic_dependencies_available"], bool)
        assert data["recommendation"] == "Run `visor index`."

    def test_doctor_reports_ready_after_index(self, tmp_path):
        import json

        project = _make_project(tmp_path)
        home = tmp_path / "home"
        common = ("--workspace", str(project), "--retrieval-mode", "lexical")
        indexed = _run_cli(*common, "index", cwd=project, visor_home=home)
        assert indexed.returncode == 0, indexed.stderr
        result = _run_cli(*common, "doctor", cwd=project, visor_home=home)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["index_ready"] is True
        assert data["retrieval_mode"] == "lexical"
        assert data["recommendation"] is None

    def test_status_prints_index_health(self, tmp_path):
        import json

        project = _make_project(tmp_path)
        result = _run_cli(
            "--workspace",
            str(project),
            "status",
            cwd=project,
            visor_home=tmp_path / "home",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        for key in (
            "version",
            "status",
            "nodes",
            "vectors",
            "fts_nodes",
            "retrieval_mode",
            "ready",
        ):
            assert key in data
        assert isinstance(data["nodes"], int)
        assert isinstance(data["ready"], bool)
        assert data["ready"] is False
