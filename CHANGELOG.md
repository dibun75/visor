# Changelog

All notable changes to V.I.S.O.R. will be documented in this file.

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
