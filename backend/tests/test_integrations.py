"""
Pure-function tests for the market integrations — no network, no LLM.
Run with: pytest tests/test_integrations.py -v
"""

from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# resample_weekly
# ---------------------------------------------------------------------------

def test_resample_empty_returns_empty():
    from app.integrations._http import resample_weekly
    assert resample_weekly([]) == []


def test_resample_sub_week_returns_single_latest_point():
    from app.integrations._http import resample_weekly
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = [(base, 40.0), (base + timedelta(days=2), 55.0)]
    pts = resample_weekly(raw)
    assert len(pts) == 1
    assert pts[0].date == "2026-01-03"
    assert pts[0].probability == 55.0


def test_resample_weekly_forward_fills():
    from app.integrations._http import resample_weekly
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Two observations, ~3 weeks apart. Weeks in between forward-fill the earlier value.
    raw = [(base, 30.0), (base + timedelta(days=21), 60.0)]
    pts = resample_weekly(raw)
    assert len(pts) >= 3
    assert pts[0].probability == 30.0            # first week
    assert pts[1].probability == 30.0            # forward-filled
    assert pts[-1].probability == 60.0           # final observation represented
    # weekly cadence: consecutive dates are 7 days apart
    d0 = datetime.strptime(pts[0].date, "%Y-%m-%d")
    d1 = datetime.strptime(pts[1].date, "%Y-%m-%d")
    assert (d1 - d0).days == 7


def test_resample_rounds_to_one_decimal_and_stays_in_range():
    from app.integrations._http import resample_weekly
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = [(base + timedelta(days=i), 33.333 + i) for i in range(20)]
    pts = resample_weekly(raw)
    for p in pts:
        assert 0.0 <= p.probability <= 100.0
        assert round(p.probability, 1) == p.probability


def test_resample_respects_max_points_cap():
    from app.integrations._http import resample_weekly
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = [(base + timedelta(days=7 * i), 50.0) for i in range(500)]  # ~500 weeks
    pts = resample_weekly(raw, max_points=50)
    assert len(pts) <= 50


# ---------------------------------------------------------------------------
# Manifold normalization
# ---------------------------------------------------------------------------

def test_manifold_pct_scales_and_rounds():
    from app.integrations.manifold import _pct
    assert _pct(None) is None
    assert _pct(0.6467644) == 64.7
    assert _pct(1.0) == 100.0


def test_manifold_status_mapping():
    from app.integrations.manifold import _status
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    assert _status({"isResolved": True}) == "resolved"
    assert _status({"isResolved": False, "closeTime": now_ms - 1_000_000}) == "closed"
    assert _status({"isResolved": False, "closeTime": now_ms + 1_000_000_000}) == "open"
    assert _status({}) == "open"


# ---------------------------------------------------------------------------
# Metaculus normalization + token gating
# ---------------------------------------------------------------------------

def test_metaculus_is_binary_detects_shapes():
    from app.integrations.metaculus import _is_binary
    assert _is_binary({"possibilities": {"type": "binary"}}) is True
    assert _is_binary({"type": "binary"}) is True
    assert _is_binary({"question": {"type": "binary"}}) is True
    assert _is_binary({"type": "numeric"}) is False
    assert _is_binary({}) is False


def test_metaculus_url_construction():
    from app.integrations.metaculus import _url
    assert _url({"url": "https://www.metaculus.com/questions/42/"}) == "https://www.metaculus.com/questions/42/"
    assert _url({"page_url": "/questions/7/x/"}) == "https://www.metaculus.com/questions/7/x/"
    assert _url({"id": 99}) == "https://www.metaculus.com/questions/99/"


def test_metaculus_search_returns_empty_without_token(monkeypatch):
    """No token configured → Manifold-only degradation (search returns [])."""
    import asyncio
    import app.integrations.metaculus as met
    from app.config import Settings

    monkeypatch.setattr(met, "get_settings", lambda: Settings(metaculus_api_token=""))
    # client is never touched because we short-circuit before any request.
    out = asyncio.run(met.search_markets(client=None, term="AI", limit=5))
    assert out == []


def test_metaculus_history_parses_api2_shape():
    from app.integrations.metaculus import _history_from_detail
    detail = {
        "community_prediction": {
            "history": [
                {"t": 1735689600, "community_prediction": {"q2": 0.4}},
                {"t": 1736294400, "community_prediction": {"q2": 0.55}},
            ]
        }
    }
    raw = _history_from_detail(detail)
    assert len(raw) == 2
    assert round(raw[0][1], 1) == 40.0
    assert round(raw[1][1], 1) == 55.0
