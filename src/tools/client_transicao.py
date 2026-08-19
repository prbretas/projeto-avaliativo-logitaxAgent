"""Client for the Tool_Transicao endpoint with retry and local fallback.

Implements Requirements 5.5, 5.6, 5.7:
- Timeout of 5 seconds per request
- Retry up to 2 times with exponential backoff (1s, 2s)
- Fallback to data/tabela_transicao_local.json when all retries fail
- Sets fallback_usado=True and includes warning with file version

Mode selection (via TOOL_TRANSICAO_MODE env var):
- "api" (default): tries HTTP endpoint first, falls back to local JSON
- "local": uses local JSON directly (no HTTP calls, no delay)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.models.tabela_transicao import TabelaTransicaoResponse

logger = logging.getLogger(__name__)

# Mode selection: "api" (try HTTP first) or "local" (skip HTTP, use JSON directly)
TOOL_TRANSICAO_MODE = os.getenv("TOOL_TRANSICAO_MODE", "local")

# Default endpoint URL (configurable via env var)
DEFAULT_ENDPOINT_URL = os.getenv(
    "TOOL_TRANSICAO_URL", "http://localhost:8000/tools/tabela-transicao"
)

# Retry configuration
REQUEST_TIMEOUT_SECONDS = 5.0
MAX_RETRIES = 2
BACKOFF_BASE_SECONDS = 1.0  # delays: 1s, 2s

# Path to local fallback file
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
TABELA_TRANSICAO_LOCAL_PATH = DATA_DIR / "tabela_transicao_local.json"


@dataclass
class ConsultaTransicaoResult:
    """Result of a transition table consultation.

    Attributes:
        dados: The TabelaTransicaoResponse with tax rates for the requested year.
        fallback_usado: True if the local fallback file was used instead of the API.
        fonte: Data source identifier (e.g., "api_transicao_v1" or "tabela_local_v1.0").
        warning: Optional warning message when fallback is used.
    """

    dados: TabelaTransicaoResponse
    fallback_usado: bool
    fonte: str
    warning: str | None = None


async def consultar_tabela_transicao(
    ano: int,
    uf_origem: str,
    uf_destino: str,
    regime: str,
    *,
    endpoint_url: str = DEFAULT_ENDPOINT_URL,
) -> ConsultaTransicaoResult:
    """Consult the Tool_Transicao endpoint with retry and fallback.

    Behavior depends on TOOL_TRANSICAO_MODE:
    - "local": reads directly from data/tabela_transicao_local.json (instant, no HTTP)
    - "api": makes HTTP GET to the endpoint, retries 2x, then fallback to local JSON

    Args:
        ano: Reference year (2026–2033).
        uf_origem: Origin UF code (2 letters).
        uf_destino: Destination UF code (2 letters).
        regime: Tax regime (lucro_real, lucro_presumido, simples_nacional).
        endpoint_url: URL of the Tool_Transicao endpoint.

    Returns:
        ConsultaTransicaoResult with the transition data, fallback flag, and source.
    """
    # Local mode: skip HTTP entirely, use JSON file directly
    if TOOL_TRANSICAO_MODE == "local":
        return _carregar_fallback_local(ano, uf_origem, uf_destino)

    # API mode: try HTTP endpoint with retries
    params = {
        "ano": ano,
        "uf_origem": uf_origem,
        "uf_destino": uf_destino,
        "regime": regime,
    }

    last_exception: Exception | None = None

    for attempt in range(1 + MAX_RETRIES):  # initial + 2 retries = 3 attempts total
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(endpoint_url, params=params)
                response.raise_for_status()

                data = response.json()
                dados = TabelaTransicaoResponse(**data)

                return ConsultaTransicaoResult(
                    dados=dados,
                    fallback_usado=False,
                    fonte=f"api_transicao_{dados.versao}",
                    warning=None,
                )

        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as exc:
            last_exception = exc
            attempt_num = attempt + 1
            logger.warning(
                "Tool_Transicao request failed (attempt %d/%d): %s",
                attempt_num,
                1 + MAX_RETRIES,
                str(exc),
            )

            # Apply backoff before retry (except after last attempt)
            if attempt < MAX_RETRIES:
                backoff_delay = BACKOFF_BASE_SECONDS * (2**attempt)
                logger.info(
                    "Retrying in %.1f seconds (backoff exponencial)...",
                    backoff_delay,
                )
                await asyncio.sleep(backoff_delay)

    # All retries exhausted — use local fallback
    logger.warning(
        "All %d attempts to Tool_Transicao failed. Using local fallback: %s. Last error: %s",
        1 + MAX_RETRIES,
        TABELA_TRANSICAO_LOCAL_PATH,
        str(last_exception),
    )

    return _carregar_fallback_local(ano, uf_origem, uf_destino)


def _carregar_fallback_local(
    ano: int,
    uf_origem: str = "SP",
    uf_destino: str = "RJ",
) -> ConsultaTransicaoResult:
    """Load transition data from the local JSON fallback file.

    Args:
        ano: Reference year to look up in the local table.
        uf_origem: Origin UF for ICMS interestadual lookup.
        uf_destino: Destination UF for ICMS interestadual lookup.

    Returns:
        ConsultaTransicaoResult with fallback_usado=True and a warning message.

    Raises:
        ValueError: If the requested year is not found in the local file.
        FileNotFoundError: If the local fallback file does not exist.
    """
    from src.tools.icms_interestadual import consultar_icms_interestadual

    with open(TABELA_TRANSICAO_LOCAL_PATH, encoding="utf-8") as f:
        tabela: list[dict] = json.load(f)

    entrada = next((item for item in tabela if item["ano"] == ano), None)

    if entrada is None:
        raise ValueError(
            f"Ano {ano} não encontrado no arquivo de fallback local: {TABELA_TRANSICAO_LOCAL_PATH}"
        )

    # Add ICMS interestadual rate
    icms_rate = consultar_icms_interestadual(uf_origem, uf_destino)
    entrada["aliquota_icms_interestadual_pct"] = icms_rate

    dados = TabelaTransicaoResponse(**entrada)
    versao = dados.versao

    warning_msg = (
        f"[FALLBACK] Dados obtidos do arquivo local (versão {versao}). "
        f"As alíquotas podem diferir da fonte mais recente disponível."
    )
    logger.warning(warning_msg)

    return ConsultaTransicaoResult(
        dados=dados,
        fallback_usado=True,
        fonte=f"tabela_local_{versao}",
        warning=warning_msg,
    )
