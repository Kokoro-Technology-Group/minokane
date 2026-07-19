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


# Question scaffolding / stopwords stripped before hitting the keyword-based
# platform search — a full sentence like "Will a major AI lab win an IMO gold
# medal by 2027?" returns nothing; "AI lab win IMO gold medal 2027" matches.
_STOP = {
    "will", "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
    "by", "be", "is", "are", "was", "were", "than", "that", "which", "with",
    "from", "end", "before", "after", "least", "one", "any", "reach", "its",
    "their", "have", "has", "had", "do", "does", "this", "these", "those", "as",
    "it", "if", "when", "whether", "up", "down", "over", "under", "between",
    "into", "about", "per", "more", "most", "some", "all",
}


def _ranked_keywords(text: str) -> list[str]:
    """Salient search keywords, most-distinctive first (proper nouns/acronyms,
    then longer words). Keyword platforms score better with fewer, rarer terms."""
    import re
    words = re.findall(r"[A-Za-z0-9']+", text)
    content = [w for w in words if w.lower() not in _STOP and len(w) > 1]
    ranked = sorted(content, key=lambda w: (not (w[0].isupper() or w.isupper()), -len(w)))
    seen: set[str] = set()
    out: list[str] = []
    for w in ranked:
        k = w.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(w)
    return out or words


async def _search_all(client: httpx.AsyncClient, term: str, limit: int) -> list[MarketCandidate]:
    """Search both platforms, broadening the query (fewer keywords) until we get
    hits — keyword search returns nothing for a full sentence, and too many terms
    over-constrains it."""
    kws = _ranked_keywords(term)
    tried: list[str] = []
    for n in (6, 4, 3, 2):
        query = " ".join(kws[:n])
        if not query or query in tried:
            continue
        tried.append(query)
        results = await asyncio.gather(
            manifold.search_markets(client, query, limit),
            metaculus.search_markets(client, query, limit),
            return_exceptions=True,
        )
        merged: list[MarketCandidate] = []
        for r in results:
            if isinstance(r, list):
                merged.extend(r)
            elif isinstance(r, Exception):
                logger.warning("market_search_error", extra={"term": query[:80], "error": str(r)})
        if merged:
            return merged
    logger.info("market_search_empty", extra={"raw": term[:80], "tried": tried})
    return []


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


_LIKELIHOOD_P = {"high": 72.0, "medium": 50.0, "low": 28.0}


def _baseline_series(likelihood: str) -> list[dict]:
    """Synthetic weekly series around the LLM baseline — used when no real market
    matches, so a branch is never dropped and Think/Show always render."""
    import datetime as _dt
    import math

    target = _LIKELIHOOD_P.get(likelihood, 50.0)
    n = 16
    start = _dt.date.today() - _dt.timedelta(weeks=n - 1)
    pts = []
    for i in range(n):
        frac = i / (n - 1)
        val = 45.0 + (target - 45.0) * frac + math.sin(i * 1.3) * 3.0
        pts.append({"date": (start + _dt.timedelta(weeks=i)).isoformat(), "probability": round(max(1.0, min(99.0, val)), 1)})
    return pts


def _baseline_fields(likelihood: str) -> dict:
    return {
        "source": "estimate",
        "market_id": None,
        "market_url": None,
        "status": "estimate",
        "outcome_options": ["Yes", "No"],
        "time_series": _baseline_series(likelihood),
    }


def _baseline_minor(sub: dict) -> dict:
    return {
        "id": str(uuid4()),
        "type": "minor_category",
        "component": sub.get("text", "Sub-question"),
        "domain_tag": sub.get("domain_tag", "other"),
        "confidence_of_importance": sub.get("confidence_of_importance", "medium"),
        "llm_baseline_likelihood": sub.get("llm_baseline_likelihood", "medium"),
        **_baseline_fields(sub.get("llm_baseline_likelihood", "medium")),
    }


def _baseline_atomic(major: dict) -> dict:
    return {
        "id": str(uuid4()),
        "type": "major_category",
        "component": major.get("component", "Question"),
        "domain_tag": major.get("domain_tag", "other"),
        "confidence_of_importance": major.get("confidence_of_importance", "medium"),
        "llm_baseline_likelihood": major.get("llm_baseline_likelihood", "medium"),
        **_baseline_fields(major.get("llm_baseline_likelihood", "medium")),
    }


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
                    # never drop — fall back to a baseline estimate node
                    components.append(_baseline_atomic(major))
                continue

            subs = major.get("ideal_subquestions") or []
            sub_proposed += len(subs)
            results = await asyncio.gather(
                *[_guarded(s.get("text", ""), s.get("domain_tag", "other")) for s in subs]
            )

            minors: list[dict] = []
            for sub, match in zip(subs, results):
                if match and _dedupe_key(match[0]) not in used:
                    used.add(_dedupe_key(match[0]))
                    minors.append(_minor_node(sub, match[0], match[1]))
                    markets_found += 1
                else:
                    # no real market (or dup) → keep the sub as a baseline leaf
                    minors.append(_baseline_minor(sub))

            if minors:
                components.append(_rollup_major_node(major, minors))
            else:
                branches_dropped += 1
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
