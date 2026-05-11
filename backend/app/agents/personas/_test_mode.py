"""
TEST mode helpers — light-touch smoke test for the full forecasting pipeline.

When the user types literal "TEST" (case-insensitive) into the question input,
each persona makes ONE minimum-budget reasoning-mode API call where it briefly
introduces itself, and canned data fills the rest of the schema. This exercises
the API/network/auth/reasoning-mode plumbing + the full LangGraph + storage +
frontend path without burning a full pipeline's worth of tokens (~$0.13/run).

Anthropic constraints honored here:
- max_tokens > thinking.budget_tokens (1024 is Anthropic's minimum budget).
- temperature must be unset (defaults to 1.0) when extended thinking is enabled.
- AIMessage.content is a list of typed blocks when thinking is enabled — see
  _extract_text below for the flattener.
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings

logger = logging.getLogger(__name__)

TEST_THINKING_BUDGET = 1024
TEST_MAX_TOKENS = 1500


def is_test_question(raw: str | None) -> bool:
    return raw is not None and raw.strip().lower() == "test"


def build_test_llm(model_id: str) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=model_id,
        api_key=settings.anthropic_api_key,
        max_tokens=TEST_MAX_TOKENS,
        thinking={"type": "enabled", "budget_tokens": TEST_THINKING_BUDGET},
    )


def _extract_text(response: Any) -> str:
    content = response.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "thinking":
                    continue
                text = block.get("text")
                if text:
                    parts.append(text)
            else:
                parts.append(str(block))
        return "".join(parts).strip()
    return str(content).strip()


def run_test_intro(*, persona_name: str, persona_focus: str, model_id: str) -> str:
    llm = build_test_llm(model_id)
    messages = [
        SystemMessage(content=f"You are {persona_name}."),
        HumanMessage(
            content=(
                f"Reply in EXACTLY ONE sentence: "
                f"\"Message received. I'm {persona_name}; my focus is {persona_focus}.\" "
                "Do not add anything else."
            )
        ),
    ]
    response = llm.invoke(messages)
    intro = _extract_text(response)
    logger.info("[TEST mode] %s", intro)
    return intro


_TEST_DEADLINE = "2030-01-01T00:00:00+00:00"


def make_test_operationalized_options(intro: str) -> list[dict]:
    return [
        {
            "text": f"TEST — {intro} (canned operationalization #1)",
            "resolution_criteria": "TEST mode — canned resolution criteria.",
            "resolution_source": "TEST mode — canned resolution source.",
            "deadline": _TEST_DEADLINE,
            "outcome_type": "binary",
            "outcome_options": ["Yes", "No"],
            "outcome_unit": None,
            "void_conditions": "TEST mode — canned void conditions.",
        },
        {
            "text": "TEST — canned operationalization #2",
            "resolution_criteria": "TEST mode — alternative criteria.",
            "resolution_source": "TEST mode — alternative source.",
            "deadline": _TEST_DEADLINE,
            "outcome_type": "binary",
            "outcome_options": ["Above threshold", "Below threshold"],
            "outcome_unit": None,
            "void_conditions": "TEST mode — canned void conditions.",
        },
        {
            "text": "TEST — canned operationalization #3",
            "resolution_criteria": "TEST mode — third criteria.",
            "resolution_source": "TEST mode — third source.",
            "deadline": _TEST_DEADLINE,
            "outcome_type": "categorical",
            "outcome_options": ["Yes", "No", "Partial"],
            "outcome_unit": None,
            "void_conditions": "TEST mode — canned void conditions.",
        },
    ]


def make_test_critic_result(intro: str) -> dict:
    return {"approved": True, "feedback": f"TEST MODE — {intro}"}


def make_test_sub_questions(intro: str) -> list[dict]:
    return [
        {
            "text": f"TEST — {intro} (canned sub-question #1)",
            "explanation": "TEST mode — canned explanation for sub-question #1.",
            "domain_tag": "economics",
            "confidence_of_importance": "high",
            "llm_baseline_likelihood": "medium",
        },
        {
            "text": "TEST — canned sub-question #2",
            "explanation": "TEST mode — canned explanation for sub-question #2.",
            "domain_tag": "technology",
            "confidence_of_importance": "medium",
            "llm_baseline_likelihood": "high",
        },
        {
            "text": "TEST — canned sub-question #3",
            "explanation": "TEST mode — canned explanation for sub-question #3.",
            "domain_tag": "geopolitics",
            "confidence_of_importance": "medium",
            "llm_baseline_likelihood": "low",
        },
        {
            "text": "TEST — canned sub-question #4",
            "explanation": "TEST mode — canned explanation for sub-question #4.",
            "domain_tag": "social",
            "confidence_of_importance": "low",
            "llm_baseline_likelihood": "medium",
        },
    ]


def make_test_summary(intro: str) -> str:
    return (
        f"TEST MODE — {intro}\n\n"
        "This is canned synthesis output. The real Synthesizer would distill the "
        "operationalized question and modular sub-questions into an executive briefing here. "
        "Because raw_question == 'TEST', the pipeline ran with one minimal reasoning-mode call "
        "per persona and canned data elsewhere."
    )
