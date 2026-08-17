"""Fan-out/fan-in node for parallel multi-year tax simulation.

Implements parallel simulation across milestone years [2026, 2027, 2030, 2033].
For each year:
1. Consult transition table (via client_transicao)
2. Calculate tax under Regime_Atual
3. Calculate tax under Regime_Novo
4. Compute delta percentual

Handles partial failure: if a year fails, logs the error and continues
with successful ones. Results are aggregated into a sorted list[ResultadoAno].

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.graph.nodes.calculo import (
    calcular_delta_percentual,
    calcular_tributo_atual,
    calcular_tributo_novo,
)
from src.models.resultado import ResultadoAno
from src.tools.client_transicao import consultar_tabela_transicao

logger = logging.getLogger(__name__)

# Default milestone years for fan-out when no specific year is given
ANOS_MARCO = [2026, 2027, 2030, 2033]


async def _simular_ano_individual(
    ano: int,
    valor_frete: float,
    regime: str,
    uf_origem: str,
    uf_destino: str,
    credit_factor: float,
) -> ResultadoAno:
    """Simulate tax calculation for a single year.

    Args:
        ano: Reference year for the simulation.
        valor_frete: Freight value in BRL.
        regime: Tax regime (lucro_real, lucro_presumido, simples_nacional).
        uf_origem: Origin UF code.
        uf_destino: Destination UF code.
        credit_factor: Credit factor (1.0 for regular, 0.0 for Simples).

    Returns:
        ResultadoAno with calculated tax values and metadata.

    Raises:
        Exception: If the transition table consultation or calculation fails.
    """
    # Step 1: Consult transition table
    resultado_tool = await consultar_tabela_transicao(
        ano=ano,
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        regime=regime,
    )

    tabela = resultado_tool.dados

    # Step 2: Calculate tax under Regime_Atual
    tributo_atual = calcular_tributo_atual(valor_frete)

    # Step 3: Calculate tax under Regime_Novo
    tributo_novo = calcular_tributo_novo(
        valor_frete=valor_frete,
        tabela=tabela,
        regime=regime,
        credit_factor=credit_factor,
    )

    # Step 4: Compute delta percentual
    delta = calcular_delta_percentual(tributo_atual, tributo_novo)

    return ResultadoAno(
        ano=ano,
        valor_tributo_atual=tributo_atual,
        valor_tributo_novo=tributo_novo,
        delta_percentual=delta,
        fonte_tool=resultado_tool.fonte,
        fallback_usado=resultado_tool.fallback_usado,
    )


async def simular_ano(state: dict[str, Any]) -> dict[str, Any]:
    """Fan-out/fan-in node: simulate tax impact across milestone years in parallel.

    Reads the operation from state, determines which years to simulate,
    and runs all year calculations concurrently using asyncio.gather with
    return_exceptions=True for partial failure handling.

    Args:
        state: Current AgentState dict. Expected keys:
            - operacao: OperacaoFrete (or dict with required fields)
            - credit_factor: float (1.0 for regular, 0.0 for Simples)

    Returns:
        Partial state update with:
            - resultados_por_ano: list[ResultadoAno] sorted by year ascending
            - alertas: list[str] with warnings for any failed years
    """
    operacao = state["operacao"]
    credit_factor = state.get("credit_factor", 1.0)

    # Extract operation fields (support both Pydantic model and dict)
    if hasattr(operacao, "valor_frete"):
        valor_frete = operacao.valor_frete
        regime = operacao.regime_tributario
        uf_origem = operacao.origem_uf
        uf_destino = operacao.destino_uf
    else:
        valor_frete = operacao["valor_frete"]
        regime = operacao["regime_tributario"]
        uf_origem = operacao["origem_uf"]
        uf_destino = operacao["destino_uf"]

    # Determine years to simulate
    anos = ANOS_MARCO

    # Fan-out: launch parallel tasks for each year
    tasks = [
        _simular_ano_individual(
            ano=ano,
            valor_frete=valor_frete,
            regime=regime,
            uf_origem=uf_origem,
            uf_destino=uf_destino,
            credit_factor=credit_factor,
        )
        for ano in anos
    ]

    # Use return_exceptions=True to handle partial failures gracefully
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Fan-in: separate successes from failures
    resultados: list[ResultadoAno] = []
    alertas: list[str] = []

    for ano, result in zip(anos, results):
        if isinstance(result, Exception):
            error_msg = f"Falha no cálculo para ano {ano}: {type(result).__name__}: {result}"
            logger.error(error_msg)
            alertas.append(error_msg)
        else:
            resultados.append(result)

    # Sort results by year ascending (requirement 3.2)
    resultados.sort(key=lambda r: r.ano)

    if not resultados and alertas:
        logger.error(
            "Todos os anos falharam no fan-out. Alertas: %s", alertas
        )

    return {
        "resultados_por_ano": resultados,
        "alertas": alertas,
    }
