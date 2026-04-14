from __future__ import annotations

import csv
import io


STORE_URL = "https://store.steampowered.com/app/{appid}/"

CSV_DECK = {3: "Verified", 2: "Playable", 1: "Unsupported", 0: ""}
CSV_PROTON = {
    "native": "Native",
    "platinum": "Platinum",
    "gold": "Gold",
    "silver": "Silver",
    "bronze": "Bronze",
    "borked": "Borked",
}


def _csv_trend(trend: dict) -> str:
    if trend.get("is_first_time"):
        return "1ra vez"
    if trend.get("is_best_local") and trend.get("times_on_sale", 0) > 1:
        return "Min. local"
    if trend.get("is_first_at_price"):
        return "1ra vez a este precio"
    return f"{trend.get('times_on_sale', 0)}x, prom {trend.get('avg_fmt', '?')}"


def _build_csv_row(
    deal: dict,
    priorities: dict[str, int],
    reviews: dict[str, dict],
    deck_compat: dict[str, int],
    protondb_data: dict[str, dict],
    anticheat_data: dict[str, dict],
    tags_data: dict[str, dict],
    hltb_hours: dict[str, float],
    historical_lows: dict[str, dict],
    current_prices: dict[str, dict],
    pick_scores: dict[str, int],
    local_trends: dict[str, dict],
    achievements_data: dict[str, dict],
    *,
    get_top_tags,
    multiplayer_badges,
) -> list[object]:
    appid = deal["appid"]
    review = reviews.get(appid)
    proton = protondb_data.get(appid)
    anticheat = anticheat_data.get(appid)
    historical_low = historical_lows.get(appid)
    best_price = current_prices.get(appid)
    trend = local_trends.get(appid)
    hours = hltb_hours.get(appid)
    achievement = achievements_data.get(appid)
    price_raw = deal.get("price_raw", 0)
    price_per_hour = f"{(price_raw / 100) / hours:.2f}" if hours and hours > 0 and price_raw > 0 else ""
    priority = priorities.get(appid, 0)
    top_tags = get_top_tags(tags_data, appid, n=5)
    metacritic = deal.get("metacritic_score", "")
    mode = multiplayer_badges(deal.get("categories", []))

    return [
        appid,
        deal["name"],
        deal["discount"],
        deal["price_final"],
        deal.get("price_original", ""),
        deal.get("release_year", ""),
        review["desc"] if review else "",
        review["pct"] if review else "",
        review["total"] if review else "",
        metacritic if metacritic else "",
        CSV_DECK.get(deck_compat.get(appid, 0), ""),
        CSV_PROTON.get(proton["tier"], "") if proton else "",
        f"{', '.join(anticheat.get('anticheats', []))} ({anticheat['status']})" if anticheat else "",
        "; ".join(top_tags),
        mode,
        achievement["count"] if achievement else "",
        f"{achievement['avg_completion']:.1f}" if achievement else "",
        f"{hours:.1f}" if hours else "",
        price_per_hour,
        priority if priority > 0 else "",
        pick_scores.get(appid, ""),
        f"${historical_low['price']:.0f} ({historical_low['date']})" if historical_low else "",
        f"${best_price['price']:.0f} en {best_price['store']}" if best_price else "",
        _csv_trend(trend) if trend else "",
        STORE_URL.format(appid=appid),
    ]


def generate_csv(
    deals,
    priorities=None,
    reviews=None,
    deck_compat=None,
    protondb_data=None,
    anticheat_data=None,
    tags_data=None,
    hltb_hours=None,
    historical_lows=None,
    current_prices=None,
    top_picks=None,
    local_trends=None,
    achievements_data=None,
    *,
    get_top_tags,
    multiplayer_badges,
) -> str:
    priorities = priorities or {}
    reviews = reviews or {}
    deck_compat = deck_compat or {}
    protondb_data = protondb_data or {}
    anticheat_data = anticheat_data or {}
    tags_data = tags_data or {}
    hltb_hours = hltb_hours or {}
    historical_lows = historical_lows or {}
    current_prices = current_prices or {}
    local_trends = local_trends or {}
    achievements_data = achievements_data or {}
    pick_scores = {top_pick["appid"]: top_pick["score"] for top_pick in (top_picks or [])}

    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "AppID",
            "Name",
            "Discount%",
            "Price (MXN)",
            "Original Price",
            "Year",
            "Reviews",
            "Reviews%",
            "ReviewCount",
            "Metacritic",
            "Deck",
            "ProtonDB",
            "AntiCheat",
            "Tags",
            "Mode",
            "Achievements",
            "AvgCompletion%",
            "HLTB Hours",
            "Price/Hour",
            "Priority",
            "Score",
            "Historical Low",
            "Best Price",
            "Trend",
            "URL",
        ]
    )

    for deal in deals:
        writer.writerow(
            _build_csv_row(
                deal,
                priorities,
                reviews,
                deck_compat,
                protondb_data,
                anticheat_data,
                tags_data,
                hltb_hours,
                historical_lows,
                current_prices,
                pick_scores,
                local_trends,
                achievements_data,
                get_top_tags=get_top_tags,
                multiplayer_badges=multiplayer_badges,
            )
        )

    return buffer.getvalue()
