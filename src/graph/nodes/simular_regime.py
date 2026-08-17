"""Regime simulation nodes for the LangGraph StateGraph.

Provides two nodes that prepare the credit factor before the per-year
tax calculation (simular_ano):

- simular_regime_regular: sets credit_factor = 1.0 (full non-cumulative credits)
- simular_regime_hibrido_simples: sets credit_factor = 0.0 (no credits for Simples Nacional)

Both nodes return a partial state update dict that LangGraph merges
into the shared AgentState.

Requirements: 4.1, 4.2
"""

from __future__ import annotations

from typing import Any


def simular_regime_regular(state: dict[str, Any]) -> dict[str, Any]:
    """Prepare state for regular regime simulation (lucro_real, lucro_presumido).

    Sets credit_factor to 1.0, indicating that full non-cumulative IBS/CBS
    credit deductions are available for this regime.

    Args:
        state: Current AgentState dict.

    Returns:
        Partial state update with credit_factor = 1.0.
    """
    return {"credit_factor": 1.0}


def simular_regime_hibrido_simples(state: dict[str, Any]) -> dict[str, Any]:
    """Prepare state for Simples Nacional regime simulation.

    Sets credit_factor to 0.0, indicating that no non-cumulative IBS/CBS
    credit deductions are available under Simples Nacional.

    Args:
        state: Current AgentState dict.

    Returns:
        Partial state update with credit_factor = 0.0.
    """
    return {"credit_factor": 0.0}
