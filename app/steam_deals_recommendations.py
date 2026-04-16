from __future__ import annotations

from datetime import date


SCORE_WEIGHTS = {
    "discount": 0.22,
    "reviews": 0.26,
    "priority": 0.18,
    "price_per_hour": 0.14,
    "deck": 0.10,
    "age": 0.05,
    "metacritic": 0.05,
}


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


def _deck_signal(deck_cat: int) -> int:
    return {3: 100, 2: 70, 1: 0, 0: 50}.get(deck_cat, 50)


def _score_signals(
    discount: int,
    review_pct: int | None,
    priority: int,
    price_per_hour: float | None,
    deck_cat: int,
    release_year: int | None,
    metacritic_score: int | None,
) -> dict[str, float]:
    return {
        "discount": min(discount, 100),
        "reviews": review_pct if review_pct is not None else 50,
        "priority": _priority_score(priority),
        "price_per_hour": _price_per_hour_score(price_per_hour),
        "deck": _deck_signal(deck_cat),
        "age": _age_score(release_year),
        "metacritic": _metacritic_signal(metacritic_score),
    }


def _weighted_score(signals: dict[str, float]) -> float:
    return sum(signals[key] * SCORE_WEIGHTS[key] for key in SCORE_WEIGHTS)


def _recommendation_label(score: float) -> str:
    if score >= 85:
        return "Comprar ahora"
    if score >= 72:
        return "Muy buena oferta"
    if score >= 60:
        return "Vale la pena"
    return "Solo si ya lo traías en radar"


def _signal_reason_candidates(
    signals: dict[str, float],
    *,
    discount: int,
    review_pct: int | None,
    priority: int,
    price_per_hour: float | None,
    deck_cat: int,
    release_year: int | None,
    metacritic_score: int | None,
) -> list[tuple[float, str]]:
    candidates: list[tuple[float, str] | None] = [
        (signals["reviews"] * SCORE_WEIGHTS["reviews"], "reviews muy positivas") if review_pct is not None and review_pct >= 90 else None,
        (signals["reviews"] * SCORE_WEIGHTS["reviews"], "reviews sólidas") if review_pct is not None and 80 <= review_pct < 90 else None,
        (signals["discount"] * SCORE_WEIGHTS["discount"], "descuento muy raro de ver") if discount >= 85 else None,
        (signals["discount"] * SCORE_WEIGHTS["discount"], "descuento fuerte") if 70 <= discount < 85 else None,
        (signals["priority"] * SCORE_WEIGHTS["priority"], "prioridad alta en tu wishlist") if 0 < priority <= 10 else None,
        (signals["priority"] * SCORE_WEIGHTS["priority"], "bien posicionado en tu wishlist") if 10 < priority <= 50 else None,
        (signals["price_per_hour"] * SCORE_WEIGHTS["price_per_hour"], "excelente $/hora estimado") if price_per_hour is not None and price_per_hour <= 3 else None,
        (signals["price_per_hour"] * SCORE_WEIGHTS["price_per_hour"], "buen $/hora estimado") if price_per_hour is not None and 3 < price_per_hour <= 6 else None,
        (signals["deck"] * SCORE_WEIGHTS["deck"], "Deck Verified") if deck_cat == 3 else None,
        (signals["deck"] * SCORE_WEIGHTS["deck"], "Deck Playable") if deck_cat == 2 else None,
        (signals["metacritic"] * SCORE_WEIGHTS["metacritic"], "Metacritic fuerte") if metacritic_score is not None and metacritic_score >= 85 else None,
        (signals["metacritic"] * SCORE_WEIGHTS["metacritic"], "Metacritic sólido") if metacritic_score is not None and 75 <= metacritic_score < 85 else None,
        (signals["age"] * SCORE_WEIGHTS["age"], "todavía reciente") if release_year is not None and date.today().year - release_year <= 3 else None,
    ]
    return [candidate for candidate in candidates if candidate is not None]


def build_score_explanation(
    discount: int,
    review_pct: int | None,
    priority: int,
    price_per_hour: float | None,
    deck_cat: int,
    release_year: int | None = None,
    metacritic_score: int | None = None,
) -> dict[str, object]:
    signals = _score_signals(
        discount,
        review_pct,
        priority,
        price_per_hour,
        deck_cat,
        release_year,
        metacritic_score,
    )
    score = _weighted_score(signals)
    reasons = [
        text
        for _weight, text in sorted(
            _signal_reason_candidates(
                signals,
                discount=discount,
                review_pct=review_pct,
                priority=priority,
                price_per_hour=price_per_hour,
                deck_cat=deck_cat,
                release_year=release_year,
                metacritic_score=metacritic_score,
            ),
            key=lambda item: -item[0],
        )[:3]
    ]
    if not reasons:
        reasons = ["balance general sólido entre precio y calidad"]
    return {
        "recommendation": _recommendation_label(score),
        "score_reasons": reasons,
    }


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
    return _weighted_score(
        _score_signals(
            discount,
            review_pct,
            priority,
            price_per_hour,
            deck_cat,
            release_year,
            metacritic_score,
        )
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
    explanation = build_score_explanation(
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
        "recommendation": explanation["recommendation"],
        "score_reasons": explanation["score_reasons"],
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


def _pick_context_map(top_picks) -> dict[str, dict]:
    return {top_pick["appid"]: top_pick for top_pick in (top_picks or [])}


def _budget_pick_payload(deal: dict, score: float, *, top_pick: dict | None = None, efficiency: float | None = None) -> dict:
    payload = {
        **deal,
        "score": score,
        "recommendation": (top_pick or {}).get("recommendation") or _recommendation_label(score),
        "score_reasons": list((top_pick or {}).get("score_reasons") or []),
    }
    if efficiency is not None:
        payload["efficiency"] = efficiency
    return payload


def _build_budget_candidates(deals, pick_scores: dict[str, float], pick_contexts: dict[str, dict]) -> list[dict]:
    candidates = []
    for deal in deals:
        price = deal.get("price_raw", 0) / 100
        if price <= 0:
            continue
        score = pick_scores.get(deal["appid"], 50.0)
        candidates.append(
            _budget_pick_payload(
                deal,
                score,
                top_pick=pick_contexts.get(deal["appid"]),
                efficiency=score / price,
            )
        )
    return candidates


def _select_watchlist_hits(watchlist_alerts, pick_scores: dict[str, float], remaining: float, pick_contexts: dict[str, dict]):
    selected = []
    selected_appids = set()
    for alert in sorted(watchlist_alerts or [], key=lambda deal: deal.get("price_raw", 0)):
        cost = alert.get("price_raw", 0) / 100
        if cost <= 0 or cost > remaining:
            continue
        score = pick_scores.get(alert["appid"], 50.0)
        selected.append(
            _budget_pick_payload(
                alert,
                score,
                top_pick=pick_contexts.get(alert["appid"]),
            )
        )
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
    pick_contexts = _pick_context_map(top_picks)
    candidates = _build_budget_candidates(deals, pick_scores, pick_contexts)
    watchlist_selected, remaining, watchlist_appids = _select_watchlist_hits(
        watchlist_alerts,
        pick_scores,
        budget_mxn,
        pick_contexts,
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
