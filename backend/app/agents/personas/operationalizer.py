"""
Dr. Mira Chen — The Operationalizer.
Powered by Claude Opus (Anthropic direct).

Two-stage invocation:
  1. Research pass — Opus bound to Anthropic's native web_search server tool.
     The model may issue up to N web_search calls to ground its candidate
     operationalizations in current facts (rates, calendars, releases, etc.).
  2. Structuring pass — Opus with structured_output produces the final
     OperationalizationSchema. Tools and with_structured_output do not
     compose cleanly in LangChain, so we keep them in separate calls and
     pass the research output as additional context.

If web search is disabled in settings, the research pass is skipped and the
structuring pass is invoked directly.
"""

import logging
from typing import Literal
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.state import ForecastState
from app.agents.personas._test_mode import (
    is_test_question,
    make_test_operationalized_options,
    run_test_intro,
)
from app.agents.personas._mock_mode import (
    is_mock_mode,
    make_mock_operationalized_options,
)
from app.config import get_settings, is_reasoning_model
from app.logging_setup import agent_log, extract_token_usage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Dr. Mira Chen, a meticulous research methodologist with 20 years of experience
designing rigorous, resolvable forecasting questions for elite prediction tournaments and policy research.

Your personality: precise, uncompromising about ambiguity, slightly perfectionist. You believe vague
questions produce useless forecasts. You speak directly and don't hedge unnecessarily.

Your job is to transform a natural-language question into 2–3 candidate operationalizations. Each candidate
must satisfy ALL four resolution criteria:

1. UNAMBIGUOUS RESOLUTION CRITERIA — The outcome must be objectively verifiable from a single authoritative
   source. No room for interpretation. Specify exactly which source judges the result.

2. PRECISE TIMEFRAME — An exact deadline down to the minute and timezone. No "by end of year" — use
   "2026-12-31T23:59:59-05:00". If the user provides a deadline, honor it. If not, infer a reasonable one.

3. OUTCOME TYPE — Pick the type of resolved value that best fits the question, and fill the matching fields:
   • binary       — Yes/No. outcome_options = ["Yes","No"]. Default for "will X happen" questions.
   • categorical  — 3+ named, mutually exclusive, exhaustive buckets. Use when binary is too coarse.
                    outcome_options = full list of bucket labels.
   • date         — a single resolved date (e.g. "When will Claude Opus 5 be released?").
                    outcome_options = []. The deadline is the latest date by which the question voids.
   • numeric      — a numeric quantity. Set outcome_unit (e.g. "USD", "%", "count", "bps").
                    outcome_options = either named bucket labels or empty for a point estimate.
   Outcomes within a type must be mutually exclusive and cover all plausible scenarios.

4. CLEAR VOID CONDITIONS — Exactly what invalidates this question. What if the underlying premise changes?
   What events would make the question unanswerable or moot?

Generate diverse operationalizations that capture different interpretations of the user's intent.
Use different scopes, thresholds, resolution sources, and outcome types across your candidates so the
user has genuinely different options to choose from.

If web_search is available, use it (sparingly) to ground resolution criteria and sources in current facts —
recent rate decisions, upcoming events, release calendars, etc. Cite the source you actually verified.

Return your output in the exact JSON schema requested. All deadlines must be ISO 8601 with timezone."""


_RESEARCH_PROMPT = """Before producing your final operationalizations, briefly note any current facts you
need to ground them in (recent events, official calendars, named sources, current values). If web_search
is available, use it for anything that may have changed since training. Keep this to ~150 words of dense
bullets — this is a scratch pad, not the final answer."""


class OperationalizedOptionSchema(BaseModel):
    text: str = Field(description="The fully operationalized question text")
    resolution_criteria: str = Field(description="Exact, objective criteria for how this resolves — cite the specific data source")
    resolution_source: str = Field(description="The single authoritative source used to judge the outcome (e.g., 'Federal Reserve press release', 'BLS CPI report')")
    deadline: str = Field(description="Exact resolution deadline in ISO 8601 format with timezone, e.g. '2026-12-31T23:59:59Z'")
    outcome_type: Literal["binary", "categorical", "date", "numeric"] = Field(
        default="binary",
        description="Type of resolved outcome. 'binary'=Yes/No, 'categorical'=3+ named buckets, 'date'=a single date value (the answer IS a date), 'numeric'=a number with optional unit.",
    )
    outcome_options: list[str] = Field(
        default_factory=list,
        description="For binary: ['Yes','No']. For categorical: bucket labels. For date/numeric point estimates: leave empty (or supply labeled buckets).",
    )
    outcome_unit: str | None = Field(
        default=None,
        description="Unit for numeric outcomes (e.g. 'USD', '%', 'count', 'bps'). Null for binary/categorical/date.",
    )
    void_conditions: str = Field(description="Specific scenarios that would void/invalidate this question")


class OperationalizationSchema(BaseModel):
    options: list[OperationalizedOptionSchema] = Field(
        description="2 to 3 candidate operationalizations of the user's question",
        min_length=2,
        max_length=3,
    )


def _base_kwargs() -> dict:
    settings = get_settings()
    kwargs: dict = {
        "model": settings.opus_model,
        "max_tokens": settings.llm_max_tokens,
        "api_key": settings.anthropic_api_key,
    }
    if not is_reasoning_model(settings.opus_model):
        kwargs["temperature"] = settings.llm_temperature
    return kwargs


def build_llm() -> ChatAnthropic:
    return ChatAnthropic(**_base_kwargs())


def build_llm_with_web_search():
    """Return an Opus runnable bound to Anthropic's server-side web_search tool."""
    settings = get_settings()
    base = ChatAnthropic(**_base_kwargs())
    web_search_tool = {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": settings.web_search_max_uses,
    }
    return base.bind_tools([web_search_tool])


