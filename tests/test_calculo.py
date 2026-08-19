"""Unit tests for the tax calculation engine (src/graph/nodes/calculo.py).

Tests cover:
- Regime_Atual calculation (fixed 21.25%)
- Regime_Novo for 2026 (test phase: CBS 0.9% + IBS 0.1% + ICMS 12% = 13%)
- Regime_Novo for 2033 (full transition: CBS 8.8% + IBS 19.1% + ICMS 0% = 27.9%)
- Delta_Percentual formula correctness
- Edge cases (rounding, very small/large values)
"""

import pytest

from src.graph.nodes.calculo import (
    REGIME_ATUAL_TOTAL_PCT,
    calcular_delta_percentual,
    calcular_tributo_atual,
    calcular_tributo_novo,
)
from src.models.tabela_transicao import TabelaTransicaoResponse

# --- Fixtures ---


@pytest.fixture
def tabela_2026() -> TabelaTransicaoResponse:
    """Transition table for 2026 (test phase)."""
    return TabelaTransicaoResponse(
        ano=2026,
        fase="teste",
        aliquota_cbs_pct=0.9,
        aliquota_ibs_pct=0.1,
        aliquota_icms_pct_da_base=100.0,
        aliquota_combinada_nova_pct=1.0,
        versao="v1.0",
        oficial=True,
    )


@pytest.fixture
def tabela_2033() -> TabelaTransicaoResponse:
    """Transition table for 2033 (full transition)."""
    return TabelaTransicaoResponse(
        ano=2033,
        fase="plena",
        aliquota_cbs_pct=8.8,
        aliquota_ibs_pct=19.1,
        aliquota_icms_pct_da_base=0.0,
        aliquota_combinada_nova_pct=27.9,
        versao="v1.0",
        oficial=False,
    )


@pytest.fixture
def tabela_2030() -> TabelaTransicaoResponse:
    """Transition table for 2030 (mid-transition: 80% ICMS)."""
    return TabelaTransicaoResponse(
        ano=2030,
        fase="transicao",
        aliquota_cbs_pct=8.8,
        aliquota_ibs_pct=3.82,
        aliquota_icms_pct_da_base=80.0,
        aliquota_combinada_nova_pct=12.62,
        versao="v1.0",
        oficial=False,
    )


# --- Tests: calcular_tributo_atual ---


class TestCalcularTributoAtual:
    """Tests for Regime_Atual tax calculation."""

    def test_valor_frete_10000(self):
        """10000 × 21.25% = 2125.00"""
        resultado = calcular_tributo_atual(10000.00)
        assert resultado == 2125.00

    def test_valor_frete_1(self):
        """1 × 21.25% = 0.21 (rounded from 0.2125)"""
        resultado = calcular_tributo_atual(1.00)
        assert resultado == 0.21

    def test_valor_frete_small(self):
        """0.01 × 21.25% = 0.00 (rounded from 0.002125)"""
        resultado = calcular_tributo_atual(0.01)
        assert resultado == 0.0

    def test_valor_frete_large(self):
        """999999999.99 × 21.25% = expected large value."""
        resultado = calcular_tributo_atual(999_999_999.99)
        expected = round(999_999_999.99 * 21.25 / 100, 2)
        assert resultado == expected

    def test_rounding_two_decimal_places(self):
        """Verify rounding to 2 decimal places for fractional results."""
        # 1234.56 × 21.25% = 262.34 (rounded from 262.3440)
        resultado = calcular_tributo_atual(1234.56)
        expected = round(1234.56 * 21.25 / 100, 2)
        assert resultado == expected

    def test_regime_atual_total_is_21_25(self):
        """Verify the constant PIS + COFINS + ICMS = 21.25%."""
        assert REGIME_ATUAL_TOTAL_PCT == 21.25


# --- Tests: calcular_tributo_novo for 2026 ---


class TestCalcularTributoNovo2026:
    """Tests for Regime_Novo in 2026 (test phase).

    2026: CBS 0.9% + IBS 0.1% + ICMS 12% × 100% = 13.0%
    """

    def test_regime_regular_2026(self, tabela_2026: TabelaTransicaoResponse):
        """10000 × 13.0% = 1300.00 for lucro_real."""
        resultado = calcular_tributo_novo(10000.00, tabela_2026, "lucro_real")
        assert resultado == 1300.00

    def test_regime_presumido_2026(self, tabela_2026: TabelaTransicaoResponse):
        """10000 × 13.0% = 1300.00 for lucro_presumido."""
        resultado = calcular_tributo_novo(10000.00, tabela_2026, "lucro_presumido")
        assert resultado == 1300.00

    def test_simples_nacional_2026(self, tabela_2026: TabelaTransicaoResponse):
        """10000 × 13.0% = 1300.00 for simples_nacional (same gross, no credits)."""
        resultado = calcular_tributo_novo(10000.00, tabela_2026, "simples_nacional")
        assert resultado == 1300.00

    def test_small_value_2026(self, tabela_2026: TabelaTransicaoResponse):
        """100 × 13.0% = 13.00"""
        resultado = calcular_tributo_novo(100.00, tabela_2026, "lucro_real")
        assert resultado == 13.00


# --- Tests: calcular_tributo_novo for 2033 ---


