"""Explicit, workspace-scoped retrieval feedback.

Records are local SQLite rows. Ranking may apply one bounded adjustment when
a later query is lexically similar and has the same intent. Feedback never
creates import or call edges.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

FEEDBACK_SIMILARITY_THRESHOLD = 0.6
FEEDBACK_MAX_ADJUSTMENT = 0.35
FEEDBACK_HALF_LIFE_DAYS = 30
FEEDBACK_MAX_INJECTED_NODES = 20

REASON_BOOST = "Boosted by prior developer feedback for a similar query"
REASON_REDUCE = "Reduced by prior developer feedback for a similar query"
VERDICTS = ("useful", "irrelevant", "missing")

_FIELDS = (
    "id",
    "query",
    "query_signature",
    "intent",
    "relative_path",
    "verdict",
    "reason",
    "file_hash",
    "index_revision",
    "created_at",
    "updated_at",
    "application_count",
    "last_applied_at",
)


class FeedbackError(ValueError):
    """Raised when feedback input cannot be stored safely."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def feedback_tokens(query: str) -> list[str]:
    """Match context scoring: lowercase whitespace tokens longer than two characters."""
    return [token.lower() for token in query.split() if len(token) > 2]


def query_signature(query: str) -> str:
    return " ".join(sorted(set(feedback_tokens(query))))


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def decay_factor(updated_at: str, now: datetime | None = None) -> float:
    """Half the weight every FEEDBACK_HALF_LIFE_DAYS. Future timestamps stay at 1."""
    current = now or utcnow()
    updated = datetime.fromisoformat(updated_at)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (current - updated).total_seconds() / 86400)
    return 0.5 ** (age_days / FEEDBACK_HALF_LIFE_DAYS)


def adjustment_for(verdict: str, updated_at: str, now: datetime | None = None) -> float:
    sign = -1.0 if verdict == "irrelevant" else 1.0
    value = sign * FEEDBACK_MAX_ADJUSTMENT * decay_factor(updated_at, now)
    return max(-FEEDBACK_MAX_ADJUSTMENT, min(FEEDBACK_MAX_ADJUSTMENT, value))


def _db():
    from visor.db.client import db_client

    return db_client


def _timestamp(moment: datetime | None = None) -> str:
    current = moment or utcnow()
    return current.isoformat()


def project_relative_file(file_path: str, workspace_root: str | None = None) -> str:
    """Return a project-relative POSIX path, or raise if it is not a workspace file."""
    db = _db()
    root = Path(workspace_root or db.workspace_root).resolve()
    if not str(root):
        raise FeedbackError("Workspace is not configured.")
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise FeedbackError("File does not exist.") from exc
    if not resolved.is_file():
        raise FeedbackError("Not a file.")
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise FeedbackError("File is outside the workspace.") from exc
    if ".." in relative.parts:
        raise FeedbackError("File is outside the workspace.")
    return relative.as_posix()


def _file_hash(relative_path: str) -> str:
    absolute = Path(_db().workspace_root).resolve() / relative_path
    try:
        digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
    except OSError:
        return ""
    return digest


def _row_to_public(row: tuple, similarity: float | None = None) -> dict:
    record = dict(zip(_FIELDS, row, strict=True))
    record["similarity"] = None if similarity is None else round(similarity, 4)
    return record


def _select_row(feedback_id: str) -> tuple | None:
    db = _db()
    return db.spoke_conn.execute(
        """
        SELECT id, query, query_signature, intent, relative_path, verdict, reason,
               file_hash, index_revision, created_at, updated_at,
               application_count, last_applied_at
        FROM context_feedback
        WHERE id = ? AND workspace_hash = ?
        """,
        (feedback_id, db.workspace_hash),
    ).fetchone()


