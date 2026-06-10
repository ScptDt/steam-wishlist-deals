from __future__ import annotations

import re
from datetime import date

from app.steam_deals_tags import canonical_steam_tag_key, normalize_steam_tag_terms


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
        "id": "community_favorites",
        "title": "Favoritos de comunidad",
        "label": "Favoritos de comunidad",
        "description": "Cruza adopción/popularidad ya cacheada con calidad mínima para destacar juegos con respaldo comunitario.",
        "source_signals": [
            "review.total",
            "tags_data.players.owners",
            "tags_data.players.ccu",
            "tags_data.players.players_2weeks",
            "review_pct",
            "score",
            "metacritic_score",
        ],
    },
    {
        "id": "genre_style",
        "title": "Por género/estilo",
        "label": "Por género/estilo",
        "description": "Agrupa ofertas alrededor del género o estilo más repetido en los datos actuales.",
        "source_signals": ["genres", "tags"],
    },
    {
        "id": "story_rich",
        "title": "Story Rich",
        "label": "Story Rich",
        "description": "Destaca juegos narrativos solo cuando existe una señal Story Rich explícita.",
        "source_signals": ["genres.story_rich", "tags.story_rich"],
    },
    {
        "id": "singleplayer",
        "title": "Singleplayer",
        "label": "Singleplayer",
        "description": "Destaca juegos para un jugador solo cuando esa señal está explícita y no es trivial.",
        "source_signals": ["categories.single_player", "genres.singleplayer", "tags.singleplayer"],
    },
)

COMMUNITY_MIN_REVIEW_COUNT = 500
COMMUNITY_MIN_OWNERS_HIGH = 200_000
COMMUNITY_MIN_CCU = 500
COMMUNITY_MIN_RECENT_PLAYERS = 10_000
COMMUNITY_MIN_REVIEW_PCT = 80
COMMUNITY_MIN_SCORE = 72
COMMUNITY_MIN_METACRITIC = 75


def _gift_context_reasons(
    deal: dict,
    *,
    activity_terms: list[dict],
    is_overlap: bool,
    max_reasons: int,
) -> tuple[list[str], list[str]]:
    reasons = ["lo tiene en wishlist"]
    signals = ["friend_wishlist"]
    if is_overlap:
        reasons.append("también aparece en la wishlist compartida")
        signals.append("shared_wishlist")
    if _safe_number(deal.get("score")) >= 80:
        reasons.append(f"score alto del reporte: {_safe_number(deal.get('score')):.0f}")
        signals.append("report_score")
    if _safe_number(deal.get("discount")) >= 50:
        reasons.append(f"descuento fuerte: {int(_safe_number(deal.get('discount')))}%")
        signals.append("discount")
    matched_terms = _matched_terms(deal, activity_terms, limit=2) if activity_terms else []
    if matched_terms:
        reasons.append(f"se parece a su actividad reciente: {', '.join(matched_terms)}")
        signals.append("friend_activity")
    return reasons[:max_reasons], signals


def _gift_reason_limit(value) -> int:
    return max(1, int(_safe_number(value, 2)))


def build_gift_ideas(
    friend_set,
    deals,
    owned,
    *,
    overlap_appids=None,
    friend_activity_games=None,
    max_reasons: int = 2,
):
    """Find deals that the friend wants but you don't own."""
    friend_appids = _normalize_appid_set(friend_set)
    owned_set = _normalize_appid_set(owned)
    overlap_set = _normalize_appid_set(overlap_appids)
    activity_terms = _weighted_style_terms(
        _record_list(friend_activity_games),
        activity_weighted=True,
    )
    candidates: list[tuple[bool, dict]] = []
    for deal in deals or []:
        if not isinstance(deal, dict):
            continue
        appid = _collection_appid(deal)
        if not appid or appid not in friend_appids or appid in owned_set:
            continue
        is_overlap = appid in overlap_set
        reasons, signals = _gift_context_reasons(
            deal,
            activity_terms=activity_terms,
            is_overlap=is_overlap,
            max_reasons=_gift_reason_limit(max_reasons),
        )
        candidates.append(
            (
                is_overlap,
                {
                    **dict(deal),
                    "appid": appid,
                    "social_reasons": reasons,
                    "social_signals": signals,
                },
            )
        )
    non_overlap = [item for is_overlap, item in candidates if not is_overlap]
    selected = non_overlap if non_overlap else [item for _is_overlap, item in candidates]
    return sorted(
        selected,
        key=lambda deal: (
            -_safe_number(deal.get("discount")),
            -_safe_number(deal.get("score")),
            str(deal.get("name") or "").lower(),
        ),
    )


GROUP_GIFT_ADVISORY_COPY = "Idea para revisar; no abre carrito ni compra nada."
PROFILE_UNAVAILABLE_STATUSES = {
    "error",
    "invalid",
    "private",
    "unavailable",
    "not_public",
}


def build_multi_profile_gift_contract(
    my_wishlist_appids,
    friend_profiles,
    deals,
    owned,
    *,
    max_reasons: int = 2,
):
    """Build a local, advisory-only multi-friend gift contract."""
    my_set = _normalize_appid_set(my_wishlist_appids)
    compare_profiles = _compare_profile_entries(friend_profiles, my_set)
    valid_profiles = [profile for profile in compare_profiles if profile["status"] == "ok"]
    gift_ideas_by_friend = _build_gift_ideas_by_friend(
        valid_profiles,
        deals,
        owned,
        max_reasons=max_reasons,
    )
    shared_gift_ideas = _build_shared_gift_ideas(
        valid_profiles,
        deals,
        owned,
        max_reasons=max_reasons,
    )
    return {
        "compare_profiles": compare_profiles,
        "gift_ideas_by_friend": gift_ideas_by_friend,
        "shared_gift_ideas": shared_gift_ideas,
        "summary": {
            "profiles_count": len(compare_profiles),
            "valid_profiles_count": len(valid_profiles),
            "invalid_profiles_count": len(compare_profiles) - len(valid_profiles),
            "gift_ideas_by_friend_count": len(gift_ideas_by_friend),
            "shared_gift_ideas_count": len(shared_gift_ideas),
        },
        "advisory_only": True,
        "ranking_impact": "none",
        "advisory_copy": GROUP_GIFT_ADVISORY_COPY,
    }


def _compare_profile_entries(friend_profiles, my_set: set[str]) -> list[dict]:
    entries: list[dict] = []
    seen_keys: dict[str, int] = {}
    for index, profile in enumerate(_profile_records(friend_profiles), 1):
        entry = _compare_profile_entry(profile, my_set, index)
        key = entry["friend_key"]
        duplicate_count = seen_keys.get(key, 0)
        seen_keys[key] = duplicate_count + 1
        if duplicate_count:
            entry = {**entry, "friend_key": f"{key}-{duplicate_count + 1}"}
        entries.append(entry)
    return entries


def _profile_records(friend_profiles) -> list[dict]:
    if isinstance(friend_profiles, dict):
        return [dict(friend_profiles)]
    if isinstance(friend_profiles, (list, tuple, set)):
        return [dict(profile) for profile in friend_profiles if isinstance(profile, dict)]
    return []


def _compare_profile_entry(profile: dict, my_set: set[str], index: int) -> dict:
    label = _safe_friend_label(profile, index)
    base = {
        "friend_key": _safe_friend_key(profile, label, index),
        "friend_label": label,
        "friend_id": _safe_profile_text(profile.get("friend_id") or profile.get("steam_id")),
        "friend_vanity": _safe_profile_text(profile.get("friend_vanity") or profile.get("vanity")),
        "advisory_only": True,
        "ranking_impact": "none",
    }
    issue = _profile_issue(profile)
    friend_appids = _profile_appids(profile)
    if issue or not friend_appids:
        return {
            **base,
            "status": "unavailable",
            "issue": issue or "missing_public_wishlist",
            "friend_appids": [],
            "wishlist_count": 0,
            "overlap_appids": [],
            "overlap_count": 0,
        }
    overlap_appids = _sort_appids(set(friend_appids) & my_set)
    entry = {
        **base,
        "status": "ok",
        "friend_appids": friend_appids,
        "wishlist_count": len(friend_appids),
        "overlap_appids": overlap_appids,
        "overlap_count": len(overlap_appids),
    }
    activity = profile.get("friend_activity_games", profile.get("friend_activity"))
    if activity is not None:
        entry["friend_activity_games"] = activity
    return entry


