import sqlite3
import json
import sqlite_vec
import sys
import os
import hashlib
import threading
import struct
from typing import List, Dict, Any, Optional

EMBEDDING_DIM = 384  # Configurable to specific embedding size (e.g. all-MiniLM-L6-v2)

VISOR_HOME = os.path.expanduser("~/.visor")

def serialize_vec(vector: List[float]) -> bytes:
    """Serializes a float vector for sqlite-vec storage."""
    return struct.pack(f"{len(vector)}f", *vector)


def _resolve_paths(workspace_root: Optional[str] = None):
    """Compute canonical hub + spoke paths from the workspace root."""
    hub_path = os.path.join(VISOR_HOME, "hub.db")

    if workspace_root is None:
        workspace_root = os.environ.get(
            "WORKSPACE_ROOT",
            os.path.abspath(os.path.realpath(os.getcwd())),
        )

    workspace_root = os.path.abspath(os.path.realpath(workspace_root))
    ws_hash = hashlib.sha256(workspace_root.encode("utf-8")).hexdigest()[:12]
    ws_name = os.path.basename(workspace_root) or "unknown"
    spoke_dir = os.path.join(VISOR_HOME, "workspaces", ws_hash)
    spoke_path = os.path.join(spoke_dir, "graph.db")

    os.makedirs(os.path.dirname(hub_path), exist_ok=True)
    os.makedirs(spoke_dir, exist_ok=True)

    return hub_path, spoke_path, ws_hash, ws_name, workspace_root


