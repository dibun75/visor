"""
Auto-migration from old monolith visor_memory.db files to the
Hub-and-Spoke architecture (~/.visor/hub.db + workspaces/*/graph.db).

Runs on first boot when hub.db has zero workspaces registered.
Discovers old databases, copies global tables to the hub,
workspace tables to spokes, and registers discovered workspaces.
Old DBs are left intact as backups.
"""

import glob
import hashlib
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

VISOR_HOME = os.path.expanduser("~/.visor")

# Known locations where old monolith DBs may exist
_OLD_DB_PATTERNS = [
    os.path.expanduser("~/.cache/visor/*/visor_memory.db"),
    os.path.expanduser(
        "~/.antigravity-server/data/User/workspaceStorage/*/dibun75.visor-hud/visor_memory.db"
    ),
    os.path.expanduser(
        "~/.antigravity-server/data/User/workspaceStorage/*/undefined_publisher.visor-hud/visor_memory.db"
    ),
    os.path.expanduser(
        "~/.config/Code/User/workspaceStorage/*/dibun75.visor/visor_memory.db"
    ),
]


def _discover_old_dbs() -> list[str]:
    """Scan filesystem for old monolith visor_memory.db files."""
    found = set()
    for pattern in _OLD_DB_PATTERNS:
        for p in glob.glob(pattern):
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                found.add(p)
    return sorted(found)


