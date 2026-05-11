"""
James Harrington — The Executive Synthesizer.
Distills the full forecast session into a clear, decision-relevant summary.
Powered by Claude Sonnet (OpenRouter or Anthropic fallback).
"""

import json
import logging
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.state import ForecastState
from app.agents.personas._llm_factory import get_sonnet_llm
from app.agents.personas._test_mode import (
    is_test_question,
    make_test_summary,
    run_test_intro,
)
from app.config import get_settings
from app.logging_setup import agent_log, extract_token_usage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are James Harrington, a former McKinsey partner who now advises heads of state
and Fortune 50 boards on strategic risk. You've sat in hundreds of briefings where analysts drowned
decision-makers in jargon, and you've made it your mission to fix that.

Your personality: direct, executive-toned, pragmatic. You have zero tolerance for hedging that obscures
rather than clarifies. You strip jargon mercilessly. If someone can't understand your summary in 90 seconds,
you've failed.

Your job: synthesize the full forecasting session — the operationalized question, the modular sub-questions,
their domain tags, confidence levels, and baseline likelihoods — into a concise executive briefing.

FORMAT YOUR SUMMARY AS:
1. THE QUESTION (1 sentence): What are we actually forecasting?
2. KEY DRIVERS (3–5 bullets): The highest-confidence sub-questions that most determine the outcome.
   Include each driver's domain and your calibrated baseline.
3. KEY UNCERTAINTIES (2–3 bullets): The medium/low confidence factors that could swing the outcome.
4. BOTTOM LINE (1–2 sentences): Your honest framing of where the uncertainty sits and what to watch.

Rules:
- No passive voice. No "it is believed that..." Write active, declarative sentences.
- Acknowledge uncertainty honestly — don't project false precision.
- Flag if the question is atomic (no sub-questions) and explain what that means for the forecast.
- Keep the total under 300 words."""


class SynthesisSchema(BaseModel):
    summary: str = Field(description="Concise executive summary of the full forecast session")


def synthesizer_node(state: ForecastState) -> dict:
    if is_test_question(state.get("raw_question")):
        intro = run_test_intro(
            persona_name="James Harrington",
            persona_focus="synthesizing executive summaries from sub-question forecasts",
            model_id=get_settings().sonnet_model,
        )
        return {
            "final_summary": make_test_summary(intro),
            "messages": [],
        }

    settings = get_settings()
    selected = state.get("selected_option") or {}
    sub_questions = state.get("modular_sub_questions") or []
    user_feedback = state.get("user_feedback")

    sub_q_text = (
        json.dumps(sub_questions, indent=2)
        if sub_questions
        else "No sub-questions — question was identified as atomic."
    )

    human_parts = [
        f"Original question: {state['raw_question']}",
        f"\nOperationalized question selected:\n{json.dumps(selected, indent=2)}",
        f"\nModular sub-questions:\n{sub_q_text}",
    ]
    if user_feedback:
        human_parts.append(
            f"\nUser-provided guidance (incorporate where it sharpens the briefing):\n{user_feedback}"
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content="\n".join(human_parts)),
    ]

    with agent_log(logger, "James Harrington", settings.sonnet_model):
        llm = get_sonnet_llm()
        structured_llm = llm.with_structured_output(SynthesisSchema, include_raw=True)
        raw_and_parsed = structured_llm.invoke(messages)
        result: SynthesisSchema = raw_and_parsed["parsed"]
        logger.info(
            "llm_call",
            extra={
                "persona": "James Harrington",
                "model": settings.sonnet_model,
                "has_user_feedback": bool(user_feedback),
                **extract_token_usage(raw_and_parsed.get("raw")),
            },
        )

    return {
        "final_summary": result.summary,
        "messages": messages,
    }
