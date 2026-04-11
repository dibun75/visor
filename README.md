# Project V.I.S.O.R. 

> **Visual Intelligence System for Orchestrated Reasoning**

V.I.S.O.R. is a next-generation, JARVIS-inspired developer intelligence system. Designed to seamlessly integrate into the IDE (VS Code / Antigravity), it acts as an intelligent co-pilot backend providing deterministic architectural graphing, real-time context drift detection, and a high-performance WebGPU 3D HUD. 

<div align="center">
  <!-- Users: Place your main dashboard screenshot here -->
  <img src="./docs/assets/hud_overview.png" alt="V.I.S.O.R HUD Dashboard" width="800"/>
</div>

---

## ⚡ Key Features

* **3D Knowledge Graph**: Leverages `@react-three/fiber` to visualize the Abstract Syntax Tree (AST) of your codebase as an interactive, force-directed graph. Blue nodes represent classes/interfaces; red nodes represent methods/imports.
* **Deterministic AST Parsing**: Utilizes `tree-sitter` for sub-millisecond, low-latency code parsing rather than relying on LLMs, guaranteeing 100% accurate architectural mapping.
* **Real-time Drift Detection**: A filesystem `watchdog` daemon increments and updates the state. When active Agent context becomes outdated compared to the git lifecycle, the HUD flashes a **Critical Alert** preventing code hallucination.
* **Telemetry & Context Burn**: Live counters showing your LLM's active working memory limits (Context Burn) over your local graph database scales.
* **Zero-Touch Containerization**: Vibe-coding ready via `uv` minimal python Docker images and robust Docker Compose synchronization.

---

## 🏗️ Architecture

The system is decoupled into three major verticals:

1. **The Engine (`/src/visor/server.py`)**: A Python MCP (Model Context Protocol) daemon packing `sqlite-vec` for local vector storage, AST extractors, and telemetry dispatchers.
2. **The HUD (`/src/visor/hud/`)**: A React 19 + Vite frontend application utilizing WebGL/WebGPU for spatial 3D rendering and premium dark-mode glassmorphism styling.
3. **The IDE Bridge (`/src/visor/extension/`)**: A TypeScript VS Code extension that traps the HUD within an isolated `WebviewPanel`, capable of traversing remote SSH ports seamlessly.

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have the following installed on your host:
* `docker` and `docker compose`
* Node.js & `npm` (For compiling the IDE extension)

### 2. Bootstrapping the Environment
We use a unified startup script to allocate ephemeral ports and spin up the MCP backend alongside the development server:

```bash
chmod +x ./scripts/bootstrap.sh
./scripts/bootstrap.sh
```

### 3. Installing the IDE Extension
Navigate into the extension directory to package and install the `.vsix` plugin natively into your IDE:

```bash
cd src/visor/extension
npm install
npm run compile
npx vsce package
# If using the Antigravity IDE:
antigravity --install-extension visor-hud-0.1.0.vsix --force
```

### 4. Launching the HUD
From inside your IDE, press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) and execute:
**`> Start V.I.S.O.R. HUD`**

---

## 📖 Understanding the HUD UI

### The 3D Graph
Hover over nodes in the spatial view. They map directly back to symbols in your SQLite database. The visual connections denote references—allowing you to visually trace dependencies before executing large refactors.

### Context Drift Warning
<div align="center">
  <!-- Users: Place your drift alert screenshot here -->
  <img src="./docs/assets/drift_alert.png" alt="Context Drift Alert" width="400"/>
</div>

If you see a `CRITICAL ALERT: CONTEXT DRIFT - STALE AST` flash in the telemetry panel, it means the daemon detected a change in the filesystem (a saved file, a git checkout, etc.) that the LLM is not currently aware of. This represents a desync between the "Agent's memory" and the "Real disk state." 

### Remote Port Forwarding (SSH)
If running via a remote SSH instance, the Extension relies on dynamic Port Mapping (`vscode.window.createWebviewPanel` with `portMapping`) to pipe the remote `4173` preview port directly to the iframe running locally on your laptop without encountering CORS or connection-refused blocks.

---

## 🛠️ Tech Stack
* **Backend:** Python, MCP, `uv`, Tree-Sitter, Watchdog, SQLite (`sqlite-vec`)
* **Frontend:** React 19, Vite, TailwindCSS (Arbitrary styling), React Three Fiber, Drei
* **E2E Testing:** Playwright (Headless Chromium EGL GL rendering)
* **IDE:** VS Code Extension SDK (TypeScript)
