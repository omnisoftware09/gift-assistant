"""Gift idea scoring — embedding closeness + LLM rating → weighted rank."""

import logging
import math

from src.langchain_core.embeddings import get_embeddings

logger = logging.getLogger("gift_assistant.gift_recommender")

CLOSENESS_WEIGHT = 0.7
RATING_WEIGHT = 0.3


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _gift_text(gift: dict) -> str:
    return f"{gift.get('title', '')} {gift.get('description', '')}".strip()


def compute_profile_closeness(gift: dict, profile_chunks: list[str]) -> float:
    """
    Embed gift title+description and compare to profile chunks via cosine similarity.
    Returns 0-100 (higher = closer semantic match to stored profile).
    """
    if not profile_chunks:
        return 50.0

    text = _gift_text(gift)
    if not text:
        return 50.0

    embeddings = get_embeddings()
    gift_vec = embeddings.embed_query(text)
    profile_vecs = embeddings.embed_documents(profile_chunks)
    best = max(_cosine_similarity(gift_vec, pv) for pv in profile_vecs)
    return max(0.0, min(1.0, best)) * 100.0


def compute_final_score(closeness: float, rating: float) -> float:
    """Weighted rank: 70% embedding closeness + 30% LLM rating."""
    return CLOSENESS_WEIGHT * closeness + RATING_WEIGHT * rating


def enrich_with_closeness(ideas: list[dict], profile_chunks: list[str]) -> list[dict]:
    """Attach embedding-based closeness to each gift idea."""
    for idea in ideas:
        closeness = compute_profile_closeness(idea, profile_chunks)
        idea["closeness"] = closeness
        logger.info(
            "Gift closeness (embedding) gift=%r closeness=%.1f/100 profile_chunks=%d",
            idea.get("title"),
            closeness,
            len(profile_chunks),
        )
    return ideas


def apply_final_scores(ideas: list[dict]) -> list[dict]:
    """Compute final_score from closeness + rating on each idea."""
    for idea in ideas:
        closeness = float(idea.get("closeness", 50.0))
        rating = float(idea.get("rating", 50.0))
        idea["final_score"] = compute_final_score(closeness, rating)
    return ideas


def rank_ideas_weighted(ideas: list[dict], top_n: int = 3) -> list[dict]:
    """Rank by final_score = 0.7 * closeness + 0.3 * rating."""
    scored = apply_final_scores(list(ideas))
    ranked = sorted(scored, key=lambda item: item.get("final_score", 0), reverse=True)
    return ranked[:top_n]
