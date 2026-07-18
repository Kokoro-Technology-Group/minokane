from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class ForecastState(TypedDict):
    raw_question: str
    deadline: str | None
    outcome_description: str | None
    operationalized_options: list[dict]
    candidate_order: list[int]
    critic_feedback: str | None
    critic_approved: bool
    revision_count: int
    selected_option: dict | None
    user_feedback: str | None
    # Think stage:
    #   proposed_tree      — Anika's decomposition (majors + ideal sub-questions, no markets)
    #   forecast_components — final market-backed tree (PRD §7 contract shape)
    #   coverage           — how many proposed sub-questions found markets
    proposed_tree: list[dict]
    forecast_components: list[dict]
    coverage: dict | None
    # Retained for backward-compat with the (now deferred) synthesizer path.
    modular_sub_questions: list[dict]
    final_summary: str | None
    messages: Annotated[list, add_messages]
