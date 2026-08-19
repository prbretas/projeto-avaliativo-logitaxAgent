"""Sistema de logs estruturados — observabilidade do LogitaxAgent.

Emite JSON logs por node com: thread_id, node_name, timestamp ISO 8601,
duration_ms, status.

Implementa tabela de auditoria SQLite para: decisões humanas, eventos
de segurança, fallback.

Registra erros com tipo e ação de recovery (retry, fallback, escalation).

Requirements: 11.1, 11.2, 11.3
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# --- Structured JSON Logger ---

SQLITE_PATH = os.environ.get("SQLITE_PATH", "./data/auditoria.db")


class StructuredLogFormatter(logging.Formatter):
    """JSON formatter for structured log output."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add extra structured fields if present
        if hasattr(record, "thread_id"):
            log_entry["thread_id"] = record.thread_id
        if hasattr(record, "node_name"):
            log_entry["node_name"] = record.node_name
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "status"):
            log_entry["status"] = record.status

        return json.dumps(log_entry, ensure_ascii=False)


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with structured JSON output."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredLogFormatter())
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


# --- Node Execution Logger ---


class NodeLogger:
    """Context-based logger for LangGraph node execution.

    Tracks execution time and emits structured logs with required fields:
    thread_id, node_name, timestamp, duration_ms, status.
    """

    def __init__(self, thread_id: str, node_name: str):
        self.thread_id = thread_id
        self.node_name = node_name
        self.logger = logging.getLogger(f"node.{node_name}")
        self._start_time: float | None = None

    @contextmanager
    def track_execution(self) -> Generator[None, None, None]:
        """Context manager that tracks execution time and logs result."""
        self._start_time = time.perf_counter()
        datetime.now(UTC).isoformat()

        self.logger.info(
            "Node execution started",
            extra={
                "thread_id": self.thread_id,
                "node_name": self.node_name,
                "status": "started",
                "duration_ms": 0,
            },
        )

        try:
            yield
            duration_ms = (time.perf_counter() - self._start_time) * 1000
            self.logger.info(
                "Node execution completed",
                extra={
                    "thread_id": self.thread_id,
                    "node_name": self.node_name,
                    "status": "success",
                    "duration_ms": round(duration_ms, 2),
                },
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - self._start_time) * 1000
            self.logger.error(
                f"Node execution failed: {e}",
                extra={
                    "thread_id": self.thread_id,
                    "node_name": self.node_name,
                    "status": "error",
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise

    def log_event(
        self,
        event_type: str,
        message: str,
        **extra: Any,
    ) -> None:
        """Log a structured event within a node execution."""
        self.logger.info(
            message,
            extra={
                "thread_id": self.thread_id,
                "node_name": self.node_name,
                "event_type": event_type,
                "status": "event",
                "duration_ms": 0,
                **extra,
            },
        )


# --- Audit Trail (SQLite) ---


def _get_db_path() -> str:
    """Get SQLite database path."""
    return os.environ.get("SQLITE_PATH", SQLITE_PATH)


def _init_audit_table(conn: sqlite3.Connection) -> None:
    """Create the audit table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            node_name TEXT,
            timestamp TEXT NOT NULL,
            duration_ms REAL DEFAULT 0,
            status TEXT NOT NULL,
            details TEXT,
            recovery_action TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_auditoria_thread_id
        ON auditoria(thread_id)
    """)
    conn.commit()


def get_audit_connection() -> sqlite3.Connection:
    """Get a connection to the audit SQLite database."""
    db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _init_audit_table(conn)
    return conn


def log_audit_event(
    thread_id: str,
    event_type: str,
    node_name: str | None = None,
    status: str = "info",
    details: str | None = None,
    recovery_action: str | None = None,
    duration_ms: float = 0,
) -> None:
    """Record an audit event in the SQLite audit table.

    Event types:
    - "decisao_humana": Human review decisions (approve/reject)
    - "seguranca": Security events (prompt injection detected)
    - "fallback": Fallback events (tool unavailable)
    - "erro": Error events with recovery actions
    - "integridade": Rate validation mismatches
    - "webhook": Webhook delivery events

    Args:
        thread_id: Session/thread identifier.
        event_type: Category of the event.
        node_name: Which node generated the event.
        status: Event status (info, warning, error, critical).
        details: Additional details about the event.
        recovery_action: Action taken (retry, fallback, escalation).
        duration_ms: Duration in milliseconds.
    """
    timestamp = datetime.now(UTC).isoformat()

    try:
        conn = get_audit_connection()
        conn.execute(
            """
            INSERT INTO auditoria
                (thread_id, event_type, node_name, timestamp, duration_ms,
                 status, details, recovery_action)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                event_type,
                node_name,
                timestamp,
                duration_ms,
                status,
                details,
                recovery_action,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.getLogger(__name__).error("Falha ao gravar evento de auditoria: %s", e)


def get_audit_timeline(thread_id: str) -> list[dict[str, Any]]:
    """Retrieve the complete audit timeline for a thread_id.

    Args:
        thread_id: Session/thread identifier.

    Returns:
        List of audit events ordered chronologically.
    """
    try:
        conn = get_audit_connection()
        cursor = conn.execute(
            """
            SELECT thread_id, event_type, node_name, timestamp,
                   duration_ms, status, details, recovery_action
            FROM auditoria
            WHERE thread_id = ?
            ORDER BY timestamp ASC
            """,
            (thread_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "thread_id": row["thread_id"],
                "event_type": row["event_type"],
                "node_name": row["node_name"],
                "timestamp": row["timestamp"],
                "duration_ms": row["duration_ms"],
                "status": row["status"],
                "details": row["details"],
                "recovery_action": row["recovery_action"],
            }
            for row in rows
        ]
    except Exception as e:
        logging.getLogger(__name__).error("Falha ao recuperar timeline de auditoria: %s", e)
        return []