def _extract_text(msg: AIMessage) -> str:
    """Flatten an AIMessage.content that may be a list of typed blocks."""
    content = msg.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type")
                if btype in ("thinking", "web_search_tool_use", "web_search_tool_result"):
                    continue
                text = block.get("text")
                if text:
                    parts.append(text)
            else:
                parts.append(str(block))
        return "".join(parts).strip()
    return str(content).strip()


def _run_research_pass(messages: list, settings) -> tuple[str, int]:
    """Returns (research_text, num_web_search_calls)."""
    llm = build_llm_with_web_search()
    research_msgs = messages + [HumanMessage(content=_RESEARCH_PROMPT)]
    response: AIMessage = llm.invoke(research_msgs)
    num_searches = 0
    if isinstance(response.content, list):
        num_searches = sum(
            1 for b in response.content
            if isinstance(b, dict) and b.get("type") == "web_search_tool_use"
        )
    logger.info(
        "web_search_pass",
        extra={
            "persona": "Dr. Mira Chen",
            "model": settings.opus_model,
            "num_web_searches": num_searches,
            **extract_token_usage(response),
        },
    )
    return _extract_text(response), num_searches


def operationalizer_node(state: ForecastState) -> dict:
    settings = get_settings()

    if is_mock_mode():
        return {
            "operationalized_options": make_mock_operationalized_options(),
            "messages": [],
        }

    if is_test_question(state.get("raw_question")):
        intro = run_test_intro(
            persona_name="Dr. Mira Chen",
            persona_focus="operationalizing natural-language forecasting questions",
            model_id=settings.opus_model,
        )
        return {
            "operationalized_options": make_test_operationalized_options(intro),
            "messages": [],
        }

    context_parts = [f"Raw question: {state['raw_question']}"]
    if state.get("deadline"):
        context_parts.append(f"User-specified deadline: {state['deadline']}")
    if state.get("outcome_description"):
        context_parts.append(f"Expected outcome context: {state['outcome_description']}")
    if state.get("critic_feedback"):
        context_parts.append(
            f"\nPrevious attempt was vetoed by the critic. Revision #{state['revision_count']}."
            f"\nCritic feedback to address: {state['critic_feedback']}"
        )

    human_content = "\n".join(context_parts)
    base_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ]

    with agent_log(logger, "Dr. Mira Chen", settings.opus_model):
        research_text = ""
        if settings.enable_web_search:
            try:
                research_text, _ = _run_research_pass(base_messages, settings)
            except Exception as exc:
                logger.warning(
                    "web_search_pass_failed",
                    extra={"persona": "Dr. Mira Chen", "error": str(exc)},
                )

        messages = list(base_messages)
        if research_text:
            messages.append(
                AIMessage(content=f"Research notes (from web_search and prior knowledge):\n{research_text}")
            )
            messages.append(
                HumanMessage(content="Now produce the final operationalizations as the requested JSON schema.")
            )

        structured_llm = build_llm().with_structured_output(
            OperationalizationSchema, include_raw=True
        )
        raw_and_parsed = structured_llm.invoke(messages)
        result: OperationalizationSchema = raw_and_parsed["parsed"]
        logger.info(
            "llm_call",
            extra={
                "persona": "Dr. Mira Chen",
                "stage": "structuring",
                "model": settings.opus_model,
                "num_candidates": len(result.options),
                **extract_token_usage(raw_and_parsed.get("raw")),
            },
        )

    options = [opt.model_dump() for opt in result.options]
    return {
        "operationalized_options": options,
        "messages": messages,
    }
