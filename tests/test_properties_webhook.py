"""Property tests para webhook.

Property 19: Webhook payload contains required fields.

Validates: Requirements 14.1
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.graph.nodes.export_result import _build_webhook_payload


# --- Property 19: Webhook payload contains required fields ---


@given(
    thread_id=st.uuids().map(str),
    valor_frete=st.floats(min_value=100, max_value=1_000_000, allow_nan=False, allow_infinity=False),
    ano=st.sampled_from([2026, 2027, 2030, 2033]),
)
@settings(max_examples=50)
def test_webhook_payload_contains_required_fields(thread_id, valor_frete, ano):
    """Property 19: Payload contains Thread_Id, Delta_Percentual, ano, valor_tributo_atual, valor_tributo_novo, timestamp."""
    tributo_atual = round(valor_frete * 0.2125, 2)
    tributo_novo = round(valor_frete * 0.10, 2)
    delta = round(((tributo_novo - tributo_atual) / tributo_atual) * 100, 2)

    state = {
        "thread_id": thread_id,
        "resultados_por_ano": [
            {
                "ano": ano,
                "valor_tributo_atual": tributo_atual,
                "valor_tributo_novo": tributo_novo,
                "delta_percentual": delta,
            }
        ],
    }

    payload = _build_webhook_payload(state)

    # Verify required fields
    assert "thread_id" in payload, "Missing thread_id"
    assert payload["thread_id"] == thread_id
    assert "delta_percentual" in payload, "Missing delta_percentual"
    assert "timestamp" in payload, "Missing timestamp"
    assert "resultados_por_ano" in payload, "Missing resultados_por_ano"

    # Verify per-year fields
    assert len(payload["resultados_por_ano"]) >= 1
    resultado = payload["resultados_por_ano"][0]
    assert "ano" in resultado, "Missing ano in resultado"
    assert "valor_tributo_atual" in resultado, "Missing valor_tributo_atual"
    assert "valor_tributo_novo" in resultado, "Missing valor_tributo_novo"
    assert "delta_percentual" in resultado, "Missing delta_percentual"

    # Verify timestamp is ISO format
    assert "T" in payload["timestamp"], "Timestamp not ISO 8601"
