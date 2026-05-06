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


BUDGET_VARIANTS = (
    {
        "id": "small",
        "label": "Lista chica",
        "description": "Pocos juegos, ticket más alto y prioridad por score.",
        "strategy": "high_score",
    },
    {
        "id": "balanced",
        "label": "Lista media",
        "description": "Balance entre score, valor y cantidad de juegos.",
        "strategy": "balanced",
    },
    {
        "id": "large",
        "label": "Lista grande",
        "description": "Más juegos, ticket más bajo y valor razonable dentro del presupuesto.",
        "strategy": "low_price",
    },
)


RECOMMENDED_COLLECTION_DEFINITIONS = (
    {
        "id": "recommended_for_you",
        "title": "Recomendado para ti",
        "label": "Recomendado para ti",
        "description": "Mezcla señales de score, wishlist y calidad para empezar por lo más prometedor.",
        "source_signals": ["top_picks", "score_reasons", "score"],
    },
    {
        "id": "best_savings",
        "title": "Mayor ahorro",
        "label": "Mayor ahorro",
        "description": "Ordena ofertas por descuentos fuertes sin recalibrar el score base.",
        "source_signals": ["discount", "price_raw"],
    },
    {
        "id": "steam_deck",
        "title": "Steam Deck",
        "label": "Steam Deck",
        "description": "Destaca juegos Verified o Playable cuando esa señal está disponible.",
        "source_signals": ["top_picks.deck", "deck"],
    },
    {
        "id": "acclaimed",
        "title": "Aclamados",
        "label": "Aclamados",
        "description": "Prioriza juegos con reviews o Metacritic fuertes.",
        "source_signals": ["review", "review_pct", "metacritic_score"],
    },
    {
        "id": "genre_style",
        "title": "Por género/estilo",
        "label": "Por género/estilo",
        "description": "Agrupa ofertas alrededor del género o estilo más repetido en los datos actuales.",
        "source_signals": ["genres", "tags"],
    },
)


def build_gift_ideas(friend_set, deals, owned):
    """Find deals that the friend wants but you don't own."""
    owned_set = set(owned.keys())
    matching = [deal for deal in deals if deal["appid"] in friend_set and deal["appid"] not in owned_set]
    return sorted(matching, key=lambda deal: -deal["discount"])


def _safe_number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _collection_appid(item: dict) -> str:
    return str(item.get("appid") or item.get("steam_appid") or "").strip()


def _merge_collection_sources(deals: list[dict], top_picks: list[dict] | None) -> list[dict]:
    by_appid: dict[str, dict] = {}
    ordered_appids: list[str] = []
    for deal in deals or []:
        appid = _collection_appid(deal)
        if not appid:
            continue
        by_appid[appid] = dict(deal)
        ordered_appids.append(appid)
    for pick in top_picks or []:
        appid = _collection_appid(pick)
        if not appid:
            continue
        by_appid[appid] = {**by_appid.get(appid, {}), **dict(pick)}
        if appid not in ordered_appids:
            ordered_appids.append(appid)
    return [by_appid[appid] for appid in ordered_appids]


def _review_pct(item: dict) -> int | None:
    review = item.get("review")
    if isinstance(review, dict) and review.get("pct") is not None:
        return int(_safe_number(review.get("pct")))
    for key in ("review_pct", "reviews_pct", "positive_review_pct"):
        if item.get(key) is not None:
            return int(_safe_number(item.get(key)))
    return None


def _deck_category(item: dict) -> int:
    for key in ("deck", "deck_cat", "deck_category", "steam_deck"):
        if item.get(key) is not None:
            return int(_safe_number(item.get(key)))
    return 0


def _style_terms(item: dict) -> list[str]:
    terms: list[str] = []
    for key in ("genres", "tags"):
        raw = item.get(key)
        if isinstance(raw, dict):
            terms.extend(str(term).strip() for term in raw.keys())
        elif isinstance(raw, list):
            for value in raw:
                if isinstance(value, dict):
                    terms.append(str(value.get("description") or value.get("name") or "").strip())
                else:
                    terms.append(str(value).strip())
    return [term for term in terms if term]


def _collection_item(item: dict, reason: str) -> dict:
    return {
        "appid": _collection_appid(item),
        "name": item.get("name") or item.get("steam_name") or "Juego desconocido",
        "reason": reason,
        "score": round(_safe_number(item.get("score")), 1) if item.get("score") is not None else None,
        "discount": int(_safe_number(item.get("discount"))),
        "price_final": item.get("price_final") or item.get("price") or "",
    }


