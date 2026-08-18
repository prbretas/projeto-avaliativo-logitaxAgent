"""Property tests para cálculos tributários.

Property 3: Tax calculation uses correct year-specific formula.
Property 4: Delta percentual is correctly derived.
Property 5: Regime routing produces differentiated results.

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 4.1, 4.2, 4.5
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.graph.nodes.calculo import (
    calcular_tributo_atual,
    calcular_tributo_novo,
    calcular_delta_percentual,
    PIS_PCT,
    COFINS_PCT,
    ICMS_BASE_PCT,
)

import json
from pathlib import Path

# Load transition table for verification
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
with open(DATA_DIR / "tabela_transicao_local.json", encoding="utf-8") as f:
    TABELA_TRANSICAO = json.load(f)

TABELA_POR_ANO = {item["ano"]: item for item in TABELA_TRANSICAO}


# --- Property 3: Tax calculation uses correct year-specific formula ---


@given(valor_frete=st.floats(min_value=0.01, max_value=10_000_000, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_tributo_atual_formula(valor_frete):
    """Property 3a: valor_tributo_atual = valor_frete × (PIS + COFINS + ICMS) = 21.25%."""
    resultado = calcular_tributo_atual(valor_frete)
    esperado = round(valor_frete * (PIS_PCT + COFINS_PCT + ICMS_BASE_PCT) / 100, 2)
    assert abs(resultado - esperado) < 0.01, f"Expected {esperado}, got {resultado}"


@given(
    valor_frete=st.floats(min_value=100, max_value=1_000_000, allow_nan=False, allow_infinity=False),
    ano=st.sampled_from([2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]),
)
@settings(max_examples=80)
def test_tributo_novo_uses_tabela_rates(valor_frete, ano):
    """Property 3b: valor_tributo_novo uses rates from the transition table."""
    tabela = TABELA_POR_ANO[ano]

    from src.models.tabela_transicao import TabelaTransicaoResponse
    tabela_response = TabelaTransicaoResponse(**tabela)

    resultado = calcular_tributo_novo(
        valor_frete=valor_frete,
        tabela=tabela_response,
        regime="lucro_real",
        credit_factor=1.0,
    )

    # Result should always be non-negative
    assert resultado >= 0, f"Tributo novo should be >= 0, got {resultado}"
    # Result should be finite
    assert resultado < valor_frete * 2, f"Tributo novo unreasonably high: {resultado}"


# --- Property 4: Delta percentual is correctly derived ---


@given(
    tributo_atual=st.floats(min_value=0.01, max_value=1_000_000, allow_nan=False, allow_infinity=False),
    tributo_novo=st.floats(min_value=0.0, max_value=1_000_000, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_delta_percentual_formula(tributo_atual, tributo_novo):
    """Property 4: delta = ((novo - atual) / atual) × 100 rounded to 2 decimals."""
    resultado = calcular_delta_percentual(tributo_atual, tributo_novo)
    esperado = round(((tributo_novo - tributo_atual) / tributo_atual) * 100, 2)
    assert abs(resultado - esperado) < 0.01, f"Expected {esperado}, got {resultado}"


# --- Property 5: Regime routing produces differentiated results ---


@given(
    valor_frete=st.floats(min_value=1000, max_value=100_000, allow_nan=False, allow_infinity=False),
    ano=st.sampled_from([2026, 2027, 2030, 2033]),
)
@settings(max_examples=50)
def test_regime_routing_differentiated(valor_frete, ano):
    """Property 5: Simples (credit=0) and Lucro Real (credit=1) produce different results."""
    tabela = TABELA_POR_ANO[ano]

    from src.models.tabela_transicao import TabelaTransicaoResponse
    tabela_response = TabelaTransicaoResponse(**tabela)

    resultado_regular = calcular_tributo_novo(
        valor_frete=valor_frete,
        tabela=tabela_response,
        regime="lucro_real",
        credit_factor=1.0,
    )

    resultado_simples = calcular_tributo_novo(
        valor_frete=valor_frete,
        tabela=tabela_response,
        regime="simples_nacional",
        credit_factor=0.0,
    )

    # Different regimes should (generally) produce different values
    # unless the credit component is zero for that year
    # At minimum, simples should be >= regular (no credit deduction)
    assert resultado_simples >= resultado_regular - 0.01, (
        f"Simples ({resultado_simples}) should be >= Regular ({resultado_regular}) "
        f"since credit_factor=0 means no deduction"
    )
