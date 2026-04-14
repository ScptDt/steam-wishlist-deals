from __future__ import annotations

import csv
import io


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
    store_url_template,
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
    pick_scores = {tp["appid"]: tp["score"] for tp in (top_picks or [])}

    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
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
        appid = deal["appid"]
        review = reviews.get(appid)
        proton = protondb_data.get(appid)
        anticheat = anticheat_data.get(appid)
        low = historical_lows.get(appid)
        best_price = current_prices.get(appid)
        trend = local_trends.get(appid)
        hours = hltb_hours.get(appid)
        price_raw = deal.get("price_raw", 0)
        price_per_hour = (
            f"{(price_raw / 100) / hours:.2f}"
            if hours and hours > 0 and price_raw > 0
            else ""
        )
        priority = priorities.get(appid, 0)
        top_tags = get_top_tags(tags_data, appid, n=5)

        metacritic = deal.get("metacritic_score", "")
        multiplayer = multiplayer_badges(deal.get("categories", []))
        achievements = achievements_data.get(appid)

        writer.writerow(
            [
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
                f"{', '.join(anticheat.get('anticheats', []))} ({anticheat['status']})"
                if anticheat
                else "",
                "; ".join(top_tags),
                multiplayer,
                achievements["count"] if achievements else "",
                f"{achievements['avg_completion']:.1f}" if achievements else "",
                f"{hours:.1f}" if hours else "",
                price_per_hour,
                priority if priority > 0 else "",
                pick_scores.get(appid, ""),
                f"${low['price']:.0f} ({low['date']})" if low else "",
                f"${best_price['price']:.0f} en {best_price['store']}"
                if best_price
                else "",
                _csv_trend(trend) if trend else "",
                store_url_template.format(appid=appid),
            ]
        )

    return buf.getvalue()
