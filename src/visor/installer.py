"""
One-command client wiring for ``visor install`` and ``visor uninstall``.

The installer registers the ``visor-mcp`` stdio server and the bundled
``visor-context`` Agent Skill with coding clients found on this machine.

Safety rules:

- Only user-level files of detected clients are touched.
- An existing ``visor`` entry or Skill that differs from what V.I.S.O.R. would
  write is left alone unless ``force`` is set.
- Other keys, servers, and hooks in a config file are preserved.
- A file that cannot be parsed is reported and never rewritten.
- Every modified file is first copied to ``<file>.visor-backup``.
- ``dry_run`` computes the same plan and writes nothing.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path

SERVER_NAME = "visor"
SKILL_NAME = "visor-context"
BACKUP_SUFFIX = ".visor-backup"

# Change kinds reported to the user.
ADDED = "added"
UPDATED = "updated"
REMOVED = "removed"
UNCHANGED = "unchanged"
SKIPPED = "skipped"
ERROR = "error"
NOT_FOUND = "not found"

WRITING_ACTIONS = {ADDED, UPDATED, REMOVED}


@dataclass
class Change:
    client: str
    component: str  # mcp | skill | hook
    path: str
    action: str
    detail: str = ""


@dataclass
class Report:
    dry_run: bool
    clients_detected: list[str] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)

    @property
    def files_changed(self) -> list[str]:
        seen: list[str] = []
        for change in self.changes:
            if change.action in WRITING_ACTIONS and change.path not in seen:
                seen.append(change.path)
        return seen

    @property
    def has_errors(self) -> bool:
        return any(change.action == ERROR for change in self.changes)

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "clients_detected": self.clients_detected,
            "files_changed": self.files_changed,
            "changes": [asdict(change) for change in self.changes],
        }


@dataclass(frozen=True)
class Client:
    key: str
    label: str
    config_dir: str  # relative to home; its presence means "installed"
    binary: str
    mcp_file: str  # relative to home
    mcp_format: str  # json-mcpServers | codex-toml
    skills_dir: str | None  # relative to home


CLIENTS: dict[str, Client] = {
    client.key: client
    for client in (
        Client(
            key="claude-code",
            label="Claude Code",
            config_dir=".claude",
            binary="claude",
            mcp_file=".claude.json",
            mcp_format="json-mcpServers",
            skills_dir=".claude/skills",
        ),
        Client(
            key="codex",
            label="Codex CLI",
            config_dir=".codex",
            binary="codex",
            mcp_file=".codex/config.toml",
            mcp_format="codex-toml",
            skills_dir=".codex/skills",
        ),
        Client(
            key="cursor",
            label="Cursor",
            config_dir=".cursor",
            binary="cursor",
            mcp_file=".cursor/mcp.json",
            mcp_format="json-mcpServers",
            skills_dir=".cursor/skills",
        ),
        Client(
            key="gemini",
            label="Gemini CLI",
            config_dir=".gemini",
            binary="gemini",
            mcp_file=".gemini/settings.json",
            mcp_format="json-mcpServers",
            skills_dir=".gemini/skills",
        ),
    )
}

CLAUDE_SETTINGS_FILE = ".claude/settings.json"
HOOK_EVENT = "SessionStart"


# ---------------------------------------------------------------------------
# Detection and payloads
# ---------------------------------------------------------------------------


def detect_clients(home: Path, which=shutil.which) -> list[str]:
    """Return keys of clients whose config directory or binary exists."""
    found = []
    for client in CLIENTS.values():
        if (home / client.config_dir).is_dir() or which(client.binary):
            found.append(client.key)
    return found


def server_command(which=shutil.which) -> tuple[str, list[str]]:
    """Prefer an installed ``visor-mcp``; otherwise run it through ``uvx``."""
    if which("visor-mcp"):
        return "visor-mcp", []
    return "uvx", ["visor-mcp"]


def hook_command(which=shutil.which) -> str:
    """SessionStart hook: print index readiness into the agent's context."""
    if which("visor"):
        return "visor doctor"
    return "uvx --from visor-mcp visor doctor"


def bundled_skill_text() -> str:
    return (
        resources.files("visor")
        .joinpath("assets", "skills", SKILL_NAME, "SKILL.md")
        .read_text(encoding="utf-8")
    )


