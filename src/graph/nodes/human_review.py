"""Node human_review: interrupt para decisão humana com LangGraph.

Implementa o ponto de interrupção (interrupt) no grafo LangGraph onde a
execução pausa até que um revisor humano aprove ou rejeite o resultado
da simulação.

Apresenta resumo com: valores por regime, delta, flag fallback, justificativa.
Trata aprovação → export_result; rejeição → log + terminar.
Timeout de 24h → expirar sessão.
Retrieval idempotente (consultar sem alterar estado).

Requirements: 10.1, 10.2, 10.3, 10.5, 10.6
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Timeout for human review (24 hours in seconds)
REVIEW_TIMEOUT_SECONDS = 24 * 60 * 60


def _build_review_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Build a structured summary for the human reviewer.

    Presents: values per regime, delta, fallback flag, justification.

    Args:
        state: Current AgentState dict.

    Returns:
        Summary dict with relevant simulation data for human decision.
    """
    operacao = state.get("operacao", {})
    resultados = state.get("resultados_por_ano", [])
    justificativa = state.get("justificativa", "")
    alertas = state.get("alertas", [])

    # Extract operation info (support dict and Pydantic model)
    if hasattr(operacao, "model_dump"):
        op_info = operacao.model_dump()
    elif hasattr(operacao, "dict"):
        op_info = operacao.dict()
    else:
        op_info = dict(operacao) if operacao else {}

    # Check for fallback usage in alerts
    fallback_usado = any("fallback" in str(a).lower() for a in alertas)

    # Build results summary
    resultados_resumo = []
    for r in resultados:
        if hasattr(r, "model_dump"):
            resultados_resumo.append(r.model_dump())
        elif hasattr(r, "dict"):
            resultados_resumo.append(r.dict())
        elif isinstance(r, dict):
            resultados_resumo.append(r)

    return {
        "operacao": {
            "modal": op_info.get("modal", ""),
            "origem_uf": op_info.get("origem_uf", ""),
            "destino_uf": op_info.get("destino_uf", ""),
            "regime_tributario": op_info.get("regime_tributario", ""),
            "valor_frete": op_info.get("valor_frete", 0),
        },
        "resultados_por_ano": resultados_resumo,
        "justificativa": justificativa or "(sem justificativa gerada)",
        "fallback_usado": fallback_usado,
        "alertas": alertas,
        "thread_id": state.get("thread_id", ""),
        "revisao_manual": state.get("revisao_manual", False),
        "timestamp_solicitacao": datetime.now(timezone.utc).isoformat(),
    }


def get_review_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Retrieve the review summary without altering state (idempotent).

    This function can be called multiple times to check the pending review
    without modifying the state. Satisfies Requirements 10.6.

    Args:
        state: Current AgentState dict.

    Returns:
        Review summary dict.
    """
    return _build_review_summary(state)


def human_review(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: human review interrupt point.

    This node represents the interrupt in the LangGraph StateGraph.
    When the graph reaches this node, execution pauses (interrupt)
    until a human decision is provided via the /review/{thread_id} endpoint.

    The node:
    1. Builds a review summary for the human reviewer
    2. Sets state to indicate pending review
    3. Returns partial state update

    The actual interrupt mechanism is handled by LangGraph's interrupt_before
    or interrupt_after configuration on the StateGraph.

    Approval flow: aprovado_humano=True → proceed to export_result
    Rejection flow: aprovado_humano=False → log + terminate

    Args:
        state: Current AgentState dict.

    Returns:
        Partial state update with review metadata.
    """
    thread_id = state.get("thread_id", "unknown")

    logger.info(
        "human_review: simulação pendente de revisão humana (thread_id=%s)",
        thread_id,
    )

    # Build summary for reviewer
    summary = _build_review_summary(state)

    # Log summary for observability
    logger.info(
        "human_review: resumo gerado - regime=%s, resultados=%d anos, "
        "fallback=%s, revisao_manual=%s",
        summary["operacao"].get("regime_tributario", ""),
        len(summary["resultados_por_ano"]),
        summary["fallback_usado"],
        summary["revisao_manual"],
    )

    # The state update indicates this node was reached
    # The actual interrupt is configured at the StateGraph level
    return {
        "review_summary": summary,
    }


def process_human_decision(
    state: dict[str, Any],
    aprovado: bool,
    motivo_rejeicao: str | None = None,
) -> dict[str, Any]:
    """Process the human reviewer's decision.

    Called when a human approves or rejects via POST /review/{thread_id}.

    Args:
        state: Current AgentState dict.
        aprovado: True if approved, False if rejected.
        motivo_rejeicao: Optional rejection reason.

    Returns:
        Partial state update with decision recorded.
    """
    thread_id = state.get("thread_id", "unknown")

    if aprovado:
        logger.info(
            "human_review: APROVADO pelo revisor (thread_id=%s)",
            thread_id,
        )
        return {
            "aprovado_humano": True,
        }
    else:
        logger.info(
            "human_review: REJEITADO pelo revisor (thread_id=%s, motivo=%s)",
            thread_id,
            motivo_rejeicao or "não informado",
        )
        return {
            "aprovado_humano": False,
        }


def is_review_expired(state: dict[str, Any]) -> bool:
    """Check if the pending review has expired (24h timeout).

    Args:
        state: Current AgentState dict.

    Returns:
        True if the review has timed out.
    """
    summary = state.get("review_summary", {})
    timestamp_str = summary.get("timestamp_solicitacao")

    if not timestamp_str:
        return False

    try:
        timestamp = datetime.fromisoformat(timestamp_str)
        elapsed = (datetime.now(timezone.utc) - timestamp).total_seconds()
        return elapsed > REVIEW_TIMEOUT_SECONDS
    except (ValueError, TypeError):
        return False
