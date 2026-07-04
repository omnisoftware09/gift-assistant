from src.agents.subagents.gift_recommender.parsing import (
    apply_ratings,
    extract_json_array,
    normalize_candidates,
)
from src.agents.subagents.gift_recommender.scoring import (
    compute_final_score,
    rank_ideas_weighted,
)


def test_extract_json_array_from_fenced_output():
    text = """Here you go:
```json
[{"title": "Mug", "description": "Ceramic", "price_range": "$15", "category": "home"}]
```
"""
    data = extract_json_array(text)
    assert len(data) == 1
    assert data[0]["title"] == "Mug"


def test_weighted_rank_prefers_closeness_and_rating():
    ideas = [
        {
            "title": "High closeness",
            "description": "",
            "price_range": "",
            "category": "",
            "closeness": 90.0,
            "rating": 50.0,
            "reason": "a",
        },
        {
            "title": "High rating",
            "description": "",
            "price_range": "",
            "category": "",
            "closeness": 50.0,
            "rating": 90.0,
            "reason": "b",
        },
    ]
    # 0.7*90 + 0.3*50 = 63 + 15 = 78
    # 0.7*50 + 0.3*90 = 35 + 27 = 62
    ranked = rank_ideas_weighted(ideas, top_n=1)
    assert ranked[0]["title"] == "High closeness"
    assert ranked[0]["final_score"] == compute_final_score(90.0, 50.0)


def test_apply_ratings_accepts_score_or_rating_key():
    candidates = normalize_candidates(
        [{"title": "A", "description": "one", "price_range": "$10", "category": "x"}]
    )
    evaluated = apply_ratings(candidates, [{"title": "A", "rating": 88, "reason": "great"}])
    assert evaluated[0]["rating"] == 88

    evaluated2 = apply_ratings(
        candidates, [{"title": "A", "score": 77, "reason": "legacy"}]
    )
    assert evaluated2[0]["rating"] == 77


def test_apply_ratings_defaults_missing():
    candidates = [{"title": "X", "description": "", "price_range": "", "category": ""}]
    evaluated = apply_ratings(candidates, [])
    assert evaluated[0]["rating"] == 50
