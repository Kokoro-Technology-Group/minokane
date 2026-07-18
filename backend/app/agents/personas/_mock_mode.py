"""
MOCK mode — full offline stub for the forecasting pipeline.

When settings.mock_llm is true (driven by ./test.sh via MOCK_LLM=1), every
persona short-circuits to schema-valid *lorem ipsum* data and makes ZERO
Anthropic API calls. No ANTHROPIC_API_KEY is required.

This differs from _test_mode.py: TEST mode still makes one minimal real intro
call per persona to exercise API/auth/reasoning-mode plumbing. MOCK mode makes
NO network calls at all — it is a pure-offline smoke test of the FastAPI +
LangGraph + storage + frontend wiring.

Every builder returns the same shape as the real persona node, so the graph,
storage layer, and frontend render exactly as they would for a real run — only
the text is lorem ipsum.
"""

from app.config import get_settings

_LOREM = (
    "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua ut enim ad minim "
    "veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat duis aute irure dolor in reprehenderit in voluptate "
    "velit esse cillum dolore eu fugiat nulla pariatur excepteur sint "
    "occaecat cupidatat non proident sunt in culpa qui officia deserunt "
    "mollit anim id est laborum"
).split()


def is_mock_mode() -> bool:
    return get_settings().mock_llm


def _lorem(words: int = 12, *, cap: bool = True) -> str:
    out = " ".join(_LOREM[i % len(_LOREM)] for i in range(words))
    if cap:
        out = out[:1].upper() + out[1:]
    return out


_MOCK_DEADLINE = "2030-01-01T00:00:00+00:00"


def make_mock_operationalized_options() -> list[dict]:
    return [
        {
            "text": f"Lorem ipsum — {_lorem(10)}?",
            "resolution_criteria": _lorem(16),
            "resolution_source": f"Lorem ipsum source — {_lorem(4)}",
            "deadline": _MOCK_DEADLINE,
            "outcome_type": "binary",
            "outcome_options": ["Yes", "No"],
            "outcome_unit": None,
            "void_conditions": _lorem(10),
        },
        {
            "text": f"Dolor sit amet — {_lorem(10)}?",
            "resolution_criteria": _lorem(16),
            "resolution_source": f"Lorem ipsum source — {_lorem(4)}",
            "deadline": _MOCK_DEADLINE,
            "outcome_type": "categorical",
            "outcome_options": ["Lorem", "Ipsum", "Dolor"],
            "outcome_unit": None,
            "void_conditions": _lorem(10),
        },
    ]


def make_mock_critic_feedback() -> str:
    return f"MOCK MODE — {_lorem(14)}."


def make_mock_sub_questions() -> list[dict]:
    domains = ["economics", "technology", "geopolitics", "social"]
    importance = ["high", "medium", "medium", "low"]
    likelihood = ["medium", "high", "low", "medium"]
    return [
        {
            "text": f"Lorem ipsum sub-question — {_lorem(8)}?",
            "explanation": _lorem(12),
            "domain_tag": domains[i],
            "confidence_of_importance": importance[i],
            "llm_baseline_likelihood": likelihood[i],
        }
        for i in range(4)
    ]


def make_mock_summary() -> str:
    return (
        "MOCK MODE — lorem ipsum executive briefing.\n\n"
        f"1. THE QUESTION: {_lorem(12)}?\n"
        f"2. KEY DRIVERS: {_lorem(18)}.\n"
        f"3. KEY UNCERTAINTIES: {_lorem(14)}.\n"
        f"4. BOTTOM LINE: {_lorem(12)}.\n\n"
        "No Anthropic API calls were made. This is pure offline lorem ipsum "
        "output (settings.mock_llm=True)."
    )
