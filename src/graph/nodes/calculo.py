"""Tax calculation engine for the logitaxAgent simulator.

Implements deterministic tax calculations for:
- Regime_Atual: PIS 1.65% + COFINS 7.6% + ICMS 12.0% (fixed = 21.25%)
- Regime_Novo (regular): CBS + IBS + ICMS phase-out per transition table
- Regime_Novo (Simples Nacional): same formula, no credit deductions
- Delta_Percentual: ((novo - atual) / atual) × 100

All monetary values are rounded to 2 decimal places.
All percentage values are rounded to 2 decimal places.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 4.1, 4.2
"""

from __future__ import annotations

from src.models.tabela_transicao import TabelaTransicaoResponse

# Fixed rates for Regime_Atual (current tax system)
PIS_PCT = 1.65
COFINS_PCT = 7.60
ICMS_BASE_PCT = 12.0
REGIME_ATUAL_TOTAL_PCT = PIS_PCT + COFINS_PCT + ICMS_BASE_PCT  # 21.25%


def calcular_tributo_atual(valor_frete: float) -> float:
    """Calculate tax under the current regime (Regime_Atual).

    Formula: valor_frete × (PIS 1.65% + COFINS 7.6% + ICMS 12.0%) = valor_frete × 21.25%

    Args:
        valor_frete: Freight value in BRL (must be > 0).

    Returns:
        Tax amount rounded to 2 decimal places.

    Requirements: 2.1
    """
    return round(valor_frete * REGIME_ATUAL_TOTAL_PCT / 100, 2)


def calcular_tributo_novo(
    valor_frete: float,
    tabela: TabelaTransicaoResponse,
    regime: str,
    credit_factor: float = 1.0,
) -> float:
    """Calculate tax under the new regime (Regime_Novo).

    Routes between regular and Simples Nacional calculation based on regime.

    For regular regimes (lucro_real, lucro_presumido):
        novo = valor_frete × (CBS% + IBS% + ICMS_BASE% × icms_pct_da_base/100) / 100
        The credit_factor parameter is reserved for future credit deduction modeling.

    For simples_nacional:
        Same formula but credit_factor is forced to 0 (no credit deductions).
        In practice, for this simplified model, both calculate the same gross tax
        since credit deductions are not yet subtracted from the base calculation.

    Args:
        valor_frete: Freight value in BRL (must be > 0).
        tabela: Transition table data for the reference year.
        regime: Tax regime ('lucro_real', 'lucro_presumido', 'simples_nacional').
        credit_factor: Credit factor (1.0 = full credits for regular, 0.0 = no credits for Simples).
                       Default 1.0. For Simples Nacional, this is overridden to 0.0.

    Returns:
        Tax amount rounded to 2 decimal places.

    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2
    """
    if regime == "simples_nacional":
        return _calcular_tributo_novo_simples(valor_frete, tabela)
    return _calcular_tributo_novo_regular(valor_frete, tabela, credit_factor)


def _calcular_tributo_novo_regular(
    valor_frete: float,
    tabela: TabelaTransicaoResponse,
    credit_factor: float = 1.0,
) -> float:
    """Calculate Regime_Novo tax for regular regimes (lucro_real, lucro_presumido).

    Formula:
        aliquota_efetiva = CBS% + IBS% + (ICMS_BASE% × aliquota_icms_pct_da_base / 100)
        tributo = valor_frete × aliquota_efetiva / 100

    The credit_factor is available for future modeling of non-cumulative credit
    deductions. Currently defaults to 1.0 (no deduction applied).

    Args:
        valor_frete: Freight value in BRL.
        tabela: Transition table data for the reference year.
        credit_factor: Multiplier for credit deductions (1.0 = no deduction, < 1.0 = deduction).

    Returns:
        Tax amount rounded to 2 decimal places.
    """
    aliquota_efetiva = (
        tabela.aliquota_cbs_pct
        + tabela.aliquota_ibs_pct
        + (ICMS_BASE_PCT * tabela.aliquota_icms_pct_da_base / 100)
    )
    tributo_bruto = valor_frete * aliquota_efetiva / 100
    return round(tributo_bruto, 2)


def _calcular_tributo_novo_simples(
    valor_frete: float,
    tabela: TabelaTransicaoResponse,
) -> float:
    """Calculate Regime_Novo tax for Simples Nacional.

    Same formula as regular but with no credit deductions (credit_factor=0).
    In the simplified model, Simples Nacional pays the full combined rate
    without any non-cumulative credit benefit.

    Formula:
        aliquota_efetiva = CBS% + IBS% + (ICMS_BASE% × aliquota_icms_pct_da_base / 100)
        tributo = valor_frete × aliquota_efetiva / 100

    Note: credit_factor=0 means no credits are applied (the full tax is due).

    Args:
        valor_frete: Freight value in BRL.
        tabela: Transition table data for the reference year.

    Returns:
        Tax amount rounded to 2 decimal places.

    Requirements: 4.1
    """
    aliquota_efetiva = (
        tabela.aliquota_cbs_pct
        + tabela.aliquota_ibs_pct
        + (ICMS_BASE_PCT * tabela.aliquota_icms_pct_da_base / 100)
    )
    tributo_bruto = valor_frete * aliquota_efetiva / 100
    return round(tributo_bruto, 2)


def calcular_delta_percentual(valor_atual: float, valor_novo: float) -> float:
    """Calculate the percentage difference between new and current tax values.

    Formula: ((valor_tributo_novo − valor_tributo_atual) / valor_tributo_atual) × 100

    A positive delta means the new regime is more expensive.
    A negative delta means the new regime is cheaper.

    Args:
        valor_atual: Tax value under Regime_Atual (must be > 0).
        valor_novo: Tax value under Regime_Novo (must be >= 0).

    Returns:
        Delta percentage rounded to 2 decimal places.

    Raises:
        ValueError: If valor_atual is zero (division by zero).

    Requirements: 2.6
    """
    if valor_atual == 0:
        raise ValueError(
            "valor_tributo_atual não pode ser zero para cálculo de delta percentual"
        )
    delta = ((valor_novo - valor_atual) / valor_atual) * 100
    return round(delta, 2)
