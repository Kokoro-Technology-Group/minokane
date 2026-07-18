"""
TEST mode helpers — light-touch smoke test for the full forecasting pipeline.

When the user types literal "TEST" (case-insensitive) into the question input,
each persona makes ONE minimum-budget reasoning-mode API call where it briefly
introduces itself, and canned data fills the rest of the schema. This exercises
the API/network/auth/reasoning-mode plumbing + the full LangGraph + storage +
frontend path without burning a full pipeline's worth of tokens (~$0.13/run).

Anthropic constraints honored here (Opus 4.7):
- thinking={"type": "adaptive"} is the only supported on-mode — the legacy
  {"type": "enabled", "budget_tokens": N} shape returns 400 on 4.7.
- output_config={"effort": "low"} minimizes thinking + output spend for the
  smoke test (replaces the old budget_tokens=1024 knob, which is gone on 4.7).
- temperature / top_p / top_k are removed on 4.7 (don't pass them).
- AIMessage.content is a list of typed blocks when thinking is on — see
  _extract_text below for the flattener.
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings

logger = logging.getLogger(__name__)

TEST_MAX_TOKENS = 1500


def is_test_question(raw: str | None) -> bool:
    return raw is not None and raw.strip().lower() == "test"


def build_test_llm(model_id: str) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=model_id,
        api_key=settings.anthropic_api_key,
        max_tokens=TEST_MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
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


def make_test_proposed_tree(intro: str) -> list[dict]:
    """Canned decomposition (Anika pass 1) — majors + ideal sub-questions, no markets."""
    return [
        {
            "component": f"TEST — {intro} (canned rollup major #1)",
            "domain_tag": "technology",
            "confidence_of_importance": "high",
            "is_atomic": False,
            "llm_baseline_likelihood": None,
            "ideal_subquestions": [
                {
                    "text": "TEST — canned ideal sub-question #1",
                    "domain_tag": "technology",
                    "confidence_of_importance": "high",
                    "llm_baseline_likelihood": "high",
                },
                {
                    "text": "TEST — canned ideal sub-question #2",
                    "domain_tag": "economics",
                    "confidence_of_importance": "medium",
                    "llm_baseline_likelihood": "medium",
                },
            ],
        },
        {
            "component": "TEST — canned atomic major (one market answers it)",
            "domain_tag": "economics",
            "confidence_of_importance": "high",
            "is_atomic": True,
            "llm_baseline_likelihood": "high",
            "ideal_subquestions": [],
        },
    ]


def _canned_series() -> list[dict]:
    return [
        {"date": "2026-06-01", "probability": 40.0},
        {"date": "2026-06-08", "probability": 43.5},
        {"date": "2026-06-15", "probability": 41.2},
        {"date": "2026-06-22", "probability": 47.9},
    ]


def make_test_forecast_tree(proposed_tree: list[dict]) -> tuple[list[dict], dict]:
    """Canned market-backed tree + coverage — no network, no LLM (TEST mode)."""
    import uuid

    def market_fields(source: str) -> dict:
        return {
            "source": source,
            "market_id": f"test-{source}-{uuid.uuid4().hex[:8]}",
            "market_url": f"https://example.com/{source}/test-market",
            "status": "open",
            "outcome_options": ["Yes", "No"],
            "time_series": _canned_series(),
        }

    components = [
        {
            "id": str(uuid.uuid4()),
            "type": "major_category",
            "component": "TEST — canned rollup major",
            "domain_tag": "technology",
            "confidence_of_importance": "high",
            "components": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "minor_category",
                    "component": "TEST — canned market-backed minor #1",
                    "domain_tag": "technology",
                    "confidence_of_importance": "high",
                    "llm_baseline_likelihood": "high",
                    **market_fields("manifold"),
                },
                {
                    "id": str(uuid.uuid4()),
                    "type": "minor_category",
                    "component": "TEST — canned market-backed minor #2",
                    "domain_tag": "economics",
                    "confidence_of_importance": "medium",
                    "llm_baseline_likelihood": "medium",
                    **market_fields("metaculus"),
                },
            ],
        },
        {
            "id": str(uuid.uuid4()),
            "type": "major_category",
            "component": "TEST — canned atomic major (one market answers it)",
            "domain_tag": "economics",
            "confidence_of_importance": "high",
            "llm_baseline_likelihood": "high",
            **market_fields("manifold"),
        },
    ]
    coverage = {"sub_questions_proposed": 3, "markets_found": 3, "branches_dropped": 0}
    return components, coverage


def make_test_summary(intro: str) -> str:
    return (
        f"TEST MODE — {intro}\n\n"
        "This is canned synthesis output. The real Synthesizer would distill the "
        "operationalized question and modular sub-questions into an executive briefing here. "
        "Because raw_question == 'TEST', the pipeline ran with one minimal reasoning-mode call "
        "per persona and canned data elsewhere."
    )
