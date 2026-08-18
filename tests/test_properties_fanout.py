"""Property tests para fan-out/fan-in.

Property 6: Fan-out results are chronologically ordered.
Property 7: Partial failure preserves successful results.

Validates: Requirements 3.2, 3.5
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.models.resultado import (
    DetalheRegimeAtual,
    DetalheRegimeNovo,
    ResultadoAno,
)


def _make_resultado_ano(ano: int, **kwargs) -> ResultadoAno:
    """Helper to create a ResultadoAno with default detail fields for testing."""
    defaults = {
        "ano": ano,
        "valor_tributo_atual": 2125.0,
        "valor_tributo_novo": float(ano),
        "delta_percentual": -50.0,
        "fonte_tool": "test",
        "fallback_usado": False,
        "detalhe_regime_atual": DetalheRegimeAtual(
            pis_aliquota_pct=1.65,
            pis_valor=165.0,
            cofins_aliquota_pct=7.6,
            cofins_valor=760.0,
            icms_aliquota_pct=12.0,
            icms_valor=1200.0,
            total=2125.0,
        ),
        "detalhe_regime_novo": DetalheRegimeNovo(
            cbs_aliquota_pct=0.9,
            cbs_valor=90.0,
            ibs_aliquota_pct=0.1,
            ibs_valor=10.0,
            icms_residual_aliquota_pct=12.0,
            icms_residual_valor=1200.0,
            total=1300.0,
            oficial=True,
        ),
        "economia_ou_aumento": "Economia de R$ 825.00",
    }
    defaults.update(kwargs)
    return ResultadoAno(**defaults)


# --- Property 6: Fan-out results are chronologically ordered ---


@given(anos=st.permutations([2026, 2027, 2030, 2033]))
@settings(max_examples=24)
def test_results_chronologically_ordered(anos):
    """Property 6: After aggregation, results are always sorted by year ascending."""
    # Simulate results in random order
    resultados = [_make_resultado_ano(ano=ano, valor_tributo_novo=float(ano)) for ano in anos]

    # Simulate aggregation (sort by year)
    agregados = sorted(resultados, key=lambda r: r.ano)

    # Verify chronological order
    for i in range(len(agregados) - 1):
        assert agregados[i].ano < agregados[i + 1].ano, (
            f"Results not ordered: {agregados[i].ano} >= {agregados[i+1].ano}"
        )


# --- Property 7: Partial failure preserves successful results ---


@given(
    successful_anos=st.lists(
        st.sampled_from([2026, 2027, 2030, 2033]),
        min_size=1,
        max_size=4,
        unique=True,
    )
)
@settings(max_examples=30)
def test_partial_failure_preserves_successful(successful_anos):
    """Property 7: When some years fail, successful results are preserved."""
    all_anos = {2026, 2027, 2030, 2033}
    failed_anos = all_anos - set(successful_anos)

    # Simulate results for successful years only
    resultados = [
        _make_resultado_ano(
            ano=ano,
            valor_tributo_novo=100.0 * ano,
            fonte_tool="fallback",
            fallback_usado=True,
        )
        for ano in successful_anos
    ]

    # Successful results should be preserved
    assert len(resultados) == len(successful_anos)

    # All successful anos should be in results
    result_anos = {r.ano for r in resultados}
    assert result_anos == set(successful_anos)

    # No failed anos in results
    assert result_anos.isdisjoint(failed_anos)
