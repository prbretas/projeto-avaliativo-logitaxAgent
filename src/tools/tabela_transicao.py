"""FastAPI router for Tool_Transicao — tax transition table lookup endpoint.

Exposes GET /tools/tabela-transicao accepting query parameters:
  - ano: int (2026–2033)
  - uf_origem: str (valid 2-letter Brazilian UF code)
  - uf_destino: str (valid 2-letter Brazilian UF code)
  - regime: str (lucro_real | lucro_presumido | simples_nacional)

Returns TabelaTransicaoResponse with transition rates for the requested year.
Returns HTTP 422 with ErroEstruturado for invalid parameters.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from src.models.erro import CampoInvalido, ErroEstruturado
from src.models.operacao import ANO_MAXIMO, ANO_MINIMO, UFS_VALIDAS
from src.models.tabela_transicao import TabelaTransicaoResponse
from src.tools.icms_interestadual import consultar_icms_interestadual

# Path to the local transition table JSON
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
TABELA_TRANSICAO_PATH = DATA_DIR / "tabela_transicao_local.json"

# Valid regime values
REGIMES_VALIDOS = frozenset(["lucro_real", "lucro_presumido", "simples_nacional"])

router = APIRouter(prefix="/tools", tags=["tools"])


def _carregar_tabela_transicao() -> list[dict]:
    """Load the transition table from local JSON file."""
    with open(TABELA_TRANSICAO_PATH, encoding="utf-8") as f:
        return json.load(f)


def _validar_parametros(
    ano: int,
    uf_origem: str,
    uf_destino: str,
    regime: str,
) -> list[CampoInvalido]:
    """Validate all query parameters and collect all errors at once."""
    erros: list[CampoInvalido] = []

    if ano < ANO_MINIMO or ano > ANO_MAXIMO:
        erros.append(
            CampoInvalido(
                campo="ano",
                motivo=f"Ano {ano} fora do intervalo suportado [{ANO_MINIMO}, {ANO_MAXIMO}]",
            )
        )

    uf_origem_upper = uf_origem.upper()
    if uf_origem_upper not in UFS_VALIDAS:
        erros.append(
            CampoInvalido(
                campo="uf_origem",
                motivo=f"UF '{uf_origem}' inválida. UFs válidas: {sorted(UFS_VALIDAS)}",
            )
        )

    uf_destino_upper = uf_destino.upper()
    if uf_destino_upper not in UFS_VALIDAS:
        erros.append(
            CampoInvalido(
                campo="uf_destino",
                motivo=f"UF '{uf_destino}' inválida. UFs válidas: {sorted(UFS_VALIDAS)}",
            )
        )

    if regime not in REGIMES_VALIDOS:
        erros.append(
            CampoInvalido(
                campo="regime",
                motivo=(f"Regime '{regime}' inválido. Valores aceitos: {sorted(REGIMES_VALIDOS)}"),
            )
        )

    return erros


@router.get(
    "/tabela-transicao",
    response_model=TabelaTransicaoResponse,
    responses={
        422: {"model": ErroEstruturado, "description": "Parâmetros inválidos"},
    },
    summary="Consulta alíquotas da tabela de transição IBS/CBS",
    description=(
        "Retorna as alíquotas de transição para o ano solicitado. "
        "Os parâmetros uf_origem, uf_destino e regime são validados, "
        "mas nesta versão as alíquotas dependem apenas do ano."
    ),
)
async def consultar_tabela_transicao(
    ano: int = Query(..., description="Ano de referência (2026–2033)"),
    uf_origem: str = Query(..., description="UF de origem (código de 2 letras)"),
    uf_destino: str = Query(..., description="UF de destino (código de 2 letras)"),
    regime: str = Query(..., description="Regime tributário"),
) -> TabelaTransicaoResponse | JSONResponse:
    """Lookup transition table rates for a given year.

    Validates all parameters and returns HTTP 422 with structured errors
    if any parameter is invalid. Otherwise returns the transition rates
    for the requested year from the local JSON data source.
    """
    # Validate all parameters at once
    erros = _validar_parametros(ano, uf_origem, uf_destino, regime)

    if erros:
        erro_response = ErroEstruturado(
            erro="Parâmetros inválidos na consulta da tabela de transição",
            campos_invalidos=erros,
            timestamp=datetime.now(UTC),
        )
        return JSONResponse(
            status_code=422,
            content=erro_response.model_dump(mode="json"),
        )

    # Load transition data and find the entry for the requested year
    tabela = _carregar_tabela_transicao()
    entrada = next((item for item in tabela if item["ano"] == ano), None)

    if entrada is None:
        # This shouldn't happen if validation passes, but handle defensively
        erro_response = ErroEstruturado(
            erro=f"Dados não encontrados para o ano {ano}",
            campos_invalidos=[
                CampoInvalido(campo="ano", motivo=f"Nenhum registro para o ano {ano}")
            ],
            timestamp=datetime.now(UTC),
        )
        return JSONResponse(
            status_code=422,
            content=erro_response.model_dump(mode="json"),
        )

    return TabelaTransicaoResponse(
        **entrada,
        aliquota_icms_interestadual_pct=consultar_icms_interestadual(
            uf_origem.upper(), uf_destino.upper()
        ),
    )
