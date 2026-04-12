# V.I.S.O.R. Technical Architecture

> **V**isual **I**ntelligence **S**ystem for **O**rchestrated **R**easoning

## Table of Contents

1. [System Overview](#system-overview)
2. [Design Philosophy](#design-philosophy)
3. [Data Flow](#data-flow)
4. [Database Schema](#database-schema)
5. [Component Breakdown](#component-breakdown)
6. [Embedding Pipeline](#embedding-pipeline)
7. [Context Scoring Engine](#context-scoring-engine)
8. [MCP Server & Tool Registration](#mcp-server--tool-registration)
9. [IDE Extension & WebGPU HUD](#ide-extension--webgpu-hud)
10. [Security Model](#security-model)
11. [How to Extend V.I.S.O.R.](#how-to-extend-visor)

---

## System Overview

V.I.S.O.R. is a **local-first MCP (Model Context Protocol) server** that acts as a semantic knowledge graph for AI coding agents. It indexes your codebase via Tree-sitter AST parsing, stores node embeddings in a local SQLite vector database, and serves precise, ranked context to AI agents on demand — eliminating "orientation waste" where agents blindly grep through irrelevant files.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Developer IDE                            │
│                                                                 │
│  ┌──────────────┐          ┌──────────────────────────────────┐ │
│  │  AI Agent    │◄────────►│     V.I.S.O.R. MCP Server       │ │
│  │ (Antigravity)│  stdio   │  (FastMCP over stdio transport)  │ │
│  └──────────────┘          └──────────────┬─────────────────┬─┘ │
│                                           │                 │   │
│                              ┌────────────▼──┐   ┌─────────▼─┐ │
│                              │  SQLite DB    │   │  NetworkX  │ │
│                              │  (vec + AST)  │   │  DiGraph   │ │
│                              └───────────────┘   └───────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              WebGPU HUD (Sidebar / Panel)                │   │
│  │      React + Three.js force-directed 3D graph            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Philosophy

| Principle | Implementation |
|-----------|---------------|
| **Local-first** | All data lives in `visor_memory.db` (SQLite). No cloud calls. |
| **Privacy-preserving** | No traffic interception. Communicates via stdio only. |
| **Token-efficient** | Context Scoring Engine ranks and compresses before returning context. |
| **Zero-config** | Bootstrapped by the IDE extension via `uv run`. |
| **Incremental** | File watcher only re-indexes changed files (hash-based cache). |

---

## Data Flow

### Indexing Pipeline (Background)

```
File saved / workspace opened
        ↓
Watchdog detects change
        ↓
SHA-256 hash compared to DB (cache hit → skip)
        ↓
Tree-sitter parses AST (Python, TS, JS, TSX)
        ↓
Nodes extracted: classes, functions, imports
        ↓
sentence-transformers encodes each node docstring/name
        ↓
Embedding + metadata upserted to SQLite
        ↓
Import relationships written to `edges` table
```

### Query Pipeline (On AI Request)

```
MCP tool called by AI agent
        ↓
build_context(query)
        ↓
Semantic search via sqlite-vec (cosine similarity)
        ↓
Dependency expansion via NetworkX BFS
        ↓
Multi-signal relevance scoring
        ↓
Token budget enforcement (8,000 token cap)
        ↓
Ranked context payload returned as JSON
```

---

## Database Schema

All data is stored in `visor_memory.db` (SQLite with WAL mode).

### `code_nodes`
Primary store for all indexed AST symbols.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment row ID |
| `file_path` | TEXT | Relative path to source file |
| `node_type` | TEXT | `class`, `function`, or `import` |
| `name` | TEXT | Symbol name |
| `docstring` | TEXT | Extracted Python docstring (if any) |
| `start_line` | INTEGER | First line of the symbol definition |
| `end_line` | INTEGER | Last line of the symbol definition |
| `file_hash` | TEXT | SHA-256 of the file at last index (cache key) |

### `edges`
Directed dependency relationships between files.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment row ID |
| `from_node` | TEXT | Source file path |
| `to_node` | TEXT | Target module or file path |
| `relation_type` | TEXT | e.g. `IMPORTS`, `CALLS`, `INHERITS` |

### `vec_code_nodes` (virtual — sqlite-vec)
Stores 384-dimensional float embeddings for ANN search.

### `vec_agent_memory` (virtual — sqlite-vec)
Stores embeddings for agent memory recall.

### `agent_memory`
Episodic memory of agent conversations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment row ID |
| `role` | TEXT | `user` or `assistant` |
| `content` | TEXT | Conversation turn content |
| `timestamp` | DATETIME | UTC timestamp |

### `custom_skills`
User-defined AI instruction packs (managed via HUD UI).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment row ID |
| `name` | TEXT | Skill identifier (e.g. `backend-expert`) |
| `description` | TEXT | One-line summary |
| `content` | TEXT | Full Markdown prompt instructions |
| `timestamp` | DATETIME | Created at |

### `file_changelog`
Records file modification events for timestamp-based drift detection.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment row ID |
| `file_path` | TEXT | Path to modified file |
| `changed_at` | TEXT | ISO-8601 UTC timestamp |

### `telemetry_logs`
Tracks bytes transmitted per MCP tool call for context burn metrics.

---

## Component Breakdown

```
visor/
├── server.py               # FastMCP entrypoint; starts watcher + registers tools
├── db/
│   ├── client.py           # VectorDBClient: schema, CRUD, vector search
│   └── embeddings.py       # SemanticEmbedder: lazy-loaded all-MiniLM-L6-v2 singleton
├── parser/
│   ├── treesitter.py       # ASTParser: extracts nodes + edges + file hash per file
│   └── watcher.py          # Watchdog: debounced file watcher + index_workspace boot scan
└── tools/
    ├── core.py             # All MCP tool registrations
    └── context_engine.py   # Context Intelligence Engine: scoring + compression
```

---

## Embedding Pipeline

V.I.S.O.R. uses `sentence-transformers/all-MiniLM-L6-v2` for semantic embeddings.

- **Dimensions**: 384
- **Normalization**: `normalize_embeddings=True` → dot product == cosine similarity
- **Lazy loading**: Model is only instantiated on first use to keep startup instant
- **Caching**: `file_hash` prevents re-embedding unchanged files
- **Storage**: Embeddings stored as `float[384]` blobs via `sqlite-vec` virtual table

To upgrade the model (e.g. to `bge-small-en`), change the model name in `embeddings.py`:

```python
self.model = SentenceTransformer("BAAI/bge-small-en-v1.5")
```

---

## Context Scoring Engine

Located in `src/visor/tools/context_engine.py`.

The `build_context(query)` function applies a weighted multi-signal formula to rank every candidate node returned by semantic search:

```
score =
  1.0 × exact_name_match     (query token found in symbol name)
  0.7 × same_file_as_anchor  (same file as top semantic hit)
  0.5 × embedding_similarity (1 - normalised_distance / 2)
  0.3 × dependency_proximity (1 / (1 + hop_count))
```

After scoring, a **token budget** of 8,000 tokens is enforced. Nodes are added to the payload greedily by score until the budget is exhausted. The `truncated` flag in the response indicates if any nodes were dropped.

---

## MCP Server & Tool Registration

V.I.S.O.R. uses `FastMCP` from the `mcp` Python package. Tools are registered via `@mcp.tool()` decorators inside `register_tools(mcp)` in `core.py`.

All tools are automatically decorated with `@track_telemetry`, which logs the byte size of each response to `telemetry_logs` — powering the live **Agent Context Burn** metric in the HUD.

See [`MCP_TOOLS.md`](./MCP_TOOLS.md) for a complete tool reference.

---

## IDE Extension & WebGPU HUD

The IDE extension (`src/visor/extension/`) serves two roles:

1. **Backend bootstrapper**: Spawns the Python MCP server via `uv run` and manages its lifecycle.
2. **HUD host**: Embeds the React WebGPU frontend as a VS Code Webview Panel or Sidebar.

The HUD connects to the MCP server indirectly — the extension translates IPC `postMessage` events from the React frontend into direct Python subprocess calls, then forwards results back to the webview.

**Key constraint**: `acquireVsCodeApi()` may only be called **once** per Webview lifecycle. V.I.S.O.R. caches the instance in `window.vscodeApiInstance`.

---

## Security Model

- **No network proxy**: V.I.S.O.R. does not intercept your IDE's outbound AI requests.
- **No OAuth access**: Your Google or GitHub tokens are never touched.
- **stdio-only**: The MCP server communicates exclusively over stdin/stdout — no open ports.
- **Local-only data**: `visor_memory.db` never leaves your machine.

---

## How to Extend V.I.S.O.R.

### Add a new MCP Tool

```python
# In src/visor/tools/core.py, inside register_tools():

@mcp.tool()
@track_telemetry
def my_new_tool(param: str) -> str:
    """
    Docstring shown to the AI agent as the tool description.
    Be precise — agents use this to decide when to call the tool.
    """
    # Your implementation here
    return json.dumps({"result": param})
```

### Add a new language to the AST parser

```python
# In src/visor/parser/treesitter.py

import tree_sitter_rust  # pip install tree-sitter-rust

_LANG_RUST = tree_sitter.Language(tree_sitter_rust.language())

_EXT_MAP[".rs"] = _LANG_RUST

_QUERIES[_LANG_RUST] = {
    "function": "(function_item name: (identifier) @name) @node",
    "class":    "(impl_item type: (type_identifier) @name) @node",
    "import":   "(use_declaration) @node",
}
```

### Add a Custom Skill via the HUD

1. Open the V.I.S.O.R. sidebar in your IDE.
2. Click **MANAGE AI SKILLS**.
3. Fill in Name, Description, and Markdown instructions.
4. Click **+ ADD SKILL**.

The AI can now invoke it with: `get_visor_skill("your-skill-name")`.
