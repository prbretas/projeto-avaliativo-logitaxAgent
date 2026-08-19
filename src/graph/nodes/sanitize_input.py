"""Node: sanitize_input — Neutralizes prompt injection in observacoes field.

This node processes the free-text `observacoes` field of an OperacaoFrete to:
1. Truncate content to a maximum of 500 characters.
2. Wrap content in a fenced delimiter block labeled "UNTRUSTED_USER_DATA".
3. Detect prompt injection patterns and log security events.
4. Enforce a 3-second timeout — block the operation if sanitization fails.

If the sanitizer fails (timeout or unhandled exception), the operation is blocked
from proceeding to prompt composition, and a security event is logged.

Requirements: 9.1, 9.2, 9.5
"""

from __future__ import annotations

import hashlib
import logging
import re
import signal
import time
from typing import Any

logger = logging.getLogger("logitaxAgent.security")

# Maximum allowed length for observacoes content
MAX_OBSERVACOES_LENGTH = 500

# Timeout in seconds for sanitization operation
SANITIZE_TIMEOUT_SECONDS = 3

# Regex patterns associated with prompt injection attempts.
# Each pattern is case-insensitive.
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore.*instru", re.IGNORECASE),
    re.compile(r"override.*rules", re.IGNORECASE),
    re.compile(r"skip.*review", re.IGNORECASE),
    re.compile(r"forget.*instructions", re.IGNORECASE),
    re.compile(r"you are now", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
]


class SanitizationError(Exception):
    """Raised when sanitization fails (timeout or unhandled exception).

    Requirement 9.5: If the Sanitizador node fails, the operation is blocked.
    """

    pass


class SanitizationTimeoutError(SanitizationError):
    """Raised when sanitization exceeds the 3-second timeout."""

    pass


