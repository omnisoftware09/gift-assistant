"""Gift Recommender LangGraph — search → evaluate → rank."""

import logging
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from src.agents.subagents.gift_recommender.parsing import (
    apply_ratings,
    extract_json_array,
    fallback_candidates,
    normalize_candidates,
)
from src.agents.subagents.gift_recommender.scoring import (
    CLOSENESS_WEIGHT,
    RATING_WEIGHT,
    enrich_with_closeness,
    rank_ideas_weighted,
)
from src.agents.subagents.gift_recommender.prompts import evaluate_prompt, search_prompt
from src.langchain_core.llm import get_chat_model
from src.langchain_core.observability import trace_agent
from src.storage.models.gift_request import GiftRequest

logger = logging.getLogger("gift_assistant.gift_recommender")

TOP_N = 3


class GiftGraphState(TypedDict):
    recipient: str
    occasion: str | None
    profile_chunks: list[str]
    search_results: list[dict]
    evaluated: list[dict]
    ranked: list[dict]
    status: str
    error: str


def _llm_json(prompt: str, *, node: str) -> list[dict]:
    """Single-shot LLM call — not a ReAct tool loop."""
    logger.info(
        "Gift %s pattern=single-shot-llm (not ReAct) — one LLM invoke, no tool loop",
        node,
    )
    model = get_chat_model(temperature=0.3)
    response = model.invoke(
        [
            SystemMessage(content="You return only valid JSON arrays. No markdown."),
            HumanMessage(content=prompt),
        ]
    )
    content = response.content
    if isinstance(content, list):
        # Some providers return content blocks
        content = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    logger.info("Gift %s pattern=single-shot-llm complete", node)
    return extract_json_array(str(content))


@trace_agent("gift_recommender.search")
def search_node(state: GiftGraphState) -> dict:
    """Generate gift candidates from profile + occasion (LLM — no product API yet)."""
    recipient = state["recipient"]
    occasion = state.get("occasion")
    profile_chunks = state.get("profile_chunks") or []

    logger.info(
        "Gift search starting source=LLM recipient=%s occasion=%r profile_chunks=%d",
        recipient,
        occasion,
        len(profile_chunks),
    )
    for i, chunk in enumerate(profile_chunks):
        logger.info("Gift search profile context [%d]=%r", i, chunk[:120])

    try:
        raw = _llm_json(search_prompt(recipient, occasion, profile_chunks), node="search")
        candidates = normalize_candidates(raw)
        if not candidates:
            candidates = fallback_candidates(recipient, occasion)
            status = "search: used fallback candidates (LLM returned no ideas)"
            logger.warning("Gift search used fallback candidates for recipient=%s", recipient)
        else:
            status = f"search: found {len(candidates)} candidates (source=LLM)"
            for idea in candidates:
                logger.info(
                    "Gift search candidate source=LLM recipient=%s title=%r category=%s price=%s",
                    recipient,
                    idea.get("title"),
                    idea.get("category"),
                    idea.get("price_range"),
                )
        return {"search_results": candidates, "status": status, "error": ""}
    except Exception as exc:
        candidates = fallback_candidates(recipient, occasion)
        logger.exception("Gift search failed recipient=%s", recipient)
        return {
            "search_results": candidates,
            "status": "search: fallback after error",
            "error": str(exc),
        }


@trace_agent("gift_recommender.evaluate")
def evaluate_node(state: GiftGraphState) -> dict:
    """LLM rating + embedding closeness vs profile for each candidate."""
    candidates = state.get("search_results") or []
    if not candidates:
        return {
            "evaluated": [],
            "status": "evaluate: no candidates",
            "error": state.get("error") or "",
        }

    recipient = state["recipient"]
    occasion = state.get("occasion")
    profile_chunks = state.get("profile_chunks") or []

    try:
        scored = _llm_json(
            evaluate_prompt(recipient, occasion, profile_chunks, candidates),
            node="evaluate",
        )
        evaluated = apply_ratings(candidates, scored)
        logger.info(
            "Gift evaluate pattern=single-shot-llm+embeddings (not ReAct) — "
            "LLM rating then embedding closeness per idea"
        )
        evaluated = enrich_with_closeness(evaluated, profile_chunks)

        logger.info(
            "Gift evaluate complete recipient=%s occasion=%r ideas=%d "
            "weights=closeness:%.0f%%+rating:%.0f%%",
            recipient,
            occasion,
            len(evaluated),
            CLOSENESS_WEIGHT * 100,
            RATING_WEIGHT * 100,
        )
        for idea in evaluated:
            logger.info(
                "Gift evaluate gift=%r rating=%.1f/100 closeness=%.1f/100 "
                "category=%s reason=%s",
                idea.get("title"),
                float(idea.get("rating", 0)),
                float(idea.get("closeness", 0)),
                idea.get("category"),
                idea.get("reason"),
            )
        return {
            "evaluated": evaluated,
            "status": f"evaluate: rated {len(evaluated)} ideas",
            "error": state.get("error") or "",
        }
    except Exception as exc:
        evaluated = apply_ratings(candidates, [])
        evaluated = enrich_with_closeness(evaluated, profile_chunks)
        logger.exception("Gift evaluate failed recipient=%s — using default ratings", recipient)
        for idea in evaluated:
            logger.info(
                "Gift evaluate (fallback) gift=%r rating=%.1f/100 closeness=%.1f/100",
                idea.get("title"),
                float(idea.get("rating", 0)),
                float(idea.get("closeness", 0)),
            )
        return {
            "evaluated": evaluated,
            "status": "evaluate: default ratings after error",
            "error": str(exc),
        }


@trace_agent("gift_recommender.rank")
def rank_node(state: GiftGraphState) -> dict:
    """Rank by final_score = 70% closeness + 30% LLM rating (deterministic — no LLM, no ReAct)."""
    evaluated = state.get("evaluated") or []
    logger.info(
        "Gift rank pattern=deterministic (not ReAct, not LLM) — "
        "weighted sort: 0.7*closeness + 0.3*rating"
    )
    ranked = rank_ideas_weighted(evaluated, top_n=TOP_N)
    recipient = state.get("recipient", "")

    logger.info(
        "Gift rank formula recipient=%s final=0.7*closeness+0.3*rating top_n=%d",
        recipient,
        TOP_N,
    )
    for i, idea in enumerate(ranked, start=1):
        closeness = float(idea.get("closeness", 0))
        rating = float(idea.get("rating", 0))
        final = float(idea.get("final_score", 0))
        logger.info(
            "Gift rank #%d recipient=%s gift=%r closeness=%.1f rating=%.1f "
            "final=%.1f (0.7*%.1f + 0.3*%.1f)",
            i,
            recipient,
            idea.get("title"),
            closeness,
            rating,
            final,
            closeness,
            rating,
        )
    return {
        "ranked": ranked,
        "status": f"rank: top {len(ranked)} of {len(evaluated)} (70% closeness + 30% rating)",
        "error": state.get("error") or "",
    }


def build_gift_recommender_graph():
    graph = StateGraph(GiftGraphState)
    graph.add_node("search", search_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("rank", rank_node)
    graph.set_entry_point("search")
    graph.add_edge("search", "evaluate")
    graph.add_edge("evaluate", "rank")
    graph.add_edge("rank", END)
    return graph.compile()


_graph = None


def get_gift_recommender_graph():
    global _graph
    if _graph is None:
        _graph = build_gift_recommender_graph()
    return _graph


def run_gift_pipeline(request: GiftRequest, profile_chunks: list[str]) -> GiftGraphState:
    """Run search → evaluate → rank."""
    logger.info(
        "Gift pipeline pattern=LangGraph-linear (not ReAct) — "
        "nodes: search(single-shot LLM) → evaluate(single-shot LLM+embeddings) → rank(deterministic)"
    )
    graph = get_gift_recommender_graph()
    return graph.invoke(
        {
            "recipient": request.recipient,
            "occasion": request.occasion,
            "profile_chunks": profile_chunks,
            "search_results": [],
            "evaluated": [],
            "ranked": [],
            "status": "starting",
            "error": "",
        }
    )
