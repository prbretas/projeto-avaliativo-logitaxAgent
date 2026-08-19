"""Typed state definition for the LangGraph StateGraph.

Defines the AgentGraphState as a TypedDict with proper annotations
for LangGraph state management. Uses Annotated with operator.add for
list fields that accumulate values across nodes.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentGraphState(TypedDict, total=False):
    """Typed state for the LangGraph StateGraph.

    All fields are optional (total=False) so nodes can return partial updates.
    LangGraph merges partial returns into the accumulated state.
    """

    # Core operation data
    operacao: Any  # OperacaoFrete model or dict
    thread_id: str
    error: Any  # ErroEstruturado or None

    # Regime routing
    credit_factor: float

    # Reclassification control
    tentativas_reclassificacao: int
    revisao_manual: bool

    # Simulation results
    resultados_por_ano: list

    # RAG context
    trechos_rag: list

    # Justification
    justificativa: str | None
    comentario_agente: str

    # Human review
    aprovado_humano: bool | None
    review_summary: dict

    # Export
    export_status: str
    webhook_sent: bool
    exported_at: str

    # Enrichment
    dados_mcp: dict

    # Alerts (accumulated across nodes)
    alertas: list

    # Injection detection
    injection_detected: bool
