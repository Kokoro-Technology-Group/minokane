"""
Orchestrator tests for the Think market-matching service — no network, no LLM.
The search / pick / validate / fetch collaborators are injected as fakes.
Run with: pytest tests/test_market_matching.py -v
"""

import asyncio

from app.integrations.models import MarketCandidate, MarketPick, TimeSeriesPoint
from app.models.schemas import Coverage, ForecastComponent
from app.services import market_matching as mm


# ---- fixtures / helpers -----------------------------------------------------

def _cand(mid, source="manifold", status="open"):
    return MarketCandidate(
        source=source, market_id=mid, question=f"Will {mid} happen?",
        url=f"https://{source}.example/{mid}", probability=55.0, status=status,
        description=f"desc {mid}",
    )


def _series():
    return [TimeSeriesPoint("2026-01-05", 55.0), TimeSeriesPoint("2026-01-12", 57.0)]


def _major(component, subs, atomic=False, likelihood=None):
    return {
        "component": component,
        "domain_tag": "technology",
        "confidence_of_importance": "high",
        "is_atomic": atomic,
        "llm_baseline_likelihood": likelihood,
        "ideal_subquestions": subs,
    }


def _sub(text, domain="technology"):
    return {
        "text": text, "domain_tag": domain,
        "confidence_of_importance": "medium", "llm_baseline_likelihood": "medium",
    }


def _run(proposed, *, pick, validate=None, search=None, series=None):
    async def default_validate(text, market):
        return True

    async def default_series(client, market):
        return _series()

    return asyncio.run(
        mm.build_forecast_tree(
            proposed,
            pick_fn=pick,
            validate_fn=validate or default_validate,
            search_fn=search,
            fetch_series_fn=series or default_series,
            client=object(),
        )
    )


def _searcher(candidates):
    async def search(client, term, limit):
        return list(candidates)
    return search


def _picker(mapping):
    """mapping: fn(text) -> MarketPick, or a fixed MarketPick."""
    async def pick(text, domain, cands):
        if callable(mapping):
            return mapping(text, cands)
        return mapping
    return pick


# ---- threshold helper -------------------------------------------------------

def test_meets_threshold():
    assert mm._meets_threshold("high", "medium") is True
    assert mm._meets_threshold("medium", "medium") is True
    assert mm._meets_threshold("low", "medium") is False
    assert mm._meets_threshold("garbage", "medium") is False


# ---- happy path -------------------------------------------------------------

def test_rollup_major_with_two_distinct_markets():
    a, b = _cand("A"), _cand("B")

    def pick(text, cands):
        # sq1 -> A, sq2 -> B
        chosen = a if "one" in text else b
        return MarketPick(market=chosen, confidence="high")

    proposed = [_major("Rollup", [_sub("sub one"), _sub("sub two")])]
    comps, cov = _run(proposed, pick=_picker(pick), search=_searcher([a, b]))

    tree = [ForecastComponent.model_validate(c) for c in comps]
    assert len(tree) == 1
    major = tree[0]
    assert major.type == "major_category" and major.components is not None
    assert len(major.components) == 2
    for minor in major.components:
        assert minor.type == "minor_category"
        assert minor.source == "manifold"
        assert minor.time_series  # non-empty
    assert cov == {"sub_questions_proposed": 2, "markets_found": 2, "branches_dropped": 0}


def test_atomic_major_carries_market_fields_and_no_children():
    a = _cand("A")
    proposed = [_major("Atomic single-market major", [], atomic=True, likelihood="high")]
    comps, cov = _run(proposed, pick=_picker(MarketPick(market=a, confidence="high")),
                      search=_searcher([a]))
    node = ForecastComponent.model_validate(comps[0])
    assert node.type == "major_category"
    assert node.components is None  # atomic → no children
    assert node.market_url == a.url and node.source == "manifold"
    assert node.time_series
    assert cov["markets_found"] == 1


# ---- drop / no-coverage paths ----------------------------------------------

def test_no_match_drops_subquestion_and_empty_major():
    proposed = [_major("Rollup", [_sub("s1"), _sub("s2")])]
    comps, cov = _run(
        proposed,
        pick=_picker(MarketPick(market=None, no_match=True, confidence="low")),
        search=_searcher([_cand("A")]),
    )
    assert comps == []  # rollup with zero surviving markets is dropped
    assert cov == {"sub_questions_proposed": 2, "markets_found": 0, "branches_dropped": 1}


def test_below_threshold_pick_is_dropped():
    a = _cand("A")
    proposed = [_major("Atomic", [], atomic=True)]
    comps, cov = _run(proposed, pick=_picker(MarketPick(market=a, confidence="low")),
                      search=_searcher([a]))
    assert comps == []
    assert cov["markets_found"] == 0 and cov["branches_dropped"] == 1


def test_empty_search_yields_zero_coverage():
    proposed = [_major("Rollup", [_sub("s1")])]
    comps, cov = _run(proposed, pick=_picker(MarketPick(market=_cand("A"), confidence="high")),
                      search=_searcher([]))
    assert comps == []
    assert cov == {"sub_questions_proposed": 1, "markets_found": 0, "branches_dropped": 1}


def test_empty_series_market_is_dropped():
    a = _cand("A")

    async def empty_series(client, market):
        return []

    proposed = [_major("Atomic", [], atomic=True)]
    comps, cov = _run(proposed, pick=_picker(MarketPick(market=a, confidence="high")),
                      search=_searcher([a]), series=empty_series)
    assert comps == []  # non-empty time_series is required for a shipped leaf
    assert cov["markets_found"] == 0


# ---- validate reject → fallback --------------------------------------------

def test_validate_reject_falls_back_to_second_choice_once():
    a, b = _cand("A"), _cand("B")
    calls = {"n": 0}

    async def validate(text, market):
        # Reject the first candidate (A), accept the fallback (B).
        return market.market_id == "B"

    proposed = [_major("Atomic", [], atomic=True)]
    comps, cov = _run(
        proposed,
        pick=_picker(MarketPick(market=a, second=b, confidence="high")),
        validate=validate,
        search=_searcher([a, b]),
    )
    node = ForecastComponent.model_validate(comps[0])
    assert node.market_id == "B"
    assert cov["markets_found"] == 1


# ---- dedupe -----------------------------------------------------------------

def test_market_deduped_across_tree_first_placement_wins():
    a = _cand("A")
    # Every sub-question picks the same market A.
    proposed = [
        _major("Rollup", [_sub("s1"), _sub("s2")]),
        _major("Atomic", [], atomic=True),
    ]
    comps, cov = _run(proposed, pick=_picker(MarketPick(market=a, confidence="high")),
                      search=_searcher([a]))
    tree = [ForecastComponent.model_validate(c) for c in comps]
    # Only the first rollup gets market A (one minor); atomic major is dropped.
    assert len(tree) == 1
    assert tree[0].type == "major_category" and len(tree[0].components) == 1
    assert cov["markets_found"] == 1
    assert cov["branches_dropped"] == 1


# ---- market_match_node TEST-mode short-circuit ------------------------------

def test_market_match_node_test_mode_no_network():
    from app.agents.graph import market_match_node

    state = {"raw_question": "TEST", "proposed_tree": []}
    result = market_match_node(state)
    comps = [ForecastComponent.model_validate(c) for c in result["forecast_components"]]
    cov = Coverage.model_validate(result["coverage"])
    assert len(comps) == 2
    assert cov.markets_found == 3
    # every leaf has a real-shaped market with a time_series
    leaf = comps[0].components[0]
    assert leaf.time_series and leaf.outcome_options == ["Yes", "No"]
