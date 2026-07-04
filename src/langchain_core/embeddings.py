"""Swappable embeddings — OpenAI or Ollama."""

from langchain_core.embeddings import Embeddings

from src.langchain_core.settings import get_embedding_settings


def get_embeddings(
    *,
    provider: str | None = None,
    model: str | None = None,
) -> Embeddings:
    """
    Return embeddings model. Swap via EMBEDDING_PROVIDER env:
      openai  → text-embedding-3-small (default)
      ollama  → nomic-embed-text or similar local model
    """
    settings = get_embedding_settings()
    provider = (provider or settings["provider"]).lower()
    model = model or settings["model"]

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=model, base_url=settings["base_url"])

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=model)
