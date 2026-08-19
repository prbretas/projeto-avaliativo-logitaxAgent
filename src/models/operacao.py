"""Pydantic model for freight operation input (OperacaoFrete)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Valid Brazilian UF codes (27 states + DF)
UFS_VALIDAS = frozenset(
    [
        "AC",
        "AL",
        "AM",
        "AP",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MG",
        "MS",
        "MT",
        "PA",
        "PB",
        "PE",
        "PI",
        "PR",
        "RJ",
        "RN",
        "RO",
        "RR",
        "RS",
        "SC",
        "SE",
        "SP",
        "TO",
    ]
)

# Valid year range for the transition period
ANO_MINIMO = 2026
ANO_MAXIMO = 2033

# Freight value limits
VALOR_FRETE_MINIMO = 0.0  # exclusive (must be > 0)
VALOR_FRETE_MAXIMO = 999_999_999.99


class OperacaoFrete(BaseModel):
    """Input model representing a freight operation for tax simulation.

    Validates all required fields per Requirements 1.1–1.7:
    - modal: type of freight transport
    - origem_uf / destino_uf: valid Brazilian state codes
    - regime_tributario: tax regime of the operator
    - valor_frete: positive freight value up to 999,999,999.99
    - data_referencia: reference date with year in [2026, 2033]
    - observacoes: optional free-text field (max 500 chars, sanitization target)
    """

    modal: Literal["rodoviario", "aereo", "ferroviario", "aquaviario"] = Field(
        ...,
        description="Tipo de modal de transporte de frete",
    )
    origem_uf: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="UF de origem (código de 2 letras)",
    )
    destino_uf: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="UF de destino (código de 2 letras)",
    )
    regime_tributario: Literal["lucro_real", "lucro_presumido", "simples_nacional"] = Field(
        ...,
        description="Regime tributário do transportador",
    )
    valor_frete: float = Field(
        ...,
        gt=VALOR_FRETE_MINIMO,
        le=VALOR_FRETE_MAXIMO,
        description="Valor do frete em reais (> 0 e <= 999.999.999,99)",
    )
    data_referencia: date = Field(
        ...,
        description="Data de referência para a simulação (ano entre 2026 e 2033)",
    )
    observacoes: str | None = Field(
        default=None,
        max_length=500,
        description="Campo livre de observações (máximo 500 caracteres)",
    )

    @field_validator("origem_uf", "destino_uf")
    @classmethod
    def validar_uf(cls, v: str) -> str:
        """Validate that UF is one of the 27 valid Brazilian state codes."""
        v_upper = v.upper()
        if v_upper not in UFS_VALIDAS:
            raise ValueError(f"UF '{v}' inválida. UFs válidas: {sorted(UFS_VALIDAS)}")
        return v_upper

    @field_validator("data_referencia")
    @classmethod
    def validar_ano_referencia(cls, v: date) -> date:
        """Validate that the reference date year is within 2026–2033."""
        if v.year < ANO_MINIMO or v.year > ANO_MAXIMO:
            raise ValueError(
                f"Ano {v.year} fora do intervalo suportado [{ANO_MINIMO}, {ANO_MAXIMO}]"
            )
        return v
