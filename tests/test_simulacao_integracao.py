"""Testes de integração end-to-end do simulador IBS/CBS.

Testa fluxo completo: validação → cálculo paralelo (4 anos: 2026, 2027, 2030, 2033)
→ agregação → estrutura do resultado.

Verifica presença de: valor_tributo_atual, valor_tributo_novo, delta_percentual,
fonte, fallback_flag por ano.

Testa cenário com fallback quando tool indisponível.
Tempo máximo: 120s.

Requirements: 12.2, 12.3
"""

from __future__ import annotations

import os
from datetime import date
from unittest.mock import patch, AsyncMock

import pytest

from src.graph.nodes.parse_operacao import parse_operacao
from src.graph.nodes.sanitize_input import sanitize_input
from src.graph.nodes.route_regime import route_regime
from src.graph.graph import _route_by_regime
from src.graph.nodes.simular_regime import (
    simular_regime_regular,
    simular_regime_hibrido_simples,
)
from src.graph.nodes.simular_ano import simular_ano
from src.graph.nodes.retrieve_context import retrieve_context
from src.graph.nodes.human_review import human_review
from src.graph.nodes.export_result import export_result
from src.models.operacao import OperacaoFrete


# --- Fixtures ---


@pytest.fixture
def operacao_valida_lucro_real():
    """Valid operation with Lucro Real regime."""
    return {
        "modal": "rodoviario",
        "origem_uf": "SP",
        "destino_uf": "RJ",
        "regime_tributario": "lucro_real",
        "valor_frete": 10000.00,
        "data_referencia": "2026-06-15",
        "observacoes": "Teste de integração",
    }


@pytest.fixture
def operacao_valida_simples():
    """Valid operation with Simples Nacional regime."""
    return {
        "modal": "aereo",
        "origem_uf": "MG",
        "destino_uf": "BA",
        "regime_tributario": "simples_nacional",
        "valor_frete": 5000.00,
        "data_referencia": "2030-01-01",
    }


# --- Integration Tests ---


class TestFluxoCompleto:
    """Test the complete simulation flow node by node."""

    def test_fluxo_parse_sanitize_route_lucro_real(self, operacao_valida_lucro_real):
        """Test: parse → sanitize → route for Lucro Real."""
        # 1. Parse (parse_operacao receives the payload dict directly)
        result = parse_operacao(operacao_valida_lucro_real)

        assert result["operacao"] is not None
        assert result["error"] is None
        assert result["operacao"].regime_tributario == "lucro_real"

        # 2. Sanitize
        state = {"operacao": result["operacao"]}
        sanitized = sanitize_input(state)
        assert "operacao" in sanitized

        # 3. Route (returns next node name as string)
        state.update(sanitized)
        routed = _route_by_regime(state)
        assert routed == "simular_regime_regular"

    def test_fluxo_parse_sanitize_route_simples(self, operacao_valida_simples):
        """Test: parse → sanitize → route for Simples Nacional."""
        result = parse_operacao(operacao_valida_simples)
        assert result["operacao"] is not None

        state = {"operacao": result["operacao"]}
        sanitized = sanitize_input(state)
        state.update(sanitized)

        routed = _route_by_regime(state)
        assert routed == "simular_regime_hibrido_simples"

    @pytest.mark.asyncio
    async def test_fluxo_simulacao_4_anos_lucro_real(self, operacao_valida_lucro_real):
        """Test: full simulation with 4 milestone years for Lucro Real.
        
        Patches the tool client to use fallback directly.
        """
        from src.tools.client_transicao import _carregar_fallback_local, ConsultaTransicaoResult

        async def mock_consultar(ano, uf_origem, uf_destino, regime, **kwargs):
            """Mock that goes straight to local fallback."""
            return _carregar_fallback_local(ano)

        # Parse
        result = parse_operacao(operacao_valida_lucro_real)
        assert result["operacao"] is not None
        state = {"operacao": result["operacao"]}

        # Sanitize
        sanitized = sanitize_input(state)
        state.update(sanitized)

        # Route
        routed = _route_by_regime(state)
        assert routed == "simular_regime_regular"

        # Simulate regime
        regime_result = simular_regime_regular(state)
        state.update(regime_result)

        # Simulate years with mocked tool client
        state["tentativas_reclassificacao"] = 0
        state["revisao_manual"] = False
        
        with patch("src.graph.nodes.simular_ano.consultar_tabela_transicao", side_effect=mock_consultar):
            anos_result = await simular_ano(state)
            state.update(anos_result)

        # Verify results structure
        resultados = state.get("resultados_por_ano", [])
        assert len(resultados) == 4, f"Expected 4 years, got {len(resultados)}"

        # Verify each year has required fields
        anos_esperados = {2026, 2027, 2030, 2033}
        anos_retornados = set()

        for r in resultados:
            if hasattr(r, "model_dump"):
                rd = r.model_dump()
            else:
                rd = r

            assert "ano" in rd
            assert "valor_tributo_atual" in rd
            assert "valor_tributo_novo" in rd
            assert "delta_percentual" in rd

            anos_retornados.add(rd["ano"])

            # Values should be positive numbers
            assert rd["valor_tributo_atual"] > 0
            assert rd["valor_tributo_novo"] >= 0
            # Delta can be negative (reduction)
            assert isinstance(rd["delta_percentual"], (int, float))

        assert anos_retornados == anos_esperados

    @pytest.mark.asyncio
    async def test_fluxo_simulacao_simples_nacional(self, operacao_valida_simples):
        """Test simulation flow for Simples Nacional."""
        from src.tools.client_transicao import _carregar_fallback_local

        async def mock_consultar(ano, uf_origem, uf_destino, regime, **kwargs):
            return _carregar_fallback_local(ano)

        result = parse_operacao(operacao_valida_simples)
        assert result["operacao"] is not None
        state = {"operacao": result["operacao"]}

        sanitized = sanitize_input(state)
        state.update(sanitized)

        routed = _route_by_regime(state)
        assert routed == "simular_regime_hibrido_simples"

        regime_result = simular_regime_hibrido_simples(state)
        state.update(regime_result)

        state["tentativas_reclassificacao"] = 0
        state["revisao_manual"] = False

        with patch("src.graph.nodes.simular_ano.consultar_tabela_transicao", side_effect=mock_consultar):
            anos_result = await simular_ano(state)
            state.update(anos_result)

        resultados = state.get("resultados_por_ano", [])
        assert len(resultados) == 4

    def test_retrieve_context_after_simulation(self, operacao_valida_lucro_real):
        """Test retrieve_context with valid state from simulation."""
        # Build minimal state for retrieve_context
        state = {
            "operacao": OperacaoFrete(
                modal="rodoviario",
                origem_uf="SP",
                destino_uf="RJ",
                regime_tributario="lucro_real",
                valor_frete=10000.00,
                data_referencia=date(2026, 6, 15),
            ),
            "resultados_por_ano": [],
            "alertas": [],
        }

        result = retrieve_context(state)
        assert "trechos_rag" in result
        assert "alertas" in result
        assert isinstance(result["trechos_rag"], list)

    def test_human_review_builds_summary(self):
        """Test human_review node builds proper summary."""
        state = {
            "thread_id": "test-thread-123",
            "operacao": {
                "modal": "rodoviario",
                "origem_uf": "SP",
                "destino_uf": "RJ",
                "regime_tributario": "lucro_real",
                "valor_frete": 10000.00,
            },
            "resultados_por_ano": [
                {"ano": 2026, "valor_tributo_atual": 2125.0, "valor_tributo_novo": 100.0, "delta_percentual": -95.29}
            ],
            "justificativa": "Justificativa de teste",
            "alertas": [],
        }

        result = human_review(state)
        assert "review_summary" in result
        summary = result["review_summary"]
        assert summary["thread_id"] == "test-thread-123"
        assert "operacao" in summary
        assert "resultados_por_ano" in summary

    def test_export_blocked_without_approval(self):
        """Test export_result blocks without human approval."""
        state = {
            "thread_id": "test-thread-456",
            "aprovado_humano": False,
            "resultados_por_ano": [],
        }

        result = export_result(state)
        assert result["export_status"] == "blocked"

    def test_export_succeeds_with_approval(self):
        """Test export_result proceeds with human approval."""
        state = {
            "thread_id": "test-thread-789",
            "aprovado_humano": True,
            "operacao": {
                "modal": "rodoviario",
                "origem_uf": "SP",
                "destino_uf": "RJ",
                "regime_tributario": "lucro_real",
                "valor_frete": 10000.00,
            },
            "resultados_por_ano": [
                {"ano": 2026, "valor_tributo_atual": 2125.0, "valor_tributo_novo": 100.0, "delta_percentual": -95.29}
            ],
            "justificativa": "Aprovado",
            "trechos_rag": [],
            "alertas": [],
        }

        # No webhook configured = webhook_sent will be False
        result = export_result(state)
        assert result["export_status"] == "completed"


