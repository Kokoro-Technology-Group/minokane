import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_setup import configure_logging, new_request_id, request_id_var
from app.routes.questions import get_store, router as questions_router


configure_logging(get_settings().log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    get_store()  # Initialise JSON store and create the data file if missing
    logger.info(
        "startup",
        extra={"data_file_path": settings.data_file_path, "log_level": settings.log_level},
    )
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Minokane — Ambient Superforecasting API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or new_request_id()
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-Id"] = rid
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questions_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
