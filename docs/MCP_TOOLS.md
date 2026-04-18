# V.I.S.O.R. MCP Tool Reference

This document is the authoritative API reference for all tools exposed by the V.I.S.O.R. MCP server. AI agents and developers should use this to understand when and how to invoke each tool.

> **Tip for AI agents**: The most powerful entry point is `build_context`. Start there for any code-understanding task before reaching for more specific tools.

---

## Tool Index

| Tool | Category | Description |
|------|----------|-------------|
| [`build_context`](#build_context) | 🧠 Intelligence | Ranked, compressed context with skill-aware scoring, reasoning, and metrics |
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
| [`set_hud_focus`](#set_hud_focus) | 📊 HUD | Highlight files on the 3D graph to show agent attention |
| [`store_memory`](#store_memory) | 🧩 Memory | Persist a conversation turn with semantic embedding |
| [`get_visor_skill`](#get_visor_skill) | 🧩 Skills | Fetch a custom skill instruction pack by name |
| [`list_custom_skills`](#list_custom_skills) | 🧩 Skills | List all available custom skills with strategies |
| [`add_custom_skill`](#add_custom_skill) | 🧩 Skills | Create a new custom skill with optional strategy |
| [`delete_custom_skill`](#delete_custom_skill) | 🧩 Skills | Remove a custom skill by ID |

---

## Recommended Workflows

For common tasks, use these tool sequences:

| Task | Recommended Flow |
|------|-----------------|
| **Bug investigation** | `build_context(query, skill="bug-fixer")` → `get_dependency_chain` → `get_drift_report` |
| **Architecture review** | `build_context(query, skill="architecture-explainer")` → `get_architecture_map` → `trace_route` |
| **Safe refactoring** | `build_context(query, skill="refactor-assistant")` → `impact_analysis` → `dead_code_detection` |
| **Performance tuning** | `build_context(query, skill="performance-optimizer")` → `get_dependency_chain` |

---

## 🧠 Intelligence

### `build_context`

The **Context Intelligence Engine**. Builds a ranked, token-budget-aware context payload from a natural language query. This is V.I.S.O.R.'s signature tool.

**When to use**: Any time an AI agent needs to understand relevant code for a task. This should be tried first before more specific lookups.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | ✅ | Natural language description of the task or question |
| `skill` | string | ❌ | Skill name to apply strategy overrides (e.g. `"bug-fixer"`) |

**Returns**: JSON object

```json
{
  "context": [
    {
      "id": 42,
      "file_path": "src/auth/jwt.py",
      "name": "verify_token",
      "node_type": "function",
      "start_line": 15,
      "end_line": 34,
      "code_snippet": "def verify_token(token: str) -> dict:\n    ...",
      "relevance_score": 2.85
    }
  ],
  "debug": {
    "intent": "BUG_FIX",
    "skill": "bug-fixer",
    "scores": {
      "42": {
        "final": 2.85,
        "exact_match": 1.0,
        "proximity": 1.5,
        "embedding": 0.375,
        "dependency": 1.2,
        "recency": 1.5
      }
    },
    "reasoning": {
      "42": [
        "Matched query token in symbol name",
        "Co-located in same file as top semantic hit",
        "Reachable via dependency chain",
        "Recently modified file (boosted)"
      ]
    }
  },
  "metrics": {
    "estimated_tokens_without": 11400,
    "estimated_tokens_with": 2180,
    "reduction_percent": 80.9
  },
  "prompt_ready": "// src/auth/jwt.py:15-34 (verify_token)\ndef verify_token(token: str) -> dict:\n    ...",
  "query": "authentication crash",
  "total_tokens": 2180,
  "truncated": false
}
```

**Scoring formula**:
```
score = W_exact × exact_match
      + W_same  × same_file
      + W_embed × embedding_sim
      + W_dep   × dependency_proximity
      + W_rec   × recency
```

Where weights are determined by the active intent profile (DEFAULT / BUG_FIX / REFACTOR / EXPLAIN), and optionally overridden by a skill's `scoring_bias`.

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

Returns a full AST symbol listing for a specific source file.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | ✅ | Relative file path (as indexed by V.I.S.O.R.) |

**Returns**: JSON object with `file_path`, `symbol_count`, and `symbols` array.

---

## 🗺️ Graph

### `get_dependency_chain`

Traverses the import edges graph from a symbol's source file and returns the full transitive dependency chain (BFS, max depth 5).

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `symbol` | string | ✅ | Symbol name to use as the graph traversal root |

**Returns**: JSON object with `symbol`, `source_file`, and `dependency_chain` array.

---

### `impact_analysis`

Calculates the downstream blast radius of a file change using BFS traversal (max depth 5). Answers: *"If I change this file, what else might break?"*

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | ✅ | Relative path of the file being changed |

**Returns**: JSON object with `target` and `blast_radius` array.

---

### `trace_route`

Finds the shortest architectural path between two files in the dependency graph.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `source` | string | ✅ | Starting file path |
| `target` | string | ✅ | Destination file path |

**Returns**: JSON object with `path` array.

---

### `dead_code_detection`

Finds files with zero incoming dependency edges (in-degree 0).

**Parameters**: None

**Returns**: JSON object with `isolated_nodes` array.

---

## ⚠️ Drift Detection

### `get_drift_report`

Detects context drift — situations where the AI's loaded snapshot is stale.

**Two detection modes**:
- **Hash-based** (preferred): Pass `file_hashes`. V.I.S.O.R. compares SHA-256 hashes.
- **Timestamp-based** (fallback): Compares `loaded_at` against `file_changelog`.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `context_files` | string[] | ✅ | File paths the agent has in context |
| `loaded_at` | string | ✅ | ISO-8601 timestamp of when context was loaded |
| `file_hashes` | object | ❌ | Dict of `{file_path: sha256_hex}` |

**Returns**: JSON (DriftReport schema) with `drift_detected`, `severity`, and `stale_files`.

---

## 📊 HUD & Telemetry

### `get_architecture_map`

Returns the full codebase file topology as a graph JSON for the 3D WebGPU HUD.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `depth` | integer | ❌ | Reserved for future BFS depth control |

**Returns**: JSON object with `nodes` and `edges` arrays.

---

### `get_telemetry`

Returns live telemetry snapshot for the current workspace.

**Parameters**: None

**Returns**: JSON object

```json
{
  "graph_nodes": 873,
  "context_burn": 48210,
  "drift_alert": false,
  "workspace_name": "visor"
}
```

---

### `set_hud_focus`

Controls the V.I.S.O.R. Developer HUD to visually highlight files the AI agent is actively reasoning about. Gives the developer real-time 3D visual feedback of the agent's attention and intent.

**When to use**: Call this as you investigate the codebase to show the developer which files you're looking at. Pass an empty list to clear the focus.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_paths` | string[] | ✅ | Paths to files to highlight on the graph (empty list to clear) |
| `intent` | string | ✅ | 2–4 word description of what the agent is doing (e.g. "Reviewing Auth Flow") |

**Returns**: JSON confirmation with highlighted file count.

---

### `store_memory`

Persists a conversation turn with a semantic embedding for future recall.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `role` | string | ✅ | `"user"` or `"assistant"` |
| `content` | string | ✅ | Conversation content |

---

### `add_custom_skill`

Creates a new custom skill with an optional execution strategy.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ | Unique skill name (e.g. `backend-expert`) |
| `description` | string | ✅ | One-line summary |
| `content` | string | ✅ | Markdown prompt instructions |
| `strategy` | string | ❌ | JSON strategy for execution overrides |

**Strategy format**:

```json
{
  "intent_override": "BUG_FIX",
  "scoring_bias": {
    "dependency": 1.2,
    "recency": 1.5
  },
  "tool_priority": [
    "build_context",
    "get_dependency_chain"
  ]
}
```

---

### `list_custom_skills`

Returns all custom skills with their strategies.

**Parameters**: None

---

### `get_visor_skill`

*(MCP Prompt)* Fetches a skill instruction pack by name for injection into AI prompts.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `skill_name` | string | ✅ | Name of the skill to retrieve |

---

### `delete_custom_skill`

Deletes a custom skill by its numeric database ID.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `skill_id` | integer | ✅ | The numeric ID from `list_custom_skills` |
