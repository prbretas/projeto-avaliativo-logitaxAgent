"""Property tests para Tool_Transicao.

Property 8: Tool validation rejects invalid parameters.

Validates: Requirements 5.2, 5.3, 5.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from fastapi.testclient import TestClient

from src.tools.tabela_transicao import router
from fastapi import FastAPI

# Create test app with tool router
test_app = FastAPI()
test_app.include_router(router)
client = TestClient(test_app)


# --- Property 8: Tool validation rejects invalid parameters ---


@given(ano=st.integers(min_value=-1000, max_value=2025))
@settings(max_examples=30)
def test_invalid_year_below_range_rejected(ano):
    """Property 8a: Year below 2026 returns HTTP 422."""
    response = client.get(
        "/tools/tabela-transicao",
        params={"ano": ano, "uf_origem": "SP", "uf_destino": "RJ", "regime": "lucro_real"},
    )
    assert response.status_code == 422, f"Year {ano} should be rejected, got {response.status_code}"


@given(ano=st.integers(min_value=2034, max_value=3000))
@settings(max_examples=30)
def test_invalid_year_above_range_rejected(ano):
    """Property 8b: Year above 2033 returns HTTP 422."""
    response = client.get(
        "/tools/tabela-transicao",
        params={"ano": ano, "uf_origem": "SP", "uf_destino": "RJ", "regime": "lucro_real"},
    )
    assert response.status_code == 422, f"Year {ano} should be rejected, got {response.status_code}"


@given(
    uf=st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=("Lu",))).filter(
        lambda x: x not in {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"}
    )
)
@settings(max_examples=30)
def test_invalid_uf_rejected(uf):
    """Property 8c: Invalid UF returns HTTP 422."""
    response = client.get(
        "/tools/tabela-transicao",
        params={"ano": 2026, "uf_origem": uf, "uf_destino": "SP", "regime": "lucro_real"},
    )
    assert response.status_code == 422, f"UF '{uf}' should be rejected, got {response.status_code}"


@given(
    regime=st.text(min_size=1, max_size=30).filter(
        lambda x: x not in {"lucro_real", "lucro_presumido", "simples_nacional"}
    )
)
@settings(max_examples=30)
def test_invalid_regime_rejected(regime):
    """Property 8d: Invalid regime returns HTTP 422."""
    response = client.get(
        "/tools/tabela-transicao",
        params={"ano": 2026, "uf_origem": "SP", "uf_destino": "RJ", "regime": regime},
    )
    assert response.status_code == 422, f"Regime '{regime}' should be rejected, got {response.status_code}"
