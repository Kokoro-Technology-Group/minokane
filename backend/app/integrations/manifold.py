"""
Manifold integration — public REST, no key required (PRD §9).

  Search:  GET /v0/search-markets?term=&filter=open&contractType=BINARY
  History: GET /v0/bets?contractId=&limit=&before=   (probAfter over createdTime)

Manifold internal probabilities are 0-1; we convert to a 0-100 percent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.integrations._http import get_json, resample_weekly
from app.integrations.models import MarketCandidate, TimeSeriesPoint

logger = logging.getLogger(__name__)

SOURCE = "manifold"


def _pct(prob: float | None) -> float | None:
    if prob is None:
        return None
    return round(float(prob) * 100.0, 1)


def _status(market: dict) -> str:
    if market.get("isResolved"):
        return "resolved"
    close_ms = market.get("closeTime")
    if isinstance(close_ms, (int, float)):
        now_ms = datetime.now(timezone.utc).timestamp() * 1000
        if close_ms < now_ms:
            return "closed"
    return "open"


async def search_markets(
    client: httpx.AsyncClient, term: str, limit: int | None = None
) -> list[MarketCandidate]:
    """Search open binary Manifold markets for `term`."""
    settings = get_settings()
    limit = limit or settings.market_search_limit
    data = await get_json(
        client,
        f"{settings.manifold_base_url}/search-markets",
        params={
            "term": term,
            "filter": "open",
            "contractType": "BINARY",
            "sort": "score",
            "limit": limit,
        },
    )
    if not isinstance(data, list):
        return []

    out: list[MarketCandidate] = []
    for m in data:
        if not isinstance(m, dict) or m.get("outcomeType") != "BINARY":
            continue
        market_id = m.get("id")
        url = m.get("url")
        if not market_id or not url:
            continue
        out.append(
            MarketCandidate(
                source=SOURCE,
                market_id=str(market_id),
                question=m.get("question", "") or "",
                url=url,
                probability=_pct(m.get("probability")),
                status=_status(m),
                description=(m.get("textDescription") or "")[:600],
            )
        )
    return out


async def fetch_time_series(
    client: httpx.AsyncClient, market_id: str
) -> list[TimeSeriesPoint]:
    """Reconstruct the weekly P(Yes) series from a market's bet history."""
    settings = get_settings()
    raw: list[tuple[datetime, float]] = []
    before: str | None = None
    page_size = 1000
    fetched = 0

    while fetched < settings.market_max_bets:
        params: dict = {"contractId": market_id, "limit": page_size}
        if before:
            params["before"] = before
        page = await get_json(
            client, f"{settings.manifold_base_url}/bets", params=params,
            use_cache=before is None,  # only cache the first page
        )
        if not isinstance(page, list) or not page:
            break
        for b in page:
            prob_after = b.get("probAfter")
            created = b.get("createdTime")
            if prob_after is None or created is None:
                continue
            ts = datetime.fromtimestamp(created / 1000, tz=timezone.utc)
            raw.append((ts, float(prob_after) * 100.0))
        fetched += len(page)
        if len(page) < page_size:
            break
        before = page[-1].get("id")
        if not before:
            break

    return resample_weekly(raw)
