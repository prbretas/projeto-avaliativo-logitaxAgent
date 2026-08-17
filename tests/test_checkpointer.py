"""Tests for the SessionCheckpointer (SQLite session persistence).

Validates:
- State persistence and retrieval by thread_id (round-trip)
- TTL-based purge of expired sessions
- Structured error for unknown thread_id
- Follow-up query retrieves most recent results

Requirements: 8.1, 8.2, 8.3, 8.4
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, date, datetime, timedelta

import pytest

from src.persistence.checkpointer import SessionCheckpointer


@pytest.fixture
def tmp_db_path():
    """Provide a temporary database path for isolated test runs."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def checkpointer(tmp_db_path):
    """Provide a fresh SessionCheckpointer instance with a temp database."""
    return SessionCheckpointer(db_path=tmp_db_path)


@pytest.fixture
def sample_state():
    """Return a sample simulation state dict."""
    return {
        "operacao": {
            "modal": "rodoviario",
            "origem_uf": "SP",
            "destino_uf": "RJ",
            "regime_tributario": "lucro_real",
            "valor_frete": 10000.00,
            "data_referencia": "2026-06-15",
        },
        "resultados_por_ano": [
            {
                "ano": 2026,
                "valor_tributo_atual": 2125.00,
                "valor_tributo_novo": 100.00,
                "delta_percentual": -95.29,
                "fonte_tool": "tabela_local_v1",
                "fallback_usado": False,
            }
        ],
        "justificativa": "Com base no art. 343 da LC 214/2025, a alíquota-teste de 1%...",
        "thread_id": "thread-test-001",
    }


class TestSessionCheckpointerSaveAndLoad:
    """Tests for save/load round-trip (Requirement 8.1, 8.2)."""

    def test_save_and_load_basic(self, checkpointer, sample_state):
        """Saved state should be retrievable by the same thread_id."""
        thread_id = "thread-round-trip-001"
        checkpointer.save(thread_id, sample_state)

        loaded = checkpointer.load(thread_id)
        assert loaded is not None
        assert loaded == sample_state

    def test_save_overwrites_existing(self, checkpointer, sample_state):
        """Saving with the same thread_id should update the state."""
        thread_id = "thread-overwrite-001"
        checkpointer.save(thread_id, sample_state)

        updated_state = {**sample_state, "justificativa": "Justificativa atualizada"}
        checkpointer.save(thread_id, updated_state)

        loaded = checkpointer.load(thread_id)
        assert loaded is not None
        assert loaded["justificativa"] == "Justificativa atualizada"

    def test_load_nonexistent_returns_none(self, checkpointer):
        """Loading a non-existent thread_id should return None."""
        result = checkpointer.load("thread-nao-existe-999")
        assert result is None

    def test_save_with_datetime_objects(self, checkpointer):
        """State containing datetime objects should serialize correctly."""
        state = {
            "operacao": {"data_referencia": date(2026, 6, 15)},
            "timestamp": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        }
        thread_id = "thread-datetime-001"
        checkpointer.save(thread_id, state)

        loaded = checkpointer.load(thread_id)
        assert loaded is not None
        # Dates are serialized as ISO strings
        assert loaded["operacao"]["data_referencia"] == "2026-06-15"
        assert "2026-01-01" in loaded["timestamp"]

    def test_save_preserves_all_fields(self, checkpointer, sample_state):
        """All fields of the state dict should be preserved after round-trip."""
        thread_id = "thread-fields-001"
        checkpointer.save(thread_id, sample_state)

        loaded = checkpointer.load(thread_id)
        assert loaded["operacao"]["modal"] == "rodoviario"
        assert loaded["operacao"]["valor_frete"] == 10000.00
        assert loaded["resultados_por_ano"][0]["delta_percentual"] == -95.29
        assert loaded["resultados_por_ano"][0]["fonte_tool"] == "tabela_local_v1"
        assert loaded["resultados_por_ano"][0]["fallback_usado"] is False
        assert "art. 343" in loaded["justificativa"]

    def test_multiple_threads_independent(self, checkpointer, sample_state):
        """Multiple threads should store and retrieve independent states."""
        state_a = {**sample_state, "thread_id": "thread-a"}
        state_b = {**sample_state, "thread_id": "thread-b", "justificativa": "Outra"}

        checkpointer.save("thread-a", state_a)
        checkpointer.save("thread-b", state_b)

        loaded_a = checkpointer.load("thread-a")
        loaded_b = checkpointer.load("thread-b")

        assert loaded_a["thread_id"] == "thread-a"
        assert loaded_b["thread_id"] == "thread-b"
        assert loaded_b["justificativa"] == "Outra"


class TestSessionCheckpointerExists:
    """Tests for the exists() method."""

    def test_exists_returns_true_for_saved(self, checkpointer, sample_state):
        """exists() should return True for a saved thread_id."""
        checkpointer.save("thread-exists-001", sample_state)
        assert checkpointer.exists("thread-exists-001") is True

    def test_exists_returns_false_for_unknown(self, checkpointer):
        """exists() should return False for an unknown thread_id."""
        assert checkpointer.exists("thread-nao-existe") is False


