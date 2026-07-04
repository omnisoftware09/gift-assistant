"""Swappable LLM factory — OpenAI, Anthropic, or Ollama."""

from langchain_core.language_models.chat_models import BaseChatModel

from src.langchain_core.settings import get_llm_settings


def get_chat_model(
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """
    Return a chat model. Swap provider via LLM_PROVIDER env var:
      openai    → OPENAI_API_KEY
      anthropic → ANTHROPIC_API_KEY
      ollama    → local Ollama (OLLAMA_BASE_URL, default localhost:11434)
    """
    settings = get_llm_settings()
    provider = (provider or settings["provider"]).lower()
    model = model or settings["model"]
    temperature = temperature if temperature is not None else settings["temperature"]

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=temperature)

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=settings["base_url"],
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, temperature=temperature)
