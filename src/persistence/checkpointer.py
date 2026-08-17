"""SQLite-based session checkpointer for simulation state persistence.

Persists simulation state per thread_id, enabling follow-up queries
without re-submission of input data. Implements 72h TTL with automatic purge.

Requirements: 8.1, 8.2, 8.3, 8.4
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# Default database path
DEFAULT_DB_PATH = "data/logitax.db"

# Default TTL in hours
DEFAULT_TTL_HOURS = 72


class _DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime and date objects."""

    def default(self, obj: object) -> str:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


class SessionCheckpointer:
    """SQLite checkpointer for persisting simulation session state.

    Stores simulation state (input, results, justification) keyed by thread_id.
    Supports TTL-based expiration and automatic purge of expired sessions.

    Attributes:
        db_path: Path to the SQLite database file.
        ttl_hours: Default TTL for session expiration (hours).
    """

    def __init__(self, db_path: str | None = None, ttl_hours: int = DEFAULT_TTL_HOURS) -> None:
        """Initialize the checkpointer and create the sessions table if needed.

        Args:
            db_path: Path to the SQLite database file. Defaults to data/logitax.db.
            ttl_hours: Default TTL for session state in hours. Defaults to 72.
        """
        self.db_path = db_path or os.getenv("LOGITAX_DB_PATH", DEFAULT_DB_PATH)
        self.ttl_hours = ttl_hours

        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Create table on initialization
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a new database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create the sessions table if it does not exist."""
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    thread_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save(self, thread_id: str, state: dict) -> None:
        """Persist simulation state for a given thread_id.

        If the thread_id already exists, updates the state and updated_at timestamp.
        If new, inserts a fresh record.

        Args:
            thread_id: Unique session identifier.
            state: Dictionary containing simulation state (input, results, justification).
        """
        now = datetime.now(UTC).isoformat()
        state_json = json.dumps(state, cls=_DateTimeEncoder, ensure_ascii=False)

        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO sessions (thread_id, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (thread_id, state_json, now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def load(self, thread_id: str) -> dict | None:
        """Load simulation state by thread_id.

        Args:
            thread_id: Unique session identifier.

        Returns:
            The stored state dictionary, or None if thread_id not found.
        """
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT state_json FROM sessions WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()

            if row is None:
                return None

            return json.loads(row["state_json"])
        finally:
            conn.close()

    def exists(self, thread_id: str) -> bool:
        """Check if a session exists for the given thread_id.

        Args:
            thread_id: Unique session identifier.

        Returns:
            True if the session exists, False otherwise.
        """
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def purge_expired(self, ttl_hours: int | None = None) -> int:
        """Delete sessions older than the specified TTL.

        Purges sessions whose updated_at timestamp is older than
        (now - ttl_hours). This implements automatic session expiration.

        Args:
            ttl_hours: TTL in hours. Defaults to instance ttl_hours (72h).

        Returns:
            Number of sessions deleted.
        """
        hours = ttl_hours if ttl_hours is not None else self.ttl_hours
        cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE updated_at < ?",
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get_or_error(self, thread_id: str) -> dict:
        """Load session state or raise an error for unknown thread_id.

        This implements Requirement 8.3: if a thread_id has no prior simulation
        state, return a structured error requesting full input parameters.

        Args:
            thread_id: Unique session identifier.

        Returns:
            The stored state dictionary.

        Raises:
            ValueError: If no session exists for the given thread_id, with a
                structured error message indicating no previous simulation exists.
        """
        state = self.load(thread_id)
        if state is None:
            raise ValueError(
                f"Nenhuma simulação anterior encontrada para a sessão '{thread_id}'. "
                "Por favor, envie os parâmetros completos da operação de frete."
            )
        return state
