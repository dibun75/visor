# Recording the terminal demo

## HUD still

The HUD screenshot is generated from the current repository index and the real
`get_architecture_map`, `get_telemetry`, and `build_context` MCP tool outputs.
It does not use fixture telemetry or a hand-authored graph.

```bash
cd src/visor/hud
npm ci
cd ../../..
node demo/capture_hud.mjs
```

The script runs a temporary local Vite server, injects the same messages that
the VS Code extension sends to the webview, and writes
`docs/assets/hud_overview.png`. Review the image for private paths before
committing it.

## Social preview

`docs/assets/social-preview.png` is a 1280×640 solid-background image assembled
from the project icon and a cropped frame of the real lexical terminal demo. It
contains no benchmark result. GitHub's public API does not expose social-preview
uploads; a repository owner uploads the reviewed file under **Settings → Social
preview → Edit → Upload an image**.

Record the CLI, not the 3D graph. The source of truth is [`terminal_demo.tape`](./terminal_demo.tape).

## Command

From the repository root, with [VHS](https://github.com/charmbracelet/vhs) installed:

```bash
uv run visor index
vhs demo/terminal_demo.tape
```

VHS types and runs `visor doctor` and `visor index` in full. The context line in the tape is:

```bash
uv run visor context "resolve local workspace project root" | sed -n '1,42p'
```

That `sed` pipe is only for the recording. It displays the first lines of the real CLI output so they stay readable in the frame. The normal CLI command, without `sed`, returns the complete result.

`demo/vhs_bashrc` is the tape's shell rcfile. It pipes those three `uv run visor` invocations through `sed` so the frames omit home directories, the local username, and the workspace-hash directory. Review the GIF before committing it.

## Frame

- About 10–15 seconds when the index is already warm
- 1200×800, font size 16
- Optimized GIF under 5 MB when the generator is available

The tape types `clear` before the context command so the first lines start at the top of the frame.

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
bash --rcfile demo/vhs_bashrc -i -c 'uv run visor context "resolve local workspace project root"'
```
