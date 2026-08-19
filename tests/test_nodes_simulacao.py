"""Unit tests for the simulation pipeline nodes: route_regime, simular_regime, simular_ano.

Tests cover:
- route_regime routing logic for all three regimes
- simular_regime_regular and simular_regime_hibrido_simples credit factor assignment
- simular_ano fan-out/fan-in with mocked client_transicao
- Partial failure handling in simular_ano
- Chronological ordering of results
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from src.graph.nodes.route_regime import route_regime
from src.graph.nodes.simular_ano import ANOS_MARCO, simular_ano
from src.graph.nodes.simular_regime import (
    simular_regime_hibrido_simples,
    simular_regime_regular,
)
from src.models.operacao import OperacaoFrete
from src.models.tabela_transicao import TabelaTransicaoResponse
from src.tools.client_transicao import ConsultaTransicaoResult

# --- Helpers ---


def _make_operacao(regime: str = "lucro_real") -> OperacaoFrete:
    """Create a valid OperacaoFrete for testing."""
    return OperacaoFrete(
        modal="rodoviario",
        origem_uf="SP",
        destino_uf="RJ",
        regime_tributario=regime,
        valor_frete=10000.00,
        data_referencia=date(2026, 6, 15),
    )


def _make_tabela(ano: int) -> TabelaTransicaoResponse:
    """Create a TabelaTransicaoResponse for a given year."""
    # Simplified rates for testing
    rates = {
        2026: {"cbs": 0.9, "ibs": 0.1, "icms_pct": 100.0, "combinada": 1.0, "fase": "teste"},
        2027: {"cbs": 0.9, "ibs": 0.1, "icms_pct": 100.0, "combinada": 1.0, "fase": "transicao"},
        2030: {"cbs": 8.8, "ibs": 7.08, "icms_pct": 70.0, "combinada": 15.88, "fase": "transicao"},
        2033: {"cbs": 8.8, "ibs": 17.7, "icms_pct": 0.0, "combinada": 26.5, "fase": "plena"},
    }
    r = rates.get(ano, rates[2026])
    return TabelaTransicaoResponse(
        ano=ano,
        fase=r["fase"],
        aliquota_cbs_pct=r["cbs"],
        aliquota_ibs_pct=r["ibs"],
        aliquota_icms_pct_da_base=r["icms_pct"],
        aliquota_combinada_nova_pct=r["combinada"],
        versao="v1.0",
        oficial=True,
    )


def _make_consulta_result(ano: int) -> ConsultaTransicaoResult:
    """Create a ConsultaTransicaoResult for a given year."""
    return ConsultaTransicaoResult(
        dados=_make_tabela(ano),
        fallback_usado=False,
        fonte="api_transicao_v1.0",
    )


# --- Tests for route_regime (Task 5.5) ---


class TestRouteRegime:
    """Tests for the route_regime node and _route_by_regime conditional edge."""

    def test_node_returns_empty_dict(self):
        """route_regime node should return empty dict (routing is via conditional edge)."""
        state = {"operacao": _make_operacao("simples_nacional")}
        result = route_regime(state)
        assert result == {}

    def test_route_by_regime_simples_nacional(self):
        """_route_by_regime should route simples_nacional to hibrido."""
        from src.graph.graph import _route_by_regime

        state = {"operacao": _make_operacao("simples_nacional")}
        result = _route_by_regime(state)
        assert result == "simular_regime_hibrido_simples"

    def test_route_by_regime_lucro_real(self):
        """_route_by_regime should route lucro_real to regular."""
        from src.graph.graph import _route_by_regime

        state = {"operacao": _make_operacao("lucro_real")}
        result = _route_by_regime(state)
        assert result == "simular_regime_regular"

    def test_route_by_regime_lucro_presumido(self):
        """_route_by_regime should route lucro_presumido to regular."""
        from src.graph.graph import _route_by_regime

        state = {"operacao": _make_operacao("lucro_presumido")}
        result = _route_by_regime(state)
        assert result == "simular_regime_regular"

    def test_route_by_regime_with_dict_operacao(self):
        """_route_by_regime should also work when operacao is a plain dict."""
        from src.graph.graph import _route_by_regime

        state = {"operacao": {"regime_tributario": "simples_nacional"}}
        result = _route_by_regime(state)
        assert result == "simular_regime_hibrido_simples"

    def test_route_by_regime_dict_lucro_real(self):
        """_route_by_regime should route dict with lucro_real to regular."""
        from src.graph.graph import _route_by_regime

        state = {"operacao": {"regime_tributario": "lucro_real"}}
        result = _route_by_regime(state)
        assert result == "simular_regime_regular"


# --- Tests for simular_regime nodes (Task 5.6) ---


class TestSimularRegime:
    """Tests for simular_regime_regular and simular_regime_hibrido_simples."""

    def test_regular_sets_credit_factor_1(self):
        """simular_regime_regular should set credit_factor to 1.0."""
        state = {"operacao": _make_operacao("lucro_real")}
        result = simular_regime_regular(state)
        assert result == {"credit_factor": 1.0}

    def test_simples_sets_credit_factor_0(self):
        """simular_regime_hibrido_simples should set credit_factor to 0.0."""
        state = {"operacao": _make_operacao("simples_nacional")}
        result = simular_regime_hibrido_simples(state)
        assert result == {"credit_factor": 0.0}

    def test_regular_returns_dict(self):
        """simular_regime_regular should return a plain dict for state merge."""
        result = simular_regime_regular({"operacao": {}})
        assert isinstance(result, dict)
        assert "credit_factor" in result

    def test_simples_returns_dict(self):
        """simular_regime_hibrido_simples should return a plain dict for state merge."""
        result = simular_regime_hibrido_simples({"operacao": {}})
        assert isinstance(result, dict)
        assert "credit_factor" in result


# --- Tests for simular_ano (Task 5.7) ---


class TestSimularAno:
    """Tests for the simular_ano fan-out/fan-in node."""

    @pytest.mark.asyncio
    @patch("src.graph.nodes.simular_ano.consultar_tabela_transicao")
    async def test_simular_ano_all_years_success(self, mock_consultar):
        """All milestone years should succeed and results sorted by year."""

        async def _mock_consultar(ano, **kwargs):
            return _make_consulta_result(ano)

        mock_consultar.side_effect = _mock_consultar

        state = {
            "operacao": _make_operacao("lucro_real"),
            "credit_factor": 1.0,
        }

        result = await simular_ano(state)

        assert "resultados_por_ano" in result
        assert "alertas" in result
        assert len(result["resultados_por_ano"]) == 4
        assert result["alertas"] == []

        # Verify chronological order
        anos = [r.ano for r in result["resultados_por_ano"]]
        assert anos == sorted(anos)
        assert anos == ANOS_MARCO

    @pytest.mark.asyncio
    @patch("src.graph.nodes.simular_ano.consultar_tabela_transicao")
    async def test_simular_ano_partial_failure(self, mock_consultar):
        """Partial failure: some years fail but successful ones are preserved."""

        async def _mock_consultar(ano, **kwargs):
            if ano == 2027:
                raise TimeoutError("Connection timed out for year 2027")
            return _make_consulta_result(ano)

        mock_consultar.side_effect = _mock_consultar

        state = {
            "operacao": _make_operacao("lucro_real"),
            "credit_factor": 1.0,
        }

        result = await simular_ano(state)

        # Should have 3 successful results (2026, 2030, 2033)
        assert len(result["resultados_por_ano"]) == 3
        anos_sucesso = [r.ano for r in result["resultados_por_ano"]]
        assert 2027 not in anos_sucesso
        assert 2026 in anos_sucesso
        assert 2030 in anos_sucesso
        assert 2033 in anos_sucesso

        # Should have 1 alert for 2027
        assert len(result["alertas"]) == 1
        assert "2027" in result["alertas"][0]

    @pytest.mark.asyncio
    @patch("src.graph.nodes.simular_ano.consultar_tabela_transicao")
    async def test_simular_ano_total_failure(self, mock_consultar):
        """Total failure: all years fail, empty results with alerts."""

        async def _mock_consultar(ano, **kwargs):
            raise ConnectionError(f"Cannot connect for year {ano}")

        mock_consultar.side_effect = _mock_consultar

        state = {
            "operacao": _make_operacao("lucro_real"),
            "credit_factor": 1.0,
        }

        result = await simular_ano(state)

        assert len(result["resultados_por_ano"]) == 0
        assert len(result["alertas"]) == 4

    @pytest.mark.asyncio
    @patch("src.graph.nodes.simular_ano.consultar_tabela_transicao")
    async def test_simular_ano_results_have_correct_values(self, mock_consultar):
        """Verify tax calculations are correct for a known input."""

        async def _mock_consultar(ano, **kwargs):
            return _make_consulta_result(ano)

        mock_consultar.side_effect = _mock_consultar

        state = {
            "operacao": _make_operacao("lucro_real"),
            "credit_factor": 1.0,
        }

        result = await simular_ano(state)

        # For 2026 with valor_frete=10000:
        # tributo_atual = 10000 * 21.25% = 2125.0
        # tributo_novo = 10000 * (0.9 + 0.1 + 12.0 * 100/100) / 100
        #              = 10000 * 13.0 / 100 = 1300.0
        r2026 = next(r for r in result["resultados_por_ano"] if r.ano == 2026)
        assert r2026.valor_tributo_atual == 2125.0
        assert r2026.valor_tributo_novo == 1300.0
        # delta = ((1300 - 2125) / 2125) * 100 = -38.82%
        assert r2026.delta_percentual == -38.82
        assert r2026.fallback_usado is False

    @pytest.mark.asyncio
    @patch("src.graph.nodes.simular_ano.consultar_tabela_transicao")
    async def test_simular_ano_with_dict_operacao(self, mock_consultar):
        """Should work with operacao as a plain dict."""

        async def _mock_consultar(ano, **kwargs):
            return _make_consulta_result(ano)

        mock_consultar.side_effect = _mock_consultar

        state = {
            "operacao": {
                "valor_frete": 5000.0,
                "regime_tributario": "simples_nacional",
                "origem_uf": "MG",
                "destino_uf": "SP",
            },
            "credit_factor": 0.0,
        }

        result = await simular_ano(state)

        assert len(result["resultados_por_ano"]) == 4
        # Results should be sorted
        anos = [r.ano for r in result["resultados_por_ano"]]
        assert anos == ANOS_MARCO

    @pytest.mark.asyncio
    @patch("src.graph.nodes.simular_ano.consultar_tabela_transicao")
    async def test_simular_ano_default_credit_factor(self, mock_consultar):
        """If credit_factor not in state, should default to 1.0."""

        async def _mock_consultar(ano, **kwargs):
            return _make_consulta_result(ano)

        mock_consultar.side_effect = _mock_consultar

        state = {
            "operacao": _make_operacao("lucro_real"),
            # No credit_factor key — should default to 1.0
        }

        result = await simular_ano(state)
        assert len(result["resultados_por_ano"]) == 4