def _open_connection(db_path: str, load_vec: bool = False) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and optional sqlite-vec."""
    conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    if load_vec:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    return conn


class VectorDBClient:
    _instance = None

    def __new__(cls, db_path=None, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(VectorDBClient, cls).__new__(cls)
            cls._instance._lock = threading.Lock()
            cls._instance._init_dual(db_path)
        return cls._instance

    def _init_dual(self, legacy_path: Optional[str] = None):
        """Initialize the hub + spoke dual-DB connections."""
        hub_path, spoke_path, ws_hash, ws_name, ws_root = _resolve_paths()

        self.hub_path = hub_path
        self.spoke_path = spoke_path
        self.workspace_hash = ws_hash
        self.workspace_name = ws_name
        self.workspace_root = ws_root

        # Hub: global data (no sqlite-vec needed here — only vec_agent_memory uses it)
        self.hub_conn = _open_connection(hub_path, load_vec=True)
        # Spoke: workspace-specific code graph
        self.spoke_conn = _open_connection(spoke_path, load_vec=True)

        # Backward-compatible alias: existing code uses db_client.conn
        self.conn = self.spoke_conn

        print(f"[VISOR] Hub DB: {hub_path}", file=sys.stderr, flush=True)
        print(f"[VISOR] Spoke DB: {spoke_path} (workspace={ws_name}, hash={ws_hash})", file=sys.stderr, flush=True)

        self._migrate_hub()
        self._migrate_spoke()

    def reinitialize(self, workspace_root: str):
        """Re-initialize with a new workspace root (e.g. after MCP roots/list).

        Closes existing spoke connection and opens a new one for the target workspace.
        The hub connection is shared across workspaces so it stays open.
        """
        workspace_root = os.path.abspath(os.path.realpath(workspace_root))
        if workspace_root == self.workspace_root:
            return False  # Already pointing at this workspace

        # Close old spoke connection
        try:
            self.spoke_conn.close()
        except Exception:
            pass

        # Recompute paths for new workspace
        ws_hash = hashlib.sha256(workspace_root.encode("utf-8")).hexdigest()[:12]
        ws_name = os.path.basename(workspace_root) or "unknown"
        spoke_dir = os.path.join(VISOR_HOME, "workspaces", ws_hash)
        spoke_path = os.path.join(spoke_dir, "graph.db")
        os.makedirs(spoke_dir, exist_ok=True)

        self.spoke_path = spoke_path
        self.workspace_hash = ws_hash
        self.workspace_name = ws_name
        self.workspace_root = workspace_root

        self.spoke_conn = _open_connection(spoke_path, load_vec=True)
        self.conn = self.spoke_conn

        print(f"[VISOR] Workspace switched → {ws_name} ({ws_hash})", file=sys.stderr, flush=True)
        print(f"[VISOR] New Spoke DB: {spoke_path}", file=sys.stderr, flush=True)

        self._migrate_spoke()
        return True

    # ──────────────────────────────────────────────
    # Schema migrations
    # ──────────────────────────────────────────────

    def _migrate_hub(self):
        cursor = self.hub_conn.cursor()

        # Workspace registry
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workspaces (
                hash TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                root_path TEXT NOT NULL,
                last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_nodes INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0
            )
        ''')

        # Telemetry with workspace context
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS telemetry_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_hash TEXT NOT NULL,
                workspace_name TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                bytes_transmitted INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Portable custom skills (shared across all workspaces)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                content TEXT NOT NULL,
                strategy TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Safe migration: add strategy column if missing from older DBs
        try:
            cursor.execute("ALTER TABLE custom_skills ADD COLUMN strategy TEXT")
        except sqlite3.OperationalError:
            pass

        # Agent memory with optional workspace scoping
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_hash TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Vector index for agent memory
        cursor.execute(f'''
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_agent_memory USING vec0(
                embedding float[{EMBEDDING_DIM}]
            )
        ''')

        self.hub_conn.commit()

    def _migrate_spoke(self):
        cursor = self.spoke_conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS code_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                node_type TEXT NOT NULL,
                name TEXT NOT NULL,
                docstring TEXT,
                start_line INTEGER,
                end_line INTEGER,
                file_hash TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_node TEXT NOT NULL,
                to_node TEXT NOT NULL,
                relation_type TEXT NOT NULL
            )
        ''')

        cursor.execute(f'''
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_code_nodes USING vec0(
                embedding float[{EMBEDDING_DIM}]
            )
        ''')

        # UI State for bidirectional HUD control
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ui_state (
                key TEXT PRIMARY KEY,
                json_value TEXT NOT NULL
            )
        ''')

        self.spoke_conn.commit()

    # ──────────────────────────────────────────────
    # Hub methods: workspace registry
    # ──────────────────────────────────────────────

    def register_workspace(self) -> None:
        """Upsert the current workspace into the hub registry."""
        cursor = self.hub_conn.cursor()
        cursor.execute('''
            INSERT INTO workspaces (hash, name, root_path, last_accessed)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(hash) DO UPDATE SET
                name = excluded.name,
                root_path = excluded.root_path,
                last_accessed = CURRENT_TIMESTAMP
        ''', (self.workspace_hash, self.workspace_name, self.workspace_root))
        self.hub_conn.commit()

    def update_workspace_stats(self, total_nodes: int, total_tokens: int) -> None:
        """Update cached aggregates for the current workspace."""
        cursor = self.hub_conn.cursor()
        cursor.execute('''
            UPDATE workspaces SET total_nodes = ?, total_tokens = ?
            WHERE hash = ?
        ''', (total_nodes, total_tokens, self.workspace_hash))
        self.hub_conn.commit()

    def get_all_workspaces(self) -> List[Dict[str, Any]]:
        """Return all registered workspaces with cached stats."""
        cursor = self.hub_conn.cursor()
        cursor.execute('''
            SELECT hash, name, root_path, last_accessed, total_nodes, total_tokens
            FROM workspaces ORDER BY last_accessed DESC
        ''')
        return [
            {"hash": r[0], "name": r[1], "root_path": r[2],
             "last_accessed": r[3], "nodes": r[4], "tokens": r[5]}
            for r in cursor.fetchall()
        ]

    # ──────────────────────────────────────────────
    # Hub methods: telemetry
    # ──────────────────────────────────────────────

    def log_telemetry(self, tool_name: str, bytes_transmitted: int) -> int:
        cursor = self.hub_conn.cursor()
        cursor.execute(
            "INSERT INTO telemetry_logs (workspace_hash, workspace_name, tool_name, bytes_transmitted) VALUES (?, ?, ?, ?)",
            (self.workspace_hash, self.workspace_name, tool_name, bytes_transmitted),
        )
        self.hub_conn.commit()
        return cursor.lastrowid

    def get_global_telemetry(self) -> Dict[str, Any]:
        """Return total tokens + per-workspace breakdown."""
        self.hub_conn.commit()  # Flush WAL reads
        cursor = self.hub_conn.cursor()

        # Total across all workspaces
        cursor.execute("SELECT IFNULL(SUM(bytes_transmitted), 0) FROM telemetry_logs")
        total_bytes = cursor.fetchone()[0]

        # Per workspace
        cursor.execute('''
            SELECT workspace_name, workspace_hash, IFNULL(SUM(bytes_transmitted), 0)
            FROM telemetry_logs
            GROUP BY workspace_hash
            ORDER BY SUM(bytes_transmitted) DESC
        ''')
        per_workspace = [
            {"name": r[0], "hash": r[1], "bytes": r[2]}
            for r in cursor.fetchall()
        ]

        # Memory burn
        cursor.execute("SELECT IFNULL(SUM(length(content)), 0) FROM agent_memory")
        memory_bytes = cursor.fetchone()[0]

        return {
            "total_bytes": total_bytes + memory_bytes,
            "per_workspace": per_workspace,
        }

    def get_workspace_telemetry(self) -> int:
        """Return token burn for the current workspace only."""
        self.hub_conn.commit()
        cursor = self.hub_conn.cursor()
        cursor.execute(
            "SELECT IFNULL(SUM(bytes_transmitted), 0) FROM telemetry_logs WHERE workspace_hash = ?",
            (self.workspace_hash,)
        )
        return cursor.fetchone()[0]

    # ──────────────────────────────────────────────
    # Hub methods: custom skills (shared globally)
    # ──────────────────────────────────────────────

    def get_custom_skills(self) -> List[Dict[str, Any]]:
        cursor = self.hub_conn.cursor()
        cursor.execute("SELECT id, name, description, content, strategy FROM custom_skills ORDER BY name ASC")
        return [{"id": str(r[0]), "name": r[1], "description": r[2], "content": r[3], "strategy": r[4]} for r in cursor.fetchall()]

    def get_skill_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a single skill by name, parsing its strategy JSON if present."""
        import json as _json
        cursor = self.hub_conn.cursor()
        cursor.execute("SELECT id, name, description, content, strategy FROM custom_skills WHERE name = ? COLLATE NOCASE LIMIT 1", (name,))
        row = cursor.fetchone()
        if not row:
            return None
        strategy = None
        if row[4]:
            try:
                strategy = _json.loads(row[4])
            except (ValueError, TypeError):
                strategy = None
        return {"id": str(row[0]), "name": row[1], "description": row[2], "content": row[3], "strategy": strategy}

    def add_custom_skill(self, name: str, description: str, content: str, strategy: Optional[str] = None) -> int:
        cursor = self.hub_conn.cursor()
        cursor.execute("INSERT INTO custom_skills (name, description, content, strategy) VALUES (?, ?, ?, ?)", (name, description, content, strategy))
        self.hub_conn.commit()
        return cursor.lastrowid

    def delete_custom_skill(self, skill_id: int) -> bool:
        cursor = self.hub_conn.cursor()
        cursor.execute("DELETE FROM custom_skills WHERE id=?", (skill_id,))
        self.hub_conn.commit()
        return cursor.rowcount > 0

    # ──────────────────────────────────────────────
    # Hub methods: agent memory
    # ──────────────────────────────────────────────

    def store_memory(self, role: str, content: str, vector: List[float]) -> int:
        cursor = self.hub_conn.cursor()
        cursor.execute(
            "INSERT INTO agent_memory (workspace_hash, role, content) VALUES (?, ?, ?)",
            (self.workspace_hash, role, content),
        )
        mem_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO vec_agent_memory(rowid, embedding) VALUES (?, ?)",
            (mem_id, serialize_vec(vector)),
        )
        self.hub_conn.commit()
        return mem_id

    def recall_memory(self, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        cursor = self.hub_conn.cursor()
        query = """
            SELECT m.id, m.role, m.content, m.timestamp, m.workspace_hash, distance
            FROM vec_agent_memory v
            JOIN agent_memory m ON v.rowid = m.id
            WHERE embedding MATCH ? AND k = ?
        """
        cursor.execute(query, (serialize_vec(vector), limit))
        return [
            {"id": r[0], "role": r[1], "content": r[2], "timestamp": r[3], "workspace": r[4], "distance": r[5]}
            for r in cursor.fetchall()
        ]

    # ──────────────────────────────────────────────
    # Spoke methods: UI state
    # ──────────────────────────────────────────────

    def get_ui_state(self, key: str) -> dict | None:
        cursor = self.spoke_conn.cursor()
        cursor.execute("SELECT json_value FROM ui_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return None
        return None

    def set_ui_state(self, key: str, data: dict | None) -> None:
        cursor = self.spoke_conn.cursor()
        if data is None:
            cursor.execute("DELETE FROM ui_state WHERE key = ?", (key,))
        else:
            json_val = json.dumps(data)
            cursor.execute("INSERT INTO ui_state (key, json_value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET json_value = excluded.json_value", (key, json_val))
        self.spoke_conn.commit()

    # ──────────────────────────────────────────────
    # Spoke methods: code nodes & edges
    # ──────────────────────────────────────────────

    def upsert_node(self, file_path: str, node_type: str, name: str, docstring: str, vector: List[float], start_line: int = -1, end_line: int = -1, file_hash: str = "") -> int:
        with self._lock:
            cursor = self.spoke_conn.cursor()
            cursor.execute("SELECT id FROM code_nodes WHERE file_path=? AND name=? AND node_type=?", (file_path, name, node_type))
            row = cursor.fetchone()

            if row:
                node_id = row[0]
                cursor.execute("DELETE FROM vec_code_nodes WHERE rowid=?", (node_id,))
                cursor.execute(
                    "UPDATE code_nodes SET docstring=?, start_line=?, end_line=?, file_hash=? WHERE id=?",
                    (docstring, start_line, end_line, file_hash, node_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO code_nodes (file_path, node_type, name, docstring, start_line, end_line, file_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (file_path, node_type, name, docstring, start_line, end_line, file_hash)
                )
                node_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO vec_code_nodes(rowid, embedding) VALUES (?, ?)",
                (node_id, serialize_vec(vector))
            )

            self.spoke_conn.commit()
            return node_id

    def batch_upsert_nodes(
        self,
        nodes: List[dict],
    ) -> None:
        """
        High-throughput bulk upsert of code nodes within a single transaction.
        """
        cursor = self.spoke_conn.cursor()
        file_paths = list({n["file_path"] for n in nodes})
        placeholders = ",".join(["?"] * len(file_paths))
        cursor.execute(
            f"SELECT id, file_path, name, node_type FROM code_nodes WHERE file_path IN ({placeholders})",
            file_paths,
        )
        existing: dict[tuple, int] = {
            (r[1], r[2], r[3]): r[0] for r in cursor.fetchall()
        }

        with self._lock:
            # Safe sqlite-vec vector deletion OUTSIDE the insert transaction
            if existing:
                for node_id in existing.values():
                    cursor.execute("DELETE FROM vec_code_nodes WHERE rowid=?", (node_id,))

            try:
                cursor.execute("BEGIN")
                for n in nodes:
                    key = (n["file_path"], n["name"], n["node_type"])
                    vec_blob = serialize_vec(n["vector"])
                    if key in existing:
                        node_id = existing[key]
                        cursor.execute(
                            "UPDATE code_nodes SET docstring=?, start_line=?, end_line=?, file_hash=? WHERE id=?",
                            (n["docstring"], n["start_line"], n["end_line"], n["file_hash"], node_id),
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO code_nodes (file_path, node_type, name, docstring, start_line, end_line, file_hash) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (n["file_path"], n["node_type"], n["name"], n["docstring"],
                             n["start_line"], n["end_line"], n["file_hash"]),
                        )
                        node_id = cursor.lastrowid
                        existing[key] = node_id

                    try:
                        cursor.execute("DELETE FROM vec_code_nodes WHERE rowid = ?", (node_id,))
                        cursor.execute(
                            "INSERT INTO vec_code_nodes(rowid, embedding) VALUES (?, ?)",
                            (node_id, vec_blob),
                        )
                    except Exception as e:
                        print(f"FAILED ON INSERT: {key} -> {node_id} -> {e}", file=sys.stderr)
                        raise
                try:
                    cursor.execute("COMMIT")
                except Exception as e:
                    print(f"FAILED ON COMMIT: {e}", file=sys.stderr)
                    raise
            except Exception:
                cursor.execute("ROLLBACK")
                raise

    def upsert_edge(self, from_node: str, to_node: str, relation_type: str):
        cursor = self.spoke_conn.cursor()
        cursor.execute("SELECT id FROM edges WHERE from_node=? AND to_node=? AND relation_type=?", (from_node, to_node, relation_type))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO edges (from_node, to_node, relation_type) VALUES (?, ?, ?)", (from_node, to_node, relation_type))
            self.spoke_conn.commit()

    def search_similar(self, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        cursor = self.spoke_conn.cursor()
        query = """
            SELECT n.id, n.file_path, n.node_type, n.name, n.docstring, n.start_line, n.end_line, distance
            FROM vec_code_nodes v
            JOIN code_nodes n ON v.rowid = n.id
            WHERE embedding MATCH ? AND k = ?
        """
        cursor.execute(query, (serialize_vec(vector), limit))
        return [
            {"id": r[0], "file_path": r[1], "node_type": r[2], "name": r[3], "docstring": r[4], "start_line": r[5], "end_line": r[6], "distance": r[7]}
            for r in cursor.fetchall()
        ]

    def get_recency_map(self, file_paths: List[str], decay_seconds: int = 3600) -> Dict[str, float]:
        """
        Compute a decaying recency score [0.0, 1.0] for files based on the file_changelog.
        Files modified exactly now get 1.0. Files modified older than decay_seconds get 0.0.
        """
        if not file_paths:
            return {}
        cursor = self.spoke_conn.cursor()
        placeholders = ",".join("?" for _ in file_paths)
        query = f"""
            SELECT file_path, MAX(datetime(changed_at)) 
            FROM file_changelog 
            WHERE file_path IN ({placeholders})
            GROUP BY file_path
        """
        try:
            cursor.execute(query, tuple(file_paths))
            results = cursor.fetchall()
        except sqlite3.OperationalError:
            # Table might not exist yet if watcher never fired
            return {p: 0.0 for p in file_paths}

        import datetime
        now = datetime.datetime.utcnow()
        recency_map = {}
        for path, dt_str in results:
            try:
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                diff = (now - dt).total_seconds()
                score = max(0.0, 1.0 - (diff / decay_seconds))
            except ValueError:
                score = 0.0
            recency_map[path] = score

        return {p: recency_map.get(p, 0.0) for p in file_paths}

# Expose a default instance
db_client = VectorDBClient()