def _profile_issue(profile: dict) -> str:
    if profile.get("private") is True or profile.get("is_public") is False:
        return "private_or_not_public"
    status = str(profile.get("status") or "").strip().lower()
    if status in PROFILE_UNAVAILABLE_STATUSES:
        return status
    if profile.get("error"):
        return _safe_profile_text(profile.get("error"), fallback="profile_error")
    return ""


def _profile_appids(profile: dict) -> list[str]:
    for key in ("friend_appids", "wishlist_appids", "appids", "friend_set", "wishlist"):
        appids = _normalized_appid_list(profile.get(key))
        if appids:
            return appids
    return []


def _normalized_appid_list(values) -> list[str]:
    appids = _normalize_appid_set(values)
    return _sort_appids(appids)


def _sort_appids(appids) -> list[str]:
    return sorted((str(appid) for appid in appids if str(appid).strip()), key=_appid_sort_key)


def _appid_sort_key(appid: str) -> tuple[int, int | str]:
    return (0, int(appid)) if str(appid).isdigit() else (1, str(appid))


def _safe_friend_label(profile: dict, index: int) -> str:
    for key in ("friend_name", "display_name", "name", "friend_vanity", "vanity", "friend_id", "steam_id"):
        label = _safe_profile_text(profile.get(key))
        if label:
            return label
    return f"Friend {index}"


def _safe_friend_key(profile: dict, label: str, index: int) -> str:
    raw = profile.get("friend_id") or profile.get("steam_id") or profile.get("friend_vanity") or label
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(raw or "").strip().lower()).strip("-_")
    return slug[:64] or f"friend-{index}"


def _safe_profile_text(value, *, fallback: str = "", max_length: int = 80) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\x00-\x1f\x7f<>]+", " ", text)
    text = " ".join(text.split())
    return (text[:max_length].strip() or fallback).strip()


def _build_gift_ideas_by_friend(
    profiles: list[dict],
    deals,
    owned,
    *,
    max_reasons: int,
) -> list[dict]:
    groups: list[dict] = []
    for profile in profiles:
        ideas = build_gift_ideas(
            profile.get("friend_appids", []),
            deals,
            owned,
            overlap_appids=profile.get("overlap_appids", []),
            friend_activity_games=profile.get("friend_activity_games"),
            max_reasons=max_reasons,
        )
        items = [_with_friend_gift_metadata(item, profile) for item in ideas]
        if items:
            groups.append(
                {
                    "friend_key": profile["friend_key"],
                    "friend_label": profile["friend_label"],
                    "items": items,
                    "items_count": len(items),
                    "advisory_only": True,
                    "ranking_impact": "none",
                }
            )
    return groups


def _with_friend_gift_metadata(item: dict, profile: dict) -> dict:
    return {
        **dict(item),
        "friend_key": profile["friend_key"],
        "friend_label": profile["friend_label"],
        "advisory_only": True,
        "ranking_impact": "none",
        "advisory_copy": GROUP_GIFT_ADVISORY_COPY,
    }


def _build_shared_gift_ideas(
    profiles: list[dict],
    deals,
    owned,
    *,
    max_reasons: int,
) -> list[dict]:
    deals_by_appid = _records_by_appid(_record_list(deals))
    owned_set = _normalize_appid_set(owned)
    wanted_by = _shared_wishlist_appids(profiles, deals_by_appid, owned_set)
    overlap_appids = {
        appid for profile in profiles for appid in profile.get("overlap_appids", [])
    }
    candidates = [
        (appid, friends)
        for appid, friends in wanted_by.items()
        if len(friends) >= 2 and appid in deals_by_appid
    ]
    non_overlap = [(appid, friends) for appid, friends in candidates if appid not in overlap_appids]
    selected = non_overlap if non_overlap else candidates
    return [
        _shared_gift_item(appid, friends, deals_by_appid[appid], max_reasons=max_reasons)
        for appid, friends in sorted(selected, key=lambda item: _shared_gift_sort_key(deals_by_appid[item[0]]))
    ]


def _shared_wishlist_appids(
    profiles: list[dict],
    deals_by_appid: dict[str, dict],
    owned_set: set[str],
) -> dict[str, list[dict]]:
    wanted_by: dict[str, list[dict]] = {}
    for profile in profiles:
        for appid in profile.get("friend_appids", []):
            if appid in owned_set or appid not in deals_by_appid:
                continue
            wanted_by.setdefault(appid, []).append(profile)
    return wanted_by


def _shared_gift_sort_key(deal: dict) -> tuple[float, float, str]:
    return (
        -_safe_number(deal.get("discount")),
        -_safe_number(deal.get("score")),
        str(deal.get("name") or "").lower(),
    )


def _shared_gift_item(
    appid: str,
    friends: list[dict],
    deal: dict,
    *,
    max_reasons: int,
) -> dict:
    wanted_by = [
        {"friend_key": friend["friend_key"], "friend_label": friend["friend_label"]}
        for friend in friends
    ]
    labels = [friend["friend_label"] for friend in friends]
    reasons, signals = _shared_gift_reasons(deal, labels, max_reasons=max_reasons)
    return {
        **dict(deal),
        "appid": appid,
        "wanted_by": wanted_by,
        "wanted_by_count": len(wanted_by),
        "social_reasons": reasons,
        "social_signals": signals,
        "advisory_only": True,
        "ranking_impact": "none",
        "advisory_copy": GROUP_GIFT_ADVISORY_COPY,
    }


def _shared_gift_reasons(
    deal: dict,
    labels: list[str],
    *,
    max_reasons: int,
) -> tuple[list[str], list[str]]:
    visible_labels = ", ".join(labels[:3])
    extra = len(labels) - 3
    if extra > 0:
        visible_labels = f"{visible_labels} +{extra} más"
    reasons = [f"lo quieren {len(labels)} amigos: {visible_labels}"]
    signals = ["group_wishlist"]
    if _safe_number(deal.get("score")) >= 80:
        reasons.append(f"score alto del reporte: {_safe_number(deal.get('score')):.0f}")
        signals.append("report_score")
    if _safe_number(deal.get("discount")) >= 50:
        reasons.append(f"descuento fuerte: {int(_safe_number(deal.get('discount')))}%")
        signals.append("discount")
    return reasons[:_gift_reason_limit(max_reasons)], signals


def _safe_number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _collection_appid(item: dict) -> str:
    return str(item.get("appid") or item.get("steam_appid") or "").strip()


def _with_collection_review(item: dict, reviews: dict[str, dict] | None) -> dict:
    if not isinstance(reviews, dict):
        return item
    appid = _collection_appid(item)
    external_review = reviews.get(appid)
    if not isinstance(external_review, dict):
        return item
    local_review = item.get("review") if isinstance(item.get("review"), dict) else {}
    return {**item, "review": {**external_review, **local_review}}


def _merge_collection_sources(
    deals: list[dict],
    top_picks: list[dict] | None,
    *,
    reviews: dict[str, dict] | None = None,
) -> list[dict]:
    by_appid: dict[str, dict] = {}
    ordered_appids: list[str] = []
    for deal in deals or []:
        appid = _collection_appid(deal)
        if not appid:
            continue
        by_appid[appid] = _with_collection_review(dict(deal), reviews)
        ordered_appids.append(appid)
    for pick in top_picks or []:
        appid = _collection_appid(pick)
        if not appid:
            continue
        by_appid[appid] = _with_collection_review(
            {**by_appid.get(appid, {}), **dict(pick)},
            reviews,
        )
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


def _review_total(item: dict) -> int:
    review = item.get("review")
    if isinstance(review, dict) and review.get("total") is not None:
        return int(_safe_number(review.get("total")))
    for key in ("review_total", "reviews_total", "total_reviews", "review_count"):
        if item.get(key) is not None:
            return int(_safe_number(item.get(key)))
    return 0


def _format_community_count(count: int) -> str:
    if count >= 1_000_000:
        value = count / 1_000_000
        return f"{value:.1f}M" if count % 1_000_000 else f"{int(value)}M"
    if count >= 1_000:
        return f"{count // 1_000}K"
    return str(count)


def _parse_owners_range(owners: str) -> tuple[int, int]:
    if not isinstance(owners, str) or ".." not in owners:
        return (0, 0)
    low_raw, high_raw = owners.split("..", 1)
    try:
        return (
            int(low_raw.strip().replace(",", "")),
            int(high_raw.strip().replace(",", "")),
        )
    except ValueError:
        return (0, 0)