def _guess_workspace_root(db_path: str) -> str | None:
    """Try to find the WORKSPACE_ROOT that was used for an old DB.

    For ~/.cache/visor/{hash}/visor_memory.db, we can't reverse the hash,
    but we can read code_nodes file_paths to infer the workspace root.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM code_nodes LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            # Find the common root from the file_path
            # e.g., /home/user/my-project/src/server.py → /home/user/my-project
            parts = row[0].split("/")
            # Walk up until we find a directory that looks like a workspace root
            for i in range(len(parts), 2, -1):
                candidate = "/".join(parts[:i])
                if os.path.isdir(candidate) and (
                    os.path.exists(os.path.join(candidate, ".git"))
                    or os.path.exists(os.path.join(candidate, "pyproject.toml"))
                    or os.path.exists(os.path.join(candidate, "package.json"))
                ):
                    return candidate
    except Exception:
        pass
    return None


def _has_table(conn: sqlite3.Connection, table_name: str) -> bool:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    )
    return cursor.fetchone() is not None


def migrate_old_dbs(hub_conn: sqlite3.Connection) -> int:
    """Migrate data from discovered old DBs into the hub + spokes.

    Returns the number of databases migrated.
    """
    # Only run if hub has no workspaces yet (first boot)
    cursor = hub_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM workspaces")
    if cursor.fetchone()[0] > 0:
        return 0

    old_dbs = _discover_old_dbs()
    if not old_dbs:
        logger.info("[VISOR] No old databases found for migration.")
        return 0

    logger.info(f"[VISOR] Found {len(old_dbs)} old database(s) for migration.")
    migrated = 0

    for db_path in old_dbs:
        try:
            ws_root = _guess_workspace_root(db_path)
            if not ws_root:
                logger.warning(
                    f"[VISOR] Cannot determine workspace root for {db_path}, skipping."
                )
                continue

            ws_hash = hashlib.sha256(ws_root.encode("utf-8")).hexdigest()[:12]
            ws_name = os.path.basename(ws_root) or "unknown"

            old_conn = sqlite3.connect(db_path)

            # ── Migrate global data to hub ──
            _migrate_telemetry(old_conn, hub_conn, ws_hash, ws_name)
            _migrate_skills(old_conn, hub_conn)
            _migrate_memory(old_conn, hub_conn, ws_hash)

            # ── Migrate workspace data to spoke ──
            spoke_dir = os.path.join(VISOR_HOME, "workspaces", ws_hash)
            spoke_path = os.path.join(spoke_dir, "graph.db")

            if not os.path.exists(spoke_path) or os.path.getsize(spoke_path) == 0:
                os.makedirs(spoke_dir, exist_ok=True)
                _migrate_spoke_data(old_conn, spoke_path)

            # ── Register workspace in hub ──
            node_count = 0
            if _has_table(old_conn, "code_nodes"):
                node_count = old_conn.execute(
                    "SELECT COUNT(*) FROM code_nodes"
                ).fetchone()[0]

            total_bytes = 0
            if _has_table(old_conn, "telemetry_logs"):
                total_bytes = old_conn.execute(
                    "SELECT IFNULL(SUM(bytes_transmitted), 0) FROM telemetry_logs"
                ).fetchone()[0]

            hub_conn.execute(
                """
                INSERT INTO workspaces (hash, name, root_path, total_nodes, total_tokens)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(hash) DO UPDATE SET
                    total_nodes = MAX(workspaces.total_nodes, excluded.total_nodes),
                    total_tokens = MAX(workspaces.total_tokens, excluded.total_tokens)
            """,
                (ws_hash, ws_name, ws_root, node_count, total_bytes),
            )
            hub_conn.commit()

            old_conn.close()
            migrated += 1
            logger.info(
                f"[VISOR] Migrated: {db_path} → workspace={ws_name} ({node_count} nodes)"
            )

        except Exception as e:
            logger.warning(f"[VISOR] Failed to migrate {db_path}: {e}")
            continue

    return migrated


def _migrate_telemetry(
    old_conn: sqlite3.Connection,
    hub_conn: sqlite3.Connection,
    ws_hash: str,
    ws_name: str,
):
    """Copy telemetry_logs from old DB to hub with workspace context."""
    if not _has_table(old_conn, "telemetry_logs"):
        return

    try:
        rows = old_conn.execute(
            "SELECT tool_name, bytes_transmitted, timestamp FROM telemetry_logs"
        ).fetchall()
    except sqlite3.OperationalError:
        return

    if not rows:
        return

    hub_conn.executemany(
        "INSERT INTO telemetry_logs (workspace_hash, workspace_name, tool_name, bytes_transmitted, timestamp) VALUES (?, ?, ?, ?, ?)",
        [(ws_hash, ws_name, r[0], r[1], r[2]) for r in rows],
    )
    hub_conn.commit()
    logger.info(f"[VISOR]   → Migrated {len(rows)} telemetry records")


def _migrate_skills(old_conn: sqlite3.Connection, hub_conn: sqlite3.Connection):
    """Copy custom_skills from old DB to hub (deduplicate by name)."""
    if not _has_table(old_conn, "custom_skills"):
        return

    existing = {
        r[0].lower()
        for r in hub_conn.execute("SELECT name FROM custom_skills").fetchall()
    }

    try:
        rows = old_conn.execute(
            "SELECT name, description, content, strategy FROM custom_skills"
        ).fetchall()
    except sqlite3.OperationalError:
        return

    inserted = 0
    for name, desc, content, strategy in rows:
        if name.lower() not in existing:
            hub_conn.execute(
                "INSERT INTO custom_skills (name, description, content, strategy) VALUES (?, ?, ?, ?)",
                (name, desc, content, strategy),
            )
            existing.add(name.lower())
            inserted += 1

    if inserted:
        hub_conn.commit()
        logger.info(f"[VISOR]   → Migrated {inserted} custom skills")


def _migrate_memory(
    old_conn: sqlite3.Connection, hub_conn: sqlite3.Connection, ws_hash: str
):
    """Copy agent_memory from old DB to hub with workspace tag."""
    if not _has_table(old_conn, "agent_memory"):
        return

    try:
        rows = old_conn.execute(
            "SELECT role, content, timestamp FROM agent_memory"
        ).fetchall()
    except sqlite3.OperationalError:
        return

    if not rows:
        return

    hub_conn.executemany(
        "INSERT INTO agent_memory (workspace_hash, role, content, timestamp) VALUES (?, ?, ?, ?)",
        [(ws_hash, r[0], r[1], r[2]) for r in rows],
    )
    hub_conn.commit()
    logger.info(f"[VISOR]   → Migrated {len(rows)} agent memory records")


def _migrate_spoke_data(old_conn: sqlite3.Connection, spoke_path: str):
    """Copy code_nodes, edges to a new spoke graph.db.

    We skip vec_code_nodes because the rowids may not align;
    re-indexing will rebuild them.
    """
    import sqlite_vec

    spoke_conn = sqlite3.connect(spoke_path, isolation_level=None)
    spoke_conn.execute("PRAGMA journal_mode=WAL")
    spoke_conn.execute("PRAGMA synchronous=NORMAL")
    spoke_conn.enable_load_extension(True)
    sqlite_vec.load(spoke_conn)
    spoke_conn.enable_load_extension(False)

    from visor.db.client import EMBEDDING_DIM

    # Create spoke tables
    spoke_conn.execute("""
        CREATE TABLE IF NOT EXISTS code_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL, node_type TEXT NOT NULL, name TEXT NOT NULL,
            docstring TEXT, start_line INTEGER, end_line INTEGER, file_hash TEXT
        )
    """)
    spoke_conn.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_node TEXT NOT NULL, to_node TEXT NOT NULL, relation_type TEXT NOT NULL
        )
    """)
    spoke_conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_code_nodes USING vec0(
            embedding float[{EMBEDDING_DIM}]
        )
    """)
    spoke_conn.execute("""
        CREATE TABLE IF NOT EXISTS ui_state (key TEXT PRIMARY KEY, json_value TEXT NOT NULL)
    """)

    # Copy code_nodes (without vectors — re-index will rebuild)
    if _has_table(old_conn, "code_nodes"):
        rows = old_conn.execute(
            "SELECT file_path, node_type, name, docstring, start_line, end_line, file_hash FROM code_nodes"
        ).fetchall()
        if rows:
            spoke_conn.executemany(
                "INSERT INTO code_nodes (file_path, node_type, name, docstring, start_line, end_line, file_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            logger.info(f"[VISOR]   → Migrated {len(rows)} code nodes to spoke")

    # Copy edges
    if _has_table(old_conn, "edges"):
        rows = old_conn.execute(
            "SELECT from_node, to_node, relation_type FROM edges"
        ).fetchall()
        if rows:
            spoke_conn.executemany(
                "INSERT INTO edges (from_node, to_node, relation_type) VALUES (?, ?, ?)",
                rows,
            )
            logger.info(f"[VISOR]   → Migrated {len(rows)} edges to spoke")

    spoke_conn.commit()
    spoke_conn.close()
