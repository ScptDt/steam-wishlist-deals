from __future__ import annotations

from datetime import date

from .common import markdown_escape
from .social_rows import (
    compare_overlap_count,
    is_numeric_appid,
    normalize_gift_idea_rows,
    normalize_overlap_deal_rows,
)


STORE_URL = "https://store.steampowered.com/app/{appid}/"

MESES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def _md_esc(text: str) -> str:
    return markdown_escape(text)


def _link(name: str, appid: str) -> str:
    return f"[{_md_esc(name)}]({STORE_URL.format(appid=appid)})"


def _optional_link(name: str, appid: str) -> str:
    return _link(name, appid) if is_numeric_appid(appid) else _md_esc(name)


def _compact_social_reasons(item: dict, *, limit: int = 2) -> str:
    reasons = item.get("social_reasons") if isinstance(item, dict) else None
    if not isinstance(reasons, list):
        return ""
    compact: list[str] = []
    for reason in reasons:
        text = str(reason or "").strip()
        if text and text not in compact:
            compact.append(text)
        if len(compact) >= limit:
            break
    return " · ".join(compact)


def _yaml_quote(text: str) -> str:
    safe = str(text).replace('"', '\\"')
    return f'"{safe}"'


_PROMO_CATEGORY_LABELS = {
    "weeklong": "Weeklong",
    "midweek": "Midweek",
    "weekend": "Weekend",
    "launch": "Lanzamiento",
    "fest": "Fest",
    "major_sale": "Oferta grande",
    "publisher_sale": "Publisher/Franquicia",
    "themed": "Oferta temática",
    "unknown": "Otra promo",
}

_WISHLIST_HYGIENE_SIGNAL_LABELS = {
    "owned": "Ya está en biblioteca",
    "family": "Biblioteca familiar",
    "library_match": "Match biblioteca local",
    "hltb_match": "HLTB local",
    "other_store": "Otra tienda",
    "catalog_removed": "Retirado del catálogo",
    "catalog_missing": "No está en catálogo local",
    "invalid_appid": "AppID inválido",
}


def _promo_category_label(category: str) -> str:
    return _PROMO_CATEGORY_LABELS.get(str(category or ""), str(category or "Otra promo"))


def _wishlist_hygiene_signal_label(signal: str) -> str:
    key = str(signal or "").strip()
    return _WISHLIST_HYGIENE_SIGNAL_LABELS.get(key, key.replace("_", " "))


