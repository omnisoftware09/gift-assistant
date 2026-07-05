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
from src.tools.product_search.discovery import build_discovery_query, discover_gift_ideas
from src.shared.integration_settings import is_discovery_enabled, is_verification_enabled
from src.tools.product_search.retail import retail_fields_for_display, verify_gifts_retail
from src.langchain_core.observability import trace_agent
from src.storage.models.gift_request import GiftRequest

logger = logging.getLogger("gift_assistant.gift_recommender")

TOP_N = 3


class GiftGraphState(TypedDict):
    recipient: str
    occasion: str | None
    profile_chunks: list[str]
    age_range: str | None
    past_gifts_summary: str
    excluded_categories: list[str]
    feedback: str | None
    iteration: int
    search_results: list[dict]
    evaluated: list[dict]
    ranked: list[dict]
    status: str
    error: str


def _prompt_kwargs(state: GiftGraphState) -> dict:
    return {
        "age_range": state.get("age_range"),
        "past_gifts_summary": state.get("past_gifts_summary") or "",
        "excluded_categories": state.get("excluded_categories") or [],
        "feedback": state.get("feedback"),
    }


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
    """Generate gift candidates from profile + occasion + optional MCP web search."""
    recipient = state["recipient"]
    occasion = state.get("occasion")
    profile_chunks = state.get("profile_chunks") or []
    feedback = state.get("feedback")
    web_results = ""
    search_source = "LLM"

    logger.info(
        "Gift search starting recipient=%s occasion=%r iteration=%d profile_chunks=%d discovery=%s",
        recipient,
        occasion,
        state.get("iteration", 1),
        len(profile_chunks),
        is_discovery_enabled(),
    )
    if feedback:
        logger.info("Gift search user feedback=%r", feedback[:200])
    if state.get("excluded_categories"):
        logger.info(
            "Gift search excluded categories=%s",
            state.get("excluded_categories"),
        )

    if is_discovery_enabled():
        query = build_discovery_query(
            recipient, occasion, profile_chunks, feedback
        )
        try:
            web_results = discover_gift_ideas(query)
            if web_results:
                search_source = "Exa+LLM"
                logger.info(
                    "Gift discovery Exa results chars=%d query=%r",
                    len(web_results),
                    query[:200],
                )
        except Exception:
            logger.exception("Gift discovery Exa MCP failed — continuing with LLM only")

    try:
        prompt_kwargs = {**_prompt_kwargs(state), "web_results": web_results or None}
        raw = _llm_json(
            search_prompt(recipient, occasion, profile_chunks, **prompt_kwargs),
            node="search",
        )
        candidates = normalize_candidates(raw)
        if not candidates:
            candidates = fallback_candidates(recipient, occasion)
            status = f"search: used fallback candidates ({search_source} returned no ideas)"
            logger.warning("Gift search used fallback candidates for recipient=%s", recipient)
        else:
            status = f"search: found {len(candidates)} candidates (source={search_source})"
            for idea in candidates:
                logger.info(
                    "Gift search candidate source=%s recipient=%s title=%r category=%s price=%s",
                    search_source,
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
            evaluate_prompt(
                recipient, occasion, profile_chunks, candidates, **_prompt_kwargs(state)
            ),
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


@trace_agent("gift_recommender.verify")
def verify_node(state: GiftGraphState) -> dict:
    """Verification phase — Google Shopping + Amazon Rainforest MCP for top picks."""
    ranked = list(state.get("ranked") or [])
    if not ranked:
        return {
            "ranked": [],
            "status": (state.get("status") or "") + " | verify: no ranked ideas",
            "error": state.get("error") or "",
        }

    if not is_verification_enabled():
        logger.info("Gift verify skipped — verification MCP disabled")
        return {
            "ranked": ranked,
            "status": (state.get("status") or "") + " | verify: skipped (disabled)",
            "error": state.get("error") or "",
        }

    from src.shared.integration_settings import get_shopping_pipeline_settings

    settings = get_shopping_pipeline_settings()
    top_n = settings["verify_top_n"]
    recipient = state["recipient"]
    verified: list[dict] = []

    logger.info(
        "Gift verify starting recipient=%s ideas=%d verify_top_n=%d",
        recipient,
        len(ranked),
        top_n,
    )

    titles_to_verify = [idea["title"] for idea in ranked[:top_n]]
    retail_results = verify_gifts_retail(titles_to_verify, recipient=recipient)

    for index, idea in enumerate(ranked):
        enriched = dict(idea)
        if index < top_n and index < len(retail_results):
            enriched.update(retail_fields_for_display(retail_results[index]))
            logger.info(
                "Gift verify #%d title=%r live_price=%r amazon_rating=%r",
                index + 1,
                idea.get("title"),
                enriched.get("live_price"),
                enriched.get("amazon_rating"),
            )
        verified.append(enriched)

    return {
        "ranked": verified,
        "status": (state.get("status") or "")
        + f" | verify: retail checks for top {min(top_n, len(ranked))}",
        "error": state.get("error") or "",
    }


def build_gift_recommender_graph():
    graph = StateGraph(GiftGraphState)
    graph.add_node("search", search_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("rank", rank_node)
    graph.add_node("verify", verify_node)
    graph.set_entry_point("search")
    graph.add_edge("search", "evaluate")
    graph.add_edge("evaluate", "rank")
    graph.add_edge("rank", "verify")
    graph.add_edge("verify", END)
    return graph.compile()


_graph = None


def get_gift_recommender_graph():
    global _graph
    if _graph is None:
        _graph = build_gift_recommender_graph()
    return _graph


def run_gift_pipeline(
    request: GiftRequest,
    profile_chunks: list[str],
    *,
    age_range: str | None = None,
    past_gifts_summary: str = "",
    excluded_categories: list[str] | None = None,
    feedback: str | None = None,
    iteration: int = 1,
) -> GiftGraphState:
    """Run search → evaluate → rank → verify."""
    logger.info(
        "Gift pipeline iteration=%d pattern=LangGraph-linear (not ReAct)",
        iteration,
    )
    graph = get_gift_recommender_graph()
    return graph.invoke(
        {
            "recipient": request.recipient,
            "occasion": request.occasion,
            "profile_chunks": profile_chunks,
            "age_range": age_range,
            "past_gifts_summary": past_gifts_summary,
            "excluded_categories": excluded_categories or [],
            "feedback": feedback,
            "iteration": iteration,
            "search_results": [],
            "evaluated": [],
            "ranked": [],
            "status": "starting",
            "error": "",
        }
    )
