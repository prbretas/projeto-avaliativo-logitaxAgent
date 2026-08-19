"""Node: enriquecer_operacao — Enrich freight operation with real fiscal data via MCP.

Uses the mcp-fiscal-brasil library (SDK mode) to:
1. Validate if the carrier/operator is registered as Simples Nacional
2. Enrich the operation with additional CNPJ data if available

This node runs BEFORE route_regime to automatically validate/correct the
tax regime informed by the user, using real data from Receita Federal.

Fallback behavior: If mcp-fiscal-brasil is unavailable or CNPJ is not provided,
the node simply passes through without modification (accepts user-informed regime).

Requirements: 5 (Tool externa), 4 (Roteamento condicional)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("logitaxAgent.enriquecer")


async def _consultar_simples_mcp(cnpj: str) -> dict[str, Any] | None:
    """Attempt to query Simples Nacional status via mcp-fiscal-brasil SDK.

    Args:
        cnpj: CNPJ string (with or without formatting).

    Returns:
        Dict with 'optante' (bool) and 'data_opcao' if available, or None on failure.
    """
    try:
        from mcp_fiscal_brasil import FiscalBrasil

        async with FiscalBrasil() as fiscal:
            resultado = await fiscal.consultar_simples_nacional(cnpj)
            return resultado
    except ImportError:
        logger.info("mcp-fiscal-brasil not installed. Skipping regime validation.")
        return None
    except Exception as exc:
        logger.warning(
            "Failed to query MCP fiscal-brasil for CNPJ %s: %s",
            cnpj[:8] + "...",
            str(exc),
        )
        return None


async def _consultar_cnpj_mcp(cnpj: str) -> dict[str, Any] | None:
    """Attempt to query CNPJ data via mcp-fiscal-brasil SDK.

    Args:
        cnpj: CNPJ string (with or without formatting).

    Returns:
        Dict with company data if available, or None on failure.
    """
    try:
        from mcp_fiscal_brasil import FiscalBrasil

        async with FiscalBrasil() as fiscal:
            resultado = await fiscal.consultar_cnpj(cnpj)
            return resultado
    except ImportError:
        return None
    except Exception as exc:
        logger.warning("Failed to query CNPJ via MCP: %s", str(exc))
        return None


async def enriquecer_operacao(state: dict[str, Any]) -> dict[str, Any]:
    """Enrich the freight operation with data from MCP fiscal-brasil.

    Behavior:
    - If cnpj_transportador is provided in the operation, queries Simples Nacional
    - If the result confirms/contradicts the user-informed regime, logs and updates
    - If MCP is unavailable, passes through without changes (fallback = trust user input)

    Args:
        state: Current AgentState dict. Expected keys:
            - operacao: OperacaoFrete (or dict)
            - thread_id: str

    Returns:
        Partial state update with:
            - operacao: potentially updated with validated regime
            - dados_mcp: dict with enrichment data (for justification context)
            - alertas: any warnings about regime mismatch
    """
    operacao = state.get("operacao")
    thread_id = state.get("thread_id", "unknown")
    alertas = list(state.get("alertas", []))

    # Extract CNPJ if provided (optional field for enrichment)
    if isinstance(operacao, dict):
        cnpj = operacao.get("cnpj_transportador")
        regime_informado = operacao.get("regime_tributario", "")
    else:
        cnpj = getattr(operacao, "cnpj_transportador", None)
        regime_informado = getattr(operacao, "regime_tributario", "")

    dados_mcp: dict[str, Any] = {
        "mcp_disponivel": False,
        "regime_validado": False,
        "dados_empresa": None,
    }

    # If no CNPJ provided, skip enrichment (trust user input)
    if not cnpj:
        logger.info(
            "No CNPJ provided. Skipping MCP enrichment.",
            extra={"thread_id": thread_id},
        )
        return {
            "dados_mcp": dados_mcp,
            "alertas": alertas,
        }

    # Step 1: Query Simples Nacional status
    simples_data = await _consultar_simples_mcp(cnpj)

    if simples_data is not None:
        dados_mcp["mcp_disponivel"] = True
        optante_simples = simples_data.get("optante", False)

        # Validate regime against real data
        if optante_simples and regime_informado != "simples_nacional":
            alertas.append(
                f"MCP: CNPJ é optante do Simples Nacional (confirmado pela Receita Federal), "
                f"mas regime informado foi '{regime_informado}'. "
                f"Regime ajustado automaticamente para 'simples_nacional'."
            )
            logger.warning(
                "Regime mismatch: user informed '%s' but CNPJ is "
                "Simples Nacional. Auto-correcting.",
                regime_informado,
                extra={"thread_id": thread_id, "cnpj_prefix": cnpj[:8]},
            )
            # Update operation regime
            if isinstance(operacao, dict):
                operacao["regime_tributario"] = "simples_nacional"
            else:
                operacao.regime_tributario = "simples_nacional"  # type: ignore
            dados_mcp["regime_validado"] = True

        elif not optante_simples and regime_informado == "simples_nacional":
            alertas.append(
                "MCP: CNPJ NÃO é optante do Simples Nacional (confirmado pela Receita Federal), "
                "mas regime informado foi 'simples_nacional'. "
                "Verifique com o transportador. Mantendo regime informado."
            )
            logger.warning(
                "Regime mismatch: user informed 'simples_nacional' but CNPJ is NOT optante.",
                extra={"thread_id": thread_id, "cnpj_prefix": cnpj[:8]},
            )
        else:
            dados_mcp["regime_validado"] = True
            logger.info(
                "Regime validated via MCP: '%s' confirmed.",
                regime_informado,
                extra={"thread_id": thread_id},
            )

    # Step 2: Query CNPJ data for enrichment (optional)
    cnpj_data = await _consultar_cnpj_mcp(cnpj)
    if cnpj_data:
        dados_mcp["dados_empresa"] = {
            "razao_social": cnpj_data.get("razao_social"),
            "cnae_principal": cnpj_data.get("cnae_fiscal"),
            "situacao": cnpj_data.get("situacao_cadastral"),
            "porte": cnpj_data.get("porte"),
        }

    return {
        "operacao": operacao,
        "dados_mcp": dados_mcp,
        "alertas": alertas,
    }
