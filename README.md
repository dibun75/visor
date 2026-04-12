# V.I.S.O.R. (Visual Intelligence System for Orchestrated Reasoning)

V.I.S.O.R. is a local-first, privacy-focused Model Context Protocol (MCP) server and 3D Developer HUD for AI-native IDEs like Google Antigravity and VS Code. It acts as a "second brain" for your AI coding agents, providing them with persistent memory and precise codebase context while drastically reducing your API token costs.

<div align="center">
  <img src="./docs/assets/hud_overview.png" alt="V.I.S.O.R HUD Dashboard" width="800"/>
</div>

---

## ✨ Features

* **Interactive 3D WebGPU HUD**: Monitor your AI agents in real-time without leaving your IDE. The HUD visualizes your codebase architecture as a force-directed graph and displays live telemetry, including your Agent Context Burn and Graph Database Scale.
* **Semantic Context Pruning**: Instead of dumping entire directories into your LLM's context window, V.I.S.O.R. uses Tree-sitter to parse your code into an Abstract Syntax Tree (AST). It only feeds the AI the exact files and dependencies needed for the task, saving massive amounts of tokens.
* **Persistent Agentic Memory**: Powered by a local SQLite database with `sqlite-vec`, V.I.S.O.R. remembers past architectural decisions, user preferences, and custom rules across different chat sessions.
* **Context Drift Alerts**: V.I.S.O.R. monitors your Git commits and file changes. If your AI's stored context becomes outdated compared to the actual codebase, it automatically intercepts the prompt and warns you before the agent hallucinates bad code.

<div align="center">
  <img src="./docs/assets/drift_alert.png" alt="Context Drift Alert" width="400"/>
</div>

---

## 🚀 Quick Start (IDE Extension)

V.I.S.O.R. is distributed as a native IDE extension, bundling both the Python backend engine and the React WebGPU frontend.

1. Download the latest `visor-hud-0.1.0.vsix` release.
2. Open your IDE (Antigravity or VS Code) and navigate to the Extensions panel.
3. Click the `...` menu at the top right and select **Install from VSIX...**.
4. Select the downloaded `.vsix` file.
5. The extension will automatically use `uv` to bootstrap the Python MCP server and launch the HUD in your sidebar via the *Start V.I.S.O.R. HUD* command.

---

## 📊 Understanding the HUD & Telemetry

V.I.S.O.R operates entirely via the **Model Context Protocol (MCP)** boundary. It uses precision tooling rather than passively intercepting your raw chat prompts. 

* **Agent Context Burn**: A real-time token tracker showing the volume of context permanently stored by your agent. This number only increments horizontally when your AI explicitly invokes the `store_memory` MCP tool to commit knowledge to the database.
* **Graph Database Scale**: The total number of AST nodes (functions, classes, imports) currently indexed in your local SQLite vector store. This local metric only increments when you write new logic in tracked files, triggering the AST indexing pipeline.
* **Context Drift Alert**: Flashes red if the agent's internal contextual understanding is outdated. V.I.S.O.R watches the file system; if you physically modify a source file, the warning trips active for exactly 60 seconds to warn the LLM before it hallucinates via stale code references.

---

## 🔌 Wiring it to Your AI Agent (Antigravity)

V.I.S.O.R's extension provides the frontend metrics HUD, but your IDE's innate AI engine still needs to be pointed to V.I.S.O.R's daemon to gain the capability to actually call its tools!

For Google Antigravity, MCP connections are declared centrally inside your home directory.

1. Open `~/.gemini/antigravity/mcp_config.json`.
2. Append V.I.S.O.R to the active `mcpServers` dictionary:
```json
    "visor": {
      "command": "uv",
      "args": [
        "--directory",
        "<PATH_TO_VISOR_WORKSPACE>",
        "run",
        "-q",
        "<PATH_TO_VISOR_WORKSPACE>/src/visor/server.py"
      ],
      "env": {}
    }
```
3. Restart or reload your AI Agent session.
4. Try prompting your agent: *"Please use the `store_memory` tool to save 'Hello World'"*. You will immediately notice the Agent Context Burn jump up as the AI fulfills the MCP contract!

---

## 🐛 Common Webview Pitfalls

If you are developing the WebGPU HUD or contributing to V.I.S.O.R., please note the following quirks regarding VS Code Webview Main Panels:
* **`acquireVsCodeApi()` Restriction**: VS Code imposes a strict security constraint where the `acquireVsCodeApi()` method can only be called **exactly once** per Webview lifecycle. Attempting to call it repeatedly (for example, directly inside a React component body that re-renders) will throw a fatal `An instance of the VS Code API has already been acquired` error. This error will silently crash the React tree without triggering standard browser debuggers. Always memoize or cache the VS Code API object globally on initial mount.

---

## 🤝 Contributing

V.I.S.O.R. is built by the community, for the community. We recommend sharing short video demos of specific HUD features on social media to help others see the value of token optimization. Check our issues page to submit feature requests or report bugs.
