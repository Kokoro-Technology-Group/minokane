import asyncio
import secrets
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.agents.graph import get_graph
from app.agents.state import ForecastState
from app.config import Settings, get_settings
from app.models.schemas import (
    ForecastSession,
    ModularSubQuestion,
    OperationalizedQuestion,
    QuestionInput,
    SelectionInput,
)
from app.storage.json_store import JSONStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/questions", tags=["questions"])

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_store: JSONStore | None = None


def get_store() -> JSONStore:
    global _store
    if _store is None:
        _store = JSONStore(get_settings().data_file_path)
    return _store


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    if not api_key or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid or missing X-API-Key header")
    return api_key


def _parse_operationalized(options: list[dict]) -> list[OperationalizedQuestion]:
    result = []
    for opt in options:
        result.append(
            OperationalizedQuestion(
                id=str(uuid4()),
                text=opt["text"],
                resolution_criteria=opt["resolution_criteria"],
                resolution_source=opt["resolution_source"],
                deadline=opt["deadline"],
                outcome_type=opt.get("outcome_type", "binary"),
                outcome_options=opt.get("outcome_options", []),
                outcome_unit=opt.get("outcome_unit"),
                void_conditions=opt["void_conditions"],
            )
        )
    return result


def _reorder(options: list[OperationalizedQuestion], order: list[int] | None) -> list[OperationalizedQuestion]:
    """Reorder options per the critic's ranked_order. Falls back to input order."""
    if not order or sorted(order) != list(range(len(options))):
        return options
    return [options[i] for i in order]


@router.post("", response_model=ForecastSession)
async def submit_question(
    body: QuestionInput,
    _: str = Depends(verify_api_key),
    store: JSONStore = Depends(get_store),
) -> ForecastSession:
    """
    Submit a natural-language question. Runs the Operationalizer → Critic pipeline
    and pauses for user selection. Returns the session with candidate operationalizations.
    """
    session_id = str(uuid4())
    thread_id = session_id

    logger.info(
        "submit_question",
        extra={"session_id": session_id, "raw_question_len": len(body.raw_question)},
    )

    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: ForecastState = {
        "raw_question": body.raw_question,
        "deadline": body.deadline.isoformat() if body.deadline else None,
        "outcome_description": body.outcome_description,
        "operationalized_options": [],
        "candidate_order": [],
        "critic_feedback": None,
        "critic_approved": False,
        "revision_count": 0,
        "selected_option": None,
        "user_feedback": None,
        "modular_sub_questions": [],
        "final_summary": None,
        "messages": [],
    }

    try:
        await asyncio.to_thread(graph.invoke, initial_state, config)
    except Exception as e:
        logger.error(
            "graph_error",
            extra={"session_id": session_id, "stage": "operationalization", "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Agent pipeline error: {e}")

    snapshot = graph.get_state(config)
    current = snapshot.values

    operationalized = _parse_operationalized(current.get("operationalized_options", []))
    operationalized = _reorder(operationalized, current.get("candidate_order"))

    session = ForecastSession(
        id=session_id,
        thread_id=thread_id,
        created_at=datetime.now(timezone.utc),
        original_question=body,
        operationalized_options=operationalized,
        status="selecting",
    )

    await store.save_session(session)
    logger.info(
        "submit_question_done",
        extra={
            "session_id": session_id,
            "num_candidates": len(operationalized),
            "revision_count": current.get("revision_count"),
            "critic_approved": current.get("critic_approved"),
        },
    )
    return session


@router.get("/{session_id}", response_model=ForecastSession)
async def get_session(
    session_id: str,
    _: str = Depends(verify_api_key),
    store: JSONStore = Depends(get_store),
) -> ForecastSession:
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.put("/{session_id}/select", response_model=ForecastSession)
async def select_operationalization(
    session_id: str,
    body: SelectionInput,
    _: str = Depends(verify_api_key),
    store: JSONStore = Depends(get_store),
) -> ForecastSession:
    """
    User selects (or edits) one operationalization. Resumes the graph through
    modularization and synthesis.
    """
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "selecting":
        raise HTTPException(status_code=409, detail=f"Session is not awaiting selection (status={session.status})")

    logger.info(
        "select_operationalization",
        extra={
            "session_id": session_id,
            "has_user_feedback": bool(body.user_feedback),
            "selected_outcome_type": body.operationalized_question.outcome_type,
        },
    )

    graph = get_graph()
    config = {"configurable": {"thread_id": session.thread_id}}
    selected_dict = body.operationalized_question.model_dump(mode="json")
    resume_payload = {
        "selected_option": selected_dict,
        "user_feedback": body.user_feedback,
    }

    try:
        from langgraph.types import Command
        await asyncio.to_thread(graph.invoke, Command(resume=resume_payload), config)
    except Exception as e:
        logger.error(
            "graph_error",
            extra={"session_id": session_id, "stage": "modularization", "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Agent pipeline error: {e}")

    snapshot = graph.get_state(config)
    final = snapshot.values

    sub_questions = [
        ModularSubQuestion(
            id=str(uuid4()),
            parent_id=body.operationalized_question.id,
            text=sq["text"],
            explanation=sq["explanation"],
            domain_tag=sq["domain_tag"],
            confidence_of_importance=sq["confidence_of_importance"],
            llm_baseline_likelihood=sq["llm_baseline_likelihood"],
        )
        for sq in final.get("modular_sub_questions", [])
    ]

    session.selected_operationalization_id = body.operationalized_question.id
    session.user_feedback = body.user_feedback
    session.modular_sub_questions = sub_questions
    session.final_summary = final.get("final_summary")
    session.status = "complete"

    await store.save_session(session)
    logger.info(
        "select_operationalization_done",
        extra={
            "session_id": session_id,
            "num_sub_questions": len(sub_questions),
            "has_summary": session.final_summary is not None,
        },
    )
    return session


@router.get("/{session_id}/result", response_model=ForecastSession)
async def get_result(
    session_id: str,
    _: str = Depends(verify_api_key),
    store: JSONStore = Depends(get_store),
) -> ForecastSession:
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "complete":
        raise HTTPException(status_code=409, detail="Session is not yet complete")
    return session
