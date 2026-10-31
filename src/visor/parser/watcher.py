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

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from visor.db.client import db_client
from visor.db.embeddings import embedder
from visor.parser.treesitter import ast_parser, _EXT_MAP

from visor.parser.dependencies import canonical_file, normalize_edges

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
        (file_path, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Index a single file → CodeNodes in DB
# ---------------------------------------------------------------------------


def index_file(file_path: str, skip_changelog: bool = False):
    """Atomically replace one file's symbols, vectors, and dependency edges."""
    file_path = canonical_file(file_path)
    result = ast_parser.parse_file(file_path)
    if result.error:
        raise RuntimeError(f"Parse error for {file_path}: {result.error}")

    if db_client.is_file_index_current(file_path, result.file_hash):
        if not skip_changelog:
            _log_file_change(db_client.conn, file_path)
        logger.debug("Cache hit — skipping %s", file_path)
        return

    nodes = []
    for node in result.nodes:
        vector = embedder.encode(node.docstring if node.docstring else node.name)
        nodes.append(
            {
                "node_type": node.node_type,
                "name": node.name,
                "docstring": node.docstring,
                "vector": vector,
                "start_line": node.start_line,
                "end_line": node.end_line,
            }
        )

    workspace_root = db_client.workspace_root or str(Path(file_path).parent)
    edges = normalize_edges(
        source_file=file_path,
        parser_edges=result.edges,
        workspace_root=workspace_root,
        db_client=db_client,
    )
    db_client.replace_file_index(
        file_path=file_path,
        file_hash=result.file_hash,
        nodes=nodes,
        edges=edges,
    )
    db_client.resolve_call_edges()

    if not skip_changelog:
        _log_file_change(db_client.conn, file_path)
    logger.info(
        "Indexed %s nodes and %s normalized edges from %s",
        len(nodes),
        len(edges),
        file_path,
    )


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
    db_client.mark_indexing()

    # Prune stale changelog entries
    db_client.conn.execute(
        "DELETE FROM file_changelog WHERE datetime(changed_at) < datetime('now', '-300 seconds')"
    )
    db_client.conn.commit()

    root_path = Path(root)
    _IGNORE = {".venv", "__pycache__", "node_modules", ".git", "dist", ".agent"}

    all_files = [
        p
        for p in root_path.rglob("*")
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
    failures = []
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
                    failures.append((futures[future], exc))
                if done % 50 == 0 or done == total:
                    logger.info(f"Workspace scan progress: {done}/{total}")

    if failures:
        raise RuntimeError(
            f"Workspace indexing failed for {len(failures)} file(s); "
            "the previous ready index remains unavailable until a complete scan succeeds."
        )

    indexed_paths = {canonical_file(path) for path in sorted_files}
    db_paths = {
        row[0]
        for row in db_client.conn.execute(
            "SELECT file_path FROM indexed_files"
        ).fetchall()
    }
    stale = db_paths - indexed_paths
    for path in stale:
        db_client.delete_file_index(path)
    if stale:
        logger.info("Purged %s stale file(s) from graph database.", len(stale))

    resolved_calls = db_client.resolve_call_edges()
    if resolved_calls:
        logger.info("Resolved %s internal call edge(s).", resolved_calls)

    db_client.mark_index_ready()
    logger.info("Workspace scan complete and index integrity validated.")


# ---------------------------------------------------------------------------
# Watchdog event handler with debounce
# ---------------------------------------------------------------------------


class _VisorEventHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_debounce_thread()

    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent):
            path = canonical_file(event.src_path)
            if Path(path).suffix.lower() in SUPPORTED_EXTS:
                with self._lock:
                    self._pending[path] = time.monotonic()

    def on_created(self, event):
        if isinstance(event, FileCreatedEvent):
            path = canonical_file(event.src_path)
            if Path(path).suffix.lower() in SUPPORTED_EXTS:
                with self._lock:
                    self._pending[path] = time.monotonic()

    def on_deleted(self, event):
        if isinstance(event, FileDeletedEvent):
            path = canonical_file(event.src_path)
            if Path(path).suffix.lower() in SUPPORTED_EXTS:
                db_client.delete_file_index(path)
                _log_file_change(db_client.conn, path)

    def on_moved(self, event):
        if isinstance(event, FileMovedEvent):
            source = canonical_file(event.src_path)
            destination = canonical_file(event.dest_path)
            if Path(source).suffix.lower() in SUPPORTED_EXTS:
                db_client.delete_file_index(source)
                _log_file_change(db_client.conn, source)
            if Path(destination).suffix.lower() in SUPPORTED_EXTS:
                with self._lock:
                    self._pending[destination] = time.monotonic()

    def _start_debounce_thread(self):
        def flush():
            while not self._stop_event.wait(0.1):
                now = time.monotonic()
                with self._lock:
                    ready = [
                        path
                        for path, changed_at in self._pending.items()
                        if now - changed_at >= DEBOUNCE_SECONDS
                    ]
                    for path in ready:
                        del self._pending[path]
                for path in ready:
                    logger.info("[watcher] Re-indexing changed file: %s", path)
                    try:
                        index_file(path)
                    except Exception:
                        logger.exception("[watcher] Failed to re-index %s", path)

        thread = threading.Thread(target=flush, daemon=True)
        self._thread = thread
        thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_observer: Optional[Observer] = None
_event_handler: Optional[_VisorEventHandler] = None
_watched_root: Optional[str] = None


def start_watcher(workspace_root: str):
    """Start the background file watcher on the given workspace root."""
    global _observer, _event_handler, _watched_root
    workspace_root = str(Path(workspace_root).resolve())
    if _observer and _observer.is_alive() and _watched_root == workspace_root:
        return
    stop_watcher()
    _ensure_changelog(db_client.conn)
    _event_handler = _VisorEventHandler()
    _observer = Observer()
    _observer.schedule(_event_handler, workspace_root, recursive=True)
    _observer.daemon = True
    _observer.start()
    _watched_root = workspace_root
    logger.info(f"File watcher started on: {workspace_root}")


def stop_watcher():
    global _observer, _event_handler, _watched_root
    if _observer:
        _observer.stop()
        _observer.join()
        logger.info("File watcher stopped.")
    if _event_handler:
        _event_handler.stop()
    _observer = None
    _event_handler = None
    _watched_root = None