def _dedupe_collection_items(items: list[dict], limit: int) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in items:
        appid = item.get("appid")
        if not appid or appid in seen:
            continue
        seen.add(appid)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _collection_payload(collection_id: str, items: list[dict]) -> dict | None:
    if not items:
        return None
    definition = next(
        item for item in RECOMMENDED_COLLECTION_DEFINITIONS if item["id"] == collection_id
    )
    return {**definition, "items": items}


def _sort_by_score_discount_name(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda item: (
            -_safe_number(item.get("score")),
            -_safe_number(item.get("discount")),
            str(item.get("name") or ""),
            _collection_appid(item),
        ),
    )


def _top_style_term(items: list[dict]) -> str:
    counts: dict[str, tuple[int, str]] = {}
    for item in items:
        for term in _style_terms(item):
            key = term.lower()
            count, label = counts.get(key, (0, term))
            counts[key] = (count + 1, label)
    if not counts:
        return ""
    return sorted(counts.values(), key=lambda value: (-value[0], value[1].lower()))[0][1]


def build_recommended_collections(
    deals: list[dict],
    top_picks: list[dict] | None = None,
    *,
    max_items_per_collection: int = 4,
) -> list[dict]:
    """Build deterministic recommendation collections from already available report data."""
    if max_items_per_collection <= 0:
        return []
    sources = _merge_collection_sources(deals, top_picks)
    if not sources:
        return []

    recommended = [
        _collection_item(
            item,
            (item.get("score_reasons") or [item.get("recommendation") or "score alto"])[0],
        )
        for item in _sort_by_score_discount_name([item for item in sources if item.get("score") is not None])
    ]
    best_savings = [
        _collection_item(item, f"{int(_safe_number(item.get('discount')))}% de descuento")
        for item in sorted(
            sources,
            key=lambda item: (
                -_safe_number(item.get("discount")),
                -_safe_number(item.get("score")),
                str(item.get("name") or ""),
            ),
        )
        if _safe_number(item.get("discount")) > 0
    ]
    deck_ready = [
        _collection_item(
            item,
            "Steam Deck Verified" if _deck_category(item) == 3 else "Steam Deck Playable",
        )
        for item in sorted(
            [item for item in sources if _deck_category(item) in {2, 3}],
            key=lambda item: (-_deck_category(item), -_safe_number(item.get("score")), str(item.get("name") or "")),
        )
    ]
    acclaimed = [
        _collection_item(
            item,
            f"Reviews {review}% positivas" if (review := _review_pct(item)) is not None and review >= 85 else f"Metacritic {int(_safe_number(item.get('metacritic_score')))}",
        )
        for item in sorted(
            [
                item for item in sources
                if (_review_pct(item) is not None and _review_pct(item) >= 85)
                or _safe_number(item.get("metacritic_score")) >= 80
            ],
            key=lambda item: (
                -max(_review_pct(item) or 0, int(_safe_number(item.get("metacritic_score")))),
                -_safe_number(item.get("score")),
                str(item.get("name") or ""),
            ),
        )
    ]
    style_term = _top_style_term(sources)
    genre_style = [
        _collection_item(item, f"Coincide con {style_term}, una señal repetida en estas ofertas")
        for item in _sort_by_score_discount_name(
            [item for item in sources if style_term and style_term.lower() in {term.lower() for term in _style_terms(item)}]
        )
    ]

    collections = [
        _collection_payload("recommended_for_you", _dedupe_collection_items(recommended, max_items_per_collection)),
        _collection_payload("best_savings", _dedupe_collection_items(best_savings, max_items_per_collection)),
        _collection_payload("steam_deck", _dedupe_collection_items(deck_ready, max_items_per_collection)),
        _collection_payload("acclaimed", _dedupe_collection_items(acclaimed, max_items_per_collection)),
        _collection_payload("genre_style", _dedupe_collection_items(genre_style, max_items_per_collection)),
    ]
    return [collection for collection in collections if collection is not None]


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


