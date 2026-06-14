import os
from app.services.llm.provider import AIProvider
from app.services.llm.providers.xai import XAIProvider


def get_ai_provider() -> AIProvider:
    provider_type = os.getenv("ACTIVE_LLM_PROVIDER", "xai").lower()

    if provider_type == "xai":
        return XAIProvider()
    
    raise NotImplementedError(f"AI provider '{provider_type}' is not supported.")
