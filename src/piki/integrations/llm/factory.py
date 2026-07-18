from piki.composition.contracts import LLMAdapter
from piki.core.config import Settings
from piki.integrations.llm.openai_chat import create_openai_chat_adapter
from piki.integrations.llm.openai_responses import create_openai_responses_adapter


def create_llm_adapter(settings: Settings) -> LLMAdapter:
    if settings.llm_provider == "openai":
        return create_openai_responses_adapter(settings)
    if settings.llm_provider in {"nvidia_nim", "openai_chat"}:
        return create_openai_chat_adapter(settings)
    raise ValueError("unsupported or missing LLM provider")
