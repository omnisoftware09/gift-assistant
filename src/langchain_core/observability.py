"""Tracing helpers for all agents — LangSmith @traceable + local logging."""

import functools
import logging
import time
from collections.abc import Callable
from typing import Any

from langsmith import traceable

from src.langchain_core.tracing import is_tracing_enabled

logger = logging.getLogger("gift_assistant.agents")


def _slack_metadata(context: Any | None) -> dict:
    if context is None:
        return {}
    return {
        "slack_user_id": getattr(context, "user_id", None),
        "slack_channel_id": getattr(context, "channel_id", None),
        "slack_thread_ts": getattr(context, "thread_ts", None),
    }


def trace_agent(
    agent_name: str,
    *,
    run_type: str = "chain",
) -> Callable:
    """
    Decorator to trace any agent handler in LangSmith.

    Usage:
        @trace_agent("gift_recommender")
        def handle_gift_request(request, context=None):
            ...
    """

    def decorator(fn: Callable) -> Callable:
        traced = traceable(
            name=agent_name,
            run_type=run_type,
            metadata={"agent": agent_name},
        )(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            meta = _extract_context_metadata(args, kwargs)
            log_extra = {"agent": agent_name, **meta}

            logger.info("agent.start", extra=log_extra)
            try:
                if is_tracing_enabled():
                    result = traced(*args, **kwargs)
                else:
                    result = fn(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "agent.success",
                    extra={**log_extra, "elapsed_ms": round(elapsed_ms, 1)},
                )
                return result
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.exception(
                    "agent.error",
                    extra={**log_extra, "elapsed_ms": round(elapsed_ms, 1), "error": str(exc)},
                )
                raise

        return wrapper

    return decorator


def _extract_context_metadata(args: tuple, kwargs: dict) -> dict:
    for value in list(args) + list(kwargs.values()):
        if hasattr(value, "user_id") and hasattr(value, "channel_id"):
            return _slack_metadata(value)
    ctx = kwargs.get("context")
    return _slack_metadata(ctx)


def trace_tool(tool_name: str) -> Callable:
    """Decorator for tool functions (calendar, chroma, search)."""
    return trace_agent(tool_name, run_type="tool")
