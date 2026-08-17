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


def route_regime(state: dict[str, Any]) -> str:
    """Route execution based on the operation's tax regime.

    Examines `state["operacao"].regime_tributario` and returns the name
    of the next node to execute.

    Args:
        state: The current AgentState dict containing an "operacao" key
               with an OperacaoFrete instance (or dict with regime_tributario).

    Returns:
        "simular_regime_hibrido_simples" for simples_nacional regime.
        "simular_regime_regular" for lucro_real or lucro_presumido regimes.
    """
    operacao = state["operacao"]

    # Support both Pydantic model and plain dict access
    if hasattr(operacao, "regime_tributario"):
        regime = operacao.regime_tributario
    else:
        regime = operacao["regime_tributario"]

    if regime == "simples_nacional":
        return "simular_regime_hibrido_simples"

    # lucro_real and lucro_presumido both get full credits
    return "simular_regime_regular"
