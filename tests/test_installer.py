"""Tests for `visor install` / `visor uninstall` client wiring."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from visor import installer

REPO_ROOT = Path(__file__).resolve().parents[1]


def no_binaries(_name):
    return None


def with_visor_on_path(name):
    return f"/usr/local/bin/{name}" if name in {"visor", "visor-mcp"} else None


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


def make_clients(home: Path, *dirs: str) -> None:
    for name in dirs:
        (home / name).mkdir(parents=True, exist_ok=True)


def by_component(report, client, component):
    [change] = [
        c for c in report.changes if c.client == client and c.component == component
    ]
    return change


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------


def test_detects_clients_by_config_dir(home):
    make_clients(home, ".claude", ".gemini")
    assert installer.detect_clients(home, no_binaries) == ["claude-code", "gemini"]


def test_detects_clients_by_binary(home):
    home.mkdir()

    def which(name):
        return "/bin/codex" if name == "codex" else None

    assert installer.detect_clients(home, which) == ["codex"]


def test_no_clients_detected_changes_nothing(home):
    home.mkdir()
    report = installer.install(home, which=no_binaries)
    assert report.changes == []
    assert list(home.iterdir()) == []
    assert "No supported clients detected" in installer.format_report(report, "install")


def test_unknown_client_is_rejected(home):
    with pytest.raises(ValueError, match="unknown client"):
        installer.install(home, ["vim"], which=no_binaries)


# --------------------------------------------------------------------------
# Install into every client
# --------------------------------------------------------------------------


def test_install_all_clients_from_scratch(home):
    make_clients(home, ".claude", ".codex", ".cursor", ".gemini")
    report = installer.install(home, which=no_binaries)

    assert not report.has_errors
    claude = json.loads((home / ".claude.json").read_text())
    assert claude["mcpServers"]["visor"] == {
        "type": "stdio",
        "command": "uvx",
        "args": ["visor-mcp"],
        "env": {},
    }
    for rel in (".cursor/mcp.json", ".gemini/settings.json"):
        data = json.loads((home / rel).read_text())
        assert data["mcpServers"]["visor"] == {"command": "uvx", "args": ["visor-mcp"]}

    toml = (home / ".codex/config.toml").read_text()
    assert toml == '[mcp_servers.visor]\ncommand = "uvx"\nargs = ["visor-mcp"]\n'

    skill = (REPO_ROOT / "skills/visor-context/SKILL.md").read_text()
    for skills_dir in (".claude", ".codex", ".cursor", ".gemini"):
        path = home / skills_dir / "skills/visor-context/SKILL.md"
        assert path.read_text() == skill

    # The hook is opt-in.
    assert not (home / ".claude/settings.json").exists()
    assert len(report.files_changed) == 8
    assert all(p.startswith("~/") for p in report.files_changed)


def test_installed_visor_mcp_is_preferred(home):
    make_clients(home, ".cursor")
    installer.install(home, which=with_visor_on_path)
    data = json.loads((home / ".cursor/mcp.json").read_text())
    assert data["mcpServers"]["visor"] == {"command": "visor-mcp", "args": []}


def test_install_is_idempotent(home):
    make_clients(home, ".claude", ".codex", ".cursor", ".gemini")
    installer.install(home, which=no_binaries, hook=True)
    snapshot = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}

    again = installer.install(home, which=no_binaries, hook=True)
    assert {c.action for c in again.changes} == {installer.UNCHANGED}
    assert again.files_changed == []
    assert {p: p.read_bytes() for p in home.rglob("*") if p.is_file()} == snapshot


# --------------------------------------------------------------------------
# No clobbering
# --------------------------------------------------------------------------


def test_preserves_other_servers_and_keys(home):
    make_clients(home, ".cursor")
    cfg = home / ".cursor/mcp.json"
    original = {
        "mcpServers": {"github": {"command": "gh-mcp", "args": ["--x"]}},
        "theme": "dark",
    }
    cfg.write_text(json.dumps(original))

    installer.install(home, which=no_binaries, skill=False)

    data = json.loads(cfg.read_text())
    assert data["theme"] == "dark"
    assert data["mcpServers"]["github"] == original["mcpServers"]["github"]
    assert "visor" in data["mcpServers"]
    backup = home / ".cursor/mcp.json.visor-backup"
    assert json.loads(backup.read_text()) == original


def test_different_existing_entry_is_skipped_without_force(home):
    make_clients(home, ".gemini")
    cfg = home / ".gemini/settings.json"
    custom = {"mcpServers": {"visor": {"command": "/opt/visor/run", "args": []}}}
    cfg.write_text(json.dumps(custom))

    report = installer.install(home, which=no_binaries, skill=False)
    change = by_component(report, "gemini", "mcp")
    assert change.action == installer.SKIPPED
    assert "--force" in change.detail
    assert json.loads(cfg.read_text()) == custom
    assert report.files_changed == []

    forced = installer.install(home, which=no_binaries, skill=False, force=True)
    assert by_component(forced, "gemini", "mcp").action == installer.UPDATED
    entry = json.loads(cfg.read_text())["mcpServers"]["visor"]
    assert entry["command"] == "uvx"


def test_edited_skill_is_not_overwritten(home):
    make_clients(home, ".claude")
    skill = home / ".claude/skills/visor-context/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("my local edits\n")

    report = installer.install(home, which=no_binaries)
    assert by_component(report, "claude-code", "skill").action == installer.SKIPPED
    assert skill.read_text() == "my local edits\n"


def test_invalid_json_is_reported_and_not_touched(home):
    make_clients(home, ".cursor")
    cfg = home / ".cursor/mcp.json"
    cfg.write_text("{ not json")

    report = installer.install(home, which=no_binaries, skill=False)
    change = by_component(report, "cursor", "mcp")
    assert change.action == installer.ERROR
    assert "cannot parse JSON" in change.detail
    assert cfg.read_text() == "{ not json"
    assert report.has_errors


def test_codex_toml_existing_content_is_preserved(home):
    make_clients(home, ".codex")
    cfg = home / ".codex/config.toml"
    original = (
        'model = "gpt-5"\n'
        "\n"
        "[mcp_servers.other]\n"
        'command = "other"\n'
        "\n"
        "[profiles.fast]\n"
        'model = "mini"\n'
    )
    cfg.write_text(original)

    installer.install(home, which=no_binaries, skill=False)
    text = cfg.read_text()
    assert text.startswith(original)
    assert text.endswith('[mcp_servers.visor]\ncommand = "uvx"\nargs = ["visor-mcp"]\n')

    installer.uninstall(home, which=no_binaries)
    assert cfg.read_text() == original


def test_codex_custom_block_is_skipped_then_forced(home):
    make_clients(home, ".codex")
    cfg = home / ".codex/config.toml"
    cfg.write_text(
        "[mcp_servers.visor]\n"
        'command = "/opt/visor"\n'
        "\n"
        "[mcp_servers.visor.env]\n"
        'X = "1"\n'
        "\n"
        "[profiles.fast]\n"
        'model = "mini"\n'
    )
    report = installer.install(home, which=no_binaries, skill=False)
    assert by_component(report, "codex", "mcp").action == installer.SKIPPED

    installer.install(home, which=no_binaries, skill=False, force=True)
    assert cfg.read_text() == (
        "[mcp_servers.visor]\n"
        'command = "uvx"\n'
        'args = ["visor-mcp"]\n'
        "\n"
        "[profiles.fast]\n"
        'model = "mini"\n'
    )


def test_codex_toml_parses_when_tomllib_available(home):
    tomllib = pytest.importorskip("tomllib")
    make_clients(home, ".codex")
    cfg = home / ".codex/config.toml"
    cfg.write_text('model = "gpt-5"\n')
    installer.install(home, which=no_binaries, skill=False)
    parsed = tomllib.loads(cfg.read_text())
    assert parsed["model"] == "gpt-5"
    assert parsed["mcp_servers"]["visor"] == {"command": "uvx", "args": ["visor-mcp"]}


# --------------------------------------------------------------------------
# Dry run
# --------------------------------------------------------------------------


def test_dry_run_writes_nothing(home):
    make_clients(home, ".claude", ".codex", ".cursor", ".gemini")
    before = sorted(home.rglob("*"))

    report = installer.install(home, which=no_binaries, hook=True, dry_run=True)

    assert sorted(home.rglob("*")) == before
    assert len(report.files_changed) == 9
    text = installer.format_report(report, "install")
    assert "Dry run: no files were written." in text
    assert "would be added" in text
    assert "~/.claude/settings.json" in text


def test_dry_run_uninstall_writes_nothing(home):
    make_clients(home, ".cursor")
    installer.install(home, which=no_binaries)
    snapshot = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}

    report = installer.uninstall(home, which=no_binaries, dry_run=True)
    assert by_component(report, "cursor", "mcp").action == installer.REMOVED
    assert {p: p.read_bytes() for p in home.rglob("*") if p.is_file()} == snapshot


# --------------------------------------------------------------------------
# Claude Code hook
# --------------------------------------------------------------------------


def test_hook_is_appended_next_to_existing_hooks(home):
    make_clients(home, ".claude")
    settings = home / ".claude/settings.json"
    existing_group = {"hooks": [{"type": "command", "command": "echo hi"}]}
    settings.write_text(
        json.dumps({"model": "opus", "hooks": {"SessionStart": [existing_group]}})
    )

    installer.install(home, which=with_visor_on_path, hook=True, skill=False)
    data = json.loads(settings.read_text())
    assert data["model"] == "opus"
    assert data["hooks"]["SessionStart"] == [
        existing_group,
        {"hooks": [{"type": "command", "command": "visor doctor"}]},
    ]

    installer.uninstall(home, which=with_visor_on_path)
    data = json.loads(settings.read_text())
    assert data["hooks"]["SessionStart"] == [existing_group]


def test_hook_only_applies_to_claude_code(home):
    make_clients(home, ".cursor")
    report = installer.install(home, which=no_binaries, hook=True)
    assert all(c.component != "hook" for c in report.changes)


# --------------------------------------------------------------------------
# Uninstall
# --------------------------------------------------------------------------


def test_uninstall_round_trip(home):
    make_clients(home, ".claude", ".codex", ".cursor", ".gemini")
    (home / ".claude.json").write_text(json.dumps({"numStartups": 3}))

    installer.install(home, which=no_binaries, hook=True)
    report = installer.uninstall(home, which=no_binaries)
    assert not report.has_errors

    assert json.loads((home / ".claude.json").read_text()) == {
        "numStartups": 3,
        "mcpServers": {},
    }
    assert json.loads((home / ".claude/settings.json").read_text()) == {}
    for rel in (".cursor/mcp.json", ".gemini/settings.json"):
        assert json.loads((home / rel).read_text()) == {"mcpServers": {}}
    for skills_dir in (".claude", ".codex", ".cursor", ".gemini"):
        assert not (home / skills_dir / "skills/visor-context").exists()

    again = installer.uninstall(home, which=no_binaries)
    assert {c.action for c in again.changes} == {installer.NOT_FOUND}


def test_uninstall_keeps_edited_skill_without_force(home):
    make_clients(home, ".codex")
    installer.install(home, which=no_binaries)
    skill = home / ".codex/skills/visor-context/SKILL.md"
    skill.write_text("edited\n")

    report = installer.uninstall(home, which=no_binaries)
    assert by_component(report, "codex", "skill").action == installer.SKIPPED
    assert skill.exists()

    installer.uninstall(home, which=no_binaries, force=True)
    assert not skill.exists()


# --------------------------------------------------------------------------
# Packaging and CLI
# --------------------------------------------------------------------------


def test_bundled_skill_matches_repository_skill():
    source = (REPO_ROOT / "skills/visor-context/SKILL.md").read_text()
    assert installer.bundled_skill_text() == source


def _run_cli(home: Path, *args: str):
    env = {**os.environ, "HOME": str(home), "PATH": "/nonexistent"}
    return subprocess.run(
        [sys.executable, "-m", "visor.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_install_dry_run_and_real(home):
    make_clients(home, ".cursor")

    dry = _run_cli(home, "install", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert "Dry run" in dry.stdout
    assert "~/.cursor/mcp.json" in dry.stdout
    assert not (home / ".cursor/mcp.json").exists()

    real = _run_cli(home, "install", "--json")
    assert real.returncode == 0, real.stderr
    payload = json.loads(real.stdout)
    assert payload["clients_detected"] == ["cursor"]
    assert payload["files_changed"] == [
        "~/.cursor/mcp.json",
        "~/.cursor/skills/visor-context/SKILL.md",
    ]

    removed = _run_cli(home, "uninstall")
    assert removed.returncode == 0, removed.stderr
    assert "removed" in removed.stdout


def test_cli_explicit_client_without_detection(home):
    home.mkdir()
    result = _run_cli(home, "install", "--client", "gemini", "--no-skill")
    assert result.returncode == 0, result.stderr
    assert (home / ".gemini/settings.json").exists()
    assert not (home / ".gemini/skills").exists()


def test_cli_exit_code_on_error(home):
    make_clients(home, ".cursor")
    (home / ".cursor/mcp.json").write_text("[]")
    result = _run_cli(home, "install", "--no-skill")
    assert result.returncode == 1
    assert "error" in result.stdout
