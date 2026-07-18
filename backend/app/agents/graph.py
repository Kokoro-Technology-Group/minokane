"""
LangGraph StateGraph wiring the Ask + Think pipeline.

Ask:
  START → operationalizer → critic ──(approved | max revisions)──► wait_for_selection
                                  ↑────────(veto, n < 3)──────────┘

Think (rebuilt per prd_ask_think.md):
  wait_for_selection ──(user selects)──► decompose ──► market_match ──► END

`decompose` (Anika, pass 1) drafts majors + ideal sub-questions. `market_match`
runs the deterministic service that searches Metaculus + Manifold, lets Anika
pick and Marcus validate each match, fetches the weekly time_series, and emits
the market-backed tree + coverage. The synthesizer (James) is deferred to Show
and is intentionally NOT wired into this graph.
"""

import asyncio
import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.personas.critic import critic_node
from app.agents.personas.modularizer import decompose_node
from app.agents.personas.operationalizer import operationalizer_node
from app.agents.personas._test_mode import is_test_question, make_test_forecast_tree
from app.agents.state import ForecastState
from app.services.market_matching import build_forecast_tree

logger = logging.getLogger(__name__)


def wait_for_selection_node(state: ForecastState) -> dict:
    """Human-in-the-loop pause. Interrupts the graph until the user picks an option.

    The resume payload may be either:
      - a dict shaped like an OperationalizedQuestion (legacy form), or
      - {"selected_option": <op_question>, "user_feedback": <str|None>}.
    """
    payload = interrupt({
        "type": "operationalization_selection",
        "operationalized_options": state["operationalized_options"],
    })
    if isinstance(payload, dict) and "selected_option" in payload:
        return {
            "selected_option": payload["selected_option"],
            "user_feedback": payload.get("user_feedback"),
        }
    return {"selected_option": payload}


def market_match_node(state: ForecastState) -> dict:
    """Run the async market-matching service and attach the forecast tree + coverage."""
    if is_test_question(state.get("raw_question")):
        components, coverage = make_test_forecast_tree(state.get("proposed_tree") or [])
        return {"forecast_components": components, "coverage": coverage}

    components, coverage = asyncio.run(
        build_forecast_tree(state.get("proposed_tree") or [])
    )
    return {"forecast_components": components, "coverage": coverage}


def _critic_router(state: ForecastState) -> str:
    if state["critic_approved"] or state["revision_count"] >= 3:
        return "wait_for_selection"
    return "operationalizer"


def build_graph(checkpointer: MemorySaver | None = None) -> StateGraph:
    builder = StateGraph(ForecastState)

    builder.add_node("operationalizer", operationalizer_node)
    builder.add_node("critic", critic_node)
    builder.add_node("wait_for_selection", wait_for_selection_node)
    builder.add_node("decompose", decompose_node)
    builder.add_node("market_match", market_match_node)

    builder.add_edge(START, "operationalizer")
    builder.add_edge("operationalizer", "critic")
    builder.add_conditional_edges("critic", _critic_router, {
        "wait_for_selection": "wait_for_selection",
        "operationalizer": "operationalizer",
    })
    builder.add_edge("wait_for_selection", "decompose")
    builder.add_edge("decompose", "market_match")
    builder.add_edge("market_match", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())


_graph_instance: StateGraph | None = None


def get_graph() -> StateGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance
