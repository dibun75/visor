# Changelog

All notable changes to V.I.S.O.R. will be documented in this file.

---

## [1.0.7] — 2026-04-18

### 🎨 Branding & Asset Standardization
- New high-contrast "Cyber Eye" icon replacing the generic telescope icon
- Deployed icon variants: `hero.png` (128px), `logo_square.png` (256px), `icon.png` (512px)
- Fixed icon blending issues on dark/light backgrounds in Open VSX and GitHub
- Replaced MP4 demo with web-optimized GIF for inline autoplay on all platforms
- Switched all documentation media to absolute raw GitHub URLs for marketplace compatibility

### 📖 Documentation
- Streamlined installation section with `uvx visor-mcp init` as the primary method
- Added side-by-side benchmark proof table ("The Proof: Why You Need V.I.S.O.R.")
- Collapsed per-IDE manual configs into a single expandable `<details>` block

### 🔒 Security & CI
- Added CodeQL scanning workflow for Python and JavaScript
- Extended Dependabot to cover npm dependencies (HUD + Extension)
- Cleaned up Actions history

---

## [1.0.6] — 2026-04-18

### 📖 Documentation Overhaul
- Rewrote main README to be beginner-friendly with plain English descriptions
- Added "What Can You Do With It?" section with 4 real-world usage examples
- Fixed marketplace link: VS Code Marketplace → Open VSX
- Fixed Antigravity config: removed `WORKSPACE_ROOT` env var (auto-detected since v1.0.2)
- Updated tool count: 16 → 17 (added `set_hud_focus`)
- Added Open VSX badge to badge row
- Rewrote extension README for Open VSX with example prompts
- Added missing CHANGELOG entries for v1.0.2 through v1.0.5
- Updated TROUBLESHOOTING.md with modern `uvx visor-mcp` config
- Documented `session.list_roots()` auto-detection in ARCHITECTURE.md
- Added `set_hud_focus` tool documentation to MCP_TOOLS.md

---

## [1.0.5] — 2026-04-18

### 📖 Documentation
- Added comprehensive README for the V.I.S.O.R. HUD extension (shown on Open VSX page)
- Documents all features, installation, configuration, and architecture

---

## [1.0.4] — 2026-04-18

### 📦 First Combined Release (PyPI + Open VSX)
- Python MCP package published to PyPI automatically on release
- VS Code extension published to Open VSX automatically on release
- Created `dibun75` namespace on Open VSX for verified publishing
- IDE extensions now auto-update via Open VSX registry

---

## [1.0.3] — 2026-04-18

### 🔧 CI Pipeline
- Added Open VSX publish workflow to GitHub Actions
- Bumped versions for first combined PyPI + Open VSX release attempt

---

## [1.0.2] — 2026-04-17

### 🧠 Dynamic Workspace Detection
- V.I.S.O.R. now auto-detects the active project workspace via MCP `session.list_roots()` API
- Fixed critical bug where the server indexed the home directory / pip packages instead of the user's project
- Removed reliance on `WORKSPACE_ROOT` environment variable — detection is now automatic
- Added `VectorDBClient.reinitialize()` for runtime database switching when workspace changes

### 🧪 Test Isolation
- Test fixtures now use isolated temporary databases
- Fixed tests leaking into the user's real `~/.visor/` workspace database
- All 43 tests passing reliably in CI

### 🔧 Code Quality
- Applied `ruff` formatting to all source files in `src/visor/`

---

## [0.10.1] — 2026-04-17

### 🔧 Hotfix

**Bundled HUD into Extension**
- Fixed "HUD Build Not Found" error when opening non-visor workspaces
- React HUD assets are now bundled inside the `.vsix` instead of being loaded from the workspace folder
- Extension uses `context.extensionPath` for all UI asset resolution

