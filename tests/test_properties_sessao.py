"""Property tests para sessão/checkpointer.

Property 12: Session state round-trip.
Property 13: Unknown thread_id returns error.

Validates: Requirements 8.1, 8.2, 8.3
"""

import os
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from src.persistence.checkpointer import SessionCheckpointer


# --- Property 12: Session state round-trip ---


@given(
    thread_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))),
    valor_frete=st.floats(min_value=0.01, max_value=1_000_000, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=30)
def test_session_state_round_trip(thread_id, valor_frete):
    """Property 12: State persisted and retrieved is identical to original."""
    db_path = os.path.join(tempfile.gettempdir(), f"test_checkpointer_{os.getpid()}.db")

    try:
        checkpointer = SessionCheckpointer(db_path=db_path)

        state = {
            "thread_id": thread_id,
            "operacao": {"valor_frete": valor_frete, "modal": "rodoviario"},
            "resultados_por_ano": [{"ano": 2026, "valor": valor_frete * 0.2125}],
            "justificativa": f"Teste {thread_id}",
        }

        # Persist
        checkpointer.save(thread_id, state)

        # Retrieve
        retrieved = checkpointer.load(thread_id)

        # Verify round-trip
        assert retrieved is not None, f"State not found for thread_id={thread_id}"
        assert retrieved["thread_id"] == thread_id
        assert retrieved["operacao"]["valor_frete"] == valor_frete
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


# --- Property 13: Unknown thread_id returns error ---


@given(thread_id=st.uuids().map(str))
@settings(max_examples=20)
def test_unknown_thread_id_returns_none(thread_id):
    """Property 13: Unknown thread_id returns None (error state)."""
    db_path = os.path.join(tempfile.gettempdir(), f"test_checkpointer_unknown_{os.getpid()}.db")

    try:
        checkpointer = SessionCheckpointer(db_path=db_path)

        # Query unknown thread_id
        result = checkpointer.load(thread_id)

        assert result is None, f"Should return None for unknown thread_id={thread_id}"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
