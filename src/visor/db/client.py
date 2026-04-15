import sqlite3
import sqlite_vec
import sys
import threading
import struct
from typing import List, Dict, Any, Optional

EMBEDDING_DIM = 384 # Configurable to specific embedding size (e.g. all-MiniLM-L6-v2)

def serialize_vec(vector: List[float]) -> bytes:
    """Serializes a float vector for sqlite-vec storage."""
    return struct.pack(f"{len(vector)}f", *vector)

class VectorDBClient:
    _instance = None

    def __new__(cls, db_path=None, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(VectorDBClient, cls).__new__(cls)
            cls._instance._lock = threading.Lock()
            
            if db_path is None or db_path == "visor_memory.db":
                import os
                import hashlib
                
                env_path = os.environ.get("VISOR_DB_PATH")
                if env_path:
                    if env_path.endswith(".db"):
                        # Explicit .db file path
                        resolved_path = env_path
                    elif os.path.isfile(env_path):
                        # Path exists as a file (e.g., old SQLite DB) — use it directly
                        resolved_path = env_path
                    else:
                        # Treat as directory: append visor_memory.db
                        resolved_path = os.path.join(env_path, "visor_memory.db")
                else:
                    workspace = os.path.abspath(os.path.realpath(os.getcwd()))
                    hashed = hashlib.sha256(workspace.encode("utf-8")).hexdigest()[:12]
                    resolved_path = os.path.expanduser(f"~/.cache/visor/{hashed}/visor_memory.db")
                
                os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
                db_path = resolved_path
                
                print(f"[VISOR] Using DB path: {db_path}", file=sys.stderr, flush=True)
                
            cls._instance._init_db(db_path)
        return cls._instance

    def _init_db(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)
        self._migrate()

    def _migrate(self):
        cursor = self.conn.cursor()
        
        # Base tables (persist across restarts — no DROP)
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
            pass  # Column already exists
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Virtual vec0 vector tables
        cursor.execute(f'''
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_code_nodes USING vec0(
                embedding float[{EMBEDDING_DIM}]
            )
        ''')
        
        cursor.execute(f'''
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_agent_memory USING vec0(
                embedding float[{EMBEDDING_DIM}]
            )
        ''')
        
        # Telemetry usage tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS telemetry_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                bytes_transmitted INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def log_telemetry(self, tool_name: str, bytes_transmitted: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO telemetry_logs (tool_name, bytes_transmitted) VALUES (?, ?)", (tool_name, bytes_transmitted))
        self.conn.commit()
        return cursor.lastrowid

    def upsert_node(self, file_path: str, node_type: str, name: str, docstring: str, vector: List[float], start_line: int = -1, end_line: int = -1, file_hash: str = "") -> int:
        with self._lock:
            cursor = self.conn.cursor()
            # Ensure we always update the latest info
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

            self.conn.commit()
            return node_id

    def batch_upsert_nodes(
        self,
        nodes: List[dict],
    ) -> None:
        """
        High-throughput bulk upsert of code nodes within a single transaction.
        """
        cursor = self.conn.cursor()
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
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM edges WHERE from_node=? AND to_node=? AND relation_type=?", (from_node, to_node, relation_type))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO edges (from_node, to_node, relation_type) VALUES (?, ?, ?)", (from_node, to_node, relation_type))
            self.conn.commit()

    def search_similar(self, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
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
        cursor = self.conn.cursor()
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

    def store_memory(self, role: str, content: str, vector: List[float]) -> int:
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO agent_memory (role, content) VALUES (?, ?)", (role, content))
        mem_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO vec_agent_memory(rowid, embedding) VALUES (?, ?)",
            (mem_id, serialize_vec(vector))
        )
        self.conn.commit()
        return mem_id

    def recall_memory(self, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        query = """
            SELECT m.id, m.role, m.content, m.timestamp, distance
            FROM vec_agent_memory v
            JOIN agent_memory m ON v.rowid = m.id
            WHERE embedding MATCH ? AND k = ?
        """
        cursor.execute(query, (serialize_vec(vector), limit))
        return [
            {"id": r[0], "role": r[1], "content": r[2], "timestamp": r[3], "distance": r[4]}
            for r in cursor.fetchall()
        ]

    def get_custom_skills(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, description, content, strategy FROM custom_skills ORDER BY name ASC")
        return [{"id": str(r[0]), "name": r[1], "description": r[2], "content": r[3], "strategy": r[4]} for r in cursor.fetchall()]

    def get_skill_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a single skill by name, parsing its strategy JSON if present."""
        import json as _json
        cursor = self.conn.cursor()
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
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO custom_skills (name, description, content, strategy) VALUES (?, ?, ?, ?)", (name, description, content, strategy))
        self.conn.commit()
        return cursor.lastrowid

    def delete_custom_skill(self, skill_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM custom_skills WHERE id=?", (skill_id,))
        self.conn.commit()
        return cursor.rowcount > 0

# Expose a default instance
db_client = VectorDBClient()
