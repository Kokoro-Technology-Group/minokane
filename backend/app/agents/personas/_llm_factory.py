"""
LLM factory for sub-agents (Critic, Modularizer, Synthesizer).
Uses the Anthropic Claude API directly via langchain-anthropic.

Reasoning models (e.g., claude-opus-4-7) do not accept sampling parameters
(temperature, top_p, top_k). This factory conditionally omits them.
"""

from langchain_anthropic import ChatAnthropic

from app.config import get_settings, is_reasoning_model


def get_sonnet_llm() -> ChatAnthropic:
    settings = get_settings()
    kwargs: dict = {
        "model": settings.sonnet_model,
        "max_tokens": settings.llm_max_tokens,
        "api_key": settings.anthropic_api_key,
    }
    if not is_reasoning_model(settings.sonnet_model):
        kwargs["temperature"] = settings.llm_temperature
    return ChatAnthropic(**kwargs)
