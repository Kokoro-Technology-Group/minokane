"""
Internal, platform-agnostic value objects shared by the market integrations
and the matching service. These are deliberately plain dataclasses (not
Pydantic) — they never cross the API boundary; the route layer converts the
final tree into the Pydantic `ForecastComponent` contract.
"""

from dataclasses import dataclass, field


# Market status as surfaced to the tree (PRD §6.6).
MarketStatus = str  # one of: "open" | "resolved" | "closed"


@dataclass
class MarketCandidate:
    """A single real market returned by a platform search."""

    source: str            # "metaculus" | "manifold"
    market_id: str
    question: str          # the market's canonical question text
    url: str
    probability: float | None  # current P(Yes) as a percent (0-100), or None
    status: MarketStatus       # "open" | "resolved" | "closed"
    description: str = ""       # short text description, used by Marcus's relevance check

    def to_public(self) -> dict:
        """Fields the tree node adopts from the market (canonical text + link)."""
        return {
            "source": self.source,
            "market_id": self.market_id,
            "market_url": self.url,
            "status": self.status,
            "outcome_options": ["Yes", "No"],
        }


@dataclass
class MarketPick:
    """Result of Anika's per-sub-question pick pass (PRD §6.2)."""

    market: "MarketCandidate | None"        # best real match, or None
    second: "MarketCandidate | None" = None  # next-best fallback for Marcus retry
    confidence: str = "low"                  # "high" | "medium" | "low"
    reasoning: str = ""
    no_match: bool = False


@dataclass
class TimeSeriesPoint:
    """A normalized weekly probability observation (P(Yes) as a percent)."""

    date: str          # "YYYY-MM-DD"
    probability: float  # 0-100, rounded to 1 decimal

    def to_dict(self) -> dict:
        return {"date": self.date, "probability": self.probability}
