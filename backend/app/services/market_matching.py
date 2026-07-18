"""
Market matching service (Think stage orchestration, PRD §6.2).

For each ideal sub-question (and each atomic-major candidate):
  1. search  — Metaculus + Manifold, binary/live candidates
  2. pick     — Anika chooses the single best real market, or no-match
  3. gate     — drop picks below the confidence threshold
  4. validate — Marcus judges relevance (cheap, before the history fetch)
  5. fetch    — pull + normalize the full weekly time_series
  6. attach   — build the market node

Rollups with zero surviving market children are dropped. Markets are deduped
across the whole tree (first/highest-importance placement wins). Emits an honest
`coverage` object. Never fabricates a market or a series.

The LLM passes and platform calls are injected (defaults wire the real ones) so
the orchestrator can be unit-tested with no network and no model calls.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

import httpx

from app.agents.personas.critic import validate_market_match
from app.agents.personas.modularizer import pick_best_market
from app.config import get_settings
from app.integrations import manifold, metaculus
from app.integrations._http import make_client
from app.integrations.models import MarketCandidate, TimeSeriesPoint

logger = logging.getLogger(__name__)

_CONF_RANK = {"high": 3, "medium": 2, "low": 1}


def _meets_threshold(confidence: str, minimum: str) -> bool:
    return _CONF_RANK.get(confidence, 0) >= _CONF_RANK.get(minimum, 0)


def _dedupe_key(market: MarketCandidate) -> str:
    return f"{market.source}:{market.market_id}"


async def _search_all(client: httpx.AsyncClient, term: str, limit: int) -> list[MarketCandidate]:
    """Search both platforms concurrently and merge candidates."""
    results = await asyncio.gather(
        manifold.search_markets(client, term, limit),
        metaculus.search_markets(client, term, limit),
        return_exceptions=True,
    )
    merged: list[MarketCandidate] = []
    for r in results:
        if isinstance(r, list):
            merged.extend(r)
        elif isinstance(r, Exception):
            logger.warning("market_search_error", extra={"term": term[:80], "error": str(r)})
    return merged


async def _fetch_series(client: httpx.AsyncClient, market: MarketCandidate) -> list[TimeSeriesPoint]:
    if market.source == manifold.SOURCE:
        return await manifold.fetch_time_series(client, market.market_id)
    if market.source == metaculus.SOURCE:
        return await metaculus.fetch_time_series(client, market.market_id)
    return []


class _Matcher:
    """Bundles the shared context + injected collaborators for one Think run."""

    def __init__(self, client, *, pick_fn, validate_fn, search_fn, fetch_series_fn, settings):
        self.client = client
        self.pick_fn = pick_fn
        self.validate_fn = validate_fn
        self.search_fn = search_fn
        self.fetch_series_fn = fetch_series_fn
        self.settings = settings

    async def match_one(self, text: str, domain_tag: str) -> tuple[MarketCandidate, list[TimeSeriesPoint]] | None:
        """Run the full search→pick→gate→validate→fetch flow for one question."""
        candidates = await self.search_fn(self.client, text, self.settings.market_search_limit)
        if not candidates:
            return None

        pick = await self.pick_fn(text, domain_tag, candidates)
        if pick.no_match or pick.market is None:
            return None
        if not _meets_threshold(pick.confidence, self.settings.market_match_min_confidence):
            logger.info(
                "market_pick_below_threshold",
                extra={"confidence": pick.confidence, "min": self.settings.market_match_min_confidence},
            )
            return None

        # Validate the best pick; on reject, try the fallback once (PRD §6.3).
        for candidate in (pick.market, pick.second):
            if candidate is None:
                continue
            if await self.validate_fn(text, candidate):
                series = await self.fetch_series_fn(self.client, candidate)
                if series:
                    return candidate, series
                logger.info(
                    "market_dropped_empty_series",
                    extra={"source": candidate.source, "market_id": candidate.market_id},
                )
        return None


def _market_fields(market: MarketCandidate, series: list[TimeSeriesPoint]) -> dict:
    return {
        "source": market.source,
        "market_id": market.market_id,
        "market_url": market.url,
        "status": market.status,
        "outcome_options": ["Yes", "No"],
        "time_series": [p.to_dict() for p in series],
    }


def _minor_node(sub: dict, market: MarketCandidate, series: list[TimeSeriesPoint]) -> dict:
    return {
        "id": str(uuid4()),
        "type": "minor_category",
        "component": market.question,  # adopt the market's canonical question (PRD §6.2)
        "domain_tag": sub.get("domain_tag", "other"),
        "confidence_of_importance": sub.get("confidence_of_importance", "medium"),
        "llm_baseline_likelihood": sub.get("llm_baseline_likelihood", "medium"),
        **_market_fields(market, series),
    }


def _atomic_major_node(major: dict, market: MarketCandidate, series: list[TimeSeriesPoint]) -> dict:
    return {
        "id": str(uuid4()),
        "type": "major_category",
        "component": market.question,
        "domain_tag": major.get("domain_tag", "other"),
        "confidence_of_importance": major.get("confidence_of_importance", "medium"),
        "llm_baseline_likelihood": major.get("llm_baseline_likelihood", "medium"),
        **_market_fields(market, series),
    }


def _rollup_major_node(major: dict, minors: list[dict]) -> dict:
    return {
        "id": str(uuid4()),
        "type": "major_category",
        "component": major.get("component", ""),
        "domain_tag": major.get("domain_tag", "other"),
        "confidence_of_importance": major.get("confidence_of_importance", "medium"),
        "components": minors,
    }


async def build_forecast_tree(
    proposed_majors: list[dict],
    *,
    pick_fn=pick_best_market,
    validate_fn=validate_market_match,
    search_fn=_search_all,
    fetch_series_fn=_fetch_series,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[dict], dict]:
    """Turn Anika's proposed tree into the market-backed forecast tree + coverage."""
    settings = get_settings()
    owns_client = client is None
    client = client or make_client()

    used: set[str] = set()
    sub_proposed = 0
    markets_found = 0
    branches_dropped = 0
    components: list[dict] = []

    matcher = _Matcher(
        client,
        pick_fn=pick_fn,
        validate_fn=validate_fn,
        search_fn=search_fn,
        fetch_series_fn=fetch_series_fn,
        settings=settings,
    )
    sem = asyncio.Semaphore(settings.market_fetch_concurrency)

    async def _guarded(text: str, domain: str):
        async with sem:
            return await matcher.match_one(text, domain)

    try:
        for major in proposed_majors:
            is_atomic = major.get("is_atomic") or not major.get("ideal_subquestions")

            if is_atomic:
                sub_proposed += 1
                match = await _guarded(major.get("component", ""), major.get("domain_tag", "other"))
                if match and _dedupe_key(match[0]) not in used:
                    used.add(_dedupe_key(match[0]))
                    components.append(_atomic_major_node(major, match[0], match[1]))
                    markets_found += 1
                else:
                    branches_dropped += 1
                continue

            subs = major.get("ideal_subquestions") or []
            sub_proposed += len(subs)
            results = await asyncio.gather(
                *[_guarded(s.get("text", ""), s.get("domain_tag", "other")) for s in subs]
            )

            minors: list[dict] = []
            for sub, match in zip(subs, results):
                if not match:
                    continue
                key = _dedupe_key(match[0])
                if key in used:  # first/highest-importance placement wins (PRD §6.2)
                    continue
                used.add(key)
                minors.append(_minor_node(sub, match[0], match[1]))
                markets_found += 1

            if minors:
                components.append(_rollup_major_node(major, minors))
            else:
                branches_dropped += 1  # rollup with zero surviving markets (PRD §6.7)
    finally:
        if owns_client:
            await client.aclose()

    coverage = {
        "sub_questions_proposed": sub_proposed,
        "markets_found": markets_found,
        "branches_dropped": branches_dropped,
    }
    logger.info("market_matching_done", extra=coverage)
    return components, coverage
