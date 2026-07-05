"""eCard draft pipeline — context + LLM draft (3 styles)."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.subagents.ecard_generator.parsing import (
    extract_json_array,
    fallback_ecard_variants,
    normalize_ecard_variants,
)
from src.agents.subagents.ecard_generator.prompts import draft_ecard_prompt
from src.langchain_core.llm import get_chat_model
from src.langchain_core.observability import trace_agent
from src.storage.models.ecard_request import EcardRequest
from src.storage.models.recipient_context import RecipientContext

logger = logging.getLogger("gift_assistant.ecard_generator")


def _past_ecards_summary(ecards) -> str:
    if not ecards:
        return "No past eCards recorded."
    return "\n".join(
        f"- [{e.style}] {e.headline}: {e.message[:80]}..." for e in ecards
    )


@trace_agent("ecard_generator.draft")
def draft_ecard_variants(
    request: EcardRequest,
    profile_chunks: list[str],
    recipient_context: RecipientContext,
    *,
    past_ecards=None,
    feedback: str | None = None,
    iteration: int = 1,
) -> list[dict]:
    """Generate 3 eCard style variants via LLM."""
    past_ecards = past_ecards or []
    logger.info(
        "eCard draft starting recipient=%s occasion=%r iteration=%d profile_chunks=%d",
        request.recipient,
        request.occasion,
        iteration,
        len(profile_chunks),
    )

    prompt = draft_ecard_prompt(
        request.recipient,
        request.occasion,
        profile_chunks,
        age_range=recipient_context.age_range,
        past_gifts_summary=recipient_context.past_gifts_summary(),
        past_ecards_summary=_past_ecards_summary(past_ecards),
        feedback=feedback,
        iteration=iteration,
    )

    try:
        logger.info("eCard draft pattern=single-shot-llm (not ReAct)")
        model = get_chat_model(temperature=0.4)
        response = model.invoke(
            [
                SystemMessage(content="You return only valid JSON arrays. No markdown."),
                HumanMessage(content=prompt),
            ]
        )
        content = response.content
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        raw = extract_json_array(str(content))
        variants = normalize_ecard_variants(raw)
        if len(variants) < 3:
            logger.warning("eCard draft returned %d variants, using fallback fill", len(variants))
            for fb in fallback_ecard_variants(request.recipient, request.occasion):
                if fb["style"] not in {v["style"] for v in variants}:
                    variants.append(fb)
                if len(variants) >= 3:
                    break
        return variants[:3]
    except Exception:
        logger.exception("eCard draft failed recipient=%s", request.recipient)
        return fallback_ecard_variants(request.recipient, request.occasion)
