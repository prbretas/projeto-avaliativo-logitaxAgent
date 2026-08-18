"""Property tests para human review.

Property 16: No export without human approval.
Property 17: Pending review retrieval is idempotent.

Validates: Requirements 10.4, 10.6
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.graph.nodes.export_result import export_result
from src.graph.nodes.human_review import get_review_summary


# --- Property 16: No export without human approval ---


@given(
    aprovado=st.sampled_from([None, False]),
    thread_id=st.uuids().map(str),
)
@settings(max_examples=20)
def test_no_export_without_human_approval(aprovado, thread_id):
    """Property 16: export_result never executes without aprovado_humano=True."""
    state = {
        "thread_id": thread_id,
        "aprovado_humano": aprovado,
        "resultados_por_ano": [
            {"ano": 2026, "valor_tributo_atual": 2125.0, "valor_tributo_novo": 100.0, "delta_percentual": -95.0}
        ],
        "operacao": {"modal": "rodoviario", "valor_frete": 10000.0},
        "justificativa": "Test",
        "trechos_rag": [],
        "alertas": [],
    }

    result = export_result(state)
    assert result["export_status"] == "blocked", (
        f"Export should be blocked when aprovado_humano={aprovado}, "
        f"got status={result['export_status']}"
    )


@given(thread_id=st.uuids().map(str))
@settings(max_examples=10)
def test_export_allowed_with_approval(thread_id):
    """Property 16b: export proceeds when aprovado_humano=True."""
    state = {
        "thread_id": thread_id,
        "aprovado_humano": True,
        "resultados_por_ano": [
            {"ano": 2026, "valor_tributo_atual": 2125.0, "valor_tributo_novo": 100.0, "delta_percentual": -95.0}
        ],
        "operacao": {"modal": "rodoviario", "valor_frete": 10000.0},
        "justificativa": "Approved test",
        "trechos_rag": [],
        "alertas": [],
    }

    result = export_result(state)
    assert result["export_status"] == "completed", (
        f"Export should succeed with aprovado_humano=True, got {result['export_status']}"
    )


# --- Property 17: Pending review retrieval is idempotent ---


@given(
    thread_id=st.uuids().map(str),
    num_calls=st.integers(min_value=2, max_value=5),
)
@settings(max_examples=20)
def test_pending_review_retrieval_idempotent(thread_id, num_calls):
    """Property 17: Multiple calls to get_review_summary don't alter state."""
    state = {
        "thread_id": thread_id,
        "operacao": {
            "modal": "rodoviario",
            "origem_uf": "SP",
            "destino_uf": "RJ",
            "regime_tributario": "lucro_real",
            "valor_frete": 10000.0,
        },
        "resultados_por_ano": [
            {"ano": 2026, "delta_percentual": -50.0}
        ],
        "justificativa": "Pending review",
        "alertas": [],
    }

    # Call multiple times
    results = [get_review_summary(state) for _ in range(num_calls)]

    # All results should be structurally equal
    for i in range(1, len(results)):
        assert results[i]["thread_id"] == results[0]["thread_id"]
        assert results[i]["operacao"] == results[0]["operacao"]
        assert results[i]["resultados_por_ano"] == results[0]["resultados_por_ano"]

    # Original state should not be modified
    assert state["thread_id"] == thread_id
    assert len(state["resultados_por_ano"]) == 1
