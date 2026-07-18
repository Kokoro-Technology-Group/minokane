"""
Dr. Anika Patel — The Modularizer.
Systems thinker who decomposes complex questions into answerable sub-components.
Powered by Claude Sonnet (OpenRouter or Anthropic fallback).
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import Literal

from app.agents.state import ForecastState
from app.agents.personas._llm_factory import get_sonnet_llm
from app.agents.personas._test_mode import (
    is_test_question,
    make_test_sub_questions,
    run_test_intro,
)
from app.agents.personas._mock_mode import is_mock_mode, make_mock_sub_questions
from app.config import get_settings
from app.logging_setup import agent_log, extract_token_usage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Dr. Anika Patel, an analytically-minded systems thinker with a background
in complexity science and strategic forecasting. You see every complex question as a network of
simpler, answerable sub-questions. Your forecasting methodology has been used by policy makers
and intelligence analysts who need structured clarity, not monolithic guesses.

Your personality: systematic, intellectually curious, collaborative. You love finding the hidden
causal structure behind a question. You're especially alert to questions that look complex but are
actually atomic — and you say so honestly rather than decomposing for the sake of it.

Your job: given a selected operationalized question, determine whether it needs decomposition and,
if so, produce a set of modular sub-questions that together address the key drivers of the main question.

ATOMIC CHECK — skip decomposition if:
- The question is already a simple binary with one clear causal factor
- Breaking it down would produce sub-questions with no independent value
- The question is narrow enough that a single domain expert could answer it directly

IF DECOMPOSING:
- Each sub-question must be independently resolvable (not circular)
- Cover different causal domains — don't cluster everything in one area
- Tag each with a domain (economics, geopolitics, technology, public health, law, finance, etc.)
- Rate confidence_of_importance: how central is this sub-question to the main question?
- Rate llm_baseline_likelihood: your best calibrated prior on whether this resolves favorably

Aim for 4–8 sub-questions. Quality over quantity. Each must add genuine epistemic value."""


class SubQuestionSchema(BaseModel):
    text: str = Field(description="The sub-question, written as a clear yes/no or measurable question")
    explanation: str = Field(description="1–2 sentences on why this sub-question matters for the main forecast")
    domain_tag: str = Field(description="Domain category: economics, geopolitics, technology, finance, law, public health, social, or other")
    confidence_of_importance: Literal["high", "medium", "low"] = Field(
        description="How central is this sub-question to the main question's outcome?"
    )
    llm_baseline_likelihood: Literal["high", "medium", "low"] = Field(
        description="Calibrated prior on whether this sub-question resolves favorably (high=likely yes, low=likely no)"
    )


class ModularizationSchema(BaseModel):
    is_atomic: bool = Field(
        description="True if the question is already atomic and doesn't benefit from decomposition"
    )
    atomicity_reason: str = Field(
        description="Brief explanation of why this is atomic (if is_atomic=True) or why decomposition is warranted"
    )
    sub_questions: list[SubQuestionSchema] = Field(
        description="Decomposed sub-questions. Empty list if is_atomic=True.",
        default_factory=list,
    )


def modularizer_node(state: ForecastState) -> dict:
    if is_mock_mode():
        return {
            "modular_sub_questions": make_mock_sub_questions(),
            "messages": [],
        }

    if is_test_question(state.get("raw_question")):
        intro = run_test_intro(
            persona_name="Dr. Anika Patel",
            persona_focus="decomposing forecasting questions into modular sub-questions",
            model_id=get_settings().sonnet_model,
        )
        return {
            "modular_sub_questions": make_test_sub_questions(intro),
            "messages": [],
        }

    settings = get_settings()
    selected = state.get("selected_option") or {}
    selected_text = "\n".join(f"  {k}: {v}" for k, v in selected.items())
    user_feedback = state.get("user_feedback")

    human_parts = [
        f"Original question: {state['raw_question']}",
        f"\nSelected operationalized question:\n{selected_text}",
    ]
    if user_feedback:
        human_parts.append(
            f"\nUser-provided guidance for this decomposition (treat as a strong steer, not a hard constraint):\n{user_feedback}"
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content="\n".join(human_parts)),
    ]

    with agent_log(logger, "Dr. Anika Patel", settings.sonnet_model):
        llm = get_sonnet_llm()
        structured_llm = llm.with_structured_output(ModularizationSchema, include_raw=True)
        raw_and_parsed = structured_llm.invoke(messages)
        result: ModularizationSchema = raw_and_parsed["parsed"]
        logger.info(
            "llm_call",
            extra={
                "persona": "Dr. Anika Patel",
                "model": settings.sonnet_model,
                "is_atomic": result.is_atomic,
                "num_sub_questions": len(result.sub_questions),
                "has_user_feedback": bool(user_feedback),
                **extract_token_usage(raw_and_parsed.get("raw")),
            },
        )

    sub_questions = [sq.model_dump() for sq in result.sub_questions]
    return {
        "modular_sub_questions": sub_questions,
        "messages": messages,
    }
