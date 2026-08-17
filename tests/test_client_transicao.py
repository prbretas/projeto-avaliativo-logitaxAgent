"""Unit tests for the Tool_Transicao client with retry and fallback.

Tests Requirements 5.5, 5.6, 5.7:
- Timeout and retry behavior
- Fallback to local JSON when API is unavailable
- Warning message includes file version
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.tools.client_transicao import (
    BACKOFF_BASE_SECONDS,
    MAX_RETRIES,
    ConsultaTransicaoResult,
    consultar_tabela_transicao,
)


@pytest.mark.asyncio
async def test_fallback_quando_api_indisponivel():
    """When all retries fail, the client should fall back to local JSON.

    Validates Requirement 5.6: IF all retries fail, THEN fall back to local JSON
    and set fallback_usado=True.
    """
    with patch("src.tools.client_transicao.asyncio.sleep", new_callable=AsyncMock):
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
            result = await consultar_tabela_transicao(
                ano=2026,
                uf_origem="SP",
                uf_destino="RJ",
                regime="lucro_real",
                endpoint_url="http://localhost:9999/tools/tabela-transicao",
            )

    assert isinstance(result, ConsultaTransicaoResult)
    assert result.fallback_usado is True
    assert result.dados.ano == 2026
    assert result.dados.aliquota_cbs_pct == 0.9
    assert result.dados.aliquota_ibs_pct == 0.1
    assert result.fonte == "tabela_local_v1.0"


@pytest.mark.asyncio
async def test_fallback_inclui_warning_com_versao():
    """When fallback is used, warning should mention the file version.

    Validates Requirement 5.7: warning containing the fallback file version identifier.
    """
    with patch("src.tools.client_transicao.asyncio.sleep", new_callable=AsyncMock):
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
            result = await consultar_tabela_transicao(
                ano=2030,
                uf_origem="MG",
                uf_destino="SP",
                regime="lucro_presumido",
                endpoint_url="http://localhost:9999/tools/tabela-transicao",
            )

    assert result.fallback_usado is True
    assert result.warning is not None
    assert "v1.0" in result.warning
    assert "FALLBACK" in result.warning
    assert "podem diferir" in result.warning


@pytest.mark.asyncio
async def test_sucesso_na_api_sem_fallback():
    """When the API responds successfully, no fallback should be used."""
    mock_response_data = {
        "ano": 2026,
        "fase": "teste",
        "aliquota_cbs_pct": 0.9,
        "aliquota_ibs_pct": 0.1,
        "aliquota_icms_pct_da_base": 100.0,
        "aliquota_combinada_nova_pct": 1.0,
        "versao": "v1.0",
        "oficial": True,
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await consultar_tabela_transicao(
            ano=2026,
            uf_origem="SP",
            uf_destino="RJ",
            regime="lucro_real",
        )

    assert result.fallback_usado is False
    assert result.dados.ano == 2026
    assert result.dados.aliquota_cbs_pct == 0.9
    assert result.fonte == "api_transicao_v1.0"
    assert result.warning is None


@pytest.mark.asyncio
async def test_retry_com_sucesso_na_segunda_tentativa():
    """When the first attempt fails but the second succeeds, no fallback is used."""
    mock_response_data = {
        "ano": 2027,
        "fase": "transicao",
        "aliquota_cbs_pct": 8.8,
        "aliquota_ibs_pct": 0.1,
        "aliquota_icms_pct_da_base": 100.0,
        "aliquota_combinada_nova_pct": 8.9,
        "versao": "v1.0",
        "oficial": False,
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data
    mock_response.raise_for_status = MagicMock()

    # First call raises timeout, second succeeds
    with patch("src.tools.client_transicao.asyncio.sleep", new_callable=AsyncMock):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[httpx.TimeoutException("timeout"), mock_response],
        ):
            result = await consultar_tabela_transicao(
                ano=2027,
                uf_origem="SP",
                uf_destino="MG",
                regime="lucro_real",
            )

    assert result.fallback_usado is False
    assert result.dados.ano == 2027
    assert result.fonte == "api_transicao_v1.0"


@pytest.mark.asyncio
async def test_fallback_para_todos_anos_disponiveis():
    """Fallback should work for all years available in the local file (2026–2033)."""
    with patch("src.tools.client_transicao.asyncio.sleep", new_callable=AsyncMock):
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("refused")):
            for ano in range(2026, 2034):
                result = await consultar_tabela_transicao(
                    ano=ano,
                    uf_origem="SP",
                    uf_destino="RJ",
                    regime="lucro_real",
                    endpoint_url="http://localhost:9999/tools/tabela-transicao",
                )
                assert result.fallback_usado is True
                assert result.dados.ano == ano


@pytest.mark.asyncio
async def test_fallback_ano_inexistente_levanta_erro():
    """Fallback should raise ValueError for a year not in the local file."""
    with patch("src.tools.client_transicao.asyncio.sleep", new_callable=AsyncMock):
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(ValueError, match="não encontrado"):
                await consultar_tabela_transicao(
                    ano=2025,
                    uf_origem="SP",
                    uf_destino="RJ",
                    regime="lucro_real",
                    endpoint_url="http://localhost:9999/tools/tabela-transicao",
                )


@pytest.mark.asyncio
async def test_retry_respeita_backoff_exponencial():
    """Retry delays should follow exponential backoff: 1s, 2s."""
    sleep_calls: list[float] = []

    async def mock_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    with patch("src.tools.client_transicao.asyncio.sleep", side_effect=mock_sleep):
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
            await consultar_tabela_transicao(
                ano=2026,
                uf_origem="SP",
                uf_destino="RJ",
                regime="lucro_real",
                endpoint_url="http://localhost:9999/tools/tabela-transicao",
            )

    # Should have 2 backoff sleeps: 1s (2^0 * 1) and 2s (2^1 * 1)
    assert len(sleep_calls) == MAX_RETRIES
    assert sleep_calls[0] == BACKOFF_BASE_SECONDS * 1  # 1s
    assert sleep_calls[1] == BACKOFF_BASE_SECONDS * 2  # 2s