def _compute_input_hash(content: str) -> str:
    """Compute SHA-256 hash of the raw input for audit logging.

    Args:
        content: Raw input string to hash.

    Returns:
        Hex string of the SHA-256 hash.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _detect_injection(content: str) -> list[str]:
    """Check content against known prompt injection patterns.

    Args:
        content: The text to scan for injection patterns.

    Returns:
        List of pattern strings that matched (empty if no injection detected).
    """
    detected: list[str] = []
    for pattern in INJECTION_PATTERNS:
        if pattern.search(content):
            detected.append(pattern.pattern)
    return detected


def _wrap_untrusted(content: str) -> str:
    """Wrap content in UNTRUSTED_USER_DATA delimiters.

    Args:
        content: The sanitized (truncated) text content.

    Returns:
        Content wrapped in fenced delimiter block.
    """
    return f"[UNTRUSTED_USER_DATA]\n{content}\n[/UNTRUSTED_USER_DATA]"


def _sanitize_observacoes(content: str, thread_id: str | None = None) -> tuple[str, bool]:
    """Core sanitization logic for the observacoes field.

    Steps:
    1. Truncate to MAX_OBSERVACOES_LENGTH characters.
    2. Detect prompt injection patterns and log if found.
    3. Wrap in UNTRUSTED_USER_DATA delimiters.

    Args:
        content: Raw observacoes text.
        thread_id: Thread identifier for correlation in logs.

    Returns:
        Tuple of (sanitized_content, injection_detected).
    """
    # Step 1: Truncate to 500 characters
    truncated = content[:MAX_OBSERVACOES_LENGTH]

    # Step 2: Detect injection patterns
    detected_patterns = _detect_injection(truncated)
    injection_detected = len(detected_patterns) > 0

    if injection_detected:
        input_hash = _compute_input_hash(content)
        logger.warning(
            "Prompt injection detected",
            extra={
                "event": "seguranca",
                "thread_id": thread_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "patterns_detected": detected_patterns,
                "input_hash": input_hash,
            },
        )

    # Step 3: Wrap in UNTRUSTED_USER_DATA delimiters
    wrapped = _wrap_untrusted(truncated)

    return wrapped, injection_detected


def sanitize_input(state: dict[str, Any]) -> dict[str, Any]:
    """Sanitize the observacoes field in the agent state.

    This is the main node function for the LangGraph StateGraph. It processes
    the `observacoes` field of the OperacaoFrete in `state["operacao"]`.

    If observacoes is None or empty, no sanitization is needed.
    If sanitization fails (timeout or exception), a SanitizationError is raised
    to block the operation from proceeding.

    The 3-second timeout is enforced using signal.alarm on Unix systems.
    On Windows (where signal.alarm is not available), a time-based check is used.
    For production deployment, timeout enforcement should be handled at the
    graph level (e.g., via asyncio.wait_for in async execution).

    Args:
        state: The AgentState-like dict containing state["operacao"] as an
               OperacaoFrete instance.

    Returns:
        Updated state dict with sanitized observacoes field. If injection is
        detected, state["injection_detected"] is set to True.

    Raises:
        SanitizationError: If sanitization fails (timeout or unhandled exception).
            The operation MUST NOT proceed to prompt composition.

    Requirements: 9.1, 9.2, 9.5
    """
    operacao = state.get("operacao")
    if operacao is None:
        raise SanitizationError("State does not contain 'operacao' field")

    thread_id = state.get("thread_id")

    # Access observacoes — support both Pydantic model and dict
    if hasattr(operacao, "observacoes"):
        observacoes = operacao.observacoes
    elif isinstance(operacao, dict):
        observacoes = operacao.get("observacoes")
    else:
        raise SanitizationError("Cannot access 'observacoes' from operacao")

    # If observacoes is None or empty, nothing to sanitize
    if not observacoes:
        return state

    # Enforce timeout
    start_time = time.monotonic()

    try:
        # Attempt sanitization with timeout enforcement
        sanitized, injection_detected = _perform_sanitization_with_timeout(observacoes, thread_id)
    except SanitizationTimeoutError:
        logger.error(
            "Sanitization timeout exceeded",
            extra={
                "event": "seguranca",
                "thread_id": thread_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "error": "timeout_exceeded_3s",
            },
        )
        raise SanitizationError(
            "Sanitization timed out (>3s). Operation blocked per Requirement 9.5."
        )
    except Exception as e:
        logger.error(
            "Sanitization unhandled exception",
            extra={
                "event": "seguranca",
                "thread_id": thread_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "error": str(e),
            },
        )
        raise SanitizationError(
            f"Sanitization failed: {e}. Operation blocked per Requirement 9.5."
        ) from e

    elapsed = time.monotonic() - start_time
    if elapsed > SANITIZE_TIMEOUT_SECONDS:
        logger.error(
            "Sanitization exceeded timeout post-execution",
            extra={
                "event": "seguranca",
                "thread_id": thread_id,
                "elapsed_seconds": elapsed,
            },
        )
        raise SanitizationError(
            "Sanitization timed out (>3s). Operation blocked per Requirement 9.5."
        )

    # Update the operacao's observacoes with the sanitized version
    if hasattr(operacao, "observacoes"):
        # For Pydantic models, create a copy with updated field
        updated_operacao = operacao.model_copy(update={"observacoes": sanitized})
        state["operacao"] = updated_operacao
    elif isinstance(operacao, dict):
        operacao["observacoes"] = sanitized
        state["operacao"] = operacao

    # Set injection flag in state if detected
    if injection_detected:
        state["injection_detected"] = True

    return state


def _perform_sanitization_with_timeout(content: str, thread_id: str | None) -> tuple[str, bool]:
    """Perform sanitization with 3-second timeout enforcement.

    Uses signal.alarm on Unix. On Windows, falls back to time-based checking.
    For production async execution, timeout should be enforced at graph level
    using asyncio.wait_for.

    Args:
        content: Raw observacoes text.
        thread_id: Thread ID for log correlation.

    Returns:
        Tuple of (sanitized_content, injection_detected).

    Raises:
        SanitizationTimeoutError: If sanitization exceeds 3 seconds.
    """
    # Try signal-based timeout (Unix only)
    if hasattr(signal, "SIGALRM"):
        return _sanitize_with_signal_timeout(content, thread_id)

    # Fallback: time-based check (Windows / environments without SIGALRM)
    return _sanitize_with_time_check(content, thread_id)


def _timeout_handler(signum: int, frame: Any) -> None:
    """Signal handler for SIGALRM timeout."""
    raise SanitizationTimeoutError("Sanitization exceeded 3-second timeout (SIGALRM)")


def _sanitize_with_signal_timeout(content: str, thread_id: str | None) -> tuple[str, bool]:
    """Sanitize with signal.alarm timeout (Unix only).

    Args:
        content: Raw observacoes text.
        thread_id: Thread ID for log correlation.

    Returns:
        Tuple of (sanitized_content, injection_detected).

    Raises:
        SanitizationTimeoutError: If sanitization exceeds 3 seconds.
    """
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(SANITIZE_TIMEOUT_SECONDS)
    try:
        result = _sanitize_observacoes(content, thread_id)
    finally:
        signal.alarm(0)  # Cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)  # Restore previous handler
    return result


def _sanitize_with_time_check(content: str, thread_id: str | None) -> tuple[str, bool]:
    """Sanitize with time-based timeout check (Windows compatible).

    Note: This is a post-execution check. For true preemptive timeout on Windows,
    use async execution with asyncio.wait_for at the graph level.

    Args:
        content: Raw observacoes text.
        thread_id: Thread ID for log correlation.

    Returns:
        Tuple of (sanitized_content, injection_detected).

    Raises:
        SanitizationTimeoutError: If elapsed time exceeds 3 seconds.
    """
    start = time.monotonic()
    result = _sanitize_observacoes(content, thread_id)
    elapsed = time.monotonic() - start

    if elapsed > SANITIZE_TIMEOUT_SECONDS:
        raise SanitizationTimeoutError(
            f"Sanitization exceeded 3-second timeout (elapsed: {elapsed:.2f}s)"
        )

    return result
