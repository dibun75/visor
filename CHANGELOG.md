# Changelog

All notable changes to V.I.S.O.R. are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.6.0] — 2026-04-12 — Phase 3: Performance & Parallel Indexing

### Added
- **`CALLS` edge extraction** — Tree-sitter now extracts function call sites from Python, TypeScript, TSX, and JavaScript files as `CALLS` edges in the graph, complementing `IMPORTS` edges.
- **`batch_upsert_nodes()`** — New `VectorDBClient` method that batch-writes all nodes for a file in a single SQLite transaction (~10-20× faster than per-node commits).
- **Progressive workspace indexing** — `index_workspace()` now processes files in priority order: open editor files → recently modified files (< 10 min) → everything else in parallel via `ThreadPoolExecutor(max_workers=4)`.
- **Non-blocking MCP startup** — The workspace scan runs in a daemon background thread (`visor-indexer`). The MCP server is usable immediately on start without waiting for full indexing.
- **Smarter ignore list** — `.git`, `dist`, `.agent` directories are now excluded during workspace scans.

### Changed
- `index_file()` now uses `batch_upsert_nodes()` and logs at `DEBUG` level for cache hits (reducing log noise).
- `index_workspace()` accepts an optional `open_files: list` argument for progressive priority ordering.

---

## [0.5.0] — 2026-04-12 — Phase 2: Context Intelligence Engine

### Added
- **`build_context(query)`** — The Context Intelligence Engine. Ranks code nodes using a 4-signal weighted formula: embedding similarity, exact name match, co-location with anchor file, and dependency graph proximity. Enforces an 8,000-token budget.
- **`get_symbol_context(symbol)`** — Returns all indexed definitions of a symbol (partial name match), including file path, node type, and precise line range.
- **`get_dependency_chain(symbol)`** — BFS traversal from a symbol's source file through the import edges graph (max depth 5), returning the full transitive dependency chain.
- **`get_file_context(path)`** — Promoted from placeholder to a real AST symbol listing: returns every class, function, and import in a file with start/end lines.
- **`docs/ARCHITECTURE.md`** — Full technical architecture document: system design, data flow, DB schema, embedding pipeline details, and contribution guide.
- **`docs/MCP_TOOLS.md`** — Complete MCP tool API reference for all 16 tools, with parameters, return schemas, and example invocations.

### Changed
- `get_drift_report()` upgraded to support **hash-based drift detection** via an optional `file_hashes: {file_path: sha256}` parameter, in addition to the existing timestamp fallback.
- `README.md` — Added badges, full tool reference table, dev setup guide, and links to new docs.

---

## [0.4.1] — 2026-04-12 — Phase 1: Real Semantic Embeddings

### Added
- **`sentence-transformers/all-MiniLM-L6-v2`** — Replaced all `numpy.random.rand` placeholder embeddings with real 384-dim semantic vectors, normalized for cosine similarity.
- **`src/visor/db/embeddings.py`** — `SemanticEmbedder` singleton with lazy model loading to keep server startup instant.
- **`edges` table** — New SQLite table for dependency relationships (`from_node`, `to_node`, `relation_type`).
- **`file_hash`, `start_line`, `end_line`** — Added to `code_nodes` schema for hash-based cache invalidation and precise symbol location.
- **`upsert_edge()`** — New `VectorDBClient` method to persist graph edges.
- **SHA-256 file hashing** — `treesitter.py` now computes a file hash on every parse; `watcher.py` uses it to skip unchanged files.

### Changed
- `_build_nx_graph()` now reads from the `edges` table instead of simulating edges from directory clusters.
- `store_memory()` and `search_codebase()` now use real `SemanticEmbedder` vectors.
- Schema migration strategy: drop-and-recreate during development phase to avoid drift debt.

---

## [0.4.0] — 2026-04-12 — Skills Engine & UI Fixes

### Added
- **Custom Skills Engine** — SQLite-backed `custom_skills` table with full CRUD via MCP tools (`add_custom_skill`, `list_custom_skills`, `delete_custom_skill`, `get_visor_skill` prompt).
- **Glassmorphism Skills Modal** — "Manage AI Skills" panel in `TelemetryHUD.tsx` for creating and deleting instruction packs directly from the HUD.

### Fixed
- HUD overlay `pointer-events` bug that caused interactive elements (buttons, inputs) to be unclickable when the overlay was active.

---

## [0.3.x] — Earlier Releases

- Initial Tree-sitter AST parser (Python, TypeScript, JS, TSX)
- WebGPU force-directed 3D graph HUD with cluster coloring and drift pulse animation
- Watchdog-based file watcher with debounce
- `sqlite-vec` vector store integration
- FastMCP server with stdio transport
- VS Code / Antigravity extension scaffold
