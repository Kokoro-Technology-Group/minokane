"""
Metaculus integration — token-gated reads (PRD §9, revised).

NOTE (deviation from PRD §9): the Metaculus API no longer serves anonymous
reads. Every endpoint returns "The API is only available to authenticated
users." unless an API token is presented. We therefore require
`METACULUS_API_TOKEN`; when it is unset this module returns no candidates and
the tree is built from Manifold alone (graceful degradation).

Because the authenticated response shape can vary across Metaculus API versions
and cannot be validated here without a token, all parsing is defensive: any
unexpected shape or error yields [] rather than raising.

  Search: GET /api2/questions/?search=&limit=      (Authorization: Token <token>)
  Detail: GET /api2/questions/{id}/                 (community-prediction history)

Metaculus community predictions are 0-1; we convert to a 0-100 percent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.integrations._http import get_json, resample_weekly
from app.integrations.models import MarketCandidate, TimeSeriesPoint

logger = logging.getLogger(__name__)

SOURCE = "metaculus"


def _auth_headers() -> dict | None:
    token = get_settings().metaculus_api_token
    if not token:
        return None
    return {"Authorization": f"Token {token}"}


def _is_binary(q: dict) -> bool:
    # api2 nests type under "possibilities"; newer schema uses "type".
    poss = q.get("possibilities")
    if isinstance(poss, dict) and poss.get("type") == "binary":
        return True
    if q.get("type") == "binary":
        return True
    inner = q.get("question")
    if isinstance(inner, dict) and inner.get("type") == "binary":
        return True
    return False


def _status(q: dict) -> str:
    if q.get("is_resolved") or q.get("resolution") not in (None, ""):
        return "resolved"
    state = (q.get("status") or q.get("active_state") or "").lower()
    if state in ("closed",):
        return "closed"
    if state in ("resolved",):
        return "resolved"
    return "open"


def _url(q: dict) -> str:
    for key in ("url", "page_url"):
        if q.get(key):
            val = q[key]
            return val if val.startswith("http") else f"https://www.metaculus.com{val}"
    qid = q.get("id")
    return f"https://www.metaculus.com/questions/{qid}/" if qid else ""


async def search_markets(
    client: httpx.AsyncClient, term: str, limit: int | None = None
) -> list[MarketCandidate]:
    """Search open binary Metaculus questions. Returns [] when no token is set."""
    headers = _auth_headers()
    if headers is None:
        return []

    settings = get_settings()
    limit = limit or settings.market_search_limit
    data = await get_json(
        client,
        f"{settings.metaculus_base_url}/questions/",
        params={"search": term, "limit": limit, "order_by": "-hotness"},
        headers=headers,
    )
    if not isinstance(data, dict):
        return []
    results = data.get("results")
    if not isinstance(results, list):
        return []

    out: list[MarketCandidate] = []
    for q in results:
        if not isinstance(q, dict) or not _is_binary(q):
            continue
        url = _url(q)
        qid = q.get("id")
        if not qid or not url:
            continue
        out.append(
            MarketCandidate(
                source=SOURCE,
                market_id=str(qid),
                question=q.get("title") or q.get("question", {}).get("title", "") or "",
                url=url,
                probability=_current_probability(q),
                status=_status(q),
                description=(q.get("description") or "")[:600],
            )
        )
    return out


def _current_probability(q: dict) -> float | None:
    cp = q.get("community_prediction")
    if isinstance(cp, dict):
        full = cp.get("full")
        if isinstance(full, dict) and isinstance(full.get("q2"), (int, float)):
            return round(full["q2"] * 100.0, 1)
    return None


def _history_from_detail(detail: dict) -> list[tuple[datetime, float]]:
    """Pull (timestamp, prob%) pairs from whichever history shape is present."""
    raw: list[tuple[datetime, float]] = []

    # Shape A (api2): community_prediction.history = [{t, community_prediction:{q2}}]
    cp = detail.get("community_prediction")
    if isinstance(cp, dict) and isinstance(cp.get("history"), list):
        for h in cp["history"]:
            t = h.get("t") or h.get("time")
            val = None
            inner = h.get("community_prediction") or h.get("x2") or {}
            if isinstance(inner, dict):
                val = inner.get("q2")
            elif isinstance(inner, (int, float)):
                val = inner
            if t is not None and isinstance(val, (int, float)):
                raw.append((datetime.fromtimestamp(t, tz=timezone.utc), val * 100.0))
        if raw:
            return raw

    # Shape B (newer): aggregations.recency_weighted.history = [{start_time, means:[p]}]
    inner_q = detail.get("question") if isinstance(detail.get("question"), dict) else detail
    aggs = inner_q.get("aggregations") if isinstance(inner_q, dict) else None
    if isinstance(aggs, dict):
        rw = aggs.get("recency_weighted") or {}
        hist = rw.get("history") if isinstance(rw, dict) else None
        if isinstance(hist, list):
            for h in hist:
                t = h.get("start_time") or h.get("t")
                means = h.get("means") or h.get("forecast_values")
                val = None
                if isinstance(means, list) and means:
                    val = means[-1]
                elif isinstance(h.get("centers"), list) and h["centers"]:
                    val = h["centers"][-1]
                if t is not None and isinstance(val, (int, float)):
                    raw.append((datetime.fromtimestamp(t, tz=timezone.utc), val * 100.0))
    return raw


async def fetch_time_series(
    client: httpx.AsyncClient, market_id: str
) -> list[TimeSeriesPoint]:
    """Fetch and normalize the community-prediction history to weekly cadence."""
    headers = _auth_headers()
    if headers is None:
        return []
    settings = get_settings()
    detail = await get_json(
        client,
        f"{settings.metaculus_base_url}/questions/{market_id}/",
        headers=headers,
    )
    if not isinstance(detail, dict):
        return []
    return resample_weekly(_history_from_detail(detail))
