"""
Route integration tests.
Run with: pytest tests/test_routes.py -v
Requires the minokane conda env to be active and ANTHROPIC_API_KEY to be set.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.config import get_settings

TEST_API_KEY = get_settings().api_key
AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_submit_question_missing_api_key():
    response = client.post(
        "/api/questions",
        json={"raw_question": "Will the Fed cut rates by end of 2026?"},
    )
    assert response.status_code == 403


def test_submit_question_invalid_api_key():
    response = client.post(
        "/api/questions",
        headers={"X-API-Key": "wrong-key"},
        json={"raw_question": "Will the Fed cut rates by end of 2026?"},
    )
    assert response.status_code == 403


def test_get_session_not_found():
    response = client.get("/api/questions/nonexistent-id", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_select_on_missing_session():
    from app.models.schemas import OperationalizedQuestion
    from datetime import datetime, timezone

    dummy_oq = {
        "id": "test-id",
        "text": "Test question",
        "resolution_criteria": "Test criteria",
        "resolution_source": "Test source",
        "deadline": "2026-12-31T23:59:59Z",
        "outcome_options": ["Yes", "No"],
        "void_conditions": "None",
    }
    response = client.put(
        "/api/questions/nonexistent-id/select",
        headers=AUTH_HEADERS,
        json={"operationalized_question": dummy_oq},
    )
    assert response.status_code == 404


@pytest.mark.live
@pytest.mark.skipif(
    not get_settings().anthropic_api_key,
    reason="ANTHROPIC_API_KEY not set — skipping live LLM test",
)
def test_full_flow_live():
    """
    Live end-to-end test. Only runs when ANTHROPIC_API_KEY is present.
    Submits a question, checks operationalizations are returned, then selects one.
    """
    # Step 1: submit
    submit_resp = client.post(
        "/api/questions",
        headers=AUTH_HEADERS,
        json={"raw_question": "Will the US unemployment rate exceed 5% by December 2026?"},
    )
    assert submit_resp.status_code == 200, submit_resp.text
    session = submit_resp.json()
    assert session["status"] == "selecting"
    assert 2 <= len(session["operationalized_options"]) <= 3
    session_id = session["id"]

    # Step 2: fetch session
    get_resp = client.get(f"/api/questions/{session_id}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 200

    # Step 3: select first option
    first_option = session["operationalized_options"][0]
    select_resp = client.put(
        f"/api/questions/{session_id}/select",
        headers=AUTH_HEADERS,
        json={"operationalized_question": first_option},
    )
    assert select_resp.status_code == 200, select_resp.text
    final = select_resp.json()
    assert final["status"] == "complete"
    assert final["final_summary"] is not None
