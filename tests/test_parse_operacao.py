"""Tests for the parse_operacao node.

Validates:
- Valid payloads are accepted and return an OperacaoFrete instance
- Invalid payloads return ErroEstruturado with ALL errors at once (fail-fast coletivo)
- Multiple simultaneous errors are detected in a single response

Requirements: 1.1, 1.7, 1.8
"""

from datetime import date

from src.graph.nodes.parse_operacao import parse_operacao
from src.models.erro import ErroEstruturado
from src.models.operacao import OperacaoFrete


class TestParseOperacaoValid:
    """Tests for valid payload acceptance (Requirement 1.1)."""

    def test_valid_payload_returns_operacao(self, operacao_valida):
        """A valid payload should parse successfully and return an OperacaoFrete."""
        result = parse_operacao(operacao_valida)

        assert result["operacao"] is not None
        assert result["error"] is None
        assert isinstance(result["operacao"], OperacaoFrete)

    def test_valid_payload_fields_match(self, operacao_valida):
        """Parsed OperacaoFrete fields should match the input payload."""
        result = parse_operacao(operacao_valida)
        op = result["operacao"]

        assert op.modal == "rodoviario"
        assert op.origem_uf == "SP"
        assert op.destino_uf == "RJ"
        assert op.regime_tributario == "lucro_real"
        assert op.valor_frete == 10000.00
        assert op.data_referencia == date(2026, 6, 15)

    def test_valid_payload_simples_nacional(self, operacao_simples_nacional):
        """A Simples Nacional payload should parse successfully."""
        result = parse_operacao(operacao_simples_nacional)

        assert result["operacao"] is not None
        assert result["error"] is None
        assert result["operacao"].regime_tributario == "simples_nacional"

    def test_valid_payload_with_observacoes(self):
        """A payload with observacoes within 500 chars should parse."""
        payload = {
            "modal": "aereo",
            "origem_uf": "MG",
            "destino_uf": "BA",
            "regime_tributario": "lucro_presumido",
            "valor_frete": 25000.50,
            "data_referencia": "2033-12-31",
            "observacoes": "Frete urgente para entrega expressa",
        }
        result = parse_operacao(payload)

        assert result["operacao"] is not None
        assert result["error"] is None
        assert result["operacao"].observacoes == "Frete urgente para entrega expressa"


class TestParseOperacaoInvalid:
    """Tests for invalid payload rejection (Requirements 1.7, 1.8)."""

    def test_invalid_valor_frete_negative(self, operacao_invalida_valor):
        """Negative freight value should produce a validation error."""
        result = parse_operacao(operacao_invalida_valor)

        assert result["operacao"] is None
        assert result["error"] is not None
        assert isinstance(result["error"], ErroEstruturado)
        assert len(result["error"].campos_invalidos) >= 1

        campos = [c.campo for c in result["error"].campos_invalidos]
        assert "valor_frete" in campos

    def test_invalid_uf_codes(self, operacao_invalida_uf):
        """Invalid UF codes should produce validation errors for both fields."""
        result = parse_operacao(operacao_invalida_uf)

        assert result["operacao"] is None
        assert result["error"] is not None
        assert len(result["error"].campos_invalidos) >= 2

        campos = [c.campo for c in result["error"].campos_invalidos]
        assert "origem_uf" in campos
        assert "destino_uf" in campos

    def test_invalid_year_out_of_range(self):
        """Reference date with year outside 2026-2033 should produce error."""
        payload = {
            "modal": "rodoviario",
            "origem_uf": "SP",
            "destino_uf": "RJ",
            "regime_tributario": "lucro_real",
            "valor_frete": 10000.00,
            "data_referencia": "2025-01-01",
        }
        result = parse_operacao(payload)

        assert result["operacao"] is None
        assert result["error"] is not None

        campos = [c.campo for c in result["error"].campos_invalidos]
        assert "data_referencia" in campos

    def test_invalid_modal(self):
        """Invalid modal value should produce a validation error."""
        payload = {
            "modal": "maritimo",
            "origem_uf": "SP",
            "destino_uf": "RJ",
            "regime_tributario": "lucro_real",
            "valor_frete": 10000.00,
            "data_referencia": "2026-06-15",
        }
        result = parse_operacao(payload)

        assert result["operacao"] is None
        assert result["error"] is not None

        campos = [c.campo for c in result["error"].campos_invalidos]
        assert "modal" in campos

    def test_missing_required_fields(self):
        """Missing required fields should all be reported at once."""
        payload = {}
        result = parse_operacao(payload)

        assert result["operacao"] is None
        assert result["error"] is not None
        # Should report all missing required fields
        assert len(result["error"].campos_invalidos) >= 5

    def test_multiple_errors_reported_simultaneously(self):
        """Multiple invalid fields should ALL be reported in a single response (Req 1.8)."""
        payload = {
            "modal": "invalido",
            "origem_uf": "XX",
            "destino_uf": "YY",
            "regime_tributario": "invalido",
            "valor_frete": -1.0,
            "data_referencia": "2020-01-01",
        }
        result = parse_operacao(payload)

        assert result["operacao"] is None
        assert result["error"] is not None
        # All invalid fields should be reported at once
        assert len(result["error"].campos_invalidos) >= 4

    def test_error_has_correct_structure(self, operacao_invalida_valor):
        """ErroEstruturado should have the expected fields populated."""
        result = parse_operacao(operacao_invalida_valor)
        erro = result["error"]

        assert erro.erro == "Erro de validação na operação de frete"
        assert erro.thread_id is None
        assert erro.timestamp is not None
        assert len(erro.campos_invalidos) > 0
        # Each CampoInvalido has campo and motivo
        for campo_inv in erro.campos_invalidos:
            assert campo_inv.campo
            assert campo_inv.motivo

    def test_valor_frete_zero(self):
        """Freight value of exactly zero should be rejected."""
        payload = {
            "modal": "rodoviario",
            "origem_uf": "SP",
            "destino_uf": "RJ",
            "regime_tributario": "lucro_real",
            "valor_frete": 0.0,
            "data_referencia": "2026-06-15",
        }
        result = parse_operacao(payload)

        assert result["operacao"] is None
        assert result["error"] is not None

        campos = [c.campo for c in result["error"].campos_invalidos]
        assert "valor_frete" in campos

    def test_valor_frete_exceeds_maximum(self):
        """Freight value above 999,999,999.99 should be rejected."""
        payload = {
            "modal": "rodoviario",
            "origem_uf": "SP",
            "destino_uf": "RJ",
            "regime_tributario": "lucro_real",
            "valor_frete": 1_000_000_000.00,
            "data_referencia": "2026-06-15",
        }
        result = parse_operacao(payload)

        assert result["operacao"] is None
        assert result["error"] is not None

        campos = [c.campo for c in result["error"].campos_invalidos]
        assert "valor_frete" in campos
