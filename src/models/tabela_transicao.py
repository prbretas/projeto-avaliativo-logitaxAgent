"""Pydantic model for the transition table API response (TabelaTransicaoResponse)."""

from pydantic import BaseModel, Field, field_validator

from src.models.operacao import ANO_MAXIMO, ANO_MINIMO


class TabelaTransicaoResponse(BaseModel):
    """Response schema for the Tool_Transicao endpoint (GET /tools/tabela-transicao).

    Contains the tax rates for IBS/CBS transition by year, including
    the ICMS phase-out percentage and version metadata.
    """

    ano: int = Field(
        ...,
        ge=ANO_MINIMO,
        le=ANO_MAXIMO,
        description="Ano de referência da transição",
    )
    fase: str = Field(
        ...,
        description="Fase da transição (ex: 'teste', 'transicao', 'plena')",
    )
    aliquota_cbs_pct: float = Field(
        ...,
        ge=0.0,
        description="Alíquota CBS em percentual",
    )
    aliquota_ibs_pct: float = Field(
        ...,
        ge=0.0,
        description="Alíquota IBS em percentual",
    )
    aliquota_icms_pct_da_base: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentual do ICMS base mantido (0–100, onde 100 = ICMS integral)",
    )
    aliquota_combinada_nova_pct: float = Field(
        ...,
        ge=0.0,
        description="Alíquota combinada do Regime_Novo (CBS + IBS) em percentual",
    )
    versao: str = Field(
        ...,
        description="Identificador de versão dos dados (ex: 'v1.0')",
    )
    oficial: bool = Field(
        ...,
        description="Indica se os dados são de fonte oficial",
    )
    aliquota_icms_interestadual_pct: float = Field(
        default=12.0,
        ge=0.0,
        le=30.0,
        description="Alíquota ICMS interestadual aplicável à rota (CONFAZ)",
    )

    @field_validator("ano")
    @classmethod
    def validar_ano(cls, v: int) -> int:
        """Validate year is within the transition period."""
        if v < ANO_MINIMO or v > ANO_MAXIMO:
            raise ValueError(f"Ano {v} fora do intervalo suportado [{ANO_MINIMO}, {ANO_MAXIMO}]")
        return v
