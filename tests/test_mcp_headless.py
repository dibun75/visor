import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ListRootsResult, Root


def make_project(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "pyproject.toml").write_text('[project]\nname = "fixture"\n')
    return path


async def run_session(
    *,
    cwd: Path,
    visor_home: Path,
    server_args: list[str] | None = None,
    roots_callback=None,
    repeat_initialize: bool = False,
):
    env = os.environ.copy()
    env.pop("WORKSPACE_ROOT", None)
    env["VISOR_HOME"] = str(visor_home)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "visor.server", *(server_args or [])],
        env=env,
        cwd=cwd,
    )
    async with stdio_client(params, errlog=sys.stderr) as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            list_roots_callback=roots_callback,
        ) as session:
            await session.initialize()
            if repeat_initialize:
                await session.initialize()
            tools = await session.list_tools()
            telemetry = await session.call_tool("get_telemetry", {})
            return tools, telemetry, ""


def telemetry_data(result):
    assert not result.isError
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_headless_handshake_uses_active_request_roots_once(tmp_path):
    project = make_project(tmp_path / "advertised")
    plain_cwd = tmp_path / "plain-cwd"
    plain_cwd.mkdir()
    calls = 0

    async def list_roots(_context):
        nonlocal calls
        calls += 1
        return ListRootsResult(roots=[Root(uri=project.as_uri())])

    tools, telemetry, _stderr = await run_session(
        cwd=plain_cwd,
        visor_home=tmp_path / "state",
        roots_callback=list_roots,
        repeat_initialize=True,
    )

    assert len(tools.tools) == 17
    assert telemetry_data(telemetry)["workspace_name"] == project.name
    assert calls == 1


@pytest.mark.asyncio
async def test_headless_without_roots_falls_back_to_project_cwd(tmp_path):
    project = make_project(tmp_path / "cwd-project")

    _tools, telemetry, _stderr = await run_session(
        cwd=project,
        visor_home=tmp_path / "state",
    )

    assert telemetry_data(telemetry)["workspace_name"] == project.name


@pytest.mark.asyncio
async def test_explicit_workspace_overrides_mcp_roots_from_tmp(tmp_path):
    explicit = make_project(tmp_path / "explicit")
    advertised = make_project(tmp_path / "advertised")
    plain_cwd = tmp_path / "plain-cwd"
    plain_cwd.mkdir()
    calls = 0

    async def list_roots(_context):
        nonlocal calls
        calls += 1
        return ListRootsResult(roots=[Root(uri=advertised.as_uri())])

    _tools, telemetry, _stderr = await run_session(
        cwd=plain_cwd,
        visor_home=tmp_path / "state",
        server_args=["--workspace", str(explicit)],
        roots_callback=list_roots,
    )

    assert telemetry_data(telemetry)["workspace_name"] == explicit.name
    assert calls == 0


@pytest.mark.asyncio
async def test_headless_without_any_valid_workspace_fails_safely(tmp_path):
    plain_cwd = tmp_path / "plain-cwd"
    plain_cwd.mkdir()

    _tools, result, _stderr = await run_session(
        cwd=plain_cwd,
        visor_home=tmp_path / "state",
    )

    assert result.isError
    assert "No V.I.S.O.R. project workspace" in result.content[0].text