class TestSessionCheckpointerPurge:
    """Tests for TTL-based purge (Requirement 8.4)."""

    def test_purge_removes_expired_sessions(self, tmp_db_path, sample_state):
        """Sessions older than TTL should be purged."""
        import sqlite3

        checkpointer = SessionCheckpointer(db_path=tmp_db_path, ttl_hours=72)

        # Save a session
        checkpointer.save("thread-old", sample_state)

        # Manually backdate the updated_at to simulate expiration
        old_time = (datetime.now(UTC) - timedelta(hours=73)).isoformat()
        conn = sqlite3.connect(tmp_db_path)
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE thread_id = ?",
            (old_time, "thread-old"),
        )
        conn.commit()
        conn.close()

        # Purge should remove the expired session
        deleted = checkpointer.purge_expired()
        assert deleted == 1
        assert checkpointer.load("thread-old") is None

    def test_purge_keeps_recent_sessions(self, checkpointer, sample_state):
        """Sessions within TTL should NOT be purged."""
        checkpointer.save("thread-recent", sample_state)

        deleted = checkpointer.purge_expired()
        assert deleted == 0
        assert checkpointer.load("thread-recent") is not None

    def test_purge_custom_ttl(self, tmp_db_path, sample_state):
        """Custom TTL parameter should override default."""
        import sqlite3

        checkpointer = SessionCheckpointer(db_path=tmp_db_path, ttl_hours=72)
        checkpointer.save("thread-custom-ttl", sample_state)

        # Backdate to 2 hours ago
        old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        conn = sqlite3.connect(tmp_db_path)
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE thread_id = ?",
            (old_time, "thread-custom-ttl"),
        )
        conn.commit()
        conn.close()

        # With default 72h TTL, session should NOT be purged
        deleted_default = checkpointer.purge_expired()
        assert deleted_default == 0

        # With custom 1h TTL, session SHOULD be purged
        deleted_custom = checkpointer.purge_expired(ttl_hours=1)
        assert deleted_custom == 1

    def test_purge_returns_count(self, tmp_db_path, sample_state):
        """purge_expired should return the exact count of deleted sessions."""
        import sqlite3

        checkpointer = SessionCheckpointer(db_path=tmp_db_path, ttl_hours=72)

        # Save multiple sessions and backdate them
        for i in range(5):
            checkpointer.save(f"thread-expired-{i}", sample_state)

        old_time = (datetime.now(UTC) - timedelta(hours=100)).isoformat()
        conn = sqlite3.connect(tmp_db_path)
        conn.execute("UPDATE sessions SET updated_at = ?", (old_time,))
        conn.commit()
        conn.close()

        deleted = checkpointer.purge_expired()
        assert deleted == 5


class TestSessionCheckpointerGetOrError:
    """Tests for get_or_error (Requirement 8.3)."""

    def test_get_or_error_returns_state_when_exists(self, checkpointer, sample_state):
        """get_or_error should return state when thread_id exists."""
        checkpointer.save("thread-exists-002", sample_state)

        result = checkpointer.get_or_error("thread-exists-002")
        assert result == sample_state

    def test_get_or_error_raises_for_unknown_thread(self, checkpointer):
        """get_or_error should raise ValueError for unknown thread_id."""
        with pytest.raises(ValueError) as exc_info:
            checkpointer.get_or_error("thread-inexistente-xyz")

        error_msg = str(exc_info.value)
        assert "thread-inexistente-xyz" in error_msg
        assert "Nenhuma simulação anterior encontrada" in error_msg
        assert "parâmetros completos" in error_msg

    def test_get_or_error_message_is_structured(self, checkpointer):
        """Error message should contain thread_id and request for full input."""
        with pytest.raises(ValueError) as exc_info:
            checkpointer.get_or_error("unknown-thread-42")

        error_msg = str(exc_info.value)
        # Must contain the thread_id for context
        assert "unknown-thread-42" in error_msg
        # Must request full parameters
        assert "parâmetros completos" in error_msg


class TestSessionCheckpointerInitialization:
    """Tests for initialization and directory creation."""

    def test_creates_directory_if_missing(self, tmp_path):
        """Should create the database directory if it does not exist."""
        db_path = str(tmp_path / "subdir" / "nested" / "test.db")
        checkpointer = SessionCheckpointer(db_path=db_path)

        # Directory should now exist
        assert os.path.isdir(os.path.dirname(db_path))

        # Should be able to save/load without error
        checkpointer.save("thread-init-test", {"key": "value"})
        assert checkpointer.load("thread-init-test") == {"key": "value"}

    def test_table_created_on_init(self, tmp_db_path):
        """The sessions table should be created during initialization."""
        import sqlite3

        SessionCheckpointer(db_path=tmp_db_path)

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "sessions"
