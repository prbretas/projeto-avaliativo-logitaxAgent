"""Pydantic model for the LangGraph agent state (AgentState)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.models.operacao import OperacaoFrete
from src.models.resultado import ResultadoAno

# Maximum reclassification attempts before forcing human review
MAX_TENTATIVAS_RECLASSIFICACAO = 3


class AgentState(BaseModel):
    """Shared state for the LangGraph StateGraph.

    Tracks the entire simulation lifecycle from input validation through
    human review and export. The `tentativas_reclassificacao` counter
    enforces the stopping condition (max 3 attempts).
    """

    operacao: OperacaoFrete = Field(
        ...,
        description="Operação de frete validada",
    )
    tentativas_reclassificacao: int = Field(
        default=0,
        ge=0,
        le=MAX_TENTATIVAS_RECLASSIFICACAO,
        description="Contador de tentativas de reclassificação (máximo 3)",
    )
    resultados_por_ano: list[ResultadoAno] = Field(
        default_factory=list,
        description="Resultados parciais por ano simulado",
    )
    trechos_rag: list[str] = Field(
        default_factory=list,
        description="Trechos legislativos recuperados via RAG (ChromaDB)",
    )
    justificativa: str | None = Field(
        default=None,
        description="Justificativa gerada pelo LLM com citações legislativas",
    )
    aprovado_humano: bool | None = Field(
        default=None,
        description="Decisão humana: True (aprovado), False (rejeitado), None (pendente)",
    )
    thread_id: str = Field(
        ...,
        description="Identificador único da sessão/thread",
    )
    revisao_manual: bool = Field(
        default=False,
        description="Flag indicando escalação forçada para revisão humana",
    )

    @field_validator("tentativas_reclassificacao")
    @classmethod
    def validar_tentativas(cls, v: int) -> int:
        """Ensure reclassification attempts do not exceed maximum."""
        if v > MAX_TENTATIVAS_RECLASSIFICACAO:
            raise ValueError(
                f"tentativas_reclassificacao ({v}) excede o máximo permitido "
                f"({MAX_TENTATIVAS_RECLASSIFICACAO})"
            )
        return v
