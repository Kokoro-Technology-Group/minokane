"""
Dr. Anika Patel — The Decomposer (Think stage, two passes).

Pass 1 (graph node): decompose the selected core_question into ~3-5 major
branches, each with 0-4 *ideal sub-questions* — the questions we'd want markets
for. A major may be marked atomic (it is itself a single market). No markets are
attached yet; this is a draft tree.

Pass 2 (called by the matching service, once per sub-question): given the real
markets a platform search returned, pick the single best match, a fallback, and
a match confidence — or declare no-match.

Powered by Claude Sonnet.
"""

import logging
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.state import ForecastState
from app.agents.personas._llm_factory import get_sonnet_llm
from app.agents.personas._test_mode import (
    is_test_question,
    make_test_proposed_tree,
    run_test_intro,
)
from app.agents.personas._mock_mode import is_mock_mode, make_mock_sub_questions
from app.config import get_settings
from app.integrations.models import MarketCandidate, MarketPick
from app.logging_setup import agent_log, extract_token_usage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pass 1 — decomposition
# ---------------------------------------------------------------------------

DECOMPOSE_SYSTEM_PROMPT = """You are Dr. Anika Patel, an analytically-minded systems thinker with a
background in complexity science and strategic forecasting. You decompose a complex, resolvable
forecasting question into the network of simpler questions that drive its outcome.

Your job: given a selected, operationalized core question, produce a SHALLOW tree:
- {min_majors}-{max_majors} MAJOR branches — the top-level drivers/dimensions of the question. Each major
  is either a conceptual GROUPING (a rollup) or, when a single market could answer it directly, an ATOMIC
  major (is_atomic=true, no sub-questions).
- For each non-atomic major, propose 0-{max_minors} IDEAL sub-questions: the specific, independently
  resolvable questions you would most want a live prediction market for. These are drafts — we will try to
  match each to a REAL Metaculus or Manifold market, and drop any that has no good market.

Rules:
- Each sub-question must be a clear yes/no framed question that a binary market could resolve.
- Cover different causal domains — don't cluster everything in one area.
- Tag every node with a domain (economics, geopolitics, technology, finance, law, public health, policy,
  social, or other) and confidence_of_importance (how central it is to the main question).
- For sub-questions and atomic majors, also give llm_baseline_likelihood — your calibrated prior on a Yes.
- Prefer sub-questions likely to have real markets (concrete, dated, widely tracked topics).
- Quality over quantity. Every node must add genuine epistemic value."""


class IdealSubQuestion(BaseModel):
    text: str = Field(description="A clear yes/no sub-question a binary market could resolve")
    domain_tag: str = Field(description="Domain category")
    confidence_of_importance: Literal["high", "medium", "low"]
    llm_baseline_likelihood: Literal["high", "medium", "low"]


class MajorBranch(BaseModel):
    component: str = Field(
        description="The rollup question, or — if atomic — the single question one market answers"
    )
    domain_tag: str
    confidence_of_importance: Literal["high", "medium", "low"]
    is_atomic: bool = Field(
        description="True if this major is itself a single prediction market (no sub-questions)"
    )
    llm_baseline_likelihood: Literal["high", "medium", "low"] | None = Field(
        default=None, description="Calibrated Yes prior — required when is_atomic=true"
    )
    ideal_subquestions: list[IdealSubQuestion] = Field(
        default_factory=list, description="Empty when is_atomic=true"
    )


class DecompositionSchema(BaseModel):
    majors: list[MajorBranch] = Field(description="3-5 major branches")


def decompose_node(state: ForecastState) -> dict:
    settings = get_settings()
