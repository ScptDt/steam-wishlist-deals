from __future__ import annotations


def filter_by_genres(deals: list[dict], genres: list[str]) -> list[dict]:
    if not genres:
        return []
    matched = [deal for deal in deals if any(genre in deal_genre for genre in genres for deal_genre in deal.get("genres", []))]
    matched.sort(key=lambda deal: -deal["discount"])
    return matched


def _apply_price_filter(filtered: list[dict], filters: dict) -> list[dict]:
    if filters.get("max_price") is None:
        return filtered
    limit = filters["max_price"] * 100
    return [deal for deal in filtered if deal.get("price_raw", 0) <= limit]


def _apply_deck_filter(filtered: list[dict], filters: dict, deck_compat: dict[str, int]) -> list[dict]:
    if filters.get("deck_verified"):
        return [deal for deal in filtered if deck_compat.get(deal["appid"], 0) == 3]
    if filters.get("deck_only"):
        return [deal for deal in filtered if deck_compat.get(deal["appid"], 0) >= 2]
    return filtered


def _apply_review_filters(filtered: list[dict], filters: dict, reviews: dict[str, dict]) -> list[dict]:
    if filters.get("min_reviews") is not None:
        filtered = [
            deal
            for deal in filtered
            if (review := reviews.get(deal["appid"])) and review.get("pct", 0) >= filters["min_reviews"]
        ]
    if filters.get("min_review_count") is not None:
        filtered = [
            deal
            for deal in filtered
            if (review := reviews.get(deal["appid"])) and review.get("total", 0) >= filters["min_review_count"]
        ]
    return filtered


def _apply_hours_filter(filtered: list[dict], filters: dict, hltb_hours: dict[str, float]) -> list[dict]:
    if filters.get("max_hours") is None:
        return filtered
    return [
        deal
        for deal in filtered
        if (hours := hltb_hours.get(deal["appid"])) is not None and hours <= filters["max_hours"]
    ]


def _apply_new_only_filter(
    filtered: list[dict],
    filters: dict,
    previous_appids: set[str],
    comparison: dict | None,
) -> list[dict]:
    if not filters.get("new_only"):
        return filtered
    comp = comparison or {}
    new_set = comp.get("new_deals", set())
    if new_set:
        return [deal for deal in filtered if deal["appid"] in new_set]
    if previous_appids:
        return [deal for deal in filtered if deal["appid"] not in previous_appids]
    return filtered


def apply_filters(
    deals: list[dict],
    filters: dict,
    reviews: dict[str, dict],
    deck_compat: dict[str, int],
    hltb_hours: dict[str, float],
    previous_appids: set[str],
    comparison: dict | None = None,
) -> list[dict]:
    """Aplica filtros CLI avanzados sobre la lista de deals."""
    filtered = list(deals)
    filtered = _apply_price_filter(filtered, filters)
    filtered = _apply_deck_filter(filtered, filters, deck_compat)
    filtered = _apply_review_filters(filtered, filters, reviews)
    filtered = _apply_hours_filter(filtered, filters, hltb_hours)
    return _apply_new_only_filter(filtered, filters, previous_appids, comparison)
