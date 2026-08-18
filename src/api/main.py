"""FastAPI application principal — endpoints do simulador IBS/CBS.

Endpoints:
- POST /simular — submete operação de frete para simulação
- GET /tools/tabela-transicao — consulta alíquotas da tabela de transição
- POST /review/{thread_id} — aprova ou rejeita resultado pendente
- GET /observabilidade/{thread_id} — retorna timeline completa de execução

Requirements: 5.1, 10.1, 11.4, 11.5
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.models.operacao import OperacaoFrete
from src.models.erro import ErroEstruturado
from src.tools.tabela_transicao import router as tools_router

logger = logging.getLogger(__name__)

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
    status: str = "processing"
    message: str = "Simulação iniciada com sucesso"


class ReviewRequest(BaseModel):
    """Request body for POST /review/{thread_id}."""

    aprovado: bool = Field(..., description="True para aprovar, False para rejeitar")
    motivo_rejeicao: str | None = Field(None, description="Motivo da rejeição")


class ReviewResponse(BaseModel):
    """Response for POST /review/{thread_id}."""

    thread_id: str
    decisao: str
    timestamp: str


class ObservabilidadeResponse(BaseModel):
    """Response for GET /observabilidade/{thread_id}."""

    thread_id: str
    timeline: list[dict[str, Any]]
    status: str


# --- Endpoints ---


@app.post(
    "/simular",
    response_model=SimularResponse,
    status_code=202,
    responses={422: {"model": ErroEstruturado}},
)
async def simular(request: SimularRequest) -> SimularResponse:
    """Submete operação de frete para simulação de impacto IBS/CBS.

    Valida a operação e inicia o grafo de simulação assíncrono.
    Retorna thread_id para acompanhamento.
    """
    # Generate unique thread_id
    thread_id = str(uuid.uuid4())

    # Validate operation (will raise ValidationError → 422 if invalid)
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

    # In production, this would kick off the LangGraph StateGraph async
    # For now, return the thread_id for tracking
    return SimularResponse(
        thread_id=thread_id,
        status="processing",
        message="Simulação iniciada com sucesso. Use GET /observabilidade/"
        f"{thread_id} para acompanhar.",
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

    Processa a decisão humana para a simulação identificada por thread_id.
    """
    # In production, this would:
    # 1. Retrieve state from checkpointer by thread_id
    # 2. Call process_human_decision()
    # 3. Resume the graph if approved

    decisao = "aprovado" if request.aprovado else "rejeitado"
    timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(
        "POST /review/%s: decisão=%s, motivo=%s",
        thread_id,
        decisao,
        request.motivo_rejeicao or "N/A",
    )

    return ReviewResponse(
        thread_id=thread_id,
        decisao=decisao,
        timestamp=timestamp,
    )


@app.get(
    "/observabilidade/{thread_id}",
    response_model=ObservabilidadeResponse,
)
async def get_observabilidade(thread_id: str) -> ObservabilidadeResponse:
    """Retorna timeline completa de execução da simulação.

    Mostra todos os nodes executados, tempos e status para o thread_id.
    """
    # In production, this would query the audit/log table
    # for all events related to this thread_id

    logger.info("GET /observabilidade/%s", thread_id)

    return ObservabilidadeResponse(
        thread_id=thread_id,
        timeline=[],
        status="pending_implementation",
    )


# --- Health check ---


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