def build_promo_pick_reason(active_promo_context: dict | None) -> str:
    """Return a conservative pick reason based on active Steam promo context."""
    if not isinstance(active_promo_context, dict):
        return ""
    primary = active_promo_context.get("primary")
    category = ""
    if isinstance(primary, dict):
        category = str(primary.get("category", "") or "")
    if not category:
        categories = active_promo_context.get("categories", [])
        if isinstance(categories, list) and categories:
            category = str(categories[0] or "")

    reason_by_category = {
        "major_sale": "contexto de oferta grande: prioriza descuentos fuertes",
        "fest": "contexto de festival: revisa si encaja con la temática activa",
        "weeklong": "promo corta: útil si ya estaba en radar",
        "midweek": "promo corta: útil si ya estaba en radar",
        "weekend": "promo corta: útil si ya estaba en radar",
        "themed": "promo temática: valida si encaja con tus gustos",
    }
    return reason_by_category.get(category, "")


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


def _apply_promo_pick_reason(top_pick: dict, promo_reason: str) -> dict:
    if not promo_reason:
        return top_pick
    updated = dict(top_pick)
    reasons = list(updated.get("score_reasons") or [])
    if promo_reason not in reasons:
        reasons.append(promo_reason)
    updated["score_reasons"] = reasons
    return updated


def rank_top_picks(
    deals: list[dict],
    priorities: dict[str, int],
    reviews: dict[str, dict],
    hltb_hours: dict[str, float],
    deck_compat: dict[str, int],
    n: int = 10,
    active_promo_context: dict | None = None,
) -> list[dict]:
    """Rank deals by composite value score, return top N."""
    promo_reason = build_promo_pick_reason(active_promo_context)
    scored = [
        _apply_promo_pick_reason(
            _score_top_pick(deal, priorities, reviews, hltb_hours, deck_compat),
            promo_reason,
        )
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


def _budget_pick_cost(deal: dict) -> float:
    return deal.get("price_raw", 0) / 100


def _clone_budget_pick(deal: dict) -> dict:
    cloned = dict(deal)
    cloned["score_reasons"] = list(deal.get("score_reasons") or [])
    if deal.get("replacement_candidates"):
        cloned["replacement_candidates"] = [
            _clone_budget_pick(candidate)
            for candidate in deal.get("replacement_candidates", [])
        ]
    return cloned


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
            _clone_budget_pick(
                _budget_pick_payload(
                alert,
                score,
                top_pick=pick_contexts.get(alert["appid"]),
                )
            )
        )
        remaining -= cost
        selected_appids.add(alert["appid"])
    return selected, remaining, selected_appids


def _sorted_budget_candidates(candidates: list[dict], strategy: str) -> list[dict]:
    if strategy == "high_score":
        return sorted(
            candidates,
            key=lambda deal: (
                -deal["score"],
                -deal.get("price_raw", 0),
                -deal.get("efficiency", 0),
                deal["appid"],
            ),
        )
    if strategy == "low_price":
        return sorted(
            candidates,
            key=lambda deal: (
                deal.get("price_raw", 0),
                -deal["score"],
                -deal.get("efficiency", 0),
                deal["appid"],
            ),
        )
    return sorted(
        candidates,
        key=lambda deal: (
            -deal.get("efficiency", 0),
            -deal["score"],
            deal.get("price_raw", 0),
            deal["appid"],
        ),
    )


def _ordered_with_soft_deprioritization(
    candidates: list[dict], deprioritized_appids: set[str] | None
) -> list[dict]:
    if not deprioritized_appids:
        return candidates
    preferred = [deal for deal in candidates if deal["appid"] not in deprioritized_appids]
    fallback = [deal for deal in candidates if deal["appid"] in deprioritized_appids]
    return [*preferred, *fallback]


def _select_by_strategy(
    candidates: list[dict],
    remaining: float,
    excluded_appids: set[str],
    *,
    strategy: str,
    deprioritized_appids: set[str] | None = None,
) -> tuple[list[dict], float]:
    selected = []
    ordered_candidates = _ordered_with_soft_deprioritization(
        _sorted_budget_candidates(candidates, strategy),
        deprioritized_appids,
    )
    for candidate in ordered_candidates:
        if candidate["appid"] in excluded_appids:
            continue
        cost = _budget_pick_cost(candidate)
        if cost <= 0 or cost > remaining:
            continue
        selected.append(_clone_budget_pick(candidate))
        remaining -= cost
        if remaining <= 0:
            break
    return selected, remaining


def _estimate_budget_summary(selected: list[dict], budget_mxn: float, remaining: float) -> dict:
    total_spent = budget_mxn - remaining
    return {
        "budget": budget_mxn,
        "selected": selected,
        "total_spent": round(total_spent, 2),
        "total_savings": round(_estimate_total_savings(selected), 2),
        "remaining": round(remaining, 2),
        "games_count": len(selected),
    }


