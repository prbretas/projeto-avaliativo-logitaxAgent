"""Pydantic model for structured error responses (ErroEstruturado)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CampoInvalido(BaseModel):
    """Detail about a single invalid field in the input."""

    campo: str = Field(
        ...,
        description="Nome do campo inválido",
    )
    motivo: str = Field(
        ...,
        description="Descrição do motivo da invalidez",
    )


class ErroEstruturado(BaseModel):
    """Structured error response that returns ALL validation errors at once.

    Per Requirement 1.8, the system must not fail-fast on individual
    fields — all errors are detected and returned in a single response.
    """

    erro: str = Field(
        ...,
        description="Mensagem descritiva geral do erro",
    )
    campos_invalidos: list[CampoInvalido] = Field(
        default_factory=list,
        description="Lista de campos inválidos com seus respectivos motivos",
    )
    thread_id: str | None = Field(
        default=None,
        description="Identificador da sessão/thread (quando disponível)",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp ISO 8601 do momento do erro",
    )
