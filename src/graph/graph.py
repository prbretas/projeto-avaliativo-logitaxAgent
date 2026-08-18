"""Montagem do StateGraph completo do LogitaxAgent.

Registra todos os nodes e configura edges do grafo LangGraph:
parse → sanitize → route_regime → simular_regime_* → fan-out →
agregar → retrieve_context → generate_justification → human_review →
export_result

Conditional edge para route_regime.
Interrupt em human_review.

Requirements: 4.3, 6.1
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from src.graph.nodes.parse_operacao import parse_operacao
from src.graph.nodes.sanitize_input import sanitize_input
from src.graph.nodes.route_regime import route_regime
from src.graph.nodes.simular_regime import (
    simular_regime_regular,
    simular_regime_hibrido_simples,
)
from src.graph.nodes.simular_ano import simular_ano
from src.graph.nodes.retrieve_context import retrieve_context
from src.graph.nodes.generate_justification import generate_justification
from src.graph.nodes.human_review import human_review
from src.graph.nodes.export_result import export_result
from src.graph.nodes.check_reclassificacao import check_reclassificacao


# --- Routing Functions ---


def _route_by_regime(state: dict[str, Any]) -> str:
    """Conditional edge: route based on regime_tributario.

    Returns the next node name based on the operation's tax regime.
    """
    operacao = state.get("operacao", {})

    if hasattr(operacao, "regime_tributario"):
        regime = operacao.regime_tributario
    else:
        regime = operacao.get("regime_tributario", "")

    if regime == "simples_nacional":
        return "simular_regime_hibrido_simples"
    else:
        return "simular_regime_regular"


def _route_after_human_review(state: dict[str, Any]) -> str:
    """Conditional edge after human_review: export or end.

    Routes to export_result if approved, END if rejected.
    """
    aprovado = state.get("aprovado_humano")
    if aprovado is True:
        return "export_result"
    return END


def _route_reclassificacao(state: dict[str, Any]) -> str:
    """Conditional edge: check if reclassification forces human review.

    If revisao_manual=True (max reclassifications reached), go to human_review.
    Otherwise proceed normally to simular_anos.
    """
    if state.get("revisao_manual", False):
        return "human_review"
    return "simular_anos"


# --- Graph Builder ---


def build_graph() -> StateGraph:
    """Build and compile the complete LogitaxAgent StateGraph.

    Returns:
        Compiled StateGraph ready for execution.
    """
    # Define the state graph with dict-based state
    graph = StateGraph(dict)

    # --- Register Nodes ---
    graph.add_node("parse_operacao", parse_operacao)
    graph.add_node("sanitize_input", sanitize_input)
    graph.add_node("route_regime", route_regime)
    graph.add_node("simular_regime_regular", simular_regime_regular)
    graph.add_node("simular_regime_hibrido_simples", simular_regime_hibrido_simples)
    graph.add_node("check_reclassificacao", check_reclassificacao)
    graph.add_node("simular_anos", simular_ano)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("generate_justification", generate_justification)
    graph.add_node("human_review", human_review)
    graph.add_node("export_result", export_result)

    # --- Configure Edges ---

    # Entry point
    graph.set_entry_point("parse_operacao")

    # parse → sanitize
    graph.add_edge("parse_operacao", "sanitize_input")

    # sanitize → route_regime
    graph.add_edge("sanitize_input", "route_regime")

    # route_regime → conditional (simples or regular)
    graph.add_conditional_edges(
        "route_regime",
        _route_by_regime,
        {
            "simular_regime_regular": "simular_regime_regular",
            "simular_regime_hibrido_simples": "simular_regime_hibrido_simples",
        },
    )

    # regime nodes → check_reclassificacao
    graph.add_edge("simular_regime_regular", "check_reclassificacao")
    graph.add_edge("simular_regime_hibrido_simples", "check_reclassificacao")

    # check_reclassificacao → conditional (simular_anos or human_review)
    graph.add_conditional_edges(
        "check_reclassificacao",
        _route_reclassificacao,
        {
            "simular_anos": "simular_anos",
            "human_review": "human_review",
        },
    )

    # fan-out (simular_anos already aggregates internally) → retrieve_context
    graph.add_edge("simular_anos", "retrieve_context")

    # retrieve_context → generate_justification
    graph.add_edge("retrieve_context", "generate_justification")

    # generate_justification → human_review
    graph.add_edge("generate_justification", "human_review")

    # human_review → conditional (export or end)
    graph.add_conditional_edges(
        "human_review",
        _route_after_human_review,
        {
            "export_result": "export_result",
            END: END,
        },
    )

    # export_result → END
    graph.add_edge("export_result", END)

    return graph


def compile_graph(interrupt_before: list[str] | None = None):
    """Compile the graph with optional interrupt configuration.

    Args:
        interrupt_before: List of node names to interrupt before.
            Default: ["human_review"] for human-in-the-loop.

    Returns:
        Compiled runnable graph.
    """
    if interrupt_before is None:
        interrupt_before = ["human_review"]

    graph = build_graph()
    return graph.compile(interrupt_before=interrupt_before)
