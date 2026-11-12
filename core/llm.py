from functools import lru_cache

from langchain_openai import ChatOpenAI

from core.config import settings


class LLMConfigurationError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_chat_model() -> ChatOpenAI:
    model = settings.llm_model.strip()
    api_key = settings.llm_api_key.get_secret_value().strip()
    base_url = settings.llm_base_url.strip() if settings.llm_base_url else None

    if not model:
        raise LLMConfigurationError("LLM_MODEL is not configured")
    if not api_key:
        raise LLMConfigurationError("LLM_API_KEY is not configured")

    return ChatOpenAI(
        model=model,
        api_key=settings.llm_api_key,
        base_url=base_url,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
    )
