from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value)]
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _count_new_deals(deals: list[dict], previous_appids: set[str]) -> int:
    if not previous_appids:
        return 0
    return sum(1 for deal in deals if deal["appid"] not in previous_appids)


def generate_json(
    deals: list[dict],
    backlog_on_sale: list[dict],
    have_on_sale: list[dict],
    vanity: str,
    owned: dict[str, str],
    wishlist_appids: list[str],
    min_discount: int,
    genres: list[str],
    hltb_used: bool = False,
    family_appids: set[str] | None = None,
    sale_name: str = "",
    priorities: dict[str, int] | None = None,
    historical_lows: dict[str, dict] | None = None,
    previous_appids: set[str] | None = None,
    reviews: dict[str, dict] | None = None,
    deck_compat: dict[str, int] | None = None,
    current_prices: dict[str, dict] | None = None,
    top_picks: list[dict] | None = None,
    comparison: dict | None = None,
    sort_field: str = "discount",
    tags_data: dict[str, dict] | None = None,
    local_trends: dict[str, dict] | None = None,
    active_bundles: dict[str, list[dict]] | None = None,
    protondb_data: dict[str, dict] | None = None,
    anticheat_data: dict[str, dict] | None = None,
    achievements_data: dict[str, dict] | None = None,
    watchlist_alerts: list[dict] | None = None,
    budget_result: dict | None = None,
    compare_data: dict | None = None,
    gift_ideas: list[dict] | None = None,
    profile_display_name: str | None = None,
) -> str:
    previous_appids = previous_appids or set()
    family_appids = family_appids or set()
    priorities = priorities or {}
    historical_lows = historical_lows or {}
    reviews = reviews or {}
    deck_compat = deck_compat or {}
    current_prices = current_prices or {}
    top_picks = top_picks or []
    comparison = comparison or {}
    tags_data = tags_data or {}
    local_trends = local_trends or {}
    active_bundles = active_bundles or {}
    protondb_data = protondb_data or {}
    anticheat_data = anticheat_data or {}
    achievements_data = achievements_data or {}
    watchlist_alerts = watchlist_alerts or []
    gift_ideas = gift_ideas or []

    payload = {
        "meta": {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "profile": profile_display_name or vanity,
            "sale_name": sale_name or None,
        },
        "inputs": {
            "wishlist_count": len(wishlist_appids),
            "owned_count": len(owned),
            "family_count": len(family_appids),
            "min_discount": min_discount,
            "genres": genres,
            "sort_field": sort_field,
            "hltb_used": hltb_used,
        },
        "summary": {
            "deals_count": len(deals),
            "backlog_on_sale_count": len(backlog_on_sale),
            "have_on_sale_count": len(have_on_sale),
            "new_deals_count": _count_new_deals(deals, previous_appids),
            "top_picks_count": len(top_picks),
            "watchlist_alerts_count": len(watchlist_alerts),
            "gift_ideas_count": len(gift_ideas),
        },
        "comparison": _json_safe(comparison),
        "top_picks": _json_safe(top_picks),
        "watchlist_alerts": _json_safe(watchlist_alerts),
        "budget_result": _json_safe(budget_result),
        "compare_data": _json_safe(compare_data),
        "gift_ideas": _json_safe(gift_ideas),
        "deals": _json_safe(deals),
        "backlog_on_sale": _json_safe(backlog_on_sale),
        "have_on_sale": _json_safe(have_on_sale),
        "priorities": _json_safe(priorities),
        "reviews": _json_safe(reviews),
        "deck_compat": _json_safe(deck_compat),
        "historical_lows": _json_safe(historical_lows),
        "current_prices": _json_safe(current_prices),
        "tags_data": _json_safe(tags_data),
        "local_trends": _json_safe(local_trends),
        "active_bundles": _json_safe(active_bundles),
        "protondb_data": _json_safe(protondb_data),
        "anticheat_data": _json_safe(anticheat_data),
        "achievements_data": _json_safe(achievements_data),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