def _community_players(item: dict, tags_data: dict[str, dict] | None) -> dict:
    appid = _collection_appid(item)
    tag_entry = tags_data.get(appid, {}) if isinstance(tags_data, dict) else {}
    players: dict = {}
    if isinstance(tag_entry, dict):
        if isinstance(tag_entry.get("players"), dict):
            players.update(tag_entry["players"])
        players.update(
            {
                key: tag_entry[key]
                for key in ("owners", "ccu", "players_2weeks")
                if key in tag_entry
            }
        )
    if isinstance(item.get("players"), dict):
        players.update(item["players"])
    return players


def _community_popularity_signal(
    item: dict,
    tags_data: dict[str, dict] | None,
) -> tuple[float, str] | None:
    players = _community_players(item, tags_data)
    _owners_low, owners_high = _parse_owners_range(str(players.get("owners", "")))
    ccu = int(_safe_number(players.get("ccu")))
    recent_players = int(_safe_number(players.get("players_2weeks")))
    review_total = _review_total(item)
    candidates: list[tuple[float, str]] = []
    if review_total >= COMMUNITY_MIN_REVIEW_COUNT:
        candidates.append(
            (
                review_total / COMMUNITY_MIN_REVIEW_COUNT,
                f"{_format_community_count(review_total)} reviews",
            )
        )
    if owners_high >= COMMUNITY_MIN_OWNERS_HIGH:
        candidates.append(
            (
                owners_high / COMMUNITY_MIN_OWNERS_HIGH,
                f"{_format_community_count(owners_high)} owners estimados",
            )
        )
    if ccu >= COMMUNITY_MIN_CCU:
        candidates.append((ccu / COMMUNITY_MIN_CCU, f"{_format_community_count(ccu)} CCU"))
    if recent_players >= COMMUNITY_MIN_RECENT_PLAYERS:
        candidates.append(
            (
                recent_players / COMMUNITY_MIN_RECENT_PLAYERS,
                f"{_format_community_count(recent_players)} jugadores recientes",
            )
        )
    if not candidates:
        return None
    return sorted(candidates, key=lambda signal: (-signal[0], signal[1]))[0]


def _community_quality_signal(item: dict) -> tuple[float, str] | None:
    review_pct = _review_pct(item)
    score = _safe_number(item.get("score")) if item.get("score") is not None else None
    metacritic = (
        _safe_number(item.get("metacritic_score"))
        if item.get("metacritic_score") is not None
        else None
    )
    candidates: list[tuple[float, str]] = []
    if review_pct is not None and review_pct >= COMMUNITY_MIN_REVIEW_PCT:
        candidates.append((review_pct, f"{review_pct}% positivas"))
    if score is not None and score >= COMMUNITY_MIN_SCORE:
        candidates.append((score, f"score {score:g}"))
    if metacritic is not None and metacritic >= COMMUNITY_MIN_METACRITIC:
        candidates.append((metacritic, f"Metacritic {int(metacritic)}"))
    if not candidates:
        return None
    return sorted(candidates, key=lambda signal: (-signal[0], signal[1]))[0]


def _community_favorites_candidates(
    sources: list[dict],
    tags_data: dict[str, dict] | None,
) -> list[dict]:
    ranked: list[tuple[float, float, dict]] = []
    for item in sources:
        popularity = _community_popularity_signal(item, tags_data)
        quality = _community_quality_signal(item)
        if not popularity or not quality:
            continue
        popularity_rank, popularity_reason = popularity
        quality_rank, quality_reason = quality
        ranked.append(
            (
                popularity_rank,
                quality_rank,
                _collection_item(item, f"{popularity_reason} + {quality_reason}"),
            )
        )
    return [
        payload
        for _popularity_rank, _quality_rank, payload in sorted(
            ranked,
            key=lambda value: (
                -value[0],
                -value[1],
                str(value[2].get("name") or ""),
                str(value[2].get("appid") or ""),
            ),
        )
    ]


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
    return normalize_steam_tag_terms(term for term in terms if term)


def _style_term_key(term: str) -> str:
    return canonical_steam_tag_key(term)


def _canonical_style_term_key(term: str) -> str:
    return _style_term_key(term).replace(" ", "")


def _has_story_rich_signal(item: dict) -> bool:
    return "story rich" in {_style_term_key(term) for term in _style_terms(item)}


def _is_singleplayer_term(value) -> bool:
    return _canonical_style_term_key(str(value or "")) == "singleplayer"


def _has_singleplayer_category_signal(value) -> bool:
    if isinstance(value, dict):
        category_id = value.get("id") or value.get("category_id") or value.get("categoryid")
        label = value.get("description") or value.get("name") or value.get("label")
        return str(category_id).strip() == "2" or _is_singleplayer_term(label)
    return str(value).strip() == "2" or _is_singleplayer_term(value)


def _has_singleplayer_signal(item: dict) -> bool:
    categories = item.get("categories") or item.get("steam_categories") or []
    if isinstance(categories, dict):
        category_values = [*categories.keys(), *categories.values()]
    elif isinstance(categories, list):
        category_values = categories
    else:
        category_values = [categories]
    return any(_has_singleplayer_category_signal(value) for value in category_values) or any(
        _is_singleplayer_term(term) for term in _style_terms(item)
    )


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


def _select_diverse_collection_items(
    items: list[dict],
    limit: int,
    used_appids: set[str],
) -> tuple[list[dict], set[str]]:
    candidates = _dedupe_collection_items(items, len(items))
    preferred = [item for item in candidates if item.get("appid") not in used_appids]
    selected = preferred[:limit]
    if len(selected) < min(limit, len(candidates)):
        selected_appids = {str(item.get("appid")) for item in selected}
        fallback = [item for item in candidates if item.get("appid") not in selected_appids]
        selected = [*selected, *fallback[: limit - len(selected)]]
    next_used = {str(item.get("appid")) for item in selected if item.get("appid")}
    return selected, used_appids | next_used


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
            key = _canonical_style_term_key(term)
            count, label = counts.get(key, (0, term))
            counts[key] = (count + 1, label)
    if not counts:
        return ""
    return sorted(counts.values(), key=lambda value: (-value[0], value[1].lower()))[0][1]


def build_recommended_collections(
    deals: list[dict],
    top_picks: list[dict] | None = None,
    *,
    reviews: dict[str, dict] | None = None,
    tags_data: dict[str, dict] | None = None,
    max_items_per_collection: int = 4,
) -> list[dict]:
    """Build deterministic recommendation collections from already available report data."""
    if max_items_per_collection <= 0:
        return []
    sources = _merge_collection_sources(deals, top_picks, reviews=reviews)
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
            [
                item for item in sources
                if style_term
                and _canonical_style_term_key(style_term)
                in {_canonical_style_term_key(term) for term in _style_terms(item)}
            ]
        )
    ]
    story_rich = [] if _style_term_key(style_term) == "story rich" else [
        _collection_item(item, "Señal explícita Story Rich en tags/géneros")
        for item in _sort_by_score_discount_name([item for item in sources if _has_story_rich_signal(item)])
    ]
    singleplayer = [] if (
        _is_singleplayer_term(style_term)
        or all(_has_singleplayer_signal(item) for item in sources)
    ) else [
        _collection_item(item, "Señal explícita Singleplayer en categorías/tags")
        for item in _sort_by_score_discount_name([item for item in sources if _has_singleplayer_signal(item)])
    ]
    community_favorites = _community_favorites_candidates(sources, tags_data)

    collection_candidates = [
        ("recommended_for_you", recommended),
        ("best_savings", best_savings),
        ("steam_deck", deck_ready),
        ("acclaimed", acclaimed),
        ("community_favorites", community_favorites),
        ("genre_style", genre_style),
        ("story_rich", story_rich),
        ("singleplayer", singleplayer),
    ]
    collections: list[dict] = []
    used_appids: set[str] = set()
    for collection_id, candidates in collection_candidates:
        items, used_appids = _select_diverse_collection_items(
            candidates,
            max_items_per_collection,
            used_appids,
        )
        if collection := _collection_payload(collection_id, items):
            collections.append(collection)
    return collections


def _normalize_appid_set(values) -> set[str]:
    if not values:
        return set()
    if isinstance(values, dict):
        return {str(appid) for appid in values if str(appid).strip()}
    appids: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            appid = _collection_appid(value)
        else:
            appid = str(value).strip()
        if appid:
            appids.add(appid)
    return appids