class TestCalcularTributoNovo2033:
    """Tests for Regime_Novo in 2033 (full transition).

    2033: CBS 8.8% + IBS 19.1% + ICMS 12% × 0% = 27.9%
    """

    def test_regime_regular_2033(self, tabela_2033: TabelaTransicaoResponse):
        """10000 × 27.9% = 2790.00 for lucro_real."""
        resultado = calcular_tributo_novo(10000.00, tabela_2033, "lucro_real")
        assert resultado == 2790.00

    def test_regime_presumido_2033(self, tabela_2033: TabelaTransicaoResponse):
        """10000 × 27.9% = 2790.00 for lucro_presumido."""
        resultado = calcular_tributo_novo(10000.00, tabela_2033, "lucro_presumido")
        assert resultado == 2790.00

    def test_simples_nacional_2033(self, tabela_2033: TabelaTransicaoResponse):
        """10000 × 27.9% = 2790.00 for simples_nacional."""
        resultado = calcular_tributo_novo(10000.00, tabela_2033, "simples_nacional")
        assert resultado == 2790.00

    def test_fractional_value_2033(self, tabela_2033: TabelaTransicaoResponse):
        """7777.77 × 27.9% = 2169.99 (rounded)."""
        resultado = calcular_tributo_novo(7777.77, tabela_2033, "lucro_real")
        expected = round(7777.77 * 27.9 / 100, 2)
        assert resultado == expected


# --- Tests: calcular_tributo_novo for 2030 (mid-transition) ---


class TestCalcularTributoNovo2030:
    """Tests for Regime_Novo in 2030 (mid-transition).

    2030: CBS 8.8% + IBS 3.82% + ICMS 12% × 80% = 8.8 + 3.82 + 9.6 = 22.22%
    """

    def test_regime_regular_2030(self, tabela_2030: TabelaTransicaoResponse):
        """10000 × 22.22% = 2222.00"""
        resultado = calcular_tributo_novo(10000.00, tabela_2030, "lucro_real")
        expected = round(10000.00 * (8.8 + 3.82 + 12.0 * 80.0 / 100) / 100, 2)
        assert resultado == expected

    def test_simples_nacional_2030(self, tabela_2030: TabelaTransicaoResponse):
        """Simples uses same gross formula in 2030."""
        resultado = calcular_tributo_novo(5000.00, tabela_2030, "simples_nacional")
        expected = round(5000.00 * (8.8 + 3.82 + 12.0 * 80.0 / 100) / 100, 2)
        assert resultado == expected


# --- Tests: calcular_delta_percentual ---


class TestCalcularDeltaPercentual:
    """Tests for Delta_Percentual calculation."""

    def test_basic_positive_delta(self):
        """New regime more expensive: ((2790 - 2125) / 2125) × 100 = 31.29%"""
        delta = calcular_delta_percentual(2125.00, 2790.00)
        expected = round(((2790.00 - 2125.00) / 2125.00) * 100, 2)
        assert delta == expected
        assert delta == 31.29

    def test_basic_negative_delta(self):
        """New regime cheaper: ((1300 - 2125) / 2125) × 100 = -38.82%"""
        delta = calcular_delta_percentual(2125.00, 1300.00)
        expected = round(((1300.00 - 2125.00) / 2125.00) * 100, 2)
        assert delta == expected
        assert delta == -38.82

    def test_zero_delta(self):
        """Same values: delta = 0.0%"""
        delta = calcular_delta_percentual(2125.00, 2125.00)
        assert delta == 0.0

    def test_rounding_two_decimals(self):
        """Verify rounding for non-trivial fractions."""
        # ((1300 - 2125) / 2125) × 100 = -38.823529... → -38.82
        delta = calcular_delta_percentual(2125.00, 1300.00)
        assert delta == -38.82

    def test_valor_atual_zero_raises(self):
        """Division by zero should raise ValueError."""
        with pytest.raises(ValueError, match="não pode ser zero"):
            calcular_delta_percentual(0.0, 1000.00)

    def test_very_small_difference(self):
        """Very small difference rounds to 0.0."""
        delta = calcular_delta_percentual(10000.00, 10000.01)
        # ((10000.01 - 10000.00) / 10000.00) × 100 = 0.0001 → 0.0
        assert delta == 0.0


# --- Integration-style tests: full workflow ---


class TestFullCalculationWorkflow:
    """End-to-end calculation workflow tests."""

    def test_2026_full_comparison(self, tabela_2026: TabelaTransicaoResponse):
        """Full comparison for 2026: current 21.25% vs new 13.0%."""
        valor_frete = 10000.00
        tributo_atual = calcular_tributo_atual(valor_frete)
        tributo_novo = calcular_tributo_novo(valor_frete, tabela_2026, "lucro_real")
        delta = calcular_delta_percentual(tributo_atual, tributo_novo)

        assert tributo_atual == 2125.00
        assert tributo_novo == 1300.00
        assert delta == -38.82

    def test_2033_full_comparison(self, tabela_2033: TabelaTransicaoResponse):
        """Full comparison for 2033: current 21.25% vs new 27.9%."""
        valor_frete = 10000.00
        tributo_atual = calcular_tributo_atual(valor_frete)
        tributo_novo = calcular_tributo_novo(valor_frete, tabela_2033, "lucro_real")
        delta = calcular_delta_percentual(tributo_atual, tributo_novo)

        assert tributo_atual == 2125.00
        assert tributo_novo == 2790.00
        assert delta == 31.29

    def test_2030_full_comparison(self, tabela_2030: TabelaTransicaoResponse):
        """Full comparison for 2030: current 21.25% vs new 22.22%."""
        valor_frete = 10000.00
        tributo_atual = calcular_tributo_atual(valor_frete)
        tributo_novo = calcular_tributo_novo(valor_frete, tabela_2030, "lucro_real")
        delta = calcular_delta_percentual(tributo_atual, tributo_novo)

        assert tributo_atual == 2125.00
        # 2030: 8.8 + 3.82 + 9.6 = 22.22% → 2222.00
        assert tributo_novo == 2222.00
        # Delta: ((2222 - 2125) / 2125) × 100 = 4.56%
        assert delta == 4.56
