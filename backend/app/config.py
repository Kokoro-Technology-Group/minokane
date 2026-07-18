from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    opus_model: str = "claude-opus-4-7"
    sonnet_model: str = "claude-sonnet-4-6"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    data_file_path: str = "./data/questions.json"
    api_key: str = "minokane-dev-key"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Observability
    log_level: str = "INFO"

    # Anthropic native web_search tool (server-side). Wired into the
    # Operationalizer so resolution criteria/sources/deadlines can be
    # grounded in current facts. Max uses per LLM invocation.
    enable_web_search: bool = True
    web_search_max_uses: int = 3

    # ---- Think stage: market matching (Metaculus + Manifold) --------------
    # Manifold reads are public (no key). Metaculus reads now require an API
    # token; when metaculus_api_token is empty the matcher degrades to
    # Manifold-only (honest partial coverage, never a hard failure).
    manifold_base_url: str = "https://api.manifold.markets/v0"
    metaculus_base_url: str = "https://www.metaculus.com/api2"
    metaculus_api_token: str = ""

    market_search_limit: int = 6          # candidates per platform per sub-question
    market_fetch_concurrency: int = 6     # bounded async pool for search/fetch
    market_http_timeout: float = 15.0     # per-call timeout (seconds)
    market_cache_ttl: int = 900           # response cache TTL (seconds)
    market_max_bets: int = 4000           # Manifold bet-history pagination cap
    market_match_min_confidence: str = "medium"  # min Anika pick confidence -> Marcus

    # Decomposition bounds (prompt guidance for Anika, pass 1).
    max_majors: int = 5
    max_minors_per_major: int = 4

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ---- Reasoning-model guard ------------------------------------------------
# Anthropic reasoning models (e.g., claude-opus-4-7 and later) reject
# sampling parameters (temperature, top_p, top_k). This helper lets callers
# decide whether to include those kwargs.
_REASONING_MODEL_SUBSTRINGS = ("opus-4-7",)


def is_reasoning_model(model_id: str) -> bool:
    """Return True if *model_id* refers to a reasoning model that rejects
    temperature / top_p / top_k."""
    normalized = model_id.lower()
    return any(tag in normalized for tag in _REASONING_MODEL_SUBSTRINGS)
