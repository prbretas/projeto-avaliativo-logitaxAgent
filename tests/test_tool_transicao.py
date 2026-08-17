"""Unit tests for the Tool_Transicao endpoint (GET /tools/tabela-transicao).

Tests cover:
- Successful response with valid parameters for each year
- HTTP 422 for invalid year, UF, and regime parameters
- Response includes the 'versao' field
- All validation errors returned at once
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.tools.tabela_transicao import router


@pytest.fixture
def client() -> TestClient:
    """Create a test client with the tabela-transicao router mounted."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestConsultaTabelaTransicaoSucesso:
    """Tests for successful requests to the transition table endpoint."""

    def test_retorna_dados_2026_fase_teste(self, client: TestClient):
        """GET with valid params for 2026 returns test-phase rates."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2026,
                "uf_origem": "SP",
                "uf_destino": "RJ",
                "regime": "lucro_real",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ano"] == 2026
        assert data["fase"] == "teste"
        assert data["aliquota_cbs_pct"] == 0.9
        assert data["aliquota_ibs_pct"] == 0.1
        assert data["aliquota_combinada_nova_pct"] == 1.0
        assert data["aliquota_icms_pct_da_base"] == 100.0
        assert "versao" in data
        assert data["versao"] == "v1.0"

    def test_retorna_dados_2033_fase_plena(self, client: TestClient):
        """GET with valid params for 2033 returns full transition rates."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2033,
                "uf_origem": "MG",
                "uf_destino": "BA",
                "regime": "simples_nacional",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ano"] == 2033
        assert data["fase"] == "plena"
        assert data["aliquota_icms_pct_da_base"] == 0.0
        assert data["versao"] == "v1.0"

    def test_retorna_dados_2030_transicao(self, client: TestClient):
        """GET with valid params for 2030 returns mid-transition rates."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2030,
                "uf_origem": "RS",
                "uf_destino": "PR",
                "regime": "lucro_presumido",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ano"] == 2030
        assert data["fase"] == "transicao"
        assert data["aliquota_icms_pct_da_base"] == 80.0

    def test_aceita_uf_minuscula(self, client: TestClient):
        """UF codes in lowercase are accepted and validated correctly."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2026,
                "uf_origem": "sp",
                "uf_destino": "rj",
                "regime": "lucro_real",
            },
        )
        assert response.status_code == 200


class TestConsultaTabelaTransicaoErros:
    """Tests for validation errors (HTTP 422) on the transition table endpoint."""

    def test_ano_abaixo_minimo_retorna_422(self, client: TestClient):
        """Year below 2026 returns 422 with structured error."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2025,
                "uf_origem": "SP",
                "uf_destino": "RJ",
                "regime": "lucro_real",
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert data["erro"] is not None
        assert len(data["campos_invalidos"]) >= 1
        campos = [c["campo"] for c in data["campos_invalidos"]]
        assert "ano" in campos

    def test_ano_acima_maximo_retorna_422(self, client: TestClient):
        """Year above 2033 returns 422 with structured error."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2034,
                "uf_origem": "SP",
                "uf_destino": "RJ",
                "regime": "lucro_real",
            },
        )
        assert response.status_code == 422
        data = response.json()
        campos = [c["campo"] for c in data["campos_invalidos"]]
        assert "ano" in campos

    def test_uf_origem_invalida_retorna_422(self, client: TestClient):
        """Invalid origin UF returns 422 with structured error."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2026,
                "uf_origem": "XX",
                "uf_destino": "RJ",
                "regime": "lucro_real",
            },
        )
        assert response.status_code == 422
        data = response.json()
        campos = [c["campo"] for c in data["campos_invalidos"]]
        assert "uf_origem" in campos

    def test_uf_destino_invalida_retorna_422(self, client: TestClient):
        """Invalid destination UF returns 422 with structured error."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2026,
                "uf_origem": "SP",
                "uf_destino": "ZZ",
                "regime": "lucro_real",
            },
        )
        assert response.status_code == 422
        data = response.json()
        campos = [c["campo"] for c in data["campos_invalidos"]]
        assert "uf_destino" in campos

    def test_regime_invalido_retorna_422(self, client: TestClient):
        """Invalid regime returns 422 with structured error."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2026,
                "uf_origem": "SP",
                "uf_destino": "RJ",
                "regime": "mei",
            },
        )
        assert response.status_code == 422
        data = response.json()
        campos = [c["campo"] for c in data["campos_invalidos"]]
        assert "regime" in campos

    def test_multiplos_erros_retornados_de_uma_vez(self, client: TestClient):
        """Multiple invalid parameters return all errors in a single response."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2050,
                "uf_origem": "XX",
                "uf_destino": "YY",
                "regime": "invalido",
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert len(data["campos_invalidos"]) == 4
        campos = [c["campo"] for c in data["campos_invalidos"]]
        assert "ano" in campos
        assert "uf_origem" in campos
        assert "uf_destino" in campos
        assert "regime" in campos

    def test_erro_contem_timestamp(self, client: TestClient):
        """Error response includes a timestamp field."""
        response = client.get(
            "/tools/tabela-transicao",
            params={
                "ano": 2025,
                "uf_origem": "SP",
                "uf_destino": "RJ",
                "regime": "lucro_real",
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert "timestamp" in data
