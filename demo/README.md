# Terminal demo

The primary demo is a real CLI session against this repository:

```bash
uv run visor doctor
uv run visor index
uv run visor context "resolve local workspace project root"
```

## Generate the GIF

Install [VHS](https://github.com/charmbracelet/vhs), index the checkout once, then run from the repository root:

```bash
uv run visor index
vhs demo/terminal_demo.tape
```

`demo/terminal_demo.tape` is the recording source. `demo/vhs_bashrc` wraps `uv run visor` so the GIF shows command output with home directories, usernames, and the workspace-hash directory replaced. The JSON and context lines still come from the CLI.

Target frame: 1200×800, font size 16. Target length: about 10–15 seconds when the index is already warm and the tree does not contain large ignored directories. Target GIF size: under 5 MB. If VHS writes a larger GIF, recompress the frames or lower `Set Framerate` in the tape and record again. Do not draw a substitute GIF by hand.

The tape clears the screen, then types the context command with `| sed -n '1,42p'`. That pipe is only for the recording. It shows the first lines of the real CLI result so they fit the frame. `1,55p` still scrolled the first symbol off this 800px terminal, so the tape stops at line 42. The normal command, without `sed`, returns the complete result.

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

Commit `docs/assets/terminal-demo.gif` only after reviewing it for unsanitized paths and for lexical reason text. The published GIF should not say "Semantic similarity" while `doctor` reports lexical mode.

Published take: 1200×800, font size 16, 14.04 seconds, GIF 300,442 bytes, MP4 182,323 bytes. The context frame shows `resolve_mcp_roots`, `resolve_local_workspace`, `find_git_root`, and `is_project_dir`, with “top lexical hit” and no “Semantic similarity”. The CLI header still says `truncated=False` because `sed` runs outside the command.

The optional HUD still is [`docs/assets/hud_overview.png`](../docs/assets/hud_overview.png). It was not produced by this tape.
