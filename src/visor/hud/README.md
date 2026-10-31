# V.I.S.O.R. HUD

The HUD is the React/Three.js webview bundled with the optional VS Code
extension. It visualizes the indexed dependency graph and displays telemetry
returned by the local V.I.S.O.R. MCP server. The terminal CLI and MCP server do
not depend on this package.

## Develop locally

```bash
npm ci
npm run dev
```

Opening the Vite page directly renders the shell but cannot load workspace data:
the production webview receives data through VS Code `postMessage` events.

## Checks

```bash
npm run lint
npm run build
npx playwright test
```

The extension build copies the single-file Vite output into its `hud-dist`
directory. See [`../extension/README.md`](../extension/README.md) for extension
setup and [`../../../demo/recording_guide.md`](../../../demo/recording_guide.md)
for reproducible public captures.
