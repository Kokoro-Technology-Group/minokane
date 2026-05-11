from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


OutcomeType = Literal["binary", "categorical", "date", "numeric"]


class QuestionInput(BaseModel):
    raw_question: str
    deadline: datetime | None = None
    outcome_description: str | None = None


class OperationalizedQuestion(BaseModel):
    id: str
    text: str
    resolution_criteria: str
    resolution_source: str
    deadline: datetime
    outcome_type: OutcomeType = "binary"
    outcome_options: list[str] = Field(default_factory=list)
    outcome_unit: str | None = None
    void_conditions: str


class ModularSubQuestion(BaseModel):
    id: str
    parent_id: str
    text: str
    explanation: str
    domain_tag: str
    confidence_of_importance: Literal["high", "medium", "low"]
    llm_baseline_likelihood: Literal["high", "medium", "low"]


class ForecastSession(BaseModel):
    id: str
    thread_id: str
    created_at: datetime
    original_question: QuestionInput
    operationalized_options: list[OperationalizedQuestion] = Field(default_factory=list)
    selected_operationalization_id: str | None = None
    user_feedback: str | None = None
    modular_sub_questions: list[ModularSubQuestion] = Field(default_factory=list)
    final_summary: str | None = None
    status: Literal["intake", "operationalizing", "selecting", "modularizing", "complete"]


class SelectionInput(BaseModel):
    operationalized_question: OperationalizedQuestion
    user_feedback: str | None = None