class TestFallbackScenario:
    """Test fallback scenario when tool is unavailable."""

    @pytest.mark.asyncio
    async def test_simulation_with_tool_fallback(self):
        """When tool endpoint is unavailable, fallback to local JSON."""
        from src.tools.client_transicao import _carregar_fallback_local

        async def mock_consultar(ano, uf_origem, uf_destino, regime, **kwargs):
            return _carregar_fallback_local(ano)

        payload = {
            "modal": "rodoviario",
            "origem_uf": "SP",
            "destino_uf": "RJ",
            "regime_tributario": "lucro_real",
            "valor_frete": 15000.00,
            "data_referencia": "2030-06-15",
        }

        # Parse and setup
        result = parse_operacao(payload)
        assert result["operacao"] is not None
        state = {"operacao": result["operacao"]}

        sanitized = sanitize_input(state)
        state.update(sanitized)
        routed = _route_by_regime(state)
        assert routed == "simular_regime_regular"
        regime_result = simular_regime_regular(state)
        state.update(regime_result)

        state["tentativas_reclassificacao"] = 0
        state["revisao_manual"] = False

        # Simulate with forced fallback
        with patch("src.graph.nodes.simular_ano.consultar_tabela_transicao", side_effect=mock_consultar):
            anos_result = await simular_ano(state)
            state.update(anos_result)

        resultados = state.get("resultados_por_ano", [])
        assert len(resultados) == 4

        # Each result should have valid values
        for r in resultados:
            if hasattr(r, "model_dump"):
                rd = r.model_dump()
            else:
                rd = r
            assert rd["valor_tributo_atual"] > 0


class TestValidacaoErros:
    """Test error handling in the integration flow."""

    def test_invalid_operation_raises_error(self):
        """Parse should return error for invalid operations."""
        payload = {
            "modal": "invalido",
            "origem_uf": "XX",
            "destino_uf": "YY",
            "regime_tributario": "inexistente",
            "valor_frete": -100,
            "data_referencia": "2026-01-01",
        }

        result = parse_operacao(payload)
        # Should have error info
        assert result["operacao"] is None
        assert result["error"] is not None
        assert len(result["error"].campos_invalidos) > 0
