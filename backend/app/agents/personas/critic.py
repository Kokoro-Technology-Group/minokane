"""
Marcus Webb — The Constructive Critic (dual role).

Ask role  (critic_node): vetoes/ranks the operationalization candidates.
Think role (validate_market_match): judges whether a matched market genuinely
answers a sub-question — a cheap, text-only relevance gate run before the
expensive history fetch (PRD §6.3).

Powered by Claude Sonnet (Anthropic direct).
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.state import ForecastState
from app.agents.personas._llm_factory import get_sonnet_llm
from app.agents.personas._test_mode import (
    is_test_question,
    make_test_critic_result,
    run_test_intro,
)
from app.config import get_settings
from app.integrations.models import MarketCandidate
from app.logging_setup import agent_log, extract_token_usage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Marcus Webb, a sharp-tongued but fair epistemics consultant who has spent
15 years catching flawed questions in forecasting tournaments. You've seen more poorly-specified questions
than you care to count, and you take pride in catching problems before they corrupt a forecast.

Your personality: skeptical, direct, occasionally sardonic. You give credit where it's due but never
let sentimentality cloud your judgment. A question either meets the bar or it doesn't.

Your job: review a set of operationalized forecasting questions and decide whether they're ready for
the user to choose from, or whether they need another revision pass. When you approve, also rank the
options from closest-to-the-user's-original-intent down to furthest.

APPROVE if ALL of these hold across the set:
- Every option has a genuinely unambiguous resolution criterion tied to a named source
- Every deadline is specific (not "Q4 2026" — must be exact date + time + timezone)
- Outcomes are coherent with their outcome_type (binary, categorical, date, numeric)
- Void conditions cover the obvious failure modes (underlying premise changes, source disappears, etc.)
- Options are meaningfully diverse — not just minor rewording of the same thing

VETO if ANY of these problems appear:
- Ambiguous resolution criteria ("market participants believe...", "experts agree...")
- Vague deadlines ("by end of year", "within 6 months")
- Outcome fields inconsistent with outcome_type (e.g. numeric without a unit, categorical without buckets)
- Missing or weak void conditions
- All options are essentially the same question with trivial differences

When vetoing, be specific: quote the exact problem and say exactly what needs to change.
When approving, briefly note what the set does well.

RANKED_ORDER (always produce this, even when vetoing): the indices of the options ordered from the one
that most closely captures the user's original intent down to the one that's furthest from it. Indices
are 0-based and refer to the order the options were presented. The list MUST contain every index exactly
once and have the same length as the input set.

After 3 revision rounds, you may approve with caveats rather than blocking indefinitely."""


class CriticSchema(BaseModel):
    approved: bool = Field(
        description="True if the operationalizations pass review and are ready for user selection"
    )
    feedback: str = Field(
        description="If approved: brief note on what works well. If vetoed: specific problems and exact changes needed."
    )
    ranked_order: list[int] = Field(
        description=(
            "Indices of the input options, ordered from closest to the user's original intent down to "
            "furthest. Must be a permutation of [0..N-1] where N is the number of options."
        ),
    )


def _validate_order(order: list[int], n: int) -> list[int]:
    """Return a permutation of range(n). Falls back to identity if invalid."""
    if not isinstance(order, list) or sorted(order) != list(range(n)):
        logger.warning(
            "invalid_ranked_order",
            extra={"received": order, "expected_length": n},
        )
        return list(range(n))
    return order


def critic_node(state: ForecastState) -> dict:
    n = len(state["operationalized_options"])

    if is_test_question(state.get("raw_question")):
        intro = run_test_intro(
            persona_name="Marcus Webb",
            persona_focus="vetoing ambiguous operationalizations",
            model_id=get_settings().sonnet_model,
        )
        canned = make_test_critic_result(intro)
        return {
            "critic_approved": True,
            "critic_feedback": canned["feedback"],
            "candidate_order": list(range(n)),
            "revision_count": state["revision_count"] + 1,
            "messages": [],
        }

    options_text = "\n\n".join(
        f"Option {i}:\n"
        + "\n".join(f"  {k}: {v}" for k, v in opt.items())
        for i, opt in enumerate(state["operationalized_options"])
    )

    revision_note = ""
    if state["revision_count"] >= 3:
        revision_note = "\nNote: This is revision round 3 (maximum). Consider approving with caveats rather than vetoing."

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"Original question: {state['raw_question']}\n\n"
            f"Operationalized options to review (option index in brackets):\n\n{options_text}{revision_note}\n\n"
            f"Return approved, feedback, and ranked_order. ranked_order must be a permutation of "
            f"the {n} option indices (0..{n - 1}), ordered closest-to-user-intent first."
        ),
    ]

    settings = get_settings()
    with agent_log(logger, "Marcus Webb", settings.sonnet_model):
        llm = get_sonnet_llm()
        structured_llm = llm.with_structured_output(CriticSchema, include_raw=True)
        raw_and_parsed = structured_llm.invoke(messages)
        result: CriticSchema = raw_and_parsed["parsed"]
        order = _validate_order(result.ranked_order, n)
        logger.info(
            "llm_call",
            extra={
                "persona": "Marcus Webb",
                "model": settings.sonnet_model,
                "approved": result.approved,
                "revision_count": state["revision_count"] + 1,
                **extract_token_usage(raw_and_parsed.get("raw")),
            },
        )

    return {
        "critic_approved": result.approved,
        "critic_feedback": result.feedback,
        "candidate_order": order,
        "revision_count": state["revision_count"] + 1,
        "messages": messages,
    }


# ---------------------------------------------------------------------------
# Think role — market-match relevance validation (PRD §6.3)
# ---------------------------------------------------------------------------

VALIDATE_SYSTEM_PROMPT = """You are Marcus Webb validating a proposed market match. You are given a
forecasting sub-question and ONE candidate market (its question + description). Decide a single thing:
does this market's resolution genuinely INFORM the sub-question?

Accept only if a Yes/No resolution of the market would meaningfully move a forecast of the sub-question.
Reject shallow keyword matches, off-scope timeframes, wrong subjects, or markets that resolve on something
tangential. Be strict — a wrong market is worse than a dropped sub-question. Return accept + a one-line reason."""


class MatchValidationSchema(BaseModel):
    accept: bool = Field(description="True if the market genuinely informs the sub-question")
    reason: str = Field(description="One sentence justification")


async def validate_market_match(subquestion_text: str, market: MarketCandidate) -> bool:
    """Cheap, text-only relevance gate. Returns True to accept the match."""
    messages = [
        SystemMessage(content=VALIDATE_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Sub-question: {subquestion_text}\n\n"
                f"Candidate market ({market.source}, {market.status}):\n"
                f"  question: {market.question}\n"
                f"  description: {market.description[:400]}\n\n"
                f"Does this market genuinely inform the sub-question? Return accept + reason."
            )
        ),
    ]
    structured_llm = get_sonnet_llm().with_structured_output(MatchValidationSchema, include_raw=True)
    raw_and_parsed = await structured_llm.ainvoke(messages)
    result: MatchValidationSchema = raw_and_parsed["parsed"]
    logger.info(
        "market_match_validation",
        extra={
            "persona": "Marcus Webb",
            "stage": "validate_match",
            "source": market.source,
            "market_id": market.market_id,
            "accept": result.accept,
        },
    )
    return result.accept