def _display(path: Path, home: Path) -> str:
    try:
        return "~/" + path.relative_to(home).as_posix()
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    pass


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"cannot parse JSON ({exc.msg} at line {exc.lineno})")
    if not isinstance(data, dict):
        raise ConfigError("top-level JSON value is not an object")
    return data


def _write_text(path: Path, text: str) -> None:
    """Back up an existing file, then replace it atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + BACKUP_SUFFIX))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        if path.exists():
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _write_json(path: Path, data: dict) -> None:
    _write_text(path, json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# MCP registration: JSON ``mcpServers`` files
# ---------------------------------------------------------------------------


def _json_entry(client: Client, command: str, args: list[str]) -> dict:
    entry: dict = {"command": command, "args": list(args)}
    if client.key == "claude-code":
        entry = {"type": "stdio", **entry, "env": {}}
    return entry


def _install_json_mcp(
    path: Path, entry: dict, force: bool, dry_run: bool
) -> tuple[str, str]:
    data = _read_json(path)
    servers = data.get("mcpServers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        raise ConfigError("`mcpServers` is not an object")
    existing = servers.get(SERVER_NAME)
    if existing == entry:
        return UNCHANGED, ""
    if existing is not None and not force:
        return SKIPPED, "a different `visor` server is configured; use --force"
    action = UPDATED if existing is not None else ADDED
    servers[SERVER_NAME] = entry
    data["mcpServers"] = servers
    if not dry_run:
        _write_json(path, data)
    return action, ""


def _uninstall_json_mcp(path: Path, dry_run: bool) -> tuple[str, str]:
    if not path.exists():
        return NOT_FOUND, ""
    data = _read_json(path)
    servers = data.get("mcpServers")
    if not isinstance(servers, dict) or SERVER_NAME not in servers:
        return NOT_FOUND, ""
    del servers[SERVER_NAME]
    if not dry_run:
        _write_json(path, data)
    return REMOVED, ""


# ---------------------------------------------------------------------------
# MCP registration: Codex ``config.toml``
# ---------------------------------------------------------------------------

_TOML_HEADER = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")


def _toml_table_name(line: str) -> str | None:
    match = _TOML_HEADER.match(line)
    if not match:
        return None
    return ".".join(part.strip().strip('"').strip("'") for part in match[1].split("."))


def _is_visor_table(name: str) -> bool:
    prefix = f"mcp_servers.{SERVER_NAME}"
    return name == prefix or name.startswith(prefix + ".")


def _split_codex_block(text: str) -> tuple[list[str], list[str], list[str]]:
    """Split TOML into (before, visor block, after) by line."""
    lines = text.splitlines(keepends=True)
    start = end = None
    for index, line in enumerate(lines):
        name = _toml_table_name(line)
        if name is None:
            continue
        if start is None and _is_visor_table(name):
            start = index
        elif start is not None and not _is_visor_table(name):
            end = index
            break
    if start is None:
        return lines, [], []
    if end is None:
        end = len(lines)
    return lines[:start], lines[start:end], lines[end:]


def _toml_string(value: str) -> str:
    return json.dumps(value)  # JSON strings are valid TOML basic strings


def _codex_block(command: str, args: list[str]) -> str:
    rendered_args = ", ".join(_toml_string(arg) for arg in args)
    return (
        f"[mcp_servers.{SERVER_NAME}]\n"
        f"command = {_toml_string(command)}\n"
        f"args = [{rendered_args}]\n"
    )


def _install_codex_mcp(
    path: Path, command: str, args: list[str], force: bool, dry_run: bool
) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    before, block, after = _split_codex_block(text)
    desired = _codex_block(command, args)
    if block:
        if "".join(block).strip() == desired.strip():
            return UNCHANGED, ""
        if not force:
            return SKIPPED, "a different `visor` server is configured; use --force"
        trailing = "\n" if after else ""
        new_text = "".join(before) + desired + trailing + "".join(after)
        action = UPDATED
    else:
        prefix = text
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        if prefix.strip():
            prefix += "\n"
        new_text = prefix + desired
        action = ADDED
    if not dry_run:
        _write_text(path, new_text)
    return action, ""


def _uninstall_codex_mcp(path: Path, dry_run: bool) -> tuple[str, str]:
    if not path.exists():
        return NOT_FOUND, ""
    before, block, after = _split_codex_block(path.read_text(encoding="utf-8"))
    if not block:
        return NOT_FOUND, ""
    head = "".join(before).rstrip("\n")
    tail = "".join(after).lstrip("\n")
    new_text = head + ("\n\n" if head and tail else "\n" if head else "") + tail
    if not dry_run:
        _write_text(path, new_text)
    return REMOVED, ""


# ---------------------------------------------------------------------------
# Agent Skill
# ---------------------------------------------------------------------------


def _install_skill(path: Path, force: bool, dry_run: bool) -> tuple[str, str]:
    desired = bundled_skill_text()
    if path.exists():
        if path.read_text(encoding="utf-8") == desired:
            return UNCHANGED, ""
        if not force:
            return SKIPPED, "an edited copy of the Skill exists; use --force"
        action = UPDATED
    else:
        action = ADDED
    if not dry_run:
        _write_text(path, desired)
    return action, ""


def _uninstall_skill(path: Path, force: bool, dry_run: bool) -> tuple[str, str]:
    if not path.exists():
        return NOT_FOUND, ""
    if path.read_text(encoding="utf-8") != bundled_skill_text() and not force:
        return SKIPPED, "the Skill was edited; use --force to remove it"
    if not dry_run:
        path.unlink()
        backup = path.with_name(path.name + BACKUP_SUFFIX)
        if backup.exists():
            backup.unlink()
        try:
            path.parent.rmdir()  # only if now empty
        except OSError:
            pass
    return REMOVED, ""


# ---------------------------------------------------------------------------
# Claude Code SessionStart hook (opt-in)
# ---------------------------------------------------------------------------

_HOOK_COMMANDS = {"visor doctor", "uvx --from visor-mcp visor doctor"}


def _is_visor_hook(hook: object) -> bool:
    return (
        isinstance(hook, dict)
        and hook.get("type") == "command"
        and hook.get("command") in _HOOK_COMMANDS
    )


def _install_hook(path: Path, command: str, dry_run: bool) -> tuple[str, str]:
    data = _read_json(path)
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ConfigError("`hooks` is not an object")
    groups = hooks.setdefault(HOOK_EVENT, [])
    if not isinstance(groups, list):
        raise ConfigError(f"`hooks.{HOOK_EVENT}` is not a list")
    for group in groups:
        if isinstance(group, dict) and any(
            _is_visor_hook(hook) for hook in group.get("hooks", [])
        ):
            return UNCHANGED, ""
    groups.append({"hooks": [{"type": "command", "command": command}]})
    if not dry_run:
        _write_json(path, data)
    return ADDED, ""


def _uninstall_hook(path: Path, dry_run: bool) -> tuple[str, str]:
    if not path.exists():
        return NOT_FOUND, ""
    data = _read_json(path)
    hooks = data.get("hooks")
    groups = hooks.get(HOOK_EVENT) if isinstance(hooks, dict) else None
    if not isinstance(groups, list):
        return NOT_FOUND, ""
    removed = False
    kept_groups = []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            kept_groups.append(group)
            continue
        kept = [hook for hook in group["hooks"] if not _is_visor_hook(hook)]
        if len(kept) != len(group["hooks"]):
            removed = True
        if kept:
            kept_groups.append({**group, "hooks": kept})
    if not removed:
        return NOT_FOUND, ""
    if kept_groups:
        hooks[HOOK_EVENT] = kept_groups
    else:
        del hooks[HOOK_EVENT]
        if not hooks:
            del data["hooks"]
    if not dry_run:
        _write_json(path, data)
    return REMOVED, ""


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def _resolve_clients(
    home: Path, requested: list[str] | None, which
) -> tuple[list[str], list[str]]:
    detected = detect_clients(home, which)
    if requested:
        unknown = [key for key in requested if key not in CLIENTS]
        if unknown:
            raise ValueError(
                f"unknown client(s): {', '.join(unknown)}; "
                f"choose from {', '.join(CLIENTS)}"
            )
        return detected, list(dict.fromkeys(requested))
    return detected, detected


def _run(report: Report, client: Client, component: str, path: Path, home, step):
    try:
        action, detail = step()
    except (ConfigError, OSError, UnicodeDecodeError) as exc:
        action, detail = ERROR, str(exc)
    report.changes.append(
        Change(client.key, component, _display(path, home), action, detail)
    )


def install(
    home: Path | None = None,
    clients: list[str] | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    skill: bool = True,
    hook: bool = False,
    which=shutil.which,
) -> Report:
    """Register V.I.S.O.R. with detected (or the named) clients."""
    home = Path(home) if home is not None else Path.home()
    detected, selected = _resolve_clients(home, clients, which)
    report = Report(dry_run=dry_run, clients_detected=detected)
    command, args = server_command(which)

    for key in selected:
        client = CLIENTS[key]
        mcp_path = home / client.mcp_file
        if client.mcp_format == "codex-toml":
            step = lambda p=mcp_path: _install_codex_mcp(  # noqa: E731
                p, command, args, force, dry_run
            )
        else:
            entry = _json_entry(client, command, args)
            step = lambda p=mcp_path, e=entry: _install_json_mcp(  # noqa: E731
                p, e, force, dry_run
            )
        _run(report, client, "mcp", mcp_path, home, step)

        if skill and client.skills_dir:
            skill_path = home / client.skills_dir / SKILL_NAME / "SKILL.md"
            _run(
                report,
                client,
                "skill",
                skill_path,
                home,
                lambda p=skill_path: _install_skill(p, force, dry_run),
            )

        if hook and client.key == "claude-code":
            settings = home / CLAUDE_SETTINGS_FILE
            cmd = hook_command(which)
            _run(
                report,
                client,
                "hook",
                settings,
                home,
                lambda p=settings: _install_hook(p, cmd, dry_run),
            )
    return report


def uninstall(
    home: Path | None = None,
    clients: list[str] | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    which=shutil.which,
) -> Report:
    """Remove what ``install`` added: the server entry, the Skill, the hook."""
    home = Path(home) if home is not None else Path.home()
    detected, selected = _resolve_clients(home, clients, which)
    report = Report(dry_run=dry_run, clients_detected=detected)

    for key in selected:
        client = CLIENTS[key]
        mcp_path = home / client.mcp_file
        if client.mcp_format == "codex-toml":
            step = lambda p=mcp_path: _uninstall_codex_mcp(p, dry_run)  # noqa: E731
        else:
            step = lambda p=mcp_path: _uninstall_json_mcp(p, dry_run)  # noqa: E731
        _run(report, client, "mcp", mcp_path, home, step)

        if client.skills_dir:
            skill_path = home / client.skills_dir / SKILL_NAME / "SKILL.md"
            _run(
                report,
                client,
                "skill",
                skill_path,
                home,
                lambda p=skill_path: _uninstall_skill(p, force, dry_run),
            )

        if client.key == "claude-code":
            settings = home / CLAUDE_SETTINGS_FILE
            _run(
                report,
                client,
                "hook",
                settings,
                home,
                lambda p=settings: _uninstall_hook(p, dry_run),
            )
    return report


def format_report(report: Report, verb: str) -> str:
    """Human-readable summary that lists every file changed."""
    lines = []
    if not report.changes:
        lines.append(
            "No supported clients detected (Claude Code, Codex, Cursor, Gemini CLI)."
        )
        lines.append("Name one explicitly with --client, for example:")
        lines.append(f"  visor {verb} --client claude-code")
        return "\n".join(lines)

    would = "would be " if report.dry_run else ""
    current = None
    for change in report.changes:
        if change.client != current:
            current = change.client
            if lines:
                lines.append("")
            lines.append(CLIENTS[change.client].label)
        action = change.action
        if action in WRITING_ACTIONS and report.dry_run:
            action = f"{would}{action}"
        suffix = f" ({change.detail})" if change.detail else ""
        lines.append(f"  {change.component:<5}  {action:<18} {change.path}{suffix}")

    lines.append("")
    files = report.files_changed
    if report.dry_run:
        lines.append("Dry run: no files were written.")
        if files:
            lines.append("Files that would change:")
    elif files:
        lines.append("Files changed (edited configs keep a .visor-backup copy):")
    else:
        lines.append("No files changed.")
    for path in files:
        lines.append(f"  {path}")
    if verb == "install" and files and not report.dry_run:
        lines.append("")
        lines.append("Restart each client, then run `visor index` in your project.")
    return "\n".join(lines)
