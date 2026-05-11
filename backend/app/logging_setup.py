"""
Structured logging for the Minokane backend.

Emits JSON log lines to stdout, with every record carrying:
- request_id  — propagated through the async context (set by middleware)
- persona     — populated inside agent_log() spans
- elapsed_ms  — populated on agent_log() exit
- input_tokens / output_tokens — populated by callers that have token usage

Use:
    configure_logging()                       # once at app startup
    with agent_log(logger, "Dr. Mira Chen", model_id):
        ...
        logger.info("llm_call",
                    extra={"input_tokens": 1234, "output_tokens": 567})
"""

import logging
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

try:
    from pythonjsonlogger.json import JsonFormatter  # python-json-logger >= 3.x
except ImportError:  # fallback for older versions
    from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore


request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(request_id)s %(message)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(_RequestIdFilter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # Tame chatty libraries
    logging.getLogger("httpx").setLevel("WARNING")
    logging.getLogger("httpcore").setLevel("WARNING")


def new_request_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def agent_log(logger: logging.Logger, persona: str, model: str) -> Iterator[None]:
    start = time.perf_counter()
    logger.info("agent_start", extra={"persona": persona, "model": model})
    try:
        yield
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "agent_end",
            extra={"persona": persona, "model": model, "elapsed_ms": elapsed_ms},
        )


def extract_token_usage(result) -> dict:
    """Best-effort extraction of token usage from a LangChain AIMessage or similar.

    Returns a dict with int values, or {} if unavailable.
    """
    meta = getattr(result, "response_metadata", None) or {}
    usage = meta.get("usage") or meta.get("token_usage") or {}
    out: dict = {}
    for src, dst in (
        ("input_tokens", "input_tokens"),
        ("output_tokens", "output_tokens"),
        ("prompt_tokens", "input_tokens"),
        ("completion_tokens", "output_tokens"),
    ):
        v = usage.get(src) if isinstance(usage, dict) else None
        if isinstance(v, int):
            out[dst] = v
    return out