def modularizer_node(state: ForecastState) -> dict:
    if is_mock_mode():
        return {
            "modular_sub_questions": make_mock_sub_questions(),
            "messages": [],
        }

    if is_test_question(state.get("raw_question")):
        intro = run_test_intro(
            persona_name="Dr. Anika Patel",
            persona_focus="decomposing forecasting questions into a market-backed tree",
            model_id=settings.sonnet_model,
        )
        return {"proposed_tree": make_test_proposed_tree(intro), "messages": []}

    selected = state.get("selected_option") or {}
    selected_text = "\n".join(f"  {k}: {v}" for k, v in selected.items())
    user_feedback = state.get("user_feedback")

    system_prompt = DECOMPOSE_SYSTEM_PROMPT.format(
        min_majors=3, max_majors=settings.max_majors, max_minors=settings.max_minors_per_major
    )
    human_parts = [
        f"Original question: {state['raw_question']}",
        f"\nSelected operationalized core question:\n{selected_text}",
    ]
    if user_feedback:
        human_parts.append(
            f"\nUser-provided guidance (treat as a strong steer, not a hard constraint):\n{user_feedback}"
        )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="\n".join(human_parts)),
    ]

    with agent_log(logger, "Dr. Anika Patel", settings.sonnet_model):
        structured_llm = get_sonnet_llm().with_structured_output(
            DecompositionSchema, include_raw=True
        )
        raw_and_parsed = structured_llm.invoke(messages)
        result: DecompositionSchema = raw_and_parsed["parsed"]
        n_subs = sum(len(m.ideal_subquestions) for m in result.majors)
        logger.info(
            "llm_call",
            extra={
                "persona": "Dr. Anika Patel",
                "stage": "decompose",
                "model": settings.sonnet_model,
                "num_majors": len(result.majors),
                "num_sub_questions": n_subs,
                "has_user_feedback": bool(user_feedback),
                **extract_token_usage(raw_and_parsed.get("raw")),
            },
        )

    return {"proposed_tree": [m.model_dump() for m in result.majors], "messages": []}


# ---------------------------------------------------------------------------
# Pass 2 — per-sub-question market pick
# ---------------------------------------------------------------------------

PICK_SYSTEM_PROMPT = """You are Dr. Anika Patel matching a forecasting sub-question to a REAL prediction
market. You are given the sub-question and a numbered list of candidate markets returned by platform
search. Your job:

- Pick the single candidate whose resolution BEST answers the sub-question (best_index).
- Optionally pick a fallback (second_index) — the next-best candidate, or -1 if none.
- Give a match_confidence: high (the market clearly resolves the sub-question), medium (closely related,
  a reasonable proxy), or low (weak/tangential).
- If NO candidate genuinely informs the sub-question, set best_index = -1 (no match). Never force a match.

Judge on what the market actually RESOLVES, not surface keyword overlap. Prefer precise, on-topic,
still-open markets. Indices are 0-based over the candidate list as presented."""


class MarketPickSchema(BaseModel):
    best_index: int = Field(description="0-based index of the best candidate, or -1 for no match")
    second_index: int = Field(default=-1, description="0-based index of a fallback candidate, or -1")
    match_confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence that the chosen market answers the sub-question"
    )
    reasoning: str = Field(description="One sentence on why this market fits (or why none do)")


def _format_candidates(candidates: list[MarketCandidate]) -> str:
    lines = []
    for i, c in enumerate(candidates):
        desc = f" — {c.description[:200]}" if c.description else ""
        lines.append(f"[{i}] ({c.source}, {c.status}) {c.question}{desc}")
    return "\n".join(lines)


async def pick_best_market(
    subquestion_text: str, domain_tag: str, candidates: list[MarketCandidate]
) -> MarketPick:
    """Anika's lightweight pick pass. Returns a MarketPick (no_match when appropriate)."""
    if not candidates:
        return MarketPick(market=None, no_match=True, confidence="low", reasoning="no candidates")

    settings = get_settings()
    messages = [
        SystemMessage(content=PICK_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Sub-question ({domain_tag}): {subquestion_text}\n\n"
                f"Candidate markets:\n{_format_candidates(candidates)}\n\n"
                f"Return best_index, second_index, match_confidence, reasoning."
            )
        ),
    ]

    structured_llm = get_sonnet_llm().with_structured_output(MarketPickSchema, include_raw=True)
    raw_and_parsed = await structured_llm.ainvoke(messages)
    result: MarketPickSchema = raw_and_parsed["parsed"]

    def _at(idx: int) -> MarketCandidate | None:
        return candidates[idx] if 0 <= idx < len(candidates) else None

    best = _at(result.best_index)
    if best is None:
        return MarketPick(market=None, no_match=True, confidence=result.match_confidence,
                          reasoning=result.reasoning)
    second = _at(result.second_index)
    if second is best:
        second = None
    return MarketPick(
        market=best,
        second=second,
        confidence=result.match_confidence,
        reasoning=result.reasoning,
        no_match=False,
    )
