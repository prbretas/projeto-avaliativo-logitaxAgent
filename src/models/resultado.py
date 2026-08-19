"""Pydantic models for simulation results (ResultadoAno, ResultadoConsolidado)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.models.operacao import ANO_MAXIMO, ANO_MINIMO, OperacaoFrete


class DetalheRegimeAtual(BaseModel):
    """Breakdown of current regime taxes (PIS + COFINS + ICMS)."""

    pis_aliquota_pct: float = Field(..., description="Alíquota do PIS aplicada (%)")
    pis_valor: float = Field(..., ge=0.0, description="Valor do PIS (R$)")
    cofins_aliquota_pct: float = Field(..., description="Alíquota da COFINS aplicada (%)")
    cofins_valor: float = Field(..., ge=0.0, description="Valor da COFINS (R$)")
    icms_aliquota_pct: float = Field(..., description="Alíquota do ICMS interestadual aplicada (%)")
    icms_valor: float = Field(..., ge=0.0, description="Valor do ICMS (R$)")
    total: float = Field(..., ge=0.0, description="Soma total dos tributos atuais (R$)")


class DetalheRegimeNovo(BaseModel):
    """Breakdown of new IBS/CBS regime taxes."""

    cbs_aliquota_pct: float = Field(..., description="Alíquota da CBS aplicada (%)")
    cbs_valor: float = Field(..., ge=0.0, description="Valor da CBS (R$)")
    ibs_aliquota_pct: float = Field(..., description="Alíquota do IBS aplicada (%)")
    ibs_valor: float = Field(..., ge=0.0, description="Valor do IBS (R$)")
    icms_residual_aliquota_pct: float = Field(
        ..., description="Alíquota do ICMS residual no ano (% da base original)"
    )
    icms_residual_valor: float = Field(..., ge=0.0, description="Valor do ICMS residual (R$)")
    total: float = Field(..., ge=0.0, description="Soma total dos tributos novos (R$)")
    oficial: bool = Field(
        ..., description="Indica se as alíquotas usadas são oficiais (True) ou estimativas (False)"
    )


class ResultadoAno(BaseModel):
    """Partial result for a single year's tax comparison.

    Contains the tax values under both regimes, the delta percentage,
    detailed breakdown per tax component, and metadata about the data source used.
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
    detalhe_regime_atual: DetalheRegimeAtual = Field(
        ...,
        description="Breakdown detalhado dos tributos do regime atual",
    )
    detalhe_regime_novo: DetalheRegimeNovo = Field(
        ...,
        description="Breakdown detalhado dos tributos do regime novo (IBS/CBS)",
    )
    economia_ou_aumento: str = Field(
        ...,
        description="Texto descritivo: 'Economia de R$ X' ou 'Aumento de R$ X'",
    )

    @field_validator("ano")
    @classmethod
    def validar_ano(cls, v: int) -> int:
        """Validate year is within the transition period."""
        if v < ANO_MINIMO or v > ANO_MAXIMO:
            raise ValueError(f"Ano {v} fora do intervalo suportado [{ANO_MINIMO}, {ANO_MAXIMO}]")
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
    comentario_agente: str = Field(
        default="",
        description=(
            "Análise contextualizada do agente: resumo do impacto, causa, recomendação e avisos"
        ),
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