**Simplified Telemetry to Per-Workspace**
- Removed "ALL WORKSPACES" cross-workspace aggregation from the HUD
- Token counter now shows only the current workspace's usage: `TOKENS PROCESSED · {WORKSPACE_NAME}`
- Removed per-workspace breakdown bar chart — each workspace is self-contained
- Added `get_workspace_telemetry()` DB method for efficient single-workspace queries

---

## [0.10.0] — 2026-04-17

### 🏗️ Hub-and-Spoke Database Architecture

**Dual-Database Design**
- Split monolithic `visor_memory.db` into `~/.visor/hub.db` (global) + `~/.visor/workspaces/{hash}/graph.db` (per-workspace)
- Hub stores: workspace registry, telemetry logs, custom skills, agent memory
- Spoke stores: code_nodes, edges, vec_code_nodes, file_changelog, ui_state
- Deterministic path resolution — no more `VISOR_DB_PATH` environment variable

**Per-Workspace Telemetry**
- `get_telemetry` returns token usage scoped to the active workspace
- Workspace auto-registration on MCP server boot
- Cached workspace stats (node count, token usage) in the hub registry

**HUD Enhancements**
- Token counter shows workspace-scoped usage with workspace name context
- Graph database scale shows current workspace node count

**Auto-Migration**
- On first boot, discovers old monolith DBs in `~/.cache/visor/` and extension storage
- Copies global tables to hub, workspace tables to spokes
- Deduplicates custom skills, tags telemetry/memory with workspace context
- Leaves old DBs intact as backups

**Extension Cleanup**
- Removed `VISOR_DB_PATH` from extension env — Python uses `~/.visor/` convention directly
- Removed `context.storageUri` dependency for DB path resolution

---

## [0.8.0] — 2026-04-13

### 🚀 Skill-Orchestrated AI Engine (Wave 1)

**Skill Execution Layer**
- Skills are now first-class execution strategies with JSON `strategy` fields
- `intent_override` — force a specific scoring profile (BUG_FIX, EXPLAIN, REFACTOR)
- `scoring_bias` — override individual signal weights per skill
- `tool_priority` — recommended tool sequences for agents
- 4 pre-loaded skills auto-seeded on first boot: `bug-fixer`, `architecture-explainer`, `refactor-assistant`, `performance-optimizer`

**Context Intelligence Engine v2**
- 5-signal scoring: exact match + co-location + embedding + dependency + **recency**
- Explainable reasoning: human-readable justification for every selected node
- Token metrics: `estimated_tokens_without`, `estimated_tokens_with`, `reduction_percent`
- `prompt_ready` export: pre-formatted text block for direct AI injection
- Precise AST-bounded code snippet extraction (replaces generic docstrings)
- Automatic truncation with `... [N lines truncated] ...` for oversized functions

**CLI Interface**
- `visor context "query"` — general context retrieval
- `visor fix "description"` — bug investigation (auto-applies `bug-fixer` skill)
- `visor explain "module"` — architecture exploration (`architecture-explainer` skill)
- `visor trace source target` — shortest path between files
- `visor drift` — recent file modification report

**MCP Tool Upgrades**
- `build_context` now accepts optional `skill` parameter
- `add_custom_skill` now accepts optional `strategy` JSON
- `list_custom_skills` returns strategy data

---

## [0.7.0] — 2026-04-12

### Intelligence Refinement Phase

- Intent classification: BUG_FIX, REFACTOR, EXPLAIN, DEFAULT
- Recency scoring from `file_changelog` timestamps
- Debug observability: per-node scoring signal breakdown
- Database sandboxing via `VISOR_DB_PATH` / `~/.cache/visor/`

---

## [0.5.0] — 2026-04-12

### Context Intelligence Engine v1

- 16 MCP tools across 5 categories
- Multi-signal scoring formula (4 signals)
- Token budget enforcement (8,000 cap)
- Dual-mode drift detection (hash + timestamp)
- 3D WebGPU HUD with force-directed graph
- Tree-sitter AST indexing (Python, TypeScript, JavaScript, TSX)
- Semantic embeddings via all-MiniLM-L6-v2
- Persistent agentic memory with vector recall