def _wishlist_hygiene_items(payload: dict | None, *, limit: int = 12) -> tuple[list[dict], int, int]:
    if not isinstance(payload, dict):
        return [], 0, 0
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    total = len(items)
    return items[:limit], total, max(0, total - limit)


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _wishlist_hygiene_game_label(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    fallback_name = f"AppID {appid}" if appid else "Entrada sin appid"
    name = str(
        item.get("name")
        or item.get("steam_name")
        or fallback_name
    ).strip()
    return _link(name, appid) if appid.isdigit() else _md_esc(name)


def _wishlist_hygiene_is_appid_only(item: dict) -> bool:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    return bool(
        appid
        and (
            item.get("missing_local_name") is True
            or not str(item.get("name") or item.get("steam_name") or "").strip()
        )
    )


def _wishlist_hygiene_missing_name_reason() -> str:
    return "No tenemos nombre local para este AppID; revisa si quieres mantenerlo en wishlist"


def _wishlist_hygiene_signal_text(item: dict) -> str:
    signals = item.get("signals") if isinstance(item, dict) else []
    labels = [
        _wishlist_hygiene_signal_label(signal)
        for signal in signals
        if str(signal or "").strip()
    ]
    return _md_esc(" · ".join(labels[:4]) or "revisar")


def _wishlist_hygiene_reason_text(item: dict) -> str:
    reasons = item.get("reasons") if isinstance(item, dict) else []
    compact = [str(reason or "").strip() for reason in reasons if str(reason or "").strip()]
    missing_reason = _wishlist_hygiene_missing_name_reason()
    if _wishlist_hygiene_is_appid_only(item) and not any(
        "No tenemos nombre local" in reason for reason in compact
    ):
        compact.insert(0, missing_reason)
    return _md_esc(" · ".join(compact[:2]) or "revisar manualmente antes de limpiar")


def _wishlist_hygiene_action_text(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    action = "Solo revisión" if item.get("action") == "review" else "Revisar"
    if appid.isdigit():
        return f"{action} · {_link('Abrir en Steam', appid)}"
    return action


def _build_wishlist_hygiene_lines(payload: dict | None) -> list[str]:
    items, total_items, hidden_count = _wishlist_hygiene_items(payload)
    if not items:
        return []
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    wishlist_total = summary.get("total_wishlist_items") if isinstance(summary, dict) else None
    total_hint = f" de {int(wishlist_total):,} en wishlist" if isinstance(wishlist_total, int) else ""
    lines = [
        "## 🧹 Revisar wishlist",
        "",
        f"> **{total_items:,} sugerencias{total_hint}**. Sugerencias locales **advisory-only**: no borra, no auto-excluye juegos y no cambia el score.",
        "",
        "| Juego | Señales | Motivos | Acción |",
        "|-------|---------|---------|--------|",
    ]
    for item in items:
        lines.append(
            f"| {_wishlist_hygiene_game_label(item)} | {_wishlist_hygiene_signal_text(item)} | {_wishlist_hygiene_reason_text(item)} | {_wishlist_hygiene_action_text(item)} |"
        )
    if hidden_count:
        lines += ["", f"> {hidden_count:,} más en el payload completo."]
    lines += ["", "---", ""]
    return lines


def _smart_alert_digest_sections(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    if payload.get("dry_run") is not True or payload.get("send_ready") is not False:
        return []
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, dict)]


def _smart_alert_item_label(item: dict) -> str:
    title = str(item.get("title") or "").strip()
    if title:
        return _md_esc(title)
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    name = str(item.get("name") or item.get("steam_name") or f"AppID {appid}").strip()
    return _link(name, appid) if appid.isdigit() else _md_esc(name)


def _smart_alert_item_details(item: dict) -> str:
    details = []
    change_pct = _safe_float(item.get("change_pct"))
    current_price = _safe_float(item.get("current_price"))
    historical_low = _safe_float(item.get("historical_low"))
    if change_pct is not None:
        details.append(f"+{change_pct:.0f}%")
    if current_price is not None:
        details.append(f"actual ${current_price:.0f}")
    if historical_low is not None:
        details.append(f"mín. ${historical_low:.0f}")
    if item.get("games_count") is not None:
        details.append(f"{_safe_int(item.get('games_count'))} juegos")
    reason = str(item.get("reason") or "").strip()
    if reason:
        details.append(reason)
    return _md_esc(" · ".join(details))


def _smart_alert_examples(section: dict) -> str:
    items = [item for item in section.get("items", []) if isinstance(item, dict)]
    examples = []
    for item in items[:3]:
        label = _smart_alert_item_label(item)
        details = _smart_alert_item_details(item)
        examples.append(f"{label} ({details})" if details else label)
    hidden_count = _safe_int(section.get("hidden_count"), 0)
    if hidden_count:
        examples.append(f"+{hidden_count:,} más")
    return " · ".join(examples) if examples else "Ver JSON completo"


def _build_smart_alert_digest_lines(payload: dict | None) -> list[str]:
    sections = _smart_alert_digest_sections(payload)
    if not sections:
        return []
    total_count = _safe_int(payload.get("total_count"), 0) if isinstance(payload, dict) else 0
    lines = [
        "## 🔔 Alertas inteligentes — preview local",
        "",
        f"> **{total_count:,} señales agrupadas** en digest dry-run. No envía Telegram/Discord, no habilita notificaciones por juego y requiere revisión antes de conectar canales externos.",
        "",
        "| Sección | Señales | Ejemplos |",
        "|---------|---------|----------|",
    ]
    for section in sections:
        label = _md_esc(str(section.get("label") or section.get("id") or "Sección"))
        count = _safe_int(section.get("count"), 0)
        lines.append(f"| {label} | {count:,} | {_smart_alert_examples(section)} |")
    lines += ["", "---", ""]
    return lines


def _is_useful_local_trend(trend: dict | None) -> bool:
    if not trend or trend.get("is_first_time"):
        return False
    return bool(
        (trend.get("is_best_local") and trend.get("times_on_sale", 0) > 1)
        or trend.get("is_first_at_price")
    )


def _build_promo_context_lines(active_promo_context: dict | None) -> list[str]:
    if not isinstance(active_promo_context, dict):
        return []
    primary = active_promo_context.get("primary")
    primary_title = ""
    if isinstance(primary, dict):
        primary_title = str(primary.get("title", "") or "").strip()
    primary_title = primary_title or str(active_promo_context.get("sale_name", "") or "").strip()
    if not primary_title:
        return []

    categories = [
        _promo_category_label(category)
        for category in active_promo_context.get("categories", [])
        if category
    ]
    promos = active_promo_context.get("promos", [])
    extra_titles = []
    if isinstance(promos, list):
        for promo in promos:
            if not isinstance(promo, dict):
                continue
            title = str(promo.get("title", "") or "").strip()
            if title and title != primary_title and title not in extra_titles:
                extra_titles.append(title)

    lines = [f"> Promo activa: **{_md_esc(primary_title)}**"]
    lines.append("> Contexto local: no es predicción ni cambia el score.")
    if categories:
        lines.append(f"> Contexto promo: {' · '.join(_md_esc(label) for label in categories)}")
    if extra_titles:
        lines.append(
            f"> También activas: {', '.join(_md_esc(title) for title in extra_titles[:4])}"
        )
    simultaneous_hint = str(active_promo_context.get("simultaneous_hint") or "").strip()
    if simultaneous_hint:
        lines.append(f"> Promos simultáneas: {_md_esc(simultaneous_hint)}")
    decision_hint = str(active_promo_context.get("decision_hint") or "").strip()
    if decision_hint:
        lines.append(f"> Lectura sugerida: {_md_esc(decision_hint)}")
    return lines


def _build_frontmatter(
    *,
    vanity: str,
    sale_name: str,
    min_discount: int,
    wishlist_count: int,
    deals_count: int,
    top_picks_count: int,
    generated_date: str,
) -> list[str]:
    return [
        "---",
        f"title: {_yaml_quote(f'Steam Wishlist Deals — {vanity}')}",
        f"profile: {_yaml_quote(vanity)}",
        f"sale_name: {_yaml_quote(sale_name)}",
        f"generated_date: {_yaml_quote(generated_date)}",
        f"min_discount: {int(min_discount)}",
        f"wishlist_count: {int(wishlist_count)}",
        f"deals_count: {int(deals_count)}",
        f"top_picks_count: {int(top_picks_count)}",
        "tags:",
        "  - steam-deals",
        "  - wishlist",
        "  - markdown-export",
        "---",
        "",
    ]


def _prio_badge(priority: int) -> str:
    if priority == 0:
        return ""
    if priority <= 10:
        return f" **#{priority}**"
    if priority <= 50:
        return f" #{priority}"
    return ""


def format_deal_row(game: dict, show_storefront: bool = False) -> str:
    pct = f"-{game['discount']}%"
    name = _link(game["steam_name"], game["appid"])
    if (
        game["score"] < 0.95
        and game["hltb_title"].lower() != game["steam_name"].lower()
    ):
        name += f" _(HLTB: {_md_esc(game['hltb_title'])})_"
    pph = game.get("price_per_hour")
    pph_str = f" · ${pph:.1f}/h" if pph is not None else ""
    hours = game.get("hours")
    hours_str = f" · {hours:.0f}h" if hours else ""
    extra = f"{hours_str}{pph_str}" if (hours_str or pph_str) else ""

    if show_storefront:
        return (
            f"| {pct} | {game['price']}{extra} | {game['storefront'] or '?'} | {name} |"
        )
    return f"| {pct} | {game['price']}{extra} | {game['price_original']} | {name} |"


def _format_budget_pick_label(pick: dict) -> str:
    label = _link(pick["name"], pick["appid"])
    recommendation = pick.get("recommendation")
    reasons = " · ".join(_md_esc(reason) for reason in pick.get("score_reasons", []))
    if recommendation:
        label += f"<br>**{_md_esc(recommendation)}**"
    if reasons:
        label += f"<br>{reasons}"
    return label


def _build_budget_variants_lines(variants: list[dict], *, selected_variant: str | None) -> list[str]:
    if not variants:
        return []
    lines = [
        "### 🔁 Probar otra lista",
        "",
        "> El mismo presupuesto ahora se resume en tres variantes: lista chica, media y grande.",
        "",
    ]
    for variant in variants:
        marker = " **(actual)**" if variant.get("id") == selected_variant else ""
        names = ", ".join(_md_esc(item.get("name", "")) for item in variant.get("selected", []))
        lines.append(
            f"- **{_md_esc(variant.get('label') or variant.get('id') or 'Variante')}**{marker} — {_md_esc(variant.get('description', ''))}"
        )
        lines.append(
            f"  - Total: ${variant.get('total_spent', 0):.0f} | Restante: ${variant.get('remaining', 0):.0f} | Juegos: {variant.get('games_count', 0)}"
        )
        lines.append(f"  - Incluye: {names or 'Sin selección disponible'}")
    lines += ["", ""]
    return lines


def _build_budget_replacement_lines(selected: list[dict]) -> list[str]:
    groups = []
    for pick in selected:
        replacements = pick.get("replacement_candidates") or []
        if not replacements:
            continue
        groups.append(f"- **{_md_esc(pick.get('name', 'Juego'))}**")
        groups.append(
            "  - Opciones para cambiar este juego sin romper el presupuesto:"
        )
        for replacement in replacements:
            groups.append(
                f"    - {_link(replacement['name'], replacement['appid'])} | {replacement.get('price_final', '—')} | Score {replacement.get('score', '—')} | Nuevo total: ${replacement.get('swap_total_spent', 0):.0f} | Restante: ${replacement.get('swap_remaining', 0):.0f}"
            )
    if not groups:
        return []
    return [
        "### 🔄 Cambiar este juego",
        "",
        "> Cada sugerencia respeta el mismo presupuesto total de la variante mostrada arriba.",
        "",
        *groups,
        "",
        "",
    ]


def _recommended_collection_item_line(item: dict) -> str:
    appid = str(item.get("appid") or "").strip()
    name = str(item.get("name") or "Juego desconocido")
    title = _link(name, appid) if appid else _md_esc(name)
    reason = str(item.get("reason") or "Recomendado por las señales del reporte.")
    meta = []
    if item.get("score") not in (None, ""):
        meta.append(f"Score {_md_esc(str(item.get('score')))}")
    discount = int(item.get("discount") or 0)
    if discount:
        meta.append(f"-{discount}%")
    price_final = str(item.get("price_final") or "")
    if price_final:
        meta.append(_md_esc(price_final))
    meta_text = f" ({' · '.join(meta)})" if meta else ""
    return f"- {title} — {_md_esc(reason)}{meta_text}"


def _build_recommended_collection_lines(collections: list[dict]) -> list[str]:
    sections = []
    for collection in collections or []:
        items = [item for item in collection.get("items", []) if isinstance(item, dict)]
        if not items:
            continue
        title = str(collection.get("title") or collection.get("label") or "Colección")
        description = str(
            collection.get("description") or "Juegos agrupados con señales ya calculadas."
        )
        sections.extend(
            [
                f"### {_md_esc(title)}",
                "",
                f"> {_md_esc(description)}",
                "",
                *[_recommended_collection_item_line(item) for item in items],
                "",
            ]
        )
    if not sections:
        return []
    return [
        "## 🧠 Colecciones recomendadas",
        "",
        "> Secciones curadas con datos ya calculados del reporte: score, descuento, compatibilidad, reviews y géneros/etiquetas disponibles.",
        "",
        *sections,
        "---",
        "",
    ]


def _personalized_item_title(item: dict) -> str:
    appid = str(item.get("appid") or "").strip()
    name = str(item.get("name") or "Juego desconocido")
    return _link(name, appid) if appid else _md_esc(name)


def _personalized_item_line(item: dict, index: int) -> str:
    reasons = [str(reason) for reason in item.get("reasons", []) if str(reason).strip()]
    reason_text = " · ".join(_md_esc(reason) for reason in reasons) or "score base del reporte"
    meta = []
    if item.get("personalized_score") not in (None, ""):
        meta.append(f"Personal {_md_esc(str(item.get('personalized_score')))}")
    if item.get("affinity_score") not in (None, ""):
        meta.append(f"Afinidad +{_md_esc(str(item.get('affinity_score')))}")
    discount = int(item.get("discount") or 0)
    if discount:
        meta.append(f"-{discount}%")
    price_final = str(item.get("price_final") or "")
    if price_final:
        meta.append(_md_esc(price_final))
    meta_text = f" ({' · '.join(meta)})" if meta else ""
    return f"- {index}. {_personalized_item_title(item)} — {reason_text}{meta_text}"


def _profile_terms_text(terms: list[dict]) -> str:
    labels = [str(term.get("term") or "").strip() for term in terms if term.get("term")]
    return ", ".join(_md_esc(label) for label in labels[:3])


def _profile_positive_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _activity_summary_chips(summary: dict) -> list[str]:
    if not isinstance(summary, dict):
        return []
    chips: list[str] = []
    recent_hours = _profile_positive_number(summary.get("recent_hours"))
    total_hours = _profile_positive_number(summary.get("total_hours"))
    if recent_hours or total_hours:
        hours_parts = []
        if recent_hours:
            hours_parts.append(f"{recent_hours:.1f}h recientes")
        if total_hours:
            hours_parts.append(f"{total_hours:.1f}h total")
        chips.append(f"actividad local: {' · '.join(hours_parts)}")
    for item in summary.get("top_played", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        total = _profile_positive_number(item.get("total_hours"))
        if name and total:
            chips.append(f"más jugado: {_md_esc(name)} ({total:.1f}h)")
            break
    return chips


def _personalized_profile_line(profile: dict) -> str:
    parts = []
    activity_terms = _profile_terms_text(profile.get("activity_terms", []))
    if activity_terms:
        parts.append(f"actividad: {activity_terms}")
    parts.extend(_activity_summary_chips(profile.get("activity_summary") or {}))
    library_summary = profile.get("library_summary") or {}
    library_terms = _profile_terms_text(library_summary.get("top_terms", []))
    if library_terms:
        parts.append(f"biblioteca: {library_terms}")
    total_hours = library_summary.get("total_hltb_hours")
    if total_hours:
        parts.append(f"HLTB: {total_hours}h")
    average_price = library_summary.get("average_price")
    if average_price is not None:
        parts.append(f"precio promedio biblioteca: ${average_price}")
    if not parts:
        return ""
    return f"> Perfil usado: {' · '.join(parts)}"


def _build_personalized_recommendation_lines(payload: dict | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    if not items:
        return []
    profile_line = _personalized_profile_line(payload.get("profile") or {})
    profile_lines = [profile_line, ""] if profile_line else []
    return [
        "## 🎯 Recomendaciones personalizadas",
        "",
        "> Ranking explicable construido con score del reporte y señales opcionales de actividad, biblioteca y preferencias. No cambia el score global.",
        "",
        *profile_lines,
        *[_personalized_item_line(item, idx) for idx, item in enumerate(items, 1)],
        "",
        "---",
        "",
    ]


def generate_md(
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
    recommended_collections: list[dict] | None = None,
    personalized_recommendations: dict | None = None,
    wishlist_hygiene: dict | None = None,
    include_frontmatter: bool = False,
    active_promo_context: dict | None = None,
    smart_alert_digest: dict | None = None,
    *,
    group_by_tier,
    filter_by_genres,
    group_deals_by_tag,
    linux_badge,
    multiplayer_badges,
    get_top_tags,
    players_badge,
    format_trend,
    achievements_badge,
    compute_value_score,
) -> str:
    today_obj = date.today()
    today = f"{today_obj.day} de {MESES[today_obj.month]} de {today_obj.year}"
    priorities = priorities or {}
    historical_lows = historical_lows or {}
    previous_appids = previous_appids or set()
    reviews = reviews or {}
    deck_compat_data = deck_compat or {}
    tags_data = tags_data or {}
    protondb_data = protondb_data or {}
    anticheat_data = anticheat_data or {}
    achievements_data = achievements_data or {}
    local_trends = local_trends or {}
    active_bundles_data = active_bundles or {}
    current_prices = current_prices or {}
    top_picks = top_picks or []
    recommended_collections = recommended_collections or []
    personalized_recommendations = personalized_recommendations or {"items": []}
    wishlist_hygiene = wishlist_hygiene or {"items": []}
    smart_alert_digest = smart_alert_digest if isinstance(smart_alert_digest, dict) else None
    watchlist_alerts = watchlist_alerts or []
    comp = comparison or {}
    owned_and_wishlisted = sorted(
        [(a, owned[a]) for a in set(owned) & set(wishlist_appids)],
        key=lambda x: x[1].lower(),
    )

    otras = familia = steam_sf = sin_sf = []
    if hltb_used:
        family_appids = family_appids or set()
        otras = [
            g
            for g in backlog_on_sale
            if g["storefront"]
            and g["storefront"].lower() not in ("steam", "")
            and not g["in_family"]
        ]
        familia = [g for g in backlog_on_sale if g["in_family"]]
        steam_sf = [
            g
            for g in backlog_on_sale
            if g["storefront"].lower() == "steam" and not g["in_family"]
        ]
        sin_sf = [
            g for g in backlog_on_sale if not g["storefront"] and not g["in_family"]
        ]

    sale_line = f"Evento: 🏷️ **{sale_name}** | " if sale_name else ""
    lines = [
        f"# Steam Wishlist Deals — {vanity}",
        f"> {sale_line}{today} | Precios en MXN | Perfil: {vanity.lower()}",
        f"> Wishlist: {len(wishlist_appids):,} juegos | Deals (≥{min_discount}%): {len(deals):,}"
        + (f" | Backlog en oferta: {len(backlog_on_sale)}" if hltb_used else ""),
    ]
    delta_parts = []
    new_deal_count = len(comp.get("new_deals", set()))
    disappeared_count = len(comp.get("disappeared", []))
    price_drops = sum(
        1 for v in comp.get("price_changes", {}).values() if v["direction"] == "down"
    )
    if new_deal_count:
        delta_parts.append(f"🆕 {new_deal_count} nuevos")
    if disappeared_count:
        delta_parts.append(f"❌ {disappeared_count} terminaron")
    if price_drops:
        delta_parts.append(f"⬇️ {price_drops} bajaron de precio")
    if delta_parts:
        lines.append(f"> {' · '.join(delta_parts)}")
    promo_lines = _build_promo_context_lines(active_promo_context)
    if promo_lines:
        lines.extend(promo_lines)
    lines += ["", "---", ""]

    if include_frontmatter:
        lines = (
            _build_frontmatter(
                vanity=vanity,
                sale_name=sale_name,
                min_discount=min_discount,
                wishlist_count=len(wishlist_appids),
                deals_count=len(deals),
                top_picks_count=len(top_picks),
                generated_date=today_obj.isoformat(),
            )
            + lines
        )

    if top_picks:
        lines += [
            "## 🏆 Top 10 Picks",
            "",
            "> Score = recomendación compuesta para priorizar qué revisar primero. Combina reviews (26%) + descuento (22%) + prioridad (18%) + $/hora HLTB (14%) + Deck (10%) + Metacritic (5%) + antigüedad (5%).",
            "",
            "| # | Score | % | Precio | Año | Reseñas | Metacritic | Compatibilidad | Tipo de juego | Juego |",
            "|---|-------|---|--------|-----|---------|----|-----------|----|-------|",
        ]
        for idx, tp in enumerate(top_picks, 1):
            rev = tp.get("review")
            rev_str = f"{rev['desc']} ({rev['pct']}%)" if rev else "—"
            tp_dk = tp.get("deck", 0)
            tp_pdb = protondb_data.get(tp["appid"])
            tp_ac = anticheat_data.get(tp["appid"])
            dk_str = linux_badge(tp_dk, tp_pdb, tp_ac, tp.get("linux_native", False))
            mc = tp.get("metacritic_score")
            mc_str = str(mc) if mc else "—"
            mp_str = multiplayer_badges(tp.get("categories", [])) or "—"
            prio = _prio_badge(tp.get("priority", 0))
            name_col = f"{_link(tp['name'], tp['appid'])}{prio}"
            yr = tp.get("release_year") or "—"
            lines.append(
                f"| {idx} | {tp['score']} | -{tp['discount']}% | {tp['price_final']} | {yr} | {rev_str} | {mc_str} | {dk_str} | {mp_str} | {name_col} |"
            )
        if any(tp.get("recommendation") or tp.get("score_reasons") for tp in top_picks):
            lines += ["", "### ¿Por qué salió arriba?", ""]
            for idx, tp in enumerate(top_picks, 1):
                recommendation = tp.get("recommendation")
                reasons = " · ".join(
                    _md_esc(reason) for reason in tp.get("score_reasons", [])
                )
                bullet = f"- {idx}. {_link(tp['name'], tp['appid'])}"
                if recommendation:
                    bullet += f" — **{_md_esc(recommendation)}**"
                if reasons:
                    bullet += f" · {reasons}"
                lines.append(bullet)
        lines += ["", "---", ""]

    lines += _build_recommended_collection_lines(recommended_collections)
    lines += _build_personalized_recommendation_lines(personalized_recommendations)
    lines += _build_wishlist_hygiene_lines(wishlist_hygiene)
    lines += _build_smart_alert_digest_lines(smart_alert_digest)

    if watchlist_alerts:
        lines += [
            "## 🎯 Watchlist Alerts",
            "",
            f"> **{len(watchlist_alerts)} juegos** de tu watchlist alcanzaron el precio objetivo.",
            "",
            "| Juego | Precio Actual | Objetivo | Descuento | Ahorro extra |",
            "|-------|---------------|----------|-----------|--------------|",
        ]
        for wa in watchlist_alerts:
            savings = wa["target_price"] - (wa["price_raw"] / 100)
            savings_str = f"${savings:.0f}" if savings > 0 else "—"
            lines.append(
                f"| {_link(wa['name'], wa['appid'])} | {wa['price_final']} | ${wa['target_price']:.0f} | -{wa['discount']}% | {savings_str} |"
            )
        lines += ["", "---", ""]

    if budget_result:
        b = budget_result
        variants = b.get("variants") or []
        selected_variant = b.get("selected_variant")
        lines += [
            f"## 💰 Tu Presupuesto Ideal — ${b['budget']:.0f} MXN",
            "",
            f"> Con **${b['budget']:.0f} MXN** puedes comprar **{b['games_count']} juegos**.",
            f"> Total: ${b['total_spent']:.0f} | Ahorro vs original: ${b['total_savings']:.0f} | Restante: ${b['remaining']:.0f}",
            "",
            "| # | Score | % | Precio | Juego |",
            "|---|-------|---|--------|-------|",
        ]
        for idx, pick in enumerate(b["selected"], 1):
            label = _format_budget_pick_label(pick)
            lines.append(
                f"| {idx} | {pick.get('score', '—')} | -{pick['discount']}% | {pick['price_final']} | {label} |"
            )
        lines += _build_budget_variants_lines(
            variants, selected_variant=selected_variant
        )
        lines += _build_budget_replacement_lines(b.get("selected", []))
        lines += ["", "---", ""]

    if compare_data:
        friend = compare_data.get("friend_name") or compare_data.get("friend_vanity", "?")
        friend_label = _md_esc(str(friend))
        overlap_count = compare_overlap_count(compare_data)
        lines += [
            f"## 👥 Wishlist Comparison — {friend_label}",
            "",
            f"> **{overlap_count} juegos en común** entre tu wishlist y la de {friend_label}.",
            "",
        ]
        overlap_deals = normalize_overlap_deal_rows(deals, compare_data)
        if overlap_deals:
            lines += [
                f"### En común y en oferta ({len(overlap_deals)} juegos)",
                "",
                "| % | Precio | Juego |",
                "|---|--------|-------|",
            ]
            for row in overlap_deals:
                lines.append(
                    f"| -{int(row['discount'])}% | {_md_esc(str(row['price_final']))} | {_optional_link(str(row['name']), str(row['appid']))} |"
                )
            lines.append("")
        elif overlap_count:
            lines += [
                "> Hay juegos en común, pero ninguno tiene una oferta renderizable en este reporte.",
                "",
            ]
        gift_rows = normalize_gift_idea_rows(gift_ideas or [])
        if gift_rows:
            has_social_reasons = any(row.get("reason") for row in gift_rows)
            header = (
                "| % | Precio | Juego | Por qué |"
                if has_social_reasons
                else "| % | Precio | Juego |"
            )
            separator = (
                "|---|--------|-------|--------|"
                if has_social_reasons
                else "|---|--------|-------|"
            )
            lines += [
                f"### 🎁 Gift Ideas para {friend_label} ({len(gift_rows)} juegos)",
                "",
                f"> Juegos que {friend_label} quiere, están en oferta, y tú no los tienes.",
                "",
                header,
                separator,
            ]
            for gift_row in gift_rows:
                line = (
                    f"| -{int(gift_row['discount'])}% | {_md_esc(str(gift_row['price_final']))} | {_optional_link(str(gift_row['name']), str(gift_row['appid']))} |"
                )
                if has_social_reasons:
                    reason = str(gift_row.get("reason") or "—")
                    line += f" {_md_esc(reason)} |"
                lines.append(line)
        elif gift_ideas:
            lines += [
                f"### 🎁 Gift Ideas para {friend_label}",
                "",
                "> Hay datos de regalos, pero no hay items concretos para mostrar.",
                "",
            ]
        lines += ["", "---", ""]

    if active_bundles_data:
        bundles_grouped: dict[str, dict] = {}
        for appid, bundle_list in active_bundles_data.items():
            for b in bundle_list:
                key = b["title"]
                if key not in bundles_grouped:
                    bundles_grouped[key] = {**b, "appids": []}
                bundles_grouped[key]["appids"].append(appid)
        lines += [
            "## 📦 Bundles Activos",
            "",
            f"> **{len(bundles_grouped)} bundle(s)** activos con juegos de tu wishlist.",
            "",
        ]
        for bname, binfo in bundles_grouped.items():
            price_str = (
                f"${binfo['price']:.0f} {binfo['currency']}"
                if binfo["price"]
                else "Gratis"
            )
            link = (
                f"[{binfo['store']}]({binfo['url']})"
                if binfo.get("url")
                else binfo["store"]
            )
            lines += [
                f"### 📦 {bname}",
                f"> {price_str} en {link}",
                "",
                "| Juego | Precio Steam |",
                "|-------|-------------|",
            ]
            for aid in binfo["appids"]:
                deal = next((d for d in deals if d["appid"] == aid), None)
                if deal:
                    lines.append(
                        f"| {_link(deal['name'], aid)} | {deal['price_final']} |"
                    )
            lines.append("")
        lines += ["---", ""]

    if hltb_used:
        backlog_display = familia + sin_sf
        if backlog_display:
            lines += [
                "## Backlog en Oferta — Ya los Tienes en HLTB",
                "",
                f"> **{len(backlog_display)} juegos** de tu backlog de HLTB están en oferta en tu wishlist.",
                "",
            ]
            for emoji, subtitle, group in [
                ("🟡", "Confirmado en Familia de Steam", familia),
                ("🟢", "Sin plataforma registrada en HLTB", sin_sf),
            ]:
                if not group:
                    continue
                lines += [
                    f"### {emoji} {subtitle} ({len(group)} juegos)",
                    "",
                    "| % | Precio | HLTB en | Juego |",
                    "|---|--------|---------|-------|",
                ]
                for g in sorted(group, key=lambda x: -x["discount"]):
                    lines.append(format_deal_row(g, show_storefront=True))
                lines.append("")

    if genres:
        genre_deals = filter_by_genres(deals, genres)
        genre_label = ", ".join(genres)
        lines += [
            "---",
            "",
            f"## Genre Deals — {genre_label}",
            "",
            f"> **{len(genre_deals)} juegos** en oferta que coinciden con: _{genre_label}_.",
            "",
        ]
        if genre_deals:
            lines += ["| % | Precio | Precio original | Juego |", "|---|--------|----------------|-------|"]
            for d in genre_deals:
                lines.append(
                    f"| -{d['discount']}% | {d['price_final']} | {d['price_original']} | {_link(d['name'], d['appid'])} |"
                )
        else:
            lines.append(
                "_Ningún juego de tu wishlist en oferta coincide con esos géneros._"
            )
        lines.append("")

    if tags_data:
        tag_groups = group_deals_by_tag(deals, tags_data)
        if tag_groups:
            lines += ["---", "", "## Deals por Tag", ""]
            for tag_name, tag_deals in tag_groups:
                lines += [
                    f"### {tag_name} ({len(tag_deals)} juegos)",
                    "",
                    "| % | Precio | Juego |",
                    "|---|--------|-------|",
                ]
                for d in sorted(tag_deals, key=lambda x: -x["discount"])[:10]:
                    lines.append(
                        f"| -{d['discount']}% | {d['price_final']} | {_link(d['name'], d['appid'])} |"
                    )
                lines.append("")

    lines += [
        "---",
        "",
        "## Quitar de la Wishlist",
        "",
        "> Limpieza: juegos que siguen en tu wishlist pero ya no deberían estar ahí.",
        "",
        "### Ya comprados en Steam (Steam no siempre los quita automáticamente)",
        "",
    ]
    if owned_and_wishlisted:
        lines += ["| AppID | Nombre |", "|-------|--------|"]
        for appid, name in owned_and_wishlisted:
            lines.append(f"| {appid} | {_link(name, appid)} |")
    else:
        lines.append("_Ninguno encontrado._")

    if hltb_used:
        if otras:
            lines += [
                "",
                f"### 🔴 Otra plataforma — GOG, Epic, Amazon… ({len(otras)} juegos)",
                "",
                "> Ya los tienes en otra plataforma según HLTB. Considera quitarlos de la wishlist.",
                "",
                "| % | Precio | HLTB en | Juego |",
                "|---|--------|---------|-------|",
            ]
            for g in sorted(otras, key=lambda x: -x["discount"]):
                lines.append(format_deal_row(g, show_storefront=True))

        if steam_sf:
            lines += [
                "",
                f"### ⚠️ Steam en HLTB — no localizado en familia ({len(steam_sf)} juegos)",
                "",
                "> HLTB dice que los tienes en Steam, pero no aparecen en tu biblioteca familiar.",
                "",
                "| % | Precio | HLTB en | Juego |",
                "|---|--------|---------|-------|",
            ]
            for g in sorted(steam_sf, key=lambda x: -x["discount"]):
                lines.append(format_deal_row(g, show_storefront=True))

        lines += [
            "",
            "### Completados / Retirados en HLTB en oferta en la Wishlist",
            "",
        ]
        if have_on_sale:
            lines += [
                "| % | Precio | Estado | Juego |",
                "|---|--------|--------|-------|",
            ]
            for g in have_on_sale:
                lines.append(
                    f"| -{g['discount']}% | {g['price']} | {g['status']} | {_link(g['steam_name'], g['appid'])} |"
                )
        else:
            lines.append("_Ninguno encontrado._")

    current_year = date.today().year
    cleanup_neg = [
        (d, reviews.get(d["appid"]))
        for d in deals
        if (r := reviews.get(d["appid"])) and r.get("pct", 100) < 50
    ]
    cleanup_always = [
        (d, local_trends.get(d["appid"]))
        for d in deals
        if (t := local_trends.get(d["appid"])) and t.get("times_on_sale", 0) >= 5
    ]
    cleanup_nolinux = [
        d
        for d in deals
        if deck_compat_data.get(d["appid"], 0) == 1
        and (p := protondb_data.get(d["appid"]))
        and p.get("tier") == "borked"
    ]
    cleanup_ac = [
        (d, anticheat_data.get(d["appid"]))
        for d in deals
        if (a := anticheat_data.get(d["appid"]))
        and a.get("status") in ("Denied", "Broken")
    ]
    cleanup_old = [
        (d, d.get("release_year"))
        for d in deals
        if d.get("release_year")
        and (current_year - d["release_year"]) > 8
        and d["discount"] < 70
    ]

    if cleanup_neg:
        cleanup_neg.sort(key=lambda x: x[1]["pct"])
        lines += [
            "",
            f"### 👎 Reviews muy negativas ({len(cleanup_neg)} juegos)",
            "",
            "> Estos juegos tienen reviews negativas, ¿seguro que los quieres?",
            "",
            "| % | Precio | Reseñas | Juego |",
            "|---|--------|---------|-------|",
        ]
        for d, rev in cleanup_neg:
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {rev['desc']} ({rev['pct']}%) | {_link(d['name'], d['appid'])} |"
            )

    if cleanup_always:
        cleanup_always.sort(key=lambda x: -x[1]["times_on_sale"])
        lines += [
            "",
            f"### 🔄 Siempre en oferta ({len(cleanup_always)} juegos)",
            "",
            "> Estos juegos están siempre en oferta, no hay prisa.",
            "",
            "| % | Precio | Veces | Prom. | Juego |",
            "|---|--------|-------|-------|-------|",
        ]
        for d, trend in cleanup_always:
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {trend['times_on_sale']}x | {trend.get('avg_fmt', '?')} | {_link(d['name'], d['appid'])} |"
            )

    if cleanup_nolinux:
        lines += [
            "",
            f"### 🐧 Sin soporte Linux/Deck ({len(cleanup_nolinux)} juegos)",
            "",
            "> ProtonDB Borked + Deck Unsupported.",
            "",
            "| % | Precio | Juego |",
            "|---|--------|-------|",
        ]
        for d in sorted(cleanup_nolinux, key=lambda x: -x["discount"]):
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {_link(d['name'], d['appid'])} |"
            )

    if cleanup_ac:
        lines += [
            "",
            f"### ⛔ Anti-cheat no funciona en Linux ({len(cleanup_ac)} juegos)",
            "",
            "> Anti-cheat status Denied o Broken en Linux.",
            "",
            "| % | Precio | Anti-Cheat | Status | Juego |",
            "|---|--------|------------|--------|-------|",
        ]
        for d, ac in cleanup_ac:
            ac_names = ", ".join(ac.get("anticheats", []))
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {ac_names} | {ac['status']} | {_link(d['name'], d['appid'])} |"
            )

    if cleanup_old:
        cleanup_old.sort(key=lambda x: (x[1], -x[0]["discount"]))
        lines += [
            "",
            f"### 🕰️ Juego viejo, descuento bajo ({len(cleanup_old)} juegos)",
            "",
            "> Juegos de más de 8 años con menos de 70% de descuento. Suelen bajar más.",
            "",
            "| % | Precio | Año | Juego |",
            "|---|--------|-----|-------|",
        ]
        for d, year in cleanup_old:
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {year} | {_link(d['name'], d['appid'])} |"
            )

    lines += ["", "---", ""]

    disappeared = comp.get("disappeared", [])
    if disappeared:
        lines += [
            f"## ❌ Ofertas Terminadas ({len(disappeared)} juegos)",
            "",
            "> Juegos que estaban en oferta el run anterior pero ya no.",
            "",
            "| % | Último precio | Juego |",
            "|---|---------------|-------|",
        ]
        for dd in disappeared:
            lines.append(
                f"| -{dd['discount']}% | {dd['price_final']} | {_link(dd['name'], dd['appid'])} |"
            )
        lines += ["", "---", ""]

    has_itad = bool(historical_lows)
    has_best_prices = bool(current_prices)
    for tier_name, tier_deals in group_by_tier(deals):
        sort_keys = {
            "discount": lambda d: -d["discount"],
            "price": lambda d: d.get("price_raw", 0),
            "reviews": lambda d: -(reviews.get(d["appid"], {}).get("pct", 0)),
            "priority": lambda d: (
                priorities.get(d["appid"], 0) == 0,
                priorities.get(d["appid"], 9999),
            ),
            "score": lambda d: (
                -(
                    compute_value_score(
                        d["discount"],
                        reviews.get(d["appid"], {}).get("pct"),
                        priorities.get(d["appid"], 0),
                        None,
                        deck_compat_data.get(d["appid"], 0),
                        release_year=d.get("release_year"),
                        metacritic_score=d.get("metacritic_score"),
                    )
                )
            ),
        }
        tier_deals.sort(key=sort_keys.get(sort_field, sort_keys["discount"]))

        lines += [
            f"## {tier_name} de Descuento ({len(tier_deals)} juegos)",
            "",
        ]

        has_tags = bool(tags_data)
        has_ach = bool(achievements_data)
        has_trends = any(_is_useful_local_trend(trend) for trend in local_trends.values())
        metric_notes = []
        if has_itad:
            metric_notes.append(
                "Mín. histórico = mejor precio detectado antes en Steam."
            )
        if has_trends:
            metric_notes.append(
                "Historial local = señal útil del precio en tus corridas previas; no es predicción."
            )
        metric_notes.append(
            "Tipo de juego = si se juega solo, cooperativo, PvP o multijugador."
        )
        if metric_notes:
            lines += [f"> {' · '.join(metric_notes)}", ""]

        header = "| | % | Precio | Precio original | Año | Reseñas | Metacritic | Compatibilidad | Tipo de juego"
        sep = "|-|---|--------|-----|-----|---------|----|-----------|----|"
        if has_ach:
            header += " | Logros"
            sep += "|-------"
        if has_tags:
            header += " | Etiquetas"
            sep += "|------"
        if has_itad:
            header += " | Mín. histórico"
            sep += "|------------"
        if has_best_prices:
            header += " | Mejor precio"
            sep += "|--------------"
        if has_trends:
            header += " | Historial local"
            sep += "|-----------"
        header += " | Juego |"
        sep += "|-------|"
        lines += [header, sep]

        for d in tier_deals:
            markers = []
            appid = d["appid"]
            if appid in comp.get("new_deals", set()):
                markers.append("🆕")
            pc = comp.get("price_changes", {}).get(appid)
            if pc:
                markers.append(
                    f"⬇️ -{pc['delta_str']}"
                    if pc["direction"] == "down"
                    else f"⬆️ +{pc['delta_str']}"
                )
            streak = comp.get("deal_streak", {}).get(appid, 0)
            if streak >= 3:
                markers.append(f"🔥 {streak}º run")
            if (
                not markers
                and not comp
                and previous_appids
                and appid not in previous_appids
            ):
                markers.append("🆕")
            new_marker = " ".join(markers)
            prio = _prio_badge(priorities.get(d["appid"], 0))
            name_col = f"{_link(d['name'], d['appid'])}{prio}"

            rev = reviews.get(d["appid"])
            rev_str = f"{rev['desc']} ({rev['pct']}%)" if rev else "—"

            dk = deck_compat_data.get(d["appid"], 0)
            pdb = protondb_data.get(d["appid"])
            ac = anticheat_data.get(d["appid"])
            dk_str = linux_badge(dk, pdb, ac, d.get("linux_native", False))

            mc = d.get("metacritic_score")
            mc_str = str(mc) if mc else "—"
            mp_str = multiplayer_badges(d.get("categories", [])) or "—"

            year_str = str(d.get("release_year", "")) if d.get("release_year") else "—"
            row = f"| {new_marker} | -{d['discount']}% | {d['price_final']} | {d['price_original']} | {year_str} | {rev_str} | {mc_str} | {dk_str} | {mp_str}"
            if has_ach:
                ach = achievements_data.get(d["appid"])
                row += f" | {achievements_badge(ach)}"
            if has_tags:
                top_t = get_top_tags(tags_data, d["appid"], n=3)
                tags_str = " ".join(f"`{t}`" for t in top_t) if top_t else "—"
                pb = players_badge(tags_data.get(d["appid"], {}))
                if pb:
                    tags_str += f" {pb}"
                row += f" | {tags_str}"

            if has_itad:
                low = historical_lows.get(d["appid"])
                low_str = f"${low['price']:.0f} ({low['date']})" if low else "—"
                row += f" | {low_str}"

            if has_best_prices:
                bp = current_prices.get(d["appid"])
                bp_str = (
                    f"${bp['price']:.0f} en [{bp['store']}]({bp['url']})" if bp else "—"
                )
                row += f" | {bp_str}"

            if has_trends:
                trend = local_trends.get(d["appid"])
                row += f" | {format_trend(trend)}" if _is_useful_local_trend(trend) else " | —"

            row += f" | {name_col} |"
            lines.append(row)
        lines += ["", "---", ""]

    return "\n".join(lines)
