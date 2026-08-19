"""FastAPI application principal — endpoints do simulador IBS/CBS.

Endpoints:
- POST /simular — submete operação de frete e executa o grafo LangGraph completo
- GET /tools/tabela-transicao — consulta alíquotas da tabela de transição
- POST /review/{thread_id} — aprova ou rejeita resultado pendente
- GET /observabilidade/{thread_id} — retorna timeline completa de execução
- GET /resultado/{thread_id} — retorna resultado da simulação persistido

Requirements: 5.1, 10.1, 11.4, 11.5
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.models.operacao import OperacaoFrete
from src.models.erro import ErroEstruturado
from src.tools.tabela_transicao import router as tools_router
from src.persistence.checkpointer import SessionCheckpointer
from src.observability.logger import (
    get_audit_timeline,
    log_audit_event,
    setup_structured_logging,
)

logger = logging.getLogger(__name__)

# Initialize structured logging
setup_structured_logging()

# Initialize session checkpointer
checkpointer = SessionCheckpointer()

app = FastAPI(
    title="LogitaxAgent — Simulador IBS/CBS",
    description="Sistema agêntico para simulação de impacto da Reforma Tributária (IBS/CBS) sobre operações de frete.",
    version="0.1.0",
)

# Include the tools router (GET /tools/tabela-transicao)
app.include_router(tools_router)


# --- Request/Response Models ---


class SimularRequest(BaseModel):
    """Request body for POST /simular."""

    modal: str = Field(..., description="Modal de transporte")
    origem_uf: str = Field(..., description="UF de origem (2 letras)")
    destino_uf: str = Field(..., description="UF de destino (2 letras)")
    regime_tributario: str = Field(..., description="Regime tributário")
    valor_frete: float = Field(..., gt=0, description="Valor do frete em R$")
    data_referencia: str = Field(..., description="Data de referência (YYYY-MM-DD)")
    observacoes: str | None = Field(None, description="Observações (max 500 chars)")


class SimularResponse(BaseModel):
    """Response for POST /simular."""

    thread_id: str
    status: str
    message: str
    resultados_por_ano: list[dict[str, Any]] = Field(default_factory=list)
    justificativa: str | None = None
    comentario_agente: str | None = None
    alertas: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    """Request body for POST /review/{thread_id}."""

    aprovado: bool = Field(..., description="True para aprovar, False para rejeitar")
    motivo_rejeicao: str | None = Field(None, description="Motivo da rejeição")


class ReviewResponse(BaseModel):
    """Response for POST /review/{thread_id}."""

    thread_id: str
    decisao: str
    timestamp: str
    export_status: str | None = None


class ObservabilidadeResponse(BaseModel):
    """Response for GET /observabilidade/{thread_id}."""

    thread_id: str
    timeline: list[dict[str, Any]]
    status: str


class ResultadoResponse(BaseModel):
    """Response for GET /resultado/{thread_id}."""

    thread_id: str
    status: str
    state: dict[str, Any] = Field(default_factory=dict)


# --- Graph Execution Helper ---


async def _execute_graph(initial_state: dict[str, Any]) -> dict[str, Any]:
    """Execute the LangGraph StateGraph with the given initial state.

    The graph runs until it hits the interrupt_before=["human_review"].
    For the API flow, we skip human_review interrupt and run the full
    pipeline up to (but not including) export_result. The caller can
    then approve via POST /review/{thread_id} to trigger export.

    Args:
        initial_state: Dict with operation data to seed the graph.

    Returns:
        Final state dict after graph execution.
    """
    from src.graph.graph import build_graph

    # Build graph WITHOUT interrupt (for simplified API flow that runs end-to-end)
    # The human_review node still executes (builds summary) but doesn't block
    graph = build_graph()
    compiled = graph.compile(interrupt_before=[])

    # Execute the graph
    final_state = await compiled.ainvoke(initial_state)

    return final_state


async def _execute_graph_with_interrupt(initial_state: dict[str, Any]) -> dict[str, Any]:
    """Execute graph with interrupt at human_review.

    The graph pauses before human_review. The state is saved via checkpointer
    and can be resumed via POST /review/{thread_id}.

    Args:
        initial_state: Dict with operation data to seed the graph.

    Returns:
        State dict at the point of interruption.
    """
    from src.graph.graph import build_graph

    graph = build_graph()
    compiled = graph.compile(interrupt_before=["human_review"])

    # ainvoke will run until the interrupt point and return partial state
    partial_state = await compiled.ainvoke(initial_state)

    return partial_state


# --- Endpoints ---


@app.post(
    "/simular",
    response_model=SimularResponse,
    status_code=200,
    responses={422: {"model": ErroEstruturado}},
)
async def simular(request: SimularRequest) -> SimularResponse:
    """Submete operação de frete e executa simulação completa via LangGraph.

    Executa o grafo completo: parse → sanitize → enriquecer → route →
    simular_regime → check_reclassificacao → simular_anos → retrieve_context →
    generate_justification → human_review → export_result.

    Retorna resultados, justificativa e comentário analítico.
    """
    # Generate unique thread_id
    thread_id = str(uuid.uuid4())

    # Validate operation
    try:
        operacao = OperacaoFrete(
            modal=request.modal,
            origem_uf=request.origem_uf,
            destino_uf=request.destino_uf,
            regime_tributario=request.regime_tributario,
            valor_frete=request.valor_frete,
            data_referencia=request.data_referencia,
            observacoes=request.observacoes,
        )
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail={
                "erro": "Validação falhou",
                "campos_invalidos": str(e),
                "thread_id": thread_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    logger.info(
        "POST /simular: operação aceita (thread_id=%s, regime=%s, "
        "valor_frete=%.2f)",
        thread_id,
        operacao.regime_tributario,
        operacao.valor_frete,
    )

    # Log audit event for simulation start
    log_audit_event(
        thread_id=thread_id,
        event_type="simulacao",
        node_name="api_simular",
        status="started",
        details=f"modal={request.modal}, {request.origem_uf}→{request.destino_uf}, "
        f"regime={request.regime_tributario}, valor={request.valor_frete}",
    )

    # Prepare initial state for the graph
    initial_state: dict[str, Any] = {
        "operacao": operacao,
        "thread_id": thread_id,
        "tentativas_reclassificacao": 0,
        "revisao_manual": False,
        "resultados_por_ano": [],
        "trechos_rag": [],
        "justificativa": None,
        "alertas": [],
        "aprovado_humano": True,  # Auto-approve for simplified API flow
    }

    # Execute the graph
    try:
        final_state = await _execute_graph(initial_state)
    except Exception as e:
        logger.error(
            "Graph execution failed (thread_id=%s): %s",
            thread_id,
            str(e),
            exc_info=True,
        )
        log_audit_event(
            thread_id=thread_id,
            event_type="erro",
            node_name="graph_execution",
            status="error",
            details=str(e),
            recovery_action="returning partial results",
        )
        raise HTTPException(
            status_code=500,
            detail={
                "erro": "Falha na execução do grafo",
                "thread_id": thread_id,
                "detalhes": str(e),
            },
        )

    # Extract results from final state
    resultados_por_ano = final_state.get("resultados_por_ano", [])
    justificativa = final_state.get("justificativa")
    comentario_agente = final_state.get("comentario_agente")
    alertas = final_state.get("alertas", [])

    # Serialize resultados for response
    resultados_serialized = []
    for r in resultados_por_ano:
        if hasattr(r, "model_dump"):
            resultados_serialized.append(r.model_dump())
        elif isinstance(r, dict):
            resultados_serialized.append(r)

    # Persist state via checkpointer
    state_to_persist = {
        "thread_id": thread_id,
        "operacao": operacao.model_dump(mode="json") if hasattr(operacao, "model_dump") else operacao,
        "resultados_por_ano": resultados_serialized,
        "justificativa": justificativa,
        "comentario_agente": comentario_agente,
        "alertas": alertas,
        "aprovado_humano": final_state.get("aprovado_humano"),
        "export_status": final_state.get("export_status", "completed"),
        "trechos_rag": final_state.get("trechos_rag", []),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    checkpointer.save(thread_id, state_to_persist)

    # Log audit event for completion
    log_audit_event(
        thread_id=thread_id,
        event_type="simulacao",
        node_name="api_simular",
        status="completed",
        details=f"resultados={len(resultados_serialized)} anos, "
        f"justificativa={'gerada' if justificativa else 'não gerada'}",
    )

    logger.info(
        "POST /simular: concluído (thread_id=%s, resultados=%d)",
        thread_id,
        len(resultados_serialized),
    )

    # Determine status
    status = "completed" if resultados_serialized else "error"

    return SimularResponse(
        thread_id=thread_id,
        status=status,
        message=f"Simulação concluída com {len(resultados_serialized)} anos calculados.",
        resultados_por_ano=resultados_serialized,
        justificativa=justificativa,
        comentario_agente=comentario_agente,
        alertas=alertas,
    )


@app.post(
    "/review/{thread_id}",
    response_model=ReviewResponse,
)
async def review_simulacao(
    thread_id: str,
    request: ReviewRequest,
) -> ReviewResponse:
    """Aprova ou rejeita resultado pendente de simulação.

    Recupera o estado persistido, aplica a decisão humana e, se aprovado,
    dispara o webhook n8n.
    """
    # Load state from checkpointer
    state = checkpointer.load(thread_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhuma simulação encontrada para thread_id '{thread_id}'",
        )

    decisao = "aprovado" if request.aprovado else "rejeitado"
    timestamp = datetime.now(timezone.utc).isoformat()

    # Log audit event for human decision
    log_audit_event(
        thread_id=thread_id,
        event_type="decisao_humana",
        node_name="human_review",
        status="info",
        details=f"decisão={decisao}, motivo={request.motivo_rejeicao or 'N/A'}",
    )

    # Update state with decision
    state["aprovado_humano"] = request.aprovado
    state["decisao_timestamp"] = timestamp

    export_status = None

    if request.aprovado:
        # Trigger webhook export
        from src.graph.nodes.export_result import _build_webhook_payload, _send_webhook_sync

        webhook_payload = _build_webhook_payload(state)
        webhook_sent = _send_webhook_sync(webhook_payload)
        export_status = "exported" if webhook_sent else "export_webhook_failed"
        state["export_status"] = export_status

        log_audit_event(
            thread_id=thread_id,
            event_type="webhook",
            node_name="export_result",
            status="info" if webhook_sent else "warning",
            details=f"webhook_sent={webhook_sent}",
        )
    else:
        state["export_status"] = "rejected"
        export_status = "rejected"

    # Persist updated state
    checkpointer.save(thread_id, state)

    logger.info(
        "POST /review/%s: decisão=%s, export=%s",
        thread_id,
        decisao,
        export_status,
    )

    return ReviewResponse(
        thread_id=thread_id,
        decisao=decisao,
        timestamp=timestamp,
        export_status=export_status,
    )


@app.get(
    "/observabilidade/{thread_id}",
    response_model=ObservabilidadeResponse,
)
async def get_observabilidade(thread_id: str) -> ObservabilidadeResponse:
    """Retorna timeline completa de execução da simulação.

    Mostra todos os events registrados no audit trail para o thread_id,
    incluindo nodes executados, decisões, erros e tempos.
    """
    logger.info("GET /observabilidade/%s", thread_id)

    # Get timeline from audit SQLite
    timeline = get_audit_timeline(thread_id)

    # Determine status based on timeline events
    if not timeline:
        status = "not_found"
    elif any(e.get("event_type") == "erro" for e in timeline):
        status = "error"
    elif any(e.get("status") == "completed" for e in timeline):
        status = "completed"
    else:
        status = "in_progress"

    return ObservabilidadeResponse(
        thread_id=thread_id,
        timeline=timeline,
        status=status,
    )


@app.get(
    "/resultado/{thread_id}",
    response_model=ResultadoResponse,
)
async def get_resultado(thread_id: str) -> ResultadoResponse:
    """Retorna o resultado completo de uma simulação persistida."""
    state = checkpointer.load(thread_id)

    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhuma simulação encontrada para thread_id '{thread_id}'",
        )

    status = state.get("export_status", "unknown")

    return ResultadoResponse(
        thread_id=thread_id,
        status=status,
        state=state,
    )


# --- Health check ---


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
