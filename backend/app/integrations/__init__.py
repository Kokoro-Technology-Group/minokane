"""
External prediction-market integrations for the Think stage.

Two platforms are supported:
  - Manifold  (public REST, no key) — the primary, always-available source.
  - Metaculus (token-gated reads)    — enabled only when METACULUS_API_TOKEN is set.

Each platform module exposes the same small surface:
  - async search_markets(client, term, limit) -> list[MarketCandidate]
  - async fetch_time_series(client, market_id) -> list[TimeSeriesPoint]

All series are normalized to the §6.5 contract shape:
  [{ "date": "YYYY-MM-DD", "probability": <0-100, 1 decimal> }]  (P(Yes) as a percent)
"""

from app.integrations.models import MarketCandidate, TimeSeriesPoint

__all__ = ["MarketCandidate", "TimeSeriesPoint"]
