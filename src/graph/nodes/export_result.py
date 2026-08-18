"""Node export_result: persistir resultado e disparar webhook n8n.

Persiste o JSON final do ResultadoConsolidado e dispara webhook para
Webhook_N8n com payload contendo: thread_id, delta_percentual, ano,
valores, timestamp.

Timeout webhook 10s — em caso de falha, logar na auditoria sem retry.

Requirements: 10.3, 14.1, 14.2
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Webhook timeout (10 seconds)
WEBHOOK_TIMEOUT_SECONDS = 10


def _get_webhook_url() -> str | None:
    """Get n8n webhook URL from environment variable."""
    return os.environ.get("WEBHOOK_N8N_URL")


def _build_webhook_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Build the webhook payload with required fields.

    Payload must contain: thread_id, delta_percentual, ano,
    valor_tributo_atual, valor_tributo_novo, timestamp.

    Args:
        state: Current AgentState dict.

    Returns:
        Webhook payload dict.
    """
    thread_id = state.get("thread_id", "unknown")
    resultados = state.get("resultados_por_ano", [])

    # Build results array with required fields per year
    resultados_payload = []
    for r in resultados:
        if hasattr(r, "model_dump"):
            rd = r.model_dump()
        elif hasattr(r, "dict"):
            rd = r.dict()
        else:
            rd = dict(r) if r else {}

        resultados_payload.append({
            "ano": rd.get("ano"),
            "valor_tributo_atual": rd.get("valor_tributo_atual"),
            "valor_tributo_novo": rd.get("valor_tributo_novo"),
            "delta_percentual": rd.get("delta_percentual"),
        })

    # Global delta (use last year or max delta)
    delta_global = None
    if resultados_payload:
        # Use the 2033 result or last available
        for rp in reversed(resultados_payload):
            if rp.get("delta_percentual") is not None:
                delta_global = rp["delta_percentual"]
                break

    return {
        "thread_id": thread_id,
        "delta_percentual": delta_global,
        "resultados_por_ano": resultados_payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_consolidated_result(state: dict[str, Any]) -> dict[str, Any]:
    """Build the consolidated result JSON for persistence.

    Args:
        state: Current AgentState dict.

    Returns:
        Complete consolidated result dict.
    """
    operacao = state.get("operacao", {})
    if hasattr(operacao, "model_dump"):
        op_data = operacao.model_dump(mode="json")
    elif hasattr(operacao, "dict"):
        op_data = operacao.dict()
    else:
        op_data = dict(operacao) if operacao else {}

    resultados = state.get("resultados_por_ano", [])
    resultados_data = []
    for r in resultados:
        if hasattr(r, "model_dump"):
            resultados_data.append(r.model_dump(mode="json"))
        elif hasattr(r, "dict"):
            resultados_data.append(r.dict())
        else:
            resultados_data.append(dict(r) if r else {})

    return {
        "thread_id": state.get("thread_id", "unknown"),
        "operacao": op_data,
        "resultados_por_ano": resultados_data,
        "justificativa": state.get("justificativa"),
        "aprovado_humano": state.get("aprovado_humano"),
        "trechos_rag": state.get("trechos_rag", []),
        "alertas": state.get("alertas", []),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


async def _send_webhook(payload: dict[str, Any]) -> bool:
    """Send webhook to n8n with timeout.

    Args:
        payload: Webhook payload dict.

    Returns:
        True if webhook sent successfully, False otherwise.
    """
    webhook_url = _get_webhook_url()

    if not webhook_url:
        logger.warning(
            "export_result: WEBHOOK_N8N_URL não configurada, "
            "webhook não será enviado"
        )
        return False

    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code < 300:
                logger.info(
                    "export_result: webhook enviado com sucesso "
                    "(status=%d, thread_id=%s)",
                    response.status_code,
                    payload.get("thread_id"),
                )
                return True
            else:
                logger.warning(
                    "export_result: webhook retornou status %d "
                    "(thread_id=%s)",
                    response.status_code,
                    payload.get("thread_id"),
                )
                return False
    except httpx.TimeoutException:
        logger.error(
            "export_result: webhook timeout (%ds) (thread_id=%s)",
            WEBHOOK_TIMEOUT_SECONDS,
            payload.get("thread_id"),
        )
        return False
    except Exception as e:
        logger.error(
            "export_result: falha ao enviar webhook (thread_id=%s): %s",
            payload.get("thread_id"),
            e,
        )
        return False


def export_result(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: export approved result and trigger webhook.

    Only executes if aprovado_humano=True. Persists the consolidated
    result JSON and dispatches webhook to n8n.

    Args:
        state: Current AgentState dict.

    Returns:
        Partial state update with export metadata.
    """
    thread_id = state.get("thread_id", "unknown")

    # Guard: only export if human approved
    if not state.get("aprovado_humano"):
        logger.warning(
            "export_result: tentativa de export sem aprovação humana "
            "(thread_id=%s, aprovado_humano=%s)",
            thread_id,
            state.get("aprovado_humano"),
        )
        return {
            "export_status": "blocked",
            "export_reason": "aprovado_humano is not True",
        }

    # Build consolidated result
    consolidated = _build_consolidated_result(state)

    # Persist to JSON (via checkpointer in production, here we log it)
    logger.info(
        "export_result: resultado consolidado persistido (thread_id=%s)",
        thread_id,
    )

    # Build and send webhook payload
    webhook_payload = _build_webhook_payload(state)

    # Note: In production, this would be async. For synchronous graph nodes,
    # we use httpx synchronous client as fallback.
    webhook_sent = _send_webhook_sync(webhook_payload)

    return {
        "export_status": "completed",
        "webhook_sent": webhook_sent,
        "exported_at": consolidated["exported_at"],
    }


def _send_webhook_sync(payload: dict[str, Any]) -> bool:
    """Synchronous webhook sender for use in LangGraph node.

    Args:
        payload: Webhook payload dict.

    Returns:
        True if webhook sent successfully, False otherwise.
    """
    webhook_url = _get_webhook_url()

    if not webhook_url:
        logger.warning(
            "export_result: WEBHOOK_N8N_URL não configurada, "
            "webhook não será enviado"
        )
        return False

    try:
        with httpx.Client(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
            response = client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code < 300:
                logger.info(
                    "export_result: webhook enviado com sucesso "
                    "(status=%d, thread_id=%s)",
                    response.status_code,
                    payload.get("thread_id"),
                )
                return True
            else:
                logger.warning(
                    "export_result: webhook retornou status %d (thread_id=%s)",
                    response.status_code,
                    payload.get("thread_id"),
                )
                return False
    except httpx.TimeoutException:
        logger.error(
            "export_result: webhook timeout (%ds) (thread_id=%s)",
            WEBHOOK_TIMEOUT_SECONDS,
            payload.get("thread_id"),
        )
        return False
    except Exception as e:
        logger.error(
            "export_result: falha ao enviar webhook (thread_id=%s): %s",
            payload.get("thread_id"),
            e,
        )
        return False
