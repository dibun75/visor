# V.I.S.O.R. MCP Tool Reference

This document is the authoritative API reference for all tools exposed by the V.I.S.O.R. MCP server. AI agents and developers should use this to understand when and how to invoke each tool.

> **Tip for AI agents**: The most powerful entry point is `build_context`. Start there for any code-understanding task before reaching for more specific tools.

---

## Tool Index

| Tool | Category | Description |
|------|----------|-------------|
| [`build_context`](#build_context) | 🧠 Intelligence | Ranked, compressed context from a natural language query |
| [`search_codebase`](#search_codebase) | 🔍 Search | Semantic vector search across all indexed nodes |
| [`get_symbol_context`](#get_symbol_context) | 🔍 Search | Find all definitions of a symbol with line ranges |
| [`get_file_context`](#get_file_context) | 🔍 Search | Full AST symbol listing for a specific file |
| [`get_dependency_chain`](#get_dependency_chain) | 🗺️ Graph | Transitive import chain from a symbol's source file |
| [`impact_analysis`](#impact_analysis) | 🗺️ Graph | Downstream blast radius of a file change (BFS depth 5) |
| [`trace_route`](#trace_route) | 🗺️ Graph | Shortest architectural path between two files |
| [`dead_code_detection`](#dead_code_detection) | 🗺️ Graph | Files with no incoming dependency edges |
| [`get_drift_report`](#get_drift_report) | ⚠️ Drift | Detect stale context via hash or timestamp comparison |
| [`get_architecture_map`](#get_architecture_map) | 📊 HUD | Full codebase topology for the 3D visualiser |
| [`get_telemetry`](#get_telemetry) | 📊 HUD | Live telemetry: node count, context burn, drift alert |
| [`store_memory`](#store_memory) | 🧩 Memory | Persist a conversation turn with semantic embedding |
| [`get_visor_skill`](#get_visor_skill) | 🧩 Skills | Fetch a custom skill instruction pack by name |
| [`list_custom_skills`](#list_custom_skills) | 🧩 Skills | List all available custom skills |
| [`add_custom_skill`](#add_custom_skill) | 🧩 Skills | Create a new custom skill |
| [`delete_custom_skill`](#delete_custom_skill) | 🧩 Skills | Remove a custom skill by ID |

---

## 🧠 Intelligence

### `build_context`

The **Context Intelligence Engine**. Builds a ranked, token-budget-aware context payload from a natural language query.

**When to use**: Any time an AI agent needs to understand relevant code for a task. This is the primary tool and should be tried before more specific lookups.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | ✅ | Natural language description of the task or question |

**Returns**: JSON object

```json
{
  "query": "how is authentication handled",
  "nodes": [
    {
      "id": 42,
      "file_path": "src/auth/jwt.py",
      "name": "verify_token",
      "node_type": "function",
      "docstring": "Validates a JWT and returns the decoded payload.",
      "start_line": 15,
      "end_line": 34,
      "distance": 0.23,
      "relevance_score": 1.85
    }
  ],
  "total_tokens": 412,
  "truncated": false
}
```

**Scoring formula**:
```
score = 1.0×exact_match + 0.7×same_file + 0.5×embedding_sim + 0.3×dependency_proximity
```

---

## 🔍 Search

### `search_codebase`

Pure semantic vector search across all indexed code nodes.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | ✅ | Natural language or code snippet to search for |

**Returns**: JSON array of up to 5 matching nodes with cosine distance scores.

---

### `get_symbol_context`

Finds all indexed definitions of a symbol (class, function, import) and returns their exact file location and line range.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `symbol` | string | ✅ | Exact or partial symbol name (SQL `LIKE` pattern) |

**Returns**: JSON object

```json
{
  "symbol": "VectorDBClient",
  "matches": [
    {
      "name": "VectorDBClient",
      "type": "class",
      "file": "src/visor/db/client.py",
      "start_line": 12,
      "end_line": 174,
      "docstring": ""
    }
  ]
}
```

---

### `get_file_context`

Returns a full AST symbol listing for a specific source file. Useful for getting a bird's-eye view of a file's structure before reading its raw content.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | ✅ | Relative file path (as indexed by V.I.S.O.R.) |

**Returns**: JSON object

```json
{
  "file_path": "src/visor/tools/core.py",
  "symbol_count": 18,
  "symbols": [
    {"name": "DriftReport", "type": "class", "start_line": 12, "end_line": 15, "docstring": ""},
    {"name": "track_telemetry", "type": "function", "start_line": 17, "end_line": 33, "docstring": "Decorator to track token proxy volume..."}
  ]
}
```

---

## 🗺️ Graph

### `get_dependency_chain`

Traverses the import edges graph from a symbol's source file and returns the full transitive dependency chain (BFS, max depth 5).

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `symbol` | string | ✅ | Symbol name to use as the graph traversal root |

**Returns**: JSON object

```json
{
  "symbol": "index_file",
  "source_file": "src/visor/parser/watcher.py",
  "dependency_chain": [
    "src/visor/db/client.py",
    "src/visor/db/embeddings.py",
    "src/visor/parser/treesitter.py"
  ]
}
```

---

### `impact_analysis`

Calculates the downstream blast radius of a file change using BFS traversal of the dependency graph (max depth 5). Answers: *"If I change this file, what else might break?"*

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | ✅ | Relative path of the file being changed |

**Returns**: JSON object

```json
{
  "target": "src/visor/db/client.py",
  "blast_radius": [
    "src/visor/tools/core.py",
    "src/visor/parser/watcher.py"
  ]
}
```

---

### `trace_route`

Finds the shortest architectural path between two files in the dependency graph. Useful for tracing a request from an API layer to a database layer.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `source` | string | ✅ | Starting file path |
| `target` | string | ✅ | Destination file path |

**Returns**: JSON object

```json
{
  "path": [
    "src/visor/server.py",
    "src/visor/tools/core.py",
    "src/visor/db/client.py"
  ]
}
```

---

### `dead_code_detection`

Finds files with zero incoming dependency edges (in-degree 0). These are potential entry points or orphaned modules.

**Parameters**: None

**Returns**: JSON object

```json
{
  "isolated_nodes": [
    "src/visor/server.py",
    "scripts/migrate.py"
  ]
}
```

---

## ⚠️ Drift Detection

### `get_drift_report`

Detects context drift — situations where the AI's loaded snapshot of the codebase is no longer accurate because files have changed.

**Two detection modes**:
- **Hash-based** (preferred): Pass `file_hashes`. V.I.S.O.R. compares SHA-256 hashes.
- **Timestamp-based** (fallback): Compares `loaded_at` against `file_changelog`.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `context_files` | string[] | ✅ | List of file paths the agent has in context |
| `loaded_at` | string | ✅ | ISO-8601 UTC timestamp of when context was loaded |
| `file_hashes` | object | ❌ | Dict of `{file_path: sha256_hex}` for hash-based detection |

**Returns**: JSON (DriftReport schema)

```json
{
  "drift_detected": true,
  "severity": "CRITICAL",
  "stale_files": [
    {
      "path": "src/visor/db/client.py",
      "reason": "hash_mismatch",
      "stored_hash": "a1b2c3d4...",
      "agent_hash": "deadbeef..."
    }
  ]
}
```

---

## 📊 HUD & Telemetry

### `get_architecture_map`

Returns the full codebase file topology as a graph JSON payload for the 3D WebGPU HUD visualiser.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `depth` | integer | ❌ | Depth parameter (reserved for future BFS depth control) |

**Returns**: JSON object with `nodes` and `edges` arrays for Three.js force graph.

---

### `get_telemetry`

Returns live telemetry snapshot for the HUD sidebar display.

**Parameters**: None

**Returns**: JSON object

```json
{
  "graph_nodes": 12673,
  "context_burn": 1205981,
  "drift_alert": false
}
```

- `graph_nodes`: Total AST nodes in the index
- `context_burn`: Cumulative bytes transmitted via all MCP tool calls (proxy for token usage)
- `drift_alert`: `true` if any file was modified in the last 60 seconds

---

## 🧩 Memory & Skills

### `store_memory`

Persists a conversation turn (episodic memory) with a real semantic embedding for future recall.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `role` | string | ✅ | `"user"` or `"assistant"` |
| `content` | string | ✅ | The content of the conversation turn |

---

### `get_visor_skill`

*(MCP Prompt — not a tool)* Fetches a custom skill instruction pack by name.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `skill_name` | string | ✅ | The exact name of the skill to retrieve |

**Usage**: `get_visor_skill("backend-expert")`

---

### `list_custom_skills`

Returns all custom skills stored in the local database.

**Parameters**: None

---

### `add_custom_skill`

Creates a new custom skill. Can also be done via the HUD UI.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ | Unique skill identifier (e.g. `backend-expert`) |
| `description` | string | ✅ | One-line summary |
| `content` | string | ✅ | Full Markdown prompt instructions |

---

### `delete_custom_skill`

Deletes a custom skill by its numeric database ID.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `skill_id` | integer | ✅ | The numeric ID from `list_custom_skills` |
