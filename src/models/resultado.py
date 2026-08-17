"""Pydantic models for simulation results (ResultadoAno, ResultadoConsolidado)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.models.operacao import ANO_MAXIMO, ANO_MINIMO, OperacaoFrete


class ResultadoAno(BaseModel):
    """Partial result for a single year's tax comparison.

    Contains the tax values under both regimes, the delta percentage,
    and metadata about the data source used.
    """

    ano: int = Field(
        ...,
        ge=ANO_MINIMO,
        le=ANO_MAXIMO,
        description="Ano de referência da simulação",
    )
    valor_tributo_atual: float = Field(
        ...,
        ge=0.0,
        description="Valor do tributo sob Regime_Atual (arredondado 2 casas decimais)",
    )
    valor_tributo_novo: float = Field(
        ...,
        ge=0.0,
        description="Valor do tributo sob Regime_Novo (arredondado 2 casas decimais)",
    )
    delta_percentual: float = Field(
        ...,
        description="Diferença percentual: ((novo - atual) / atual) × 100, 2 casas decimais",
    )
    fonte_tool: str = Field(
        ...,
        description="Identificador da fonte de dados (ex: 'api_transicao_v1' ou 'tabela_local_v1')",
    )
    fallback_usado: bool = Field(
        ...,
        description="Indica se dados de fallback local foram utilizados",
    )

    @field_validator("ano")
    @classmethod
    def validar_ano(cls, v: int) -> int:
        """Validate year is within the transition period."""
        if v < ANO_MINIMO or v > ANO_MAXIMO:
            raise ValueError(
                f"Ano {v} fora do intervalo suportado [{ANO_MINIMO}, {ANO_MAXIMO}]"
            )
        return v


class ResultadoConsolidado(BaseModel):
    """Consolidated simulation response containing results for all simulated years.

    This is the final output presented to the user after human approval.
    """

    thread_id: str = Field(
        ...,
        description="Identificador único da sessão",
    )
    operacao: OperacaoFrete = Field(
        ...,
        description="Operação de frete original validada",
    )
    resultados: list[ResultadoAno] = Field(
        ...,
        description="Lista de resultados por ano, ordenada cronologicamente",
    )
    justificativa: str = Field(
        ...,
        description="Justificativa em linguagem natural com citações legislativas",
    )
    fontes_citadas: list[str] = Field(
        default_factory=list,
        description="Lista de fontes legislativas citadas na justificativa",
    )
    aprovado: bool = Field(
        ...,
        description="Indica se o resultado foi aprovado pelo operador humano",
    )
    timestamp_aprovacao: datetime = Field(
        ...,
        description="Timestamp ISO 8601 da aprovação humana",
    )
    alertas: list[str] = Field(
        default_factory=list,
        description="Alertas sobre a simulação (ex: 'fallback utilizado para ano 2027')",
    )
