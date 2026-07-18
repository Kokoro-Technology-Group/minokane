"""
Shared HTTP plumbing for the market integrations:
  - a configured async httpx client factory,
  - a GET-with-retry/backoff helper over a small in-memory TTL cache,
  - the weekly resampler that normalizes raw probability observations
    into the §6.5 series shape.

The cache is process-local and best-effort — it exists to cut latency/cost and
respect upstream rate limits within a single Think run, not to be durable.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.config import get_settings
from app.integrations.models import TimeSeriesPoint

logger = logging.getLogger(__name__)

_USER_AGENT = "minokane/0.1 (+forecasting research)"

# ---- process-local TTL cache ------------------------------------------------
_cache: dict[str, tuple[float, object]] = {}
_cache_lock = asyncio.Lock()


def _cache_key(url: str, params: dict | None) -> str:
    if not params:
        return url
    items = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return f"{url}?{items}"


def make_client() -> httpx.AsyncClient:
    """A shared async client with sane timeouts and a descriptive UA."""
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.market_http_timeout),
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    retries: int = 2,
    use_cache: bool = True,
) -> object | None:
    """GET JSON with retry/backoff and a TTL cache.

    Returns the parsed JSON (list/dict) or None on persistent failure. Never
    raises — market outages degrade to partial trees (PRD risk mitigations).
    """
    settings = get_settings()
    key = _cache_key(url, params)

    if use_cache:
        async with _cache_lock:
            hit = _cache.get(key)
            if hit and (time.monotonic() - hit[0]) < settings.market_cache_ttl:
                return hit[1]

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"retryable status {resp.status_code}", request=resp.request, response=resp
                )
            if resp.status_code >= 400:
                logger.warning(
                    "market_http_client_error",
                    extra={"url": url, "status": resp.status_code},
                )
                return None
            data = resp.json()
            if use_cache:
                async with _cache_lock:
                    _cache[key] = (time.monotonic(), data)
            return data
        except Exception as exc:  # noqa: BLE001 — deliberately broad; degrade gracefully
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(0.4 * (2 ** attempt))

    logger.warning("market_http_failed", extra={"url": url, "error": str(last_exc)})
    return None


async def url_is_live(client: httpx.AsyncClient, url: str) -> bool:
    """Liveness check (HTTP 200, not deleted) before shipping a node (PRD §9)."""
    if not url:
        return False
    try:
        resp = await client.get(url)
        return 200 <= resp.status_code < 400
    except Exception:  # noqa: BLE001
        return False


# ---- weekly resampler -------------------------------------------------------

_MAX_POINTS = 200  # hard cap so multi-year histories stay reasonable


def resample_weekly(
    raw: list[tuple[datetime, float]],
    *,
    max_points: int = _MAX_POINTS,
) -> list[TimeSeriesPoint]:
    """Forward-fill raw (timestamp, probability%) observations to a weekly cadence.

    - Input probabilities are already percentages (0-100).
    - Points are emitted every 7 days from the first to the last observation,
      each carrying the most recent probability known as of that week (a step
      function — no interpolation, no synthesized values).
    - Output dates are UTC calendar dates ("YYYY-MM-DD"), probabilities rounded
      to 1 decimal. Returns [] for empty input.
    """
    obs = sorted(
        ((t.astimezone(timezone.utc) if t.tzinfo else t.replace(tzinfo=timezone.utc), p)
         for t, p in raw if p is not None),
        key=lambda x: x[0],
    )
    if not obs:
        return []

    start = obs[0][0]
    end = obs[-1][0]

    # If the whole history is under a week, emit the single latest point.
    if end - start < timedelta(days=7):
        return [TimeSeriesPoint(date=end.strftime("%Y-%m-%d"),
                                probability=round(obs[-1][1], 1))]

    points: list[TimeSeriesPoint] = []
    idx = 0
    cursor = start
    last_prob = obs[0][1]
    while cursor <= end and len(points) < max_points:
        while idx < len(obs) and obs[idx][0] <= cursor:
            last_prob = obs[idx][1]
            idx += 1
        points.append(
            TimeSeriesPoint(date=cursor.strftime("%Y-%m-%d"),
                            probability=round(last_prob, 1))
        )
        cursor += timedelta(days=7)

    # Ensure the final observation is represented.
    final_date = end.strftime("%Y-%m-%d")
    if points and points[-1].date != final_date and len(points) < max_points:
        points.append(TimeSeriesPoint(date=final_date, probability=round(obs[-1][1], 1)))

    return points
