"""Tests for the visor CLI interface."""

import subprocess
import sys


class TestCLIBasics:
    """Test CLI entry points and help output."""

    def test_version_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--version"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "V.I.S.O.R." in result.stdout
        assert "0.0.0" not in result.stdout  # Should not be dev version

    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "Context Intelligence Engine" in result.stdout

    def test_no_command_shows_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0  # exits with error
        assert "usage:" in result.stdout.lower() or "usage:" in result.stderr.lower() or "Context Intelligence Engine" in result.stdout

    def test_init_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True, text=True,
        )
        assert "init" in result.stdout

    def test_context_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True, text=True,
        )
        assert "context" in result.stdout

    def test_fix_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True, text=True,
        )
        assert "fix" in result.stdout

    def test_explain_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True, text=True,
        )
        assert "explain" in result.stdout

    def test_trace_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True, text=True,
        )
        assert "trace" in result.stdout

    def test_drift_subcommand_exists(self):
        result = subprocess.run(
            [sys.executable, "-m", "visor.cli", "--help"],
            capture_output=True, text=True,
        )
        assert "drift" in result.stdout