def _build_replacement_candidates(selected: list[dict], candidates: list[dict], remaining: float, budget_mxn: float, *, strategy: str, limit: int = 3) -> list[dict]:
    selected_appids = {deal["appid"] for deal in selected}
    ordered_candidates = _sorted_budget_candidates(candidates, strategy)
    total_spent = budget_mxn - remaining
    used_primary_replacements: set[str] = set()
    enriched = []
    for deal in selected:
        current_cost = _budget_pick_cost(deal)
        swap_budget = remaining + _budget_pick_cost(deal)
        alternatives = []
        for prefer_new_primary in (True, False):
            for candidate in ordered_candidates:
                appid = candidate["appid"]
                if appid in selected_appids:
                    continue
                if any(existing["appid"] == appid for existing in alternatives):
                    continue
                if prefer_new_primary and appid in used_primary_replacements:
                    continue
                cost = _budget_pick_cost(candidate)
                if cost <= 0 or cost > swap_budget:
                    continue
                replacement = _clone_budget_pick(candidate)
                replacement["swap_total_spent"] = round(
                    total_spent - current_cost + cost, 2
                )
                replacement["swap_remaining"] = round(swap_budget - cost, 2)
                alternatives.append(replacement)
                if len(alternatives) >= limit:
                    break
            if len(alternatives) >= limit:
                break
        enriched_deal = _clone_budget_pick(deal)
        if alternatives:
            used_primary_replacements.add(alternatives[0]["appid"])
            enriched_deal["replacement_candidates"] = alternatives
        enriched.append(enriched_deal)
    return enriched


def _build_budget_variant(
    variant: dict,
    candidates: list[dict],
    budget_mxn: float,
    watchlist_alerts,
    pick_scores: dict[str, float],
    pick_contexts: dict[str, dict],
    *,
    deprioritized_appids: set[str] | None = None,
) -> dict:
    watchlist_selected, remaining, watchlist_appids = _select_watchlist_hits(
        watchlist_alerts,
        pick_scores,
        budget_mxn,
        pick_contexts,
    )
    strategy_selected, remaining = _select_by_strategy(
        candidates,
        remaining,
        watchlist_appids,
        strategy=variant["strategy"],
        deprioritized_appids=deprioritized_appids,
    )
    selected = [*watchlist_selected, *strategy_selected]
    selected = _build_replacement_candidates(
        selected,
        candidates,
        remaining,
        budget_mxn,
        strategy=variant["strategy"],
    )
    summary = _estimate_budget_summary(selected, budget_mxn, remaining)
    return {
        **summary,
        "id": variant["id"],
        "label": variant["label"],
        "description": variant["description"],
        "strategy": variant["strategy"],
    }


def _build_budget_actions(variants: list[dict], *, selected_variant: str) -> dict:
    replaceable_by_variant = {
        variant["id"]: [
            deal["appid"]
            for deal in variant.get("selected", [])
            if deal.get("replacement_candidates")
        ]
        for variant in variants
    }
    return {
        "reroll_list": {
            "available": len(variants) > 1,
            "default_variant": selected_variant,
            "variant_ids": [variant["id"] for variant in variants],
        },
        "replace_game": {
            "available": any(replaceable_by_variant.values()),
            "candidate_limit": 3,
            "replaceable_by_variant": replaceable_by_variant,
        },
    }


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
    balanced_config = next(
        variant for variant in BUDGET_VARIANTS if variant["id"] == "balanced"
    )
    primary_variant = _build_budget_variant(
        balanced_config,
        candidates,
        budget_mxn,
        watchlist_alerts,
        pick_scores,
        pick_contexts,
    )
    primary_appids = {deal["appid"] for deal in primary_variant["selected"]}
    variants = []
    for variant in BUDGET_VARIANTS:
        if variant["id"] == primary_variant["id"]:
            variants.append(primary_variant)
            continue
        variants.append(
            _build_budget_variant(
                variant,
                candidates,
                budget_mxn,
                watchlist_alerts,
                pick_scores,
                pick_contexts,
                deprioritized_appids=primary_appids,
            )
        )
    return {
        **_estimate_budget_summary(primary_variant["selected"], budget_mxn, primary_variant["remaining"]),
        "selected_variant": primary_variant["id"],
        "variants": variants,
        "actions": _build_budget_actions(
            variants,
            selected_variant=primary_variant["id"],
        ),
    }
