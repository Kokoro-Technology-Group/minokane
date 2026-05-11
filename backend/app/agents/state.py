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
    modular_sub_questions: list[dict]
    final_summary: str | None
    messages: Annotated[list, add_messages]
