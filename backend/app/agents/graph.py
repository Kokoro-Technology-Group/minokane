"""
LangGraph StateGraph wiring the full forecasting pipeline.

Flow:
  START → operationalizer → critic ──(approved | max revisions)──► wait_for_selection
                                  ↑────────(veto, n < 3)──────────┘

  wait_for_selection ──(user selects)──► modularizer → synthesizer → END
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agents.personas.critic import critic_node
from app.agents.personas.modularizer import modularizer_node
from app.agents.personas.operationalizer import operationalizer_node
from app.agents.personas.synthesizer import synthesizer_node
from app.agents.state import ForecastState


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


def _critic_router(state: ForecastState) -> str:
    if state["critic_approved"] or state["revision_count"] >= 3:
        return "wait_for_selection"
    return "operationalizer"


def build_graph(checkpointer: MemorySaver | None = None) -> StateGraph:
    builder = StateGraph(ForecastState)

    builder.add_node("operationalizer", operationalizer_node)
    builder.add_node("critic", critic_node)
    builder.add_node("wait_for_selection", wait_for_selection_node)
    builder.add_node("modularizer", modularizer_node)
    builder.add_node("synthesizer", synthesizer_node)

    builder.add_edge(START, "operationalizer")
    builder.add_edge("operationalizer", "critic")
    builder.add_conditional_edges("critic", _critic_router, {
        "wait_for_selection": "wait_for_selection",
        "operationalizer": "operationalizer",
    })
    builder.add_edge("wait_for_selection", "modularizer")
    builder.add_edge("modularizer", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())


_graph_instance: StateGraph | None = None


def get_graph() -> StateGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance
