"""
Incremental File Watcher for V.I.S.O.R.
Listens for file saves and Git commits, re-parses only changed files,
and writes updated CodeNodes to the local vector DB.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from visor.db.client import db_client
from visor.db.embeddings import embedder
from visor.parser.treesitter import ast_parser, _EXT_MAP

logger = logging.getLogger(__name__)

SUPPORTED_EXTS: Set[str] = set(_EXT_MAP.keys())
DEBOUNCE_SECONDS = 0.3
INDEX_WORKERS = 4  # Parallel threads for workspace scan

# ---------------------------------------------------------------------------
# FileChangelog table (created alongside CodeNodes)
# ---------------------------------------------------------------------------

def _ensure_changelog(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_changelog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            changed_at TEXT NOT NULL
        )
    """)
    conn.commit()

def _log_file_change(conn: sqlite3.Connection, file_path: str):
    conn.execute(
        "INSERT INTO file_changelog (file_path, changed_at) VALUES (?, ?)",
        (file_path, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()

# ---------------------------------------------------------------------------
# Index a single file → CodeNodes in DB
# ---------------------------------------------------------------------------

def index_file(file_path: str, skip_changelog: bool = False):
    """Parse a file and batch-upsert all its AST nodes into the vector DB.

    Uses ``batch_upsert_nodes`` to flush all nodes in a single SQLite
    transaction, which is significantly faster than node-by-node commits.

    Args:
        file_path:      Path to the source file to index.
        skip_changelog: If True, do NOT write to file_changelog.
                        Used during boot-time workspace scans to avoid
                        triggering false drift alerts on every restart.
    """
    result = ast_parser.parse_file(file_path)
    if result.error:
        logger.warning(f"Parse error for {file_path}: {result.error}")
        return

    # Cache check — skip if file content is unchanged
    cursor = db_client.conn.cursor()
    cursor.execute("SELECT file_hash FROM code_nodes WHERE file_path=? LIMIT 1", (file_path,))
    row = cursor.fetchone()
    if row and row[0] == result.file_hash:
        if not skip_changelog:
            _log_file_change(db_client.conn, file_path)
        logger.debug(f"Cache hit — skipping {file_path}")
        return

    if not result.nodes:
        return

    # Build batch payload: encode embeddings for all nodes
    batch = []
    for node in result.nodes:
        vec = embedder.encode(node.docstring if node.docstring else node.name)
        batch.append({
            "file_path":  node.file_path,
            "node_type":  node.node_type,
            "name":       node.name,
            "docstring":  node.docstring,
            "vector":     vec,
            "start_line": node.start_line,
            "end_line":   node.end_line,
            "file_hash":  result.file_hash,
        })

    # Single-transaction batch write
    db_client.batch_upsert_nodes(batch)

    # Edge writes (separate — edges table has no vec table to batch)
    for edge in result.edges:
        db_client.upsert_edge(
            from_node=edge["from"],
            to_node=edge["to"],
            relation_type=edge["type"]
        )

    if not skip_changelog:
        _log_file_change(db_client.conn, file_path)
    logger.info(f"Indexed {len(result.nodes)} nodes & {len(result.edges)} edges from {file_path}")

# ---------------------------------------------------------------------------
# Full workspace scan (run once on daemon start)
# ---------------------------------------------------------------------------

def index_workspace(root: str, open_files: Optional[list] = None):
    """Walk the workspace tree and index all supported source files.

    Uses a **progressive priority order**:
    1. ``open_files`` (if provided) — currently open editor tabs, indexed first
       so the agent has context immediately.
    2. Recently modified files (mtime in the last 10 minutes).
    3. Remaining files, indexed in parallel via a ``ThreadPoolExecutor``.

    This boot-time scan does NOT write to ``file_changelog`` so the drift
    alert won't fire on every daemon restart. Old changelog entries
    (> 5 min) are also pruned to keep the table lean.

    Args:
        root:       Workspace root directory to scan.
        open_files: Optional list of currently-open file paths to index first.
    """
    _ensure_changelog(db_client.conn)

    # Prune stale changelog entries
    db_client.conn.execute(
        "DELETE FROM file_changelog WHERE datetime(changed_at) < datetime('now', '-300 seconds')"
    )
    db_client.conn.commit()

    root_path = Path(root)
    _IGNORE = {".venv", "__pycache__", "node_modules", ".git", "dist", ".agent"}

    all_files = [
        p for p in root_path.rglob("*")
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXTS
        and not any(part in _IGNORE for part in p.parts)
    ]

    now = time.time()

    def _priority(p: Path) -> int:
        """Lower = higher priority. 0=open, 1=recent, 2=rest."""
        if open_files and str(p) in open_files:
            return 0
        if (now - p.stat().st_mtime) < 600:  # modified in last 10 min
            return 1
        return 2

    sorted_files = sorted(all_files, key=_priority)
    logger.info(f"Progressive workspace scan: {len(sorted_files)} files (root={root})")

    # Phase 1: index open + recent files synchronously (instant context)
    priority_files = [f for f in sorted_files if _priority(f) < 2]
    for f in priority_files:
        index_file(str(f), skip_changelog=True)

    # Phase 2: index the rest in parallel
    rest = [f for f in sorted_files if _priority(f) == 2]
    if rest:
        with ThreadPoolExecutor(max_workers=INDEX_WORKERS) as pool:
            futures = {pool.submit(index_file, str(f), True): f for f in rest}
            done, total = 0, len(rest)
            for future in as_completed(futures):
                done += 1
                try:
                    future.result()
                except Exception as exc:
                    logger.warning(f"Index error for {futures[future]}: {exc}")
                if done % 50 == 0 or done == total:
                    logger.info(f"Workspace scan progress: {done}/{total}")

    logger.info("Workspace scan complete.")

# ---------------------------------------------------------------------------
# Watchdog event handler with debounce
# ---------------------------------------------------------------------------

class _VisorEventHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._start_debounce_thread()

    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent):
            path = event.src_path
            if Path(path).suffix.lower() in SUPPORTED_EXTS:
                with self._lock:
                    self._pending[path] = time.monotonic()

    def _start_debounce_thread(self):
        def flush():
            while True:
                time.sleep(0.1)
                now = time.monotonic()
                with self._lock:
                    ready = [p for p, t in self._pending.items() if now - t >= DEBOUNCE_SECONDS]
                    for p in ready:
                        del self._pending[p]
                for p in ready:
                    logger.info(f"[watcher] Re-indexing changed file: {p}")
                    index_file(p)

        t = threading.Thread(target=flush, daemon=True)
        t.start()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_observer: Optional[Observer] = None

def start_watcher(workspace_root: str):
    """Start the background file watcher on the given workspace root."""
    global _observer
    _ensure_changelog(db_client.conn)
    handler = _VisorEventHandler()
    _observer = Observer()
    _observer.schedule(handler, workspace_root, recursive=True)
    _observer.daemon = True
    _observer.start()
    logger.info(f"File watcher started on: {workspace_root}")

def stop_watcher():
    global _observer
    if _observer:
        _observer.stop()
        _observer.join()
        logger.info("File watcher stopped.")
