"""Central LangSmith / LangChain tracing configuration."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("gift_assistant.tracing")


def configure_tracing() -> bool:
    """
    Enable LangSmith tracing for all LangChain runs and @traceable decorators.
    Returns True if tracing is active.
    """
    api_key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
    enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

    if not enabled:
        logger.info("LangSmith tracing disabled (LANGCHAIN_TRACING_V2 != true)")
        return False

    if not api_key:
        logger.warning(
            "LANGCHAIN_TRACING_V2=true but no LANGCHAIN_API_KEY — tracing disabled"
        )
        return False

    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", api_key)
    os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "gift-assistant"))
    os.environ.setdefault("LANGCHAIN_ENDPOINT", os.getenv(
        "LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"
    ))

    logger.info(
        "LangSmith tracing enabled — project=%s",
        os.environ["LANGCHAIN_PROJECT"],
    )
    return True


def is_tracing_enabled() -> bool:
    return (
        os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        and bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))
    )
