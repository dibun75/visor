# Terminal demo

The primary demo is a real CLI session against this repository:

```bash
uv run visor doctor
uv run visor index
uv run visor context "where is MCP workspace detection handled?"
```

## Generate the GIF

Install [VHS](https://github.com/charmbracelet/vhs), index the checkout once, then run from the repository root:

```bash
uv run visor index
vhs demo/terminal_demo.tape
```

`demo/terminal_demo.tape` is the recording source. `demo/vhs_bashrc` wraps `uv run visor` so the GIF shows command output with home directories, usernames, and the workspace-hash directory replaced. The JSON and context lines still come from the CLI.

Target frame: 1200×600. Target length: about 10–15 seconds when the index is already warm and the tree does not contain large ignored directories. Target GIF size: under 5 MB. If VHS writes a larger GIF, recompress the frames or lower `Set Framerate` in the tape and record again. Do not draw a substitute GIF by hand.

`visor index` lists files with `Path.rglob` before it drops `.venv`, `node_modules`, and the other ignored directories. On this checkout that walk was still inside `.venv` and `src/visor/hud/node_modules` after several minutes. For a short recording, use a clean worktree and point the tape at it. `VISOR_UV_PROJECT` makes `uv run` use this checkout's environment so the clean tree does not get a second virtualenv. The typed commands stay `uv run visor doctor`, `uv run visor index`, and `uv run visor context`.

```bash
git worktree add --detach /tmp/visor-demo-src HEAD
uv run --project "$PWD" visor --workspace /tmp/visor-demo-src index
VISOR_DEMO_ROOT=/tmp/visor-demo-src VISOR_UV_PROJECT="$PWD" vhs demo/terminal_demo.tape
git worktree remove --force /tmp/visor-demo-src
```

If VHS cannot start Chromium because the sandbox is unavailable, retry with `VHS_NO_SANDBOX=1`.

Optional MP4, after a GIF exists:

```bash
ffmpeg -i docs/assets/terminal-demo.gif -movflags +faststart -pix_fmt yuv420p docs/assets/terminal-demo.mp4
```

Commit `docs/assets/terminal-demo.gif` only after reviewing it for unsanitized paths.

## What is not the terminal demo

`docs/assets/demo.gif` and `docs/assets/demo.mp4` are older HUD motion clips. `docs/assets/hud_overview.png` is an existing HUD still. None of those files was produced by `terminal_demo.tape`.

`demo/demo_output.json` only records that an older fictional transcript was removed. It is not command output.