def record_feedback(
    *,
    query: str,
    file_path: str,
    verdict: str,
    reason: str = "",
    intent: str,
) -> dict:
    """Insert or update the one record for this workspace, query signature, and file."""
    if verdict not in VERDICTS:
        raise FeedbackError("Verdict must be useful, irrelevant, or missing.")
    signature = query_signature(query)
    if not signature:
        raise FeedbackError(
            "Query must contain at least one token longer than two characters."
        )
    relative_path = project_relative_file(file_path)
    db = _db()
    if not db.workspace_hash:
        raise FeedbackError("Workspace is not configured.")
    now = _timestamp()
    file_hash = _file_hash(relative_path)
    revision = int(db.graph_revision)
    cleaned_reason = (reason or "").strip()
    existing = db.spoke_conn.execute(
        """
        SELECT id, created_at, application_count, last_applied_at
        FROM context_feedback
        WHERE workspace_hash = ? AND query_signature = ? AND relative_path = ?
        """,
        (db.workspace_hash, signature, relative_path),
    ).fetchone()
    if existing:
        feedback_id, created_at, applications, last_applied = existing
        db.spoke_conn.execute(
            """
            UPDATE context_feedback
            SET query = ?, intent = ?, verdict = ?, reason = ?, file_hash = ?,
                index_revision = ?, updated_at = ?
            WHERE id = ? AND workspace_hash = ?
            """,
            (
                query.strip(),
                intent,
                verdict,
                cleaned_reason,
                file_hash,
                revision,
                now,
                feedback_id,
                db.workspace_hash,
            ),
        )
    else:
        feedback_id = uuid.uuid4().hex
        created_at = now
        applications = 0
        last_applied = None
        db.spoke_conn.execute(
            """
            INSERT INTO context_feedback (
                id, workspace_hash, query, query_signature, intent, relative_path,
                verdict, reason, file_hash, index_revision, created_at, updated_at,
                application_count, last_applied_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                db.workspace_hash,
                query.strip(),
                signature,
                intent,
                relative_path,
                verdict,
                cleaned_reason,
                file_hash,
                revision,
                created_at,
                now,
                applications,
                last_applied,
            ),
        )
    db.spoke_conn.commit()
    row = _select_row(feedback_id)
    if row is None:
        raise FeedbackError("Feedback record could not be stored.")
    return _row_to_public(row)


def list_feedback(query: str | None = None, intent: str | None = None) -> list[dict]:
    """List this workspace's records. A query keeps rows at or above the similarity threshold."""
    db = _db()
    rows = db.spoke_conn.execute(
        """
        SELECT id, query, query_signature, intent, relative_path, verdict, reason,
               file_hash, index_revision, created_at, updated_at,
               application_count, last_applied_at
        FROM context_feedback
        WHERE workspace_hash = ?
        ORDER BY updated_at DESC, relative_path ASC, id ASC
        """,
        (db.workspace_hash,),
    ).fetchall()
    if query is None:
        return [_row_to_public(row) for row in rows]
    tokens = set(feedback_tokens(query))
    selected = []
    for row in rows:
        record = _row_to_public(row)
        similarity = jaccard_similarity(tokens, set(record["query_signature"].split()))
        if similarity < FEEDBACK_SIMILARITY_THRESHOLD:
            continue
        if intent is not None and record["intent"] != intent:
            continue
        record["similarity"] = round(similarity, 4)
        selected.append(record)
    selected.sort(
        key=lambda item: (-item["similarity"], item["relative_path"], item["id"])
    )
    return selected


def delete_feedback(feedback_id: str) -> bool:
    db = _db()
    cursor = db.spoke_conn.execute(
        "DELETE FROM context_feedback WHERE id = ? AND workspace_hash = ?",
        (feedback_id, db.workspace_hash),
    )
    db.spoke_conn.commit()
    return cursor.rowcount > 0


def clear_feedback() -> int:
    db = _db()
    cursor = db.spoke_conn.execute(
        "DELETE FROM context_feedback WHERE workspace_hash = ?",
        (db.workspace_hash,),
    )
    db.spoke_conn.commit()
    return cursor.rowcount


def _absolute_path(relative_path: str) -> Path | None:
    root = Path(_db().workspace_root).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def applicable_feedback(
    query: str, intent: str, now: datetime | None = None
) -> list[dict]:
    """Return the strongest in-workspace record per file for this query and intent."""
    tokens = set(feedback_tokens(query))
    if not tokens:
        return []
    best: dict[str, dict] = {}
    for record in list_feedback():
        if record["intent"] != intent:
            continue
        similarity = jaccard_similarity(tokens, set(record["query_signature"].split()))
        if similarity < FEEDBACK_SIMILARITY_THRESHOLD:
            continue
        absolute = _absolute_path(record["relative_path"])
        if absolute is None:
            continue
        scored = {
            **record,
            "similarity": round(similarity, 4),
            "adjustment": round(
                adjustment_for(record["verdict"], record["updated_at"], now), 4
            ),
            "absolute_path": str(absolute),
        }
        current = best.get(record["relative_path"])
        rank = (similarity, record["updated_at"])
        if current is None or rank > current["_rank"]:
            scored["_rank"] = rank
            best[record["relative_path"]] = scored
    results = list(best.values())
    for item in results:
        item.pop("_rank", None)
    return results


def inject_missing_candidates(
    candidates: list[dict], feedback_rows: list[dict]
) -> list[dict]:
    """Add indexed or synthetic nodes for missing-file feedback that is not already retrieved."""
    present = set()
    for candidate in candidates:
        try:
            present.add(str(Path(candidate["file_path"]).resolve()))
        except OSError:
            present.add(candidate["file_path"])
    injected: list[dict] = []
    db = _db()
    for record in feedback_rows:
        if record["verdict"] != "missing":
            continue
        absolute = record["absolute_path"]
        if absolute in present:
            continue
        rows = db.spoke_conn.execute(
            """
            SELECT id, file_path, node_type, name, docstring, start_line, end_line
            FROM code_nodes
            WHERE file_path = ?
            ORDER BY name ASC, id ASC
            LIMIT ?
            """,
            (absolute, FEEDBACK_MAX_INJECTED_NODES),
        ).fetchall()
        if rows:
            for row in rows:
                injected.append(
                    {
                        "id": row[0],
                        "file_path": row[1],
                        "node_type": row[2],
                        "name": row[3],
                        "docstring": row[4] or "",
                        "start_line": row[5],
                        "end_line": row[6],
                        "retrieval": "lexical",
                    }
                )
        else:
            injected.append(
                {
                    "id": f"feedback:{record['id']}",
                    "file_path": absolute,
                    "node_type": "file",
                    "name": Path(record["relative_path"]).name,
                    "docstring": "",
                    "start_line": 1,
                    "end_line": 1,
                    "retrieval": "lexical",
                }
            )
        present.add(absolute)
    return candidates + injected


def mark_feedback_applied(feedback_ids: list[str], now: datetime | None = None) -> None:
    if not feedback_ids:
        return
    db = _db()
    stamp = _timestamp(now)
    db.spoke_conn.executemany(
        """
        UPDATE context_feedback
        SET application_count = application_count + 1, last_applied_at = ?
        WHERE id = ? AND workspace_hash = ?
        """,
        [(stamp, feedback_id, db.workspace_hash) for feedback_id in feedback_ids],
    )
    db.spoke_conn.commit()
