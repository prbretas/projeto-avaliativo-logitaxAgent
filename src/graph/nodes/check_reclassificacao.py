"""Stopping condition node for reclassification attempts.

Implements the reclassification counter logic that prevents infinite loops
in ambiguous cases. When the counter reaches 3, the system forces transition
to human_review with revisao_manual=True.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

from __future__ import annotations

from typing import Any

from src.models.estado import MAX_TENTATIVAS_RECLASSIFICACAO


def check_reclassificacao(state: dict[str, Any]) -> dict[str, Any]:
    """Check reclassification counter and enforce stopping condition.

    This node is invoked each time a reclassification action occurs
    (re-routing through route_regime or re-invoking a simulation node
    due to ambiguous/inconsistent intermediate results).

    Behavior:
    - If revisao_manual is already True: returns state unchanged (no re-entry).
    - If tentativas_reclassificacao >= MAX (3): sets revisao_manual=True,
      forcing transition to human_review.
    - Otherwise: increments tentativas_reclassificacao by 1.

    Args:
        state: The current AgentState dict.

    Returns:
        Dict with updated fields to merge into state.
    """
    revisao_manual = state.get("revisao_manual", False)
    tentativas = state.get("tentativas_reclassificacao", 0)

    # If already flagged for manual review, do NOT allow re-entry
    # into the simulation/reclassification loop
    if revisao_manual:
        return {
            "revisao_manual": True,
            "tentativas_reclassificacao": tentativas,
        }

    # Increment the counter for this reclassification attempt
    tentativas += 1

    # If counter reaches the maximum, force human review
    if tentativas >= MAX_TENTATIVAS_RECLASSIFICACAO:
        return {
            "tentativas_reclassificacao": tentativas,
            "revisao_manual": True,
        }

    # Otherwise, just increment and allow continuation
    return {
        "tentativas_reclassificacao": tentativas,
        "revisao_manual": False,
    }


def should_continue_or_review(state: dict[str, Any]) -> str:
    """Conditional edge function for reclassification routing.

    Determines whether the graph should continue to the simulation loop
    or route to human_review based on the reclassification state.

    Args:
        state: The current AgentState dict.

    Returns:
        "human_review" if revisao_manual is True or tentativas >= MAX.
        "continue" otherwise.
    """
    revisao_manual = state.get("revisao_manual", False)
    tentativas = state.get("tentativas_reclassificacao", 0)

    if revisao_manual or tentativas >= MAX_TENTATIVAS_RECLASSIFICACAO:
        return "human_review"

    return "continue"