def _record_list(records) -> list[dict]:
    if not records:
        return []
    if isinstance(records, dict):
        return [
            {"appid": str(appid), **(value if isinstance(value, dict) else {"name": value})}
            for appid, value in records.items()
        ]
    return [dict(record) for record in records if isinstance(record, dict)]


def _records_by_appid(records: list[dict]) -> dict[str, dict]:
    return {
        _collection_appid(record): dict(record)
        for record in records
        if _collection_appid(record)
    }


ACTIVITY_PLAYTIME_KEYS = ("hours", "hours_played", "playtime_2weeks", "playtime_forever")


def _without_playtime_fields(record: dict) -> dict:
    return {
        key: value
        for key, value in record.items()
        if key not in ACTIVITY_PLAYTIME_KEYS
    }


def _activity_records_with_library_context(activity_records: list[dict], library_records: list[dict]) -> list[dict]:
    library_by_appid = _records_by_appid(library_records)
    return [
        {**_without_playtime_fields(library_by_appid.get(_collection_appid(record), {})), **record}
        for record in activity_records
    ]


def _game_activity_weight(game: dict) -> float:
    playtime = _activity_playtime_hours(game)
    return max(
        1.0,
        playtime["recent_hours"]
        + (playtime["forever_hours"] / 10)
        + playtime["explicit_hours"],
    )


def _positive_hours(value) -> float:
    return max(0.0, _safe_number(value))


def _playtime_minutes_to_hours(value) -> float:
    return _positive_hours(value) / 60


def _activity_playtime_hours(source: dict) -> dict[str, float]:
    source = source or {}
    recent_hours = _playtime_minutes_to_hours(source.get("playtime_2weeks"))
    forever_hours = _playtime_minutes_to_hours(source.get("playtime_forever"))
    explicit_hours = max(
        _positive_hours(source.get("hours_played")),
        _positive_hours(source.get("hours")),
    )
    return {
        "recent_hours": recent_hours,
        "forever_hours": forever_hours,
        "explicit_hours": explicit_hours,
        "total_hours": max(forever_hours, explicit_hours, recent_hours),
    }


def _has_local_activity_playtime(record: dict) -> bool:
    return _activity_playtime_hours(record)["total_hours"] > 0


def _activity_playtime_item(record: dict, activity_record: dict | None = None) -> dict:
    source = activity_record or record
    playtime = _activity_playtime_hours(source)
    return {
        "appid": _collection_appid(record),
        "name": str(record.get("name") or record.get("steam_name") or "Juego desconocido"),
        "recent_hours": round(playtime["recent_hours"], 1),
        "total_hours": round(playtime["total_hours"], 1),
    }


def _activity_top_items(items: list[dict], score_key: str, *, limit: int = 3) -> list[dict]:
    ranked = sorted(
        items,
        key=lambda item: (-item.get(score_key, 0), item.get("name", "").lower(), item.get("appid", "")),
    )
    return [dict(item) for item in ranked[:limit]]


def _activity_profile_summary(activity_games: list[dict], library_games: list[dict] | None = None) -> dict:
    library_by_appid = _records_by_appid(library_games or [])
    items = [
        _activity_playtime_item(
            {**library_by_appid.get(_collection_appid(record), {}), **record},
            activity_record=record,
        )
        for record in activity_games
    ]
    played_items = [item for item in items if item["recent_hours"] > 0 or item["total_hours"] > 0]
    recent_items = [item for item in played_items if item["recent_hours"] > 0]
    return {
        "records_count": len(activity_games),
        "tracked_count": len(played_items),
        "recent_count": len(recent_items),
        "recent_hours": round(sum(item["recent_hours"] for item in recent_items), 1),
        "total_hours": round(sum(item["total_hours"] for item in played_items), 1),
        "top_recent": _activity_top_items(recent_items, "recent_hours"),
        "top_played": _activity_top_items(played_items, "total_hours"),
    }


def _weighted_style_terms(records: list[dict], *, activity_weighted: bool = False) -> list[dict]:
    weights: dict[str, tuple[float, str]] = {}
    for record in records:
        weight = _game_activity_weight(record) if activity_weighted else 1.0
        for term in _style_terms(record):
            key = _canonical_style_term_key(term)
            current, label = weights.get(key, (0.0, term))
            weights[key] = (current + weight, label)
    return [
        {"term": label, "weight": round(weight, 2)}
        for weight, label in sorted(weights.values(), key=lambda value: (-value[0], value[1].lower()))
    ]


def _style_terms_by_canonical_key(record: dict) -> dict[str, str]:
    terms_by_key: dict[str, str] = {}
    for term in _style_terms(record):
        key = _canonical_style_term_key(term)
        if key and key not in terms_by_key:
            terms_by_key[key] = term
    return terms_by_key


def _library_genre_distribution(library_games: list[dict], *, limit: int = 5) -> tuple[list[dict], int]:
    counts: dict[str, tuple[int, str]] = {}
    games_with_terms = 0
    for game in library_games:
        terms_by_key = _style_terms_by_canonical_key(game)
        if not terms_by_key:
            continue
        games_with_terms += 1
        for key, label in terms_by_key.items():
            current_count, current_label = counts.get(key, (0, label))
            counts[key] = (current_count + 1, current_label)
    if not games_with_terms:
        return [], 0
    distribution = [
        {
            "term": label,
            "games_count": count,
            "share": round(count / games_with_terms, 3),
        }
        for count, label in sorted(
            counts.values(),
            key=lambda value: (-value[0], value[1].lower()),
        )
    ]
    return distribution[:limit], games_with_terms


def _matched_terms(candidate: dict, weighted_terms: list[dict], *, limit: int = 2) -> list[str]:
    candidate_terms = {_canonical_style_term_key(term) for term in _style_terms(candidate)}
    matches = [
        str(term["term"])
        for term in weighted_terms
        if _canonical_style_term_key(str(term.get("term", ""))) in candidate_terms
    ]
    return matches[:limit]


def _preference_reasons(appid: str, preference_relations) -> list[str]:
    if not isinstance(preference_relations, dict):
        return []
    raw = preference_relations.get(appid) or preference_relations.get(str(appid))
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(reason) for reason in raw if str(reason).strip()]
    return []


def _candidate_base_score(candidate: dict) -> float:
    if candidate.get("score") is not None:
        return _safe_number(candidate.get("score"), 50.0)
    return 50.0


def _library_profile_summary(library_games: list[dict], owned_appids: set[str], hltb_hours) -> dict:
    hltb_hours = hltb_hours or {}
    appids = {_collection_appid(game) for game in library_games if _collection_appid(game)}
    prices = [_safe_number(game.get("price_raw")) / 100 for game in library_games if game.get("price_raw") is not None]
    genre_distribution, genre_coverage_count = _library_genre_distribution(library_games)
    total_hours = sum(
        _safe_number(game.get("hltb_hours") or game.get("hours") or hltb_hours.get(_collection_appid(game)))
        for game in library_games
    )
    return {
        "owned_count": len(owned_appids | appids),
        "total_hltb_hours": round(total_hours, 1),
        "top_terms": _weighted_style_terms(library_games)[:5],
        "genre_distribution": genre_distribution,
        "genre_coverage_count": genre_coverage_count,
        "average_price": round(sum(prices) / len(prices), 2) if prices else None,
    }


def _personalized_candidate(candidate: dict, *, activity_terms, library_terms, liked_appids, preference_relations) -> dict:
    appid = _collection_appid(candidate)
    base_score = _candidate_base_score(candidate)
    affinity = 0.0
    reasons: list[str] = []
    if matches := _matched_terms(candidate, activity_terms):
        affinity += 16
        reasons.append(f"encaja con tu actividad reciente: {', '.join(matches)}")
    if matches := _matched_terms(candidate, library_terms):
        affinity += 12
        reasons.append(f"coincide con tu biblioteca: {', '.join(matches)}")
    if appid in liked_appids:
        affinity += 14
        reasons.append("marcado como me gusta")
    relation_reasons = _preference_reasons(appid, preference_relations)
    if relation_reasons:
        affinity += 20
        reasons.extend(relation_reasons[:2])
    if not reasons:
        reasons.append("score base del reporte")
    return {
        "appid": appid,
        "name": candidate.get("name") or candidate.get("steam_name") or "Juego desconocido",
        "base_score": round(base_score, 1),
        "affinity_score": round(affinity, 1),
        "personalized_score": round(min(100.0, base_score + affinity), 1),
        "reasons": reasons[:4],
        "discount": int(_safe_number(candidate.get("discount"))),
        "price_final": candidate.get("price_final") or candidate.get("price") or "",
    }


