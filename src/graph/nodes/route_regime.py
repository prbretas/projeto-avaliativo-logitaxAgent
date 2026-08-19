"""Conditional routing node based on tax regime.

Examines the `regime_tributario` field of the operation and determines
which simulation node should execute next:
- Simples Nacional → simular_regime_hibrido_simples (no credits)
- Lucro Real / Lucro Presumido → simular_regime_regular (full credits)

This function is intended to be used as a conditional edge function
in the LangGraph StateGraph.

Requirements: 4.1, 4.2, 4.3
"""

from __future__ import annotations

from typing import Any


def route_regime(state: dict[str, Any]) -> dict[str, Any]:
    """Node that prepares state for conditional routing based on tax regime.

    This node is a pass-through that doesn't modify state. The actual routing
    decision is made by the conditional edge function (_route_by_regime in graph.py).

    Args:
        state: The current AgentState dict containing an "operacao" key.

    Returns:
        Empty dict (no state changes needed, routing is handled by conditional edge).
    """
    return {}
