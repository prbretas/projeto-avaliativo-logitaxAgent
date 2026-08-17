"""Node parse_operacao — validates raw JSON input against OperacaoFrete schema.

This is the first node in the LangGraph StateGraph pipeline. It receives a
raw dict (JSON payload) and validates it against the Pydantic OperacaoFrete
model. All validation errors are collected and returned at once (fail-fast
coletivo) per Requirement 1.8.

Behavior:
- If valid: returns {"operacao": validated_model, "error": None}
- If invalid: returns {"operacao": None, "error": ErroEstruturado} with ALL
  detected validation failures listed in campos_invalidos.

Requirements: 1.1, 1.7, 1.8
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ValidationError

from src.models.erro import CampoInvalido, ErroEstruturado
from src.models.operacao import OperacaoFrete


def parse_operacao(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw JSON payload against the OperacaoFrete schema.

    Uses Pydantic model_validate to attempt parsing. On failure, extracts
    ALL validation errors from the ValidationError and constructs a single
    ErroEstruturado response containing every invalid field.

    Args:
        payload: Raw dict representing the JSON input from the user.

    Returns:
        A dict with keys:
        - "operacao": The validated OperacaoFrete instance, or None if invalid.
        - "error": An ErroEstruturado instance with all errors, or None if valid.
    """
    try:
        operacao = OperacaoFrete.model_validate(payload)
        return {"operacao": operacao, "error": None}
    except ValidationError as exc:
        campos_invalidos = _extrair_campos_invalidos(exc)
        erro = ErroEstruturado(
            erro="Erro de validação na operação de frete",
            campos_invalidos=campos_invalidos,
            thread_id=None,
            timestamp=datetime.now(),
        )
        return {"operacao": None, "error": erro}


def _extrair_campos_invalidos(exc: ValidationError) -> list[CampoInvalido]:
    """Extract all invalid fields from a Pydantic ValidationError.

    Iterates over every error in the ValidationError (which already captures
    ALL validation failures, not just the first) and maps them to
    CampoInvalido entries.

    Args:
        exc: The Pydantic ValidationError containing one or more errors.

    Returns:
        List of CampoInvalido with the field path and failure reason.
    """
    campos: list[CampoInvalido] = []
    for error in exc.errors():
        # Build field path from the location tuple (e.g., ("valor_frete",) -> "valor_frete")
        campo = ".".join(str(loc) for loc in error["loc"])
        motivo = error["msg"]
        campos.append(CampoInvalido(campo=campo, motivo=motivo))
    return campos
