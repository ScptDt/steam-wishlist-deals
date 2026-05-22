from __future__ import annotations

import re


PROMO_HIGHLIGHTS_ADVISORY = (
    "Highlights agrupados con señales locales del reporte; no prueban pertenencia "
    "oficial de cada juego a la promo ni cambian score, ranking, cache o fetching."
)

PROMO_CATEGORY_LABELS = {
    "major_sale": "Oferta grande",
    "next_fest": "Next Fest",
    "fest": "Fest",
    "publisher_sale": "Publisher/Franquicia",
    "themed": "Oferta temática",
    "daily_deal": "Daily Deal",
    "weekend": "Weekend",
    "free_to_keep": "Gratis para conservar",
    "free_weekend": "Free Weekend",
    "midweek": "Midweek",
    "launch": "Lanzamiento",
    "weeklong": "Weeklong",
    "unknown": "Otra promo",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except (TypeError, ValueError):
        return default


def _promo_category_label(category: str) -> str:
    key = _text(category)
    return PROMO_CATEGORY_LABELS.get(key, key.replace("_", " ").title() or "Otra promo")


def _promo_slug(title: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or fallback


def _promo_title(promo: dict) -> str:
    return _text(promo.get("title") or promo.get("name") or promo.get("sale_name"))


def _add_promo(seen: set[str], promos: list[dict], promo: dict) -> None:
    title = _promo_title(promo)
    if not title:
        return
    key = title.casefold()
    if key in seen:
        return
    seen.add(key)
    promos.append({**promo, "title": title})


def _promo_records(active_promo_context: dict | None) -> list[dict]:
    if not isinstance(active_promo_context, dict):
        return []
    seen: set[str] = set()
    promos: list[dict] = []
    primary = active_promo_context.get("primary")
    if isinstance(primary, dict):
        _add_promo(seen, promos, primary)
    raw_promos = active_promo_context.get("promos")
    if isinstance(raw_promos, list):
        for promo in raw_promos:
            if isinstance(promo, dict):
                _add_promo(seen, promos, promo)
    if not promos and _text(active_promo_context.get("sale_name")):
        _add_promo(
            seen,
            promos,
            {
                "title": active_promo_context.get("sale_name"),
                "category": (active_promo_context.get("categories") or ["unknown"])[0]
                if isinstance(active_promo_context.get("categories"), list)
                and active_promo_context.get("categories")
                else "unknown",
            },
        )
    return promos


def _score_reasons(item: dict, *, limit: int = 2) -> list[str]:
    reasons = item.get("score_reasons") or item.get("reasons")
    if not isinstance(reasons, list):
        return []
    return [_text(reason) for reason in reasons if _text(reason)][:limit]


def _candidate_key(item: dict) -> str:
    appid = _text(item.get("appid") or item.get("steam_appid"))
    if appid:
        return f"appid:{appid}"
    return f"name:{_text(item.get('name') or item.get('steam_name')).casefold()}"


def _candidate_reasons(item: dict, *, source: str) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    signals = [source]
    recommendation = _text(item.get("recommendation"))
    if recommendation:
        reasons.append(recommendation)
        signals.append("recommendation")
    for reason in _score_reasons(item):
        if reason not in reasons:
            reasons.append(reason)
            signals.append("score_reasons")
    discount = _safe_int(item.get("discount"))
    if discount >= 75:
        reasons.append(f"{discount}% de descuento")
        signals.append("discount")
    elif discount >= 50:
        signals.append("discount")
    if source == "top_pick":
        reasons.append("ya aparece en Top Picks del reporte")
    return reasons[:4], list(dict.fromkeys(signals))


def _candidate_from(item: dict, *, source: str) -> dict | None:
    appid = _text(item.get("appid") or item.get("steam_appid"))
    name = _text(item.get("name") or item.get("steam_name"))
    if not appid and not name:
        return None
    reasons, signals = _candidate_reasons(item, source=source)
    discount = _safe_int(item.get("discount"))
    if source != "top_pick" and discount < 50 and not reasons:
        return None
    candidate = {
        "appid": appid,
        "name": name or f"AppID {appid}",
        "source": source,
        "source_signals": signals,
        "highlight_reasons": reasons or ["candidato local del reporte"],
    }
    if discount:
        candidate["discount"] = discount
    price_final = _text(item.get("price_final") or item.get("price"))
    if price_final:
        candidate["price_final"] = price_final
    recommendation = _text(item.get("recommendation"))
    if recommendation:
        candidate["recommendation"] = recommendation
    return candidate


def _deal_map(deals: list[dict] | None) -> dict[str, dict]:
    return {
        _text(deal.get("appid") or deal.get("steam_appid")): deal
        for deal in deals or []
        if isinstance(deal, dict) and _text(deal.get("appid") or deal.get("steam_appid"))
    }


def _candidate_items(
    deals: list[dict] | None,
    top_picks: list[dict] | None,
    *,
    limit: int,
) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    deals_by_appid = _deal_map(deals)
    sources = ((top_picks or [], "top_pick"), (deals or [], "deal"))
    for items, source in sources:
        for raw_item in items:
            if not isinstance(raw_item, dict):
                continue
            item = dict(deals_by_appid.get(_text(raw_item.get("appid")), {}))
            item.update(raw_item)
            candidate = _candidate_from(item, source=source)
            if not candidate:
                continue
            key = _candidate_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
            if len(candidates) >= limit:
                return candidates
    return candidates


def _section_items(candidates: list[dict], promo_title: str) -> list[dict]:
    items: list[dict] = []
    for candidate in candidates:
        item = dict(candidate)
        item["promo_context"] = promo_title
        reasons = ["contexto local de promo activa", *item.get("highlight_reasons", [])]
        item["highlight_reasons"] = list(dict.fromkeys(reasons))[:4]
        items.append(item)
    return items


def _promo_section(promo: dict, candidates: list[dict], index: int) -> dict:
    title = _promo_title(promo)
    category = _text(promo.get("category") or "unknown") or "unknown"
    return {
        "id": _promo_slug(title, f"promo-{index}"),
        "title": f"Highlights de {title}",
        "promo_title": title,
        "category": category,
        "category_label": _promo_category_label(category),
        "advisory_note": PROMO_HIGHLIGHTS_ADVISORY,
        "source_signals": ["active_promo_context", "top_picks", "deals"],
        "items": _section_items(candidates, title),
    }


def build_promo_highlights(
    deals: list[dict] | None,
    *,
    top_picks: list[dict] | None = None,
    active_promo_context: dict | None = None,
    max_promos: int = 6,
    max_items_per_promo: int = 6,
) -> dict | None:
    """Build local/offline promo highlight sections from existing report signals."""
    promos = _promo_records(active_promo_context)[: max(1, max_promos)]
    candidates = _candidate_items(deals, top_picks, limit=max(1, max_items_per_promo))
    if not promos or not candidates:
        return None
    sections = [
        _promo_section(promo, candidates, index)
        for index, promo in enumerate(promos, 1)
    ]
    return {
        "summary": {
            "promos_count": len(sections),
            "items_count": sum(len(section["items"]) for section in sections),
            "advisory_only": True,
            "ranking_impact": "none",
        },
        "advisory_note": PROMO_HIGHLIGHTS_ADVISORY,
        "source_signals": ["active_promo_context", "top_picks", "deals"],
        "sections": sections,
    }