def build_personalized_recommendations(
    deals: list[dict],
    top_picks: list[dict] | None = None,
    *,
    activity_games=None,
    library_games=None,
    owned=None,
    family_appids=None,
    liked_appids=None,
    preference_relations=None,
    hltb_hours=None,
    max_items: int = 10,
) -> dict:
    """Build a deterministic personalized ranking from existing report data."""
    library_records = _record_list(library_games)
    raw_activity_records = _record_list(activity_games)
    activity_records = _activity_records_with_library_context(
        raw_activity_records,
        library_records,
    )
    owned_set = _normalize_appid_set(owned)
    excluded_appids = owned_set | _normalize_appid_set(family_appids)
    activity_terms = _weighted_style_terms(
        [record for record in activity_records if _has_local_activity_playtime(record)],
        activity_weighted=True,
    )
    library_terms = _weighted_style_terms(library_records)
    candidates = [
        candidate for candidate in _merge_collection_sources(deals, top_picks)
        if _collection_appid(candidate) and _collection_appid(candidate) not in excluded_appids
    ]
    items = [
        _personalized_candidate(
            candidate,
            activity_terms=activity_terms,
            library_terms=library_terms,
            liked_appids=_normalize_appid_set(liked_appids),
            preference_relations=preference_relations,
        )
        for candidate in candidates
    ]
    items.sort(key=lambda item: (-item["personalized_score"], -item["affinity_score"], -item["base_score"], item["name"], item["appid"]))
    return {
        "source_signals": ["top_picks", "score", "activity", "library", "preferences"],
        "items": items[:max(0, max_items)],
        "profile": {
            "activity_terms": activity_terms[:5],
            "activity_summary": _activity_profile_summary(raw_activity_records, library_records),
            "library_summary": _library_profile_summary(library_records, owned_set, hltb_hours),
            "excluded_appids_count": len(excluded_appids),
        },
    }


def _diagnostic_int(value, fallback: int = 0) -> int:
    return int(_safe_number(value, fallback))


def _diagnostic_recommendation_items(personalized_recommendations) -> list[dict]:
    if isinstance(personalized_recommendations, dict):
        return _record_list(personalized_recommendations.get("items"))
    return _record_list(personalized_recommendations)


def _diagnostic_profile_depth(
    personalized_recommendations,
    *,
    activity_games,
    library_games,
    owned,
    liked_appids,
    preference_relations,
) -> dict:
    profile = (
        personalized_recommendations.get("profile")
        if isinstance(personalized_recommendations, dict)
        else {}
    )
    activity_summary = profile.get("activity_summary") if isinstance(profile, dict) else {}
    library_summary = profile.get("library_summary") if isinstance(profile, dict) else {}
    activity_terms = profile.get("activity_terms") if isinstance(profile, dict) else []
    activity_records_count = len(_record_list(activity_games))
    library_records_count = len(_record_list(library_games))
    owned_count = len(_normalize_appid_set(owned))
    return {
        "activity_records": _diagnostic_int(
            activity_summary.get("records_count"),
            activity_records_count,
        ) if isinstance(activity_summary, dict) else activity_records_count,
        "activity_tracked_count": _diagnostic_int(
            activity_summary.get("tracked_count"),
        ) if isinstance(activity_summary, dict) else 0,
        "activity_recent_count": _diagnostic_int(
            activity_summary.get("recent_count"),
        ) if isinstance(activity_summary, dict) else 0,
        "activity_terms_count": len(activity_terms) if isinstance(activity_terms, list) else 0,
        "library_records_count": library_records_count,
        "library_owned_count": _diagnostic_int(
            library_summary.get("owned_count"),
            owned_count,
        ) if isinstance(library_summary, dict) else library_records_count,
        "library_genre_coverage_count": _diagnostic_int(
            library_summary.get("genre_coverage_count"),
        ) if isinstance(library_summary, dict) else 0,
        "liked_appids_count": len(_normalize_appid_set(liked_appids)),
        "preference_relations_count": _preference_relations_count(preference_relations),
    }


def _preference_relations_count(preference_relations) -> int:
    if isinstance(preference_relations, dict):
        return sum(
            1
            for appid, reasons in preference_relations.items()
            if str(appid).strip() and reasons
        )
    return len(_record_list(preference_relations))


def _diagnostic_signal_sources(depth: dict) -> list[str]:
    sources: list[str] = []
    if depth["activity_tracked_count"] > 0 or depth["activity_terms_count"] > 0:
        sources.append("activity")
    if depth["library_records_count"] > 0 or depth["library_genre_coverage_count"] > 0:
        sources.append("library")
    if depth["liked_appids_count"] > 0:
        sources.append("liked_appids")
    if depth["preference_relations_count"] > 0:
        sources.append("preferences")
    return [*sources, "score"]


def _diagnostic_mode(
    items: list[dict],
    behavioral_signal_strength: float,
    fallback_dependence: float,
    signal_sources: list[str],
) -> str:
    non_score_sources = [source for source in signal_sources if source != "score"]
    if not items or all(_safe_number(item.get("affinity_score")) <= 0 for item in items):
        return "score_fallback"
    if (
        fallback_dependence <= 0.2
        and behavioral_signal_strength >= 0.5
        and len(non_score_sources) >= 2
    ):
        return "behavioral"
    return "mixed"


def _diagnostic_confidence(
    mode: str,
    behavioral_signal_strength: float,
    fallback_dependence: float,
    signal_sources: list[str],
) -> dict:
    non_score_sources = [source for source in signal_sources if source != "score"]
    source_bonus = min(0.18, len(non_score_sources) * 0.045)
    if mode == "behavioral":
        score = min(1.0, 0.62 + behavioral_signal_strength * 0.25 + source_bonus)
    elif mode == "mixed":
        score = min(
            0.74,
            0.42 + behavioral_signal_strength * 0.35 + source_bonus - fallback_dependence * 0.10,
        )
    else:
        score = max(0.1, 0.34 - fallback_dependence * 0.16 + source_bonus)
    score = round(_clamp_score(score, high=1.0), 3)
    level = "high" if score >= 0.67 else "medium" if score >= 0.4 else "low"
    return {"level": level, "score": score}


def _diagnostic_improvement_hints(mode: str, depth: dict, fallback_dependence: float) -> list[str]:
    hints: list[str] = []
    if depth["activity_tracked_count"] <= 0:
        hints.append("agrega actividad local reciente para distinguir gustos reales de score base")
    if depth["library_genre_coverage_count"] <= 0:
        hints.append("enriquece biblioteca con géneros/tags para medir afinidad y redundancia")
    if depth["liked_appids_count"] <= 0 and depth["preference_relations_count"] <= 0:
        hints.append("marca juegos como me gusta o agrega relaciones 'similar a' para subir confianza")
    if mode == "score_fallback" or fallback_dependence >= 0.5:
        hints.append("revisa candidatos con affinity_score=0 antes de asumir personalización fuerte")
    return _dedupe_texts(hints)[:4]


def build_recommendation_diagnostics(
    personalized_recommendations,
    *,
    activity_games=None,
    library_games=None,
    owned=None,
    liked_appids=None,
    preference_relations=None,
) -> dict:
    """Explain how much personalized recommendations depend on local behavioral signals."""
    items = _diagnostic_recommendation_items(personalized_recommendations)
    if not items:
        return {}
    affinities = [_safe_number(item.get("affinity_score")) for item in items]
    positive_count = sum(1 for affinity in affinities if affinity > 0)
    affinity_zero_rate = round((len(items) - positive_count) / len(items), 3)
    average_affinity = sum(affinities) / len(affinities)
    positive_affinity_rate = positive_count / len(items)
    behavioral_signal_strength = round(
        _clamp_score(
            (average_affinity / 60.0) * 0.7 + positive_affinity_rate * 0.3,
            high=1.0,
        ),
        3,
    )
    depth = _diagnostic_profile_depth(
        personalized_recommendations,
        activity_games=activity_games,
        library_games=library_games,
        owned=owned,
        liked_appids=liked_appids,
        preference_relations=preference_relations,
    )
    depth["recommendations_count"] = len(items)
    signal_sources = _diagnostic_signal_sources(depth)
    mode = _diagnostic_mode(items, behavioral_signal_strength, affinity_zero_rate, signal_sources)
    return {
        "schema": "recommendation_diagnostics_v1",
        "recommendation_mode": mode,
        "recommendation_confidence": _diagnostic_confidence(
            mode,
            behavioral_signal_strength,
            affinity_zero_rate,
            signal_sources,
        ),
        "behavioral_signal_strength": behavioral_signal_strength,
        "fallback_dependence": affinity_zero_rate,
        "affinity_zero_rate": affinity_zero_rate,
        "profile_depth": depth,
        "signal_sources": signal_sources,
        "improve_recommendations": _diagnostic_improvement_hints(mode, depth, affinity_zero_rate),
        "advisory_only": True,
        "ranking_impact": "none",
    }


