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

## 🐳 Docker & Remote SSH Setup

If you are running your development environment on a remote Linux VM via SSH, V.I.S.O.R. supports full Docker containerization with dynamic port allocation.

* **Reverse Tunneling**: Ensure your Antigravity Interface extension is configured properly. You must enable `enableLocalForwarding` and map your `localProxyPort` to allow the WebGPU HUD to stream over the reverse tunnel.
* **Ultra-Fast Build**: Build and spin up the container using our ultra-fast `uv` multi-stage setup:
  ```bash
  docker compose up -d --build
  ```
  Docker Compose is configured to dynamically assign an ephemeral port to prevent conflicts with other services on your VM. The extension will automatically detect this port and connect the HUD.
* **Vibe Coding Watch Mode**: The `docker-compose.yml` includes `docker compose watch` with `action: sync`. Any changes you make to the UI will instantly sync to the container without requiring a full rebuild.

---

## 📊 Understanding the HUD

Once V.I.S.O.R. is running, your sidebar will display the system status:

* **System Nominal**: Indicates the MCP server is actively communicating with your IDE's agent manager.
* **Agent Context Burn**: A real-time token tracker showing how much of your LLM's context window is filled. Keep this out of the red to prevent session failures.
* **Graph Database Scale**: The total number of AST nodes (functions, classes, imports) currently indexed in your local SQLite vector store.

---

## 🤝 Contributing

V.I.S.O.R. is built by the community, for the community. We recommend sharing short video demos of specific HUD features on social media to help others see the value of token optimization. Check our issues page to submit feature requests or report bugs.
