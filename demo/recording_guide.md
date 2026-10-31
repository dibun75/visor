# Recording the terminal demo

Record the CLI, not the 3D graph. The source of truth is [`terminal_demo.tape`](./terminal_demo.tape).

## Command

From the repository root, with [VHS](https://github.com/charmbracelet/vhs) installed:

```bash
uv run visor index
vhs demo/terminal_demo.tape
```

VHS types and runs:

```bash
uv run visor doctor
uv run visor index
uv run visor context "where is MCP workspace detection handled?"
```

`demo/vhs_bashrc` is the tape's shell rcfile. It pipes those three `uv run visor` invocations through `sed` so the frames omit home directories, the local username, and the workspace-hash directory. Review the GIF before committing it.

## Frame

- About 10–15 seconds when the index is already warm
- 1200×600
- Optimized GIF under 5 MB when the generator is available

If the warm `visor index` or `visor context` run longer than that, keep the real timing in the published GIF or shorten only the `Sleep` lines that follow a finished command. Do not delete output frames to invent a faster run.

## MP4

```bash
ffmpeg -i docs/assets/terminal-demo.gif -movflags +faststart -pix_fmt yuv420p docs/assets/terminal-demo.mp4
```

## If VHS is not installed

Do not draw or hand-type a GIF. Commit the tape and document the command above. A text transcript, if you need one, must be a sanitized copy of command output:

```bash
demo/vhs_shell.sh -c 'uv run visor doctor'
```

`demo/vhs_shell.sh` loads the same rcfile for a local interactive shell. The tape itself sets `Shell "bash"` and sources `demo/vhs_bashrc`, because VHS 0.10 rejects a shell command that includes arguments. A one-shot transcript:

```bash
bash --rcfile demo/vhs_bashrc -i -c 'uv run visor doctor'
bash --rcfile demo/vhs_bashrc -i -c 'uv run visor index'
bash --rcfile demo/vhs_bashrc -i -c 'uv run visor context "where is MCP workspace detection handled?"'
```

## Older HUD clips

`docs/assets/demo.gif` is a HUD animation of about 31 seconds and 13.5 MB. Leave it out of the README hero. The still to use for the optional HUD is `docs/assets/hud_overview.png`.
