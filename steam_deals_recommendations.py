from __future__ import annotations

from datetime import date


def build_gift_ideas(friend_set, deals, owned):
    """Find deals that the friend wants but you don't own."""
    owned_set = set(owned.keys())
    matching = [deal for deal in deals if deal["appid"] in friend_set and deal["appid"] not in owned_set]
    return sorted(matching, key=lambda deal: -deal["discount"])


def _priority_score(priority: int) -> int:
    if priority == 0:
        return 30
    if priority <= 10:
        return 100
    if priority <= 50:
        return 80
    if priority <= 200:
        return 60
    if priority <= 500:
        return 40
    return 20


def _price_per_hour_score(price_per_hour: float | None) -> float:
    if price_per_hour is None or price_per_hour <= 0:
        return 50
    return max(0, min(100, 100 - price_per_hour * 2))


def _age_score(release_year: int | None) -> int:
    if release_year is None:
        return 50
    age = max(0, date.today().year - release_year)
    if age <= 1:
        return 100
    if age <= 3:
        return 80
    if age <= 5:
        return 60
    if age <= 8:
        return 50
    return 35


def _metacritic_signal(metacritic_score: int | None) -> int:
    if metacritic_score is None:
        return 50
    if metacritic_score >= 85:
        return 100
    if metacritic_score >= 75:
        return 80
    if metacritic_score >= 60:
        return 60
    return 30


def compute_value_score(
    discount: int,
    review_pct: int | None,
    priority: int,
    price_per_hour: float | None,
    deck_cat: int,
    release_year: int | None = None,
    metacritic_score: int | None = None,
) -> float:
    """Compute a 0-100 value score combining multiple signals."""
    deck_scores = {3: 100, 2: 70, 1: 0, 0: 50}
    signals = {
        "discount": min(discount, 100),
        "reviews": review_pct if review_pct is not None else 50,
        "priority": _priority_score(priority),
        "price_per_hour": _price_per_hour_score(price_per_hour),
        "deck": deck_scores.get(deck_cat, 50),
        "age": _age_score(release_year),
        "metacritic": _metacritic_signal(metacritic_score),
    }
    return (
        signals["discount"] * 0.22
        + signals["reviews"] * 0.26
        + signals["priority"] * 0.18
        + signals["price_per_hour"] * 0.14
        + signals["deck"] * 0.10
        + signals["age"] * 0.05
        + signals["metacritic"] * 0.05
    )


def _score_top_pick(
    deal: dict,
    priorities: dict[str, int],
    reviews: dict[str, dict],
    hltb_hours: dict[str, float],
    deck_compat: dict[str, int],
) -> dict:
    appid = deal["appid"]
    review = reviews.get(appid)
    review_pct = review["pct"] if review else None
    priority = priorities.get(appid, 0)
    hours = hltb_hours.get(appid)
    price_raw = deal.get("price_raw", 0)
    price_per_hour = (price_raw / 100) / hours if hours and hours > 0 and price_raw > 0 else None
    deck_cat = deck_compat.get(appid, 0)
    metacritic_score = deal.get("metacritic_score")
    score = compute_value_score(
        deal["discount"],
        review_pct,
        priority,
        price_per_hour,
        deck_cat,
        release_year=deal.get("release_year"),
        metacritic_score=metacritic_score,
    )
    return {
        "appid": appid,
        "name": deal["name"],
        "discount": deal["discount"],
        "price_final": deal["price_final"],
        "score": round(score, 1),
        "review": review,
        "deck": deck_cat,
        "priority": priority,
        "release_year": deal.get("release_year"),
        "linux_native": deal.get("linux_native", False),
        "metacritic_score": metacritic_score,
        "categories": deal.get("categories", []),
    }


def rank_top_picks(
    deals: list[dict],
    priorities: dict[str, int],
    reviews: dict[str, dict],
    hltb_hours: dict[str, float],
    deck_compat: dict[str, int],
    n: int = 10,
) -> list[dict]:
    """Rank deals by composite value score, return top N."""
    scored = [
        _score_top_pick(deal, priorities, reviews, hltb_hours, deck_compat)
        for deal in deals
    ]
    scored.sort(key=lambda deal: -deal["score"])
    return scored[:n]


def _pick_scores_map(top_picks) -> dict[str, float]:
    return {top_pick["appid"]: top_pick["score"] for top_pick in (top_picks or [])}


def _build_budget_candidates(deals, pick_scores: dict[str, float]) -> list[dict]:
    candidates = []
    for deal in deals:
        price = deal.get("price_raw", 0) / 100
        if price <= 0:
            continue
        score = pick_scores.get(deal["appid"], 50.0)
        candidates.append({**deal, "score": score, "efficiency": score / price})
    return candidates


def _select_watchlist_hits(watchlist_alerts, pick_scores: dict[str, float], remaining: float):
    selected = []
    selected_appids = set()
    for alert in sorted(watchlist_alerts or [], key=lambda deal: deal.get("price_raw", 0)):
        cost = alert.get("price_raw", 0) / 100
        if cost <= 0 or cost > remaining:
            continue
        score = pick_scores.get(alert["appid"], 50.0)
        selected.append({**alert, "score": score})
        remaining -= cost
        selected_appids.add(alert["appid"])
    return selected, remaining, selected_appids


def _select_by_efficiency(candidates: list[dict], remaining: float, excluded_appids: set[str]) -> tuple[list[dict], float]:
    selected = []
    for candidate in sorted(candidates, key=lambda deal: -deal["efficiency"]):
        if candidate["appid"] in excluded_appids:
            continue
        cost = candidate.get("price_raw", 0) / 100
        if cost <= 0 or cost > remaining:
            continue
        selected.append(candidate)
        remaining -= cost
        if remaining <= 0:
            break
    return selected, remaining


def _estimate_total_savings(selected: list[dict]) -> float:
    total_savings = 0.0
    for deal in selected:
        price = deal.get("price_raw", 0) / 100
        discount = deal.get("discount", 0)
        if discount <= 0 or discount >= 100:
            continue
        original = price * 100 / (100 - discount)
        total_savings += original - price
    return total_savings


def compute_budget_picks(deals, budget_mxn, top_picks, watchlist_alerts=None):
    """Greedy budget optimizer: pick best deals that fit within budget."""
    pick_scores = _pick_scores_map(top_picks)
    candidates = _build_budget_candidates(deals, pick_scores)
    watchlist_selected, remaining, watchlist_appids = _select_watchlist_hits(
        watchlist_alerts,
        pick_scores,
        budget_mxn,
    )
    efficiency_selected, remaining = _select_by_efficiency(candidates, remaining, watchlist_appids)
    selected = [*watchlist_selected, *efficiency_selected]
    total_spent = budget_mxn - remaining
    total_savings = _estimate_total_savings(selected)
    return {
        "budget": budget_mxn,
        "selected": selected,
        "total_spent": round(total_spent, 2),
        "total_savings": round(total_savings, 2),
        "remaining": round(remaining, 2),
        "games_count": len(selected),
    }
