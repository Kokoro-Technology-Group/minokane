from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


OutcomeType = Literal["binary", "categorical", "date", "numeric"]
MarketSource = Literal["metaculus", "manifold"]
MarketStatus = Literal["open", "resolved", "closed"]
Confidence = Literal["high", "medium", "low"]


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


class TimeSeriesPoint(BaseModel):
    date: str  # "YYYY-MM-DD"
    probability: float = Field(description="P(Yes) as a percent, 0-100, 1 decimal")


class ForecastComponent(BaseModel):
    """A node in the forecast tree (PRD §7).

    A node is a **market** iff it has no `components` (it then carries the market
    fields: `source`, `market_id`, `market_url`, `status`, `outcome_options`,
    `time_series`). Otherwise it is a **rollup** grouping node.
    """

    id: str
    type: Literal["major_category", "minor_category"]
    component: str  # for market nodes this is the market's canonical question
    domain_tag: str
    confidence_of_importance: Confidence
    llm_baseline_likelihood: Confidence | None = None

    # Market fields — present only on market nodes (minors + atomic majors).
    source: MarketSource | None = None
    market_id: str | None = None
    market_url: str | None = None
    status: MarketStatus | None = None
    outcome_options: list[str] | None = None
    time_series: list[TimeSeriesPoint] | None = None

    # Rollup field — present only on rollup nodes.
    components: list["ForecastComponent"] | None = None


class Coverage(BaseModel):
    sub_questions_proposed: int = 0
    markets_found: int = 0
    branches_dropped: int = 0


class ForecastSession(BaseModel):
    id: str
    thread_id: str
    created_at: datetime
    original_question: QuestionInput
    operationalized_options: list[OperationalizedQuestion] = Field(default_factory=list)
    selected_operationalization_id: str | None = None
    core_question: str | None = None
    user_feedback: str | None = None
    # Think output tree + honest coverage (PRD §7). Every leaf is a real market.
    components: list[ForecastComponent] = Field(default_factory=list)
    coverage: Coverage | None = None
    # Retained for backward-compat; empty/None on new (Ask+Think) sessions.
    modular_sub_questions: list[ModularSubQuestion] = Field(default_factory=list)
    final_summary: str | None = None
    status: Literal["intake", "operationalizing", "selecting", "modularizing", "complete"]


class SelectionInput(BaseModel):
    operationalized_question: OperationalizedQuestion
    user_feedback: str | None = None
