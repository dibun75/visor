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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from visor.db.client import db_client
from visor.parser.treesitter import ast_parser, _EXT_MAP

logger = logging.getLogger(__name__)

SUPPORTED_EXTS: Set[str] = set(_EXT_MAP.keys())
DEBOUNCE_SECONDS = 0.3

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
    """Parse a file and upsert all its AST nodes into the vector DB.
    
    Args:
        file_path: Path to the source file to index.
        skip_changelog: If True, do NOT log to file_changelog.
                        Used during the initial full workspace scan
                        so boot-time indexing doesn't trigger false drift alerts.
    """
    import numpy as np
    from visor.db.client import EMBEDDING_DIM

    result = ast_parser.parse_file(file_path)
    if result.error:
        logger.warning(f"Parse error for {file_path}: {result.error}")
        return

    for node in result.nodes:
        # Placeholder embedding — replaced with real sentence-transformer in Epic 3+
        vec = list(map(float, __import__('numpy').random.rand(EMBEDDING_DIM)))
        db_client.upsert_node(
            file_path=node.file_path,
            node_type=node.node_type,
            name=node.name,
            docstring=node.docstring,
            vector=vec,
        )

    if not skip_changelog:
        _log_file_change(db_client.conn, file_path)
    logger.info(f"Indexed {len(result.nodes)} nodes from {file_path}")

# ---------------------------------------------------------------------------
# Full workspace scan (run once on daemon start)
# ---------------------------------------------------------------------------

def index_workspace(root: str):
    """Walk the workspace tree and index every supported source file.
    
    This is the boot-time full scan. It does NOT log to file_changelog
    so the drift alert won't fire on every daemon restart.
    Old changelog entries (> 5 min) are pruned to keep the table lean.
    """
    _ensure_changelog(db_client.conn)
    
    # Prune stale changelog entries older than 5 minutes
    db_client.conn.execute(
        "DELETE FROM file_changelog WHERE datetime(changed_at) < datetime('now', '-300 seconds')"
    )
    db_client.conn.commit()
    
    root_path = Path(root)
    files = [
        str(p) for p in root_path.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        and ".venv" not in str(p)
        and "__pycache__" not in str(p)
        and "node_modules" not in str(p)
    ]
    logger.info(f"Full workspace scan: {len(files)} files found in {root}")
    for f in files:
        index_file(f, skip_changelog=True)
    logger.info("Full workspace scan complete.")

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
