"""Pydantic model for audit trail records (RegistroAuditoria)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RegistroAuditoria(BaseModel):
    """Audit record for tracking human decisions, security events, and system actions.

    Each record is persisted in the SQLite audit table with correlation
    to a thread_id for full execution reconstruction (Requirement 11.2).
    """

    id: int = Field(
        ...,
        description="Identificador único do registro de auditoria",
    )
    thread_id: str = Field(
        ...,
        description="Identificador da sessão/thread correlacionada",
    )
    evento: Literal["aprovacao", "rejeicao", "seguranca", "fallback", "timeout", "erro"] = Field(
        ...,
        description="Tipo do evento auditado",
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp ISO 8601 do evento",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Detalhes adicionais do evento (formato livre)",
    )