TASTE_PRIORITY_CATEGORIES = (
    "compra_inmediata",
    "espera_oferta",
    "riesgo_abandono",
    "reemplaza_varios",
    "no_comprar_aun",
)

TASTE_CORE_LOOP_CLUSTERS = (
    {
        "id": "survival_crafting",
        "label": "Survival/crafting",
        "terms": ("Survival Crafting", "Open World Survival Craft", "Base Building", "Crafting", "Survival"),
    },
    {
        "id": "roguelite_action",
        "label": "Roguelite/action",
        "terms": ("Action Roguelike", "Roguelike", "Rogue-lite", "Bullet Hell", "Hack and Slash"),
    },
    {
        "id": "strategy_management",
        "label": "Strategy/management",
        "terms": ("Strategy", "Management", "City Builder", "Colony Sim", "Automation"),
    },
)


def _clamp_score(value: float, *, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _taste_profile(personalized_recommendations) -> dict:
    if isinstance(personalized_recommendations, dict) and isinstance(personalized_recommendations.get("profile"), dict):
        return personalized_recommendations["profile"]
    return {}


def _taste_library_distribution(profile: dict) -> list[dict]:
    library_summary = profile.get("library_summary") if isinstance(profile, dict) else {}
    distribution = library_summary.get("genre_distribution") if isinstance(library_summary, dict) else []
    if not isinstance(distribution, list):
        return []
    return [item for item in distribution if isinstance(item, dict)]


def _taste_cluster_keys(cluster: dict) -> set[str]:
    return {_canonical_style_term_key(term) for term in cluster.get("terms", ()) if term}


def _taste_clusters_for_terms(terms: list[str]) -> list[dict]:
    term_keys = {_canonical_style_term_key(term) for term in terms if term}
    matches = [
        {"id": str(cluster["id"]), "label": str(cluster["label"])}
        for cluster in TASTE_CORE_LOOP_CLUSTERS
        if term_keys & _taste_cluster_keys(cluster)
    ]
    return sorted(matches, key=lambda item: item["id"])


def _taste_candidate_clusters(candidate: dict) -> list[dict]:
    return _taste_clusters_for_terms(_style_terms(candidate))


def _taste_library_cluster_distribution(profile: dict) -> list[dict]:
    clusters: dict[str, dict] = {}
    for item in _taste_library_distribution(profile):
        share = _safe_number(item.get("share"))
        for cluster in _taste_clusters_for_terms([str(item.get("term") or "")]):
            current = clusters.get(cluster["id"], {**cluster, "share": 0.0})
            clusters[cluster["id"]] = {**current, "share": max(current["share"], share)}
    return sorted(clusters.values(), key=lambda item: (-item["share"], item["label"].lower()))


def _taste_personal_affinity(candidate: dict) -> float:
    affinity = _safe_number(candidate.get("affinity_score"))
    personalized = candidate.get("personalized_score")
    base = _selection_base_score(candidate)
    personalized_lift = max(0.0, _safe_number(personalized) - base) if personalized is not None else 0.0
    return round(_clamp_score(max(affinity * 1.5, personalized_lift * 1.5)), 1)


def _taste_value(candidate: dict) -> float:
    discount = _safe_number(candidate.get("discount"))
    base_score = _selection_base_score(candidate)
    return round(_clamp_score(discount + max(0.0, base_score - 70.0) * 0.5), 1)


def _taste_term_redundancy(candidate: dict, profile: dict) -> float:
    candidate_terms = {_canonical_style_term_key(term) for term in _style_terms(candidate)}
    if not candidate_terms:
        return 0.0
    scores = []
    for item in _taste_library_distribution(profile):
        term = str(item.get("term") or "")
        if _canonical_style_term_key(term) in candidate_terms:
            scores.append(_safe_number(item.get("share")) * 100)
    return round(_clamp_score(max(scores) if scores else 0.0), 1)


def _taste_cluster_redundancy(candidate: dict, profile: dict) -> float:
    candidate_cluster_ids = {cluster["id"] for cluster in _taste_candidate_clusters(candidate)}
    if not candidate_cluster_ids:
        return 0.0
    scores = [
        _safe_number(cluster.get("share")) * 100
        for cluster in _taste_library_cluster_distribution(profile)
        if cluster.get("id") in candidate_cluster_ids
    ]
    return round(_clamp_score(max(scores) if scores else 0.0), 1)


def _taste_redundancy(candidate: dict, profile: dict) -> float:
    return max(_taste_term_redundancy(candidate, profile), _taste_cluster_redundancy(candidate, profile))


def _taste_waiting_penalty(candidate: dict) -> float:
    discount = _safe_number(candidate.get("discount"))
    reasons = " · ".join(str(reason) for reason in candidate.get("reasons") or []).lower()
    if "mínimo" in reasons or "minimo" in reasons or "nunca baja" in reasons:
        return 0.0
    if discount < 20:
        return 70.0
    if discount < 50:
        return 45.0
    if discount < 70:
        return 15.0
    return 0.0


def _taste_abandon_risk(candidate: dict, personal_affinity: float, redundancy: float) -> float:
    risk = 0.0
    if personal_affinity < 20:
        risk += 30
    if _selection_base_score(candidate) < 55:
        risk += 25
    if redundancy >= 70 and personal_affinity < 55:
        risk += 20
    hltb_hours = max(_safe_number(candidate.get("hltb_hours")), _safe_number(candidate.get("hours")))
    if hltb_hours >= 80 and personal_affinity < 45:
        risk += 20
    return round(_clamp_score(risk), 1)


def _taste_factors(candidate: dict, profile: dict) -> dict[str, float]:
    personal_affinity = _taste_personal_affinity(candidate)
    value = _taste_value(candidate)
    redundancy = _taste_redundancy(candidate, profile)
    return {
        "personal_affinity": personal_affinity,
        "value": value,
        "redundancy": redundancy,
        "cluster_redundancy": _taste_cluster_redundancy(candidate, profile),
        "abandon_risk": _taste_abandon_risk(candidate, personal_affinity, redundancy),
        "waiting_penalty": _taste_waiting_penalty(candidate),
    }


def _taste_priority_score(candidate: dict, factors: dict[str, float]) -> float:
    base = _selection_base_score(candidate)
    score = (
        base * 0.45
        + factors["personal_affinity"] * 0.35
        + factors["value"] * 0.20
        - factors["redundancy"] * 0.20
        - factors["abandon_risk"] * 0.20
        - factors["waiting_penalty"] * 0.15
    )
    return round(_clamp_score(score), 1)


def _taste_category(score: float, factors: dict[str, float]) -> str:
    if score < 35:
        return "no_comprar_aun"
    if factors["abandon_risk"] >= 55 and score < 65:
        return "riesgo_abandono"
    if factors["redundancy"] >= 65 and score >= 45:
        return "reemplaza_varios"
    if factors["waiting_penalty"] >= 45 or factors["value"] < 40:
        return "espera_oferta"
    if score >= 70 and factors["personal_affinity"] >= 35:
        return "compra_inmediata"
    return "espera_oferta"


def _taste_reasons(candidate: dict, category: str, factors: dict[str, float]) -> list[str]:
    reasons: list[str] = []
    reasons.extend(str(reason) for reason in candidate.get("reasons") or [] if reason != "score base del reporte")
    if category == "compra_inmediata":
        if factors["personal_affinity"] >= 35:
            reasons.append("alta afinidad con tus gustos locales")
        if factors["value"] >= 60:
            reasons.append("valor/descuento sólido para revisar hoy")
    elif category == "espera_oferta":
        reasons.append(
            "no destaca lo suficiente frente a tus gustos locales para priorizarlo ahora"
        )
    elif category == "riesgo_abandono":
        reasons.append("pocas señales de afinidad local para sostenerlo")
    elif category == "reemplaza_varios":
        reasons.append("se solapa con géneros ya fuertes en tu biblioteca")
    else:
        reasons.append("score/afinidad bajos frente a otras opciones")
    return _dedupe_texts(reasons)[:4]


def _taste_priority_item(appid: str, candidate: dict, profile: dict) -> dict:
    factors = _taste_factors(candidate, profile)
    score = _taste_priority_score(candidate, factors)
    category = _taste_category(score, factors)
    return {
        "appid": appid,
        "name": candidate.get("name") or candidate.get("steam_name") or f"App {appid}",
        "taste_priority": score,
        "category": category,
        "factors": factors,
        "clusters": _taste_candidate_clusters(candidate),
        "reasons": _taste_reasons(candidate, category, factors),
    }


def build_taste_priority_contract(
    deals: list[dict] | None,
    top_picks: list[dict] | None = None,
    *,
    personalized_recommendations=None,
    activity_games=None,
    library_games=None,
    owned=None,
    family_appids=None,
    liked_appids=None,
    preference_relations=None,
    recommended_collections=None,
    hltb_hours=None,
    max_items: int = 10,
) -> dict:
    """Build a local fixture-only taste-priority contract without changing report scoring."""
    if personalized_recommendations is None:
        personalized_recommendations = build_personalized_recommendations(
            deals or [],
            top_picks=top_picks,
            activity_games=activity_games,
            library_games=library_games,
            owned=owned,
            family_appids=family_appids,
            liked_appids=liked_appids,
            preference_relations=preference_relations,
            hltb_hours=hltb_hours,
            max_items=max(0, int(_safe_number(max_items, 10))) or 10,
        )
    profile = _taste_profile(personalized_recommendations)
    context_by_appid = _selection_context_by_appid(
        deals or [],
        top_picks,
        personalized_recommendations,
        recommended_collections,
    )
    items = [
        _taste_priority_item(appid, candidate, profile)
        for appid, candidate in context_by_appid.items()
        if appid
    ]
    items.sort(key=lambda item: (-item["taste_priority"], item["category"], item["name"], item["appid"]))
    return {
        "source_signals": [
            "personalized_recommendations",
            "activity",
            "library",
            "preferences",
            "value",
            "redundancy_stub",
            "core_loop_clusters_stub",
        ],
        "categories": list(TASTE_PRIORITY_CATEGORIES),
        "cluster_distribution": _taste_library_cluster_distribution(profile),
        "items": items[:max(0, int(_safe_number(max_items, 10)))],
        "profile": profile,
    }


def _selection_records(selection) -> list[dict]:
    if not selection:
        return []
    if isinstance(selection, dict):
        raw_records = selection.get("items") if isinstance(selection.get("items"), list) else [selection]
    elif isinstance(selection, (str, int)):
        raw_records = [selection]
    else:
        raw_records = selection
    records: list[dict] = []
    for record in raw_records:
        if isinstance(record, dict):
            records.append(dict(record))
        elif record is not None and str(record).strip():
            records.append({"appid": str(record).strip()})
        else:
            records.append({})
    return records


def _personalized_items(personalized_recommendations) -> list[dict]:
    if isinstance(personalized_recommendations, dict):
        return _record_list(personalized_recommendations.get("items"))
    return _record_list(personalized_recommendations)


def _collection_signal_reason(collection: dict, item: dict) -> str:
    label = str(collection.get("label") or collection.get("title") or collection.get("id") or "").strip()
    reason = str(item.get("reason") or "").strip()
    if label and reason:
        return f"{label}: {reason}"
    if label:
        return f"aparece en {label}"
    return reason


def _recommended_collection_contexts(recommended_collections) -> list[dict]:
    contexts: dict[str, dict] = {}
    for collection in _record_list(recommended_collections):
        items = collection.get("items") if isinstance(collection.get("items"), list) else []
        label = str(collection.get("label") or collection.get("title") or collection.get("id") or "").strip()
        for item in (item for item in items if isinstance(item, dict)):
            appid = _collection_appid(item)
            if not appid:
                continue
            current = contexts.get(appid, {})
            reason = _collection_signal_reason(collection, item)
            contexts[appid] = {
                **current,
                **{key: item[key] for key in ("name", "steam_name", "score", "discount", "price_final", "price") if key in item},
                "appid": appid,
                "collection_labels": _dedupe_texts([*(current.get("collection_labels") or []), label]),
                "collection_reasons": _dedupe_texts([*(current.get("collection_reasons") or []), reason]),
            }
    return list(contexts.values())


def _selection_context_by_appid(deals, top_picks, personalized_recommendations, recommended_collections=None) -> dict[str, dict]:
    by_appid = {
        _collection_appid(candidate): dict(candidate)
        for candidate in _merge_collection_sources(deals or [], top_picks)
        if _collection_appid(candidate)
    }
    for item in _recommended_collection_contexts(recommended_collections):
        appid = _collection_appid(item)
        if appid:
            by_appid[appid] = {**item, **by_appid.get(appid, {})}
    for item in _personalized_items(personalized_recommendations):
        appid = _collection_appid(item)
        if appid:
            by_appid[appid] = {**by_appid.get(appid, {}), **dict(item)}
    return by_appid


def _selection_base_score(candidate: dict) -> float:
    if candidate.get("base_score") is not None:
        return _safe_number(candidate.get("base_score"), 50.0)
    return _candidate_base_score(candidate)


def _selection_has_score(candidate: dict) -> bool:
    return candidate.get("base_score") is not None or candidate.get("score") is not None


def _selection_decision(appid: str, candidate: dict, owned_appids: set[str], family_appids: set[str]) -> str:
    if not appid or appid in owned_appids or appid in family_appids:
        return "quitar"
    base_score = _selection_base_score(candidate)
    affinity_score = _safe_number(candidate.get("affinity_score"))
    personalized_score = candidate.get("personalized_score")
    if personalized_score is not None and _safe_number(personalized_score) >= 85:
        return "conservar"
    if affinity_score >= 24 or base_score >= 85:
        return "conservar"
    if base_score < 45 and affinity_score <= 0:
        return "quitar"
    return "dudar"


def _dedupe_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _selection_reasons(
    appid: str,
    candidate: dict,
    decision: str,
    owned_appids: set[str],
    family_appids: set[str],
    max_reasons: int,
) -> list[str]:
    reasons: list[str] = []
    if not appid:
        reasons.append("entrada sin appid válido")
    if appid in owned_appids:
        reasons.append("ya está en tu biblioteca")
    if appid in family_appids:
        reasons.append("ya disponible en biblioteca familiar")
    reasons.extend(str(reason) for reason in candidate.get("reasons") or [] if reason != "score base del reporte")
    base_score = _selection_base_score(candidate)
    affinity_score = _safe_number(candidate.get("affinity_score"))
    if candidate.get("personalized_score") is not None and _safe_number(candidate.get("personalized_score")) >= 80:
        reasons.append(f"score personal alto: {_safe_number(candidate.get('personalized_score')):.1f}")
    elif affinity_score > 0:
        reasons.append(f"afinidad positiva: {affinity_score:.1f}")
    if base_score >= 80:
        reasons.append(f"score del reporte fuerte: {base_score:.1f}")
    if _safe_number(candidate.get("discount")) >= 70:
        reasons.append(f"descuento fuerte: {int(_safe_number(candidate.get('discount')))}%")
    reasons.extend(str(reason) for reason in candidate.get("collection_reasons") or [])
    if not reasons:
        fallback = {
            "conservar": "señales positivas del reporte",
            "dudar": "no hay señales suficientes para priorizarlo",
            "quitar": "score bajo y sin afinidad visible",
        }
        reasons.append(fallback[decision])
    return _dedupe_texts(reasons)[:max_reasons]


def _selection_signals(appid: str, candidate: dict, owned_appids: set[str], family_appids: set[str]) -> list[str]:
    signals: list[str] = []
    if not appid:
        signals.append("invalid_appid")
    if appid in owned_appids:
        signals.append("owned")
    if appid in family_appids:
        signals.append("family")
    if candidate.get("personalized_score") is not None:
        signals.append("personalized_score")
    if candidate.get("affinity_score") is not None:
        signals.append("affinity")
    if _selection_has_score(candidate):
        signals.append("report_score")
    if candidate.get("discount") is not None:
        signals.append("discount")
    if candidate.get("price_final") or candidate.get("price"):
        signals.append("price")
    if candidate.get("reasons"):
        signals.append("reasons")
    if candidate.get("collection_reasons") or candidate.get("collection_labels"):
        signals.append("recommended_collection")
    return _dedupe_texts(signals) or ["selection_only"]


def _selection_confidence(
    appid: str,
    candidate: dict,
    decision: str,
    owned_appids: set[str],
    family_appids: set[str],
    signals: list[str],
) -> str:
    if not appid or appid in owned_appids or appid in family_appids:
        return "high"
    base_score = _selection_base_score(candidate)
    affinity_score = _safe_number(candidate.get("affinity_score"))
    personalized_score = candidate.get("personalized_score")
    if decision == "conservar":
        if (
            personalized_score is not None
            and _safe_number(personalized_score) >= 85
        ):
            return "high"
        if affinity_score >= 24 or base_score >= 85:
            return "high"
        return "medium"
    if decision == "quitar":
        return "medium" if _selection_has_score(candidate) else "low"
    if signals != ["selection_only"] or _selection_has_score(candidate):
        return "medium"
    return "low"


def _selection_next_step(
    decision: str,
    appid: str,
    owned_appids: set[str],
    family_appids: set[str],
) -> str:
    if not appid:
        return "Corrige o elimina esta entrada de la selección local."
    if appid in owned_appids or appid in family_appids:
        return "Puedes quitarla de esta selección local; ya aparece disponible."
    if decision == "conservar":
        return "Buena candidata para mantener en tu selección local."
    if decision == "quitar":
        return "Probablemente puedes quitarla de esta selección local."
    return "Revisa si encaja con tu backlog antes de decidir."


def _selection_why_groups(
    appid: str,
    candidate: dict,
    decision: str,
    owned_appids: set[str],
    family_appids: set[str],
    reasons: list[str],
    signals: list[str],
) -> dict[str, list[str]]:
    positive: list[str] = []
    caution: list[str] = []
    context: list[str] = []
    if not appid:
        caution.append("entrada sin appid válido")
    if appid in owned_appids:
        caution.append("ya está en tu biblioteca")
    if appid in family_appids:
        caution.append("ya disponible en biblioteca familiar")
    target = positive if decision == "conservar" else context
    if decision == "quitar":
        target = caution
    target.extend(reasons)
    if "selection_only" in signals:
        context.append("solo aparece en tu selección manual")
    if candidate.get("price_final") or candidate.get("price"):
        context.append("precio visible en el último reporte")
    return {
        "positive": _dedupe_texts(positive)[:3],
        "caution": _dedupe_texts(caution)[:3],
        "context": _dedupe_texts(context)[:3],
    }


def _selection_review_item(
    appid: str,
    candidate: dict,
    owned_appids: set[str],
    family_appids: set[str],
    max_reasons: int,
) -> dict:
    decision = _selection_decision(appid, candidate, owned_appids, family_appids)
    signals = _selection_signals(appid, candidate, owned_appids, family_appids)
    reasons = _selection_reasons(
        appid,
        candidate,
        decision,
        owned_appids,
        family_appids,
        max_reasons,
    )
    return {
        "appid": appid,
        "name": candidate.get("name") or candidate.get("steam_name") or (f"App {appid}" if appid else "Entrada inválida"),
        "decision": decision,
        "confidence": _selection_confidence(
            appid,
            candidate,
            decision,
            owned_appids,
            family_appids,
            signals,
        ),
        "next_step": _selection_next_step(
            decision,
            appid,
            owned_appids,
            family_appids,
        ),
        "base_score": round(_selection_base_score(candidate), 1) if _selection_has_score(candidate) else None,
        "affinity_score": round(_safe_number(candidate.get("affinity_score")), 1) if candidate.get("affinity_score") is not None else None,
        "personalized_score": round(_safe_number(candidate.get("personalized_score")), 1) if candidate.get("personalized_score") is not None else None,
        "discount": int(_safe_number(candidate.get("discount"))) if candidate.get("discount") is not None else None,
        "price_final": candidate.get("price_final") or candidate.get("price") or "",
        "signals": signals,
        "reasons": reasons,
        "why": _selection_why_groups(
            appid,
            candidate,
            decision,
            owned_appids,
            family_appids,
            reasons,
            signals,
        ),
    }


def build_selection_review(
    selection,
    deals: list[dict] | None = None,
    top_picks: list[dict] | None = None,
    *,
    personalized_recommendations=None,
    activity_games=None,
    library_games=None,
    owned=None,
    family_appids=None,
    liked_appids=None,
    preference_relations=None,
    recommended_collections=None,
    hltb_hours=None,
    max_reasons: int = 2,
) -> dict:
    """Evaluate a tentative local selection without checkout or score recalibration."""
    if personalized_recommendations is None and any((activity_games, library_games, liked_appids, preference_relations)):
        personalized_recommendations = build_personalized_recommendations(
            deals or [],
            top_picks=top_picks,
            activity_games=activity_games,
            library_games=library_games,
            owned=owned,
            family_appids=family_appids,
            liked_appids=liked_appids,
            preference_relations=preference_relations,
            hltb_hours=hltb_hours,
        )
    context_by_appid = _selection_context_by_appid(
        deals,
        top_picks,
        personalized_recommendations,
        recommended_collections,
    )
    owned_set = _normalize_appid_set(owned)
    family_set = _normalize_appid_set(family_appids)
    seen_appids: set[str] = set()
    duplicate_count = 0
    items: list[dict] = []
    for record in _selection_records(selection):
        appid = _collection_appid(record)
        if appid and appid in seen_appids:
            duplicate_count += 1
            continue
        if appid:
            seen_appids.add(appid)
        candidate = {**context_by_appid.get(appid, {}), **record}
        items.append(_selection_review_item(appid, candidate, owned_set, family_set, max(1, int(_safe_number(max_reasons, 2)))))
    counts = {decision: sum(1 for item in items if item["decision"] == decision) for decision in ("conservar", "dudar", "quitar")}
    return {
        "source_signals": ["selection", "score", "personalized_recommendations", "recommended_collections", "owned_family"],
        "items": items,
        "summary": {"total_items": len(items), "duplicate_count": duplicate_count, **counts},
    }


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


def _promo_context_category(active_promo_context: dict | None) -> str:
    if not isinstance(active_promo_context, dict):
        return ""
    primary = active_promo_context.get("primary")
    if isinstance(primary, dict):
        category = str(primary.get("category", "") or "").strip()
        if category:
            return category
    categories = active_promo_context.get("categories", [])
    if isinstance(categories, list) and categories:
        return str(categories[0] or "").strip()
    return ""


def _top_pick_promo_signal(top_pick: dict | None) -> dict[str, int]:
    pick = top_pick if isinstance(top_pick, dict) else {}
    return {
        "discount": int(_safe_number(pick.get("discount"))),
        "priority": int(_safe_number(pick.get("priority"))),
    }


def _is_wishlist_priority_signal(priority: int) -> bool:
    return 0 < priority <= 50


def build_promo_pick_reason(active_promo_context: dict | None, top_pick: dict | None = None) -> str:
    """Return a conservative pick reason based on active Steam promo context."""
    category = _promo_context_category(active_promo_context)
    signals = _top_pick_promo_signal(top_pick)
    discount = signals["discount"]
    priority = signals["priority"]

    if category == "major_sale" and discount >= 70:
        return f"oferta grande + {discount}% de descuento: candidato para revisar ahora"
    if category == "publisher_sale" and discount >= 70:
        return f"publisher/franquicia + {discount}% de descuento: compara contra mínimo histórico"
    if category in {"weeklong", "midweek", "weekend"}:
        if _is_wishlist_priority_signal(priority):
            return "promo corta + juego en tu radar: revisar precio sin tratarla como urgencia"
        if discount >= 75:
            return f"promo corta + {discount}% de descuento: revisar sin tratarla como evento grande"
        return ""

    reason_by_category = {
        "major_sale": "contexto de oferta grande: prioriza descuentos fuertes",
        "fest": "contexto de festival: revisa si encaja con la temática activa",
        "publisher_sale": "contexto publisher/franquicia: compara contra tu mínimo histórico",
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
    scored = [
        _score_top_pick(deal, priorities, reviews, hltb_hours, deck_compat)
        for deal in deals
    ]
    scored = [
        _apply_promo_pick_reason(
            top_pick,
            build_promo_pick_reason(active_promo_context, top_pick),
        )
        for top_pick in scored
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
