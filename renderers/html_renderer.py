from __future__ import annotations

from datetime import date
import json
import re
from urllib.parse import unquote
from urllib.parse import urlsplit

from share_payload import normalize_share_payload

from .common import html_escape
from .social_rows import (
    compare_profile_counts,
    compare_overlap_count,
    is_numeric_appid,
    normalize_gift_idea_groups,
    normalize_gift_idea_rows,
    normalize_overlap_deal_rows,
    normalize_shared_gift_idea_rows,
)


STORE_URL = "https://store.steampowered.com/app/{appid}/"
CAPSULE_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_231x87.jpg"
HEADER_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"

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

_RECOMMENDATION_DIAGNOSTIC_MODE_LABELS = {
    "behavioral": "Behavioral",
    "mixed": "Mixto",
    "score_fallback": "Score fallback",
}
_RECOMMENDATION_DIAGNOSTIC_CONFIDENCE_LABELS = {
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
}


def _html_esc(text: str) -> str:
    return html_escape(text)


def _html_link(name: str, appid: str) -> str:
    return f'<a href="{STORE_URL.format(appid=appid)}" target="_blank" rel="noopener noreferrer">{_html_esc(name)}</a>'


def _html_social_game_cell(row: dict) -> str:
    appid = str(row.get("appid") or "").strip()
    name = str(row.get("name") or "Juego sin nombre").strip()
    if not is_numeric_appid(appid):
        return _html_esc(name)
    capsule = CAPSULE_URL.format(appid=appid)
    store_url = STORE_URL.format(appid=appid)
    safe_name = _html_esc(name)
    return f'''<div class="social-game-cell">
      <a class="social-game-thumb" href="{store_url}" target="_blank" rel="noopener noreferrer" aria-label="Abrir {safe_name} en Steam">
        <img src="{capsule}" alt="" loading="lazy" onerror="this.style.display='none'">
      </a>
      <a href="{store_url}" target="_blank" rel="noopener noreferrer">{safe_name}</a>
    </div>'''


def _html_social_empty(message: str) -> str:
    return f'<p class="section-desc social-empty">{_html_esc(message)}</p>'


def _html_profile_summary(compare_profiles: list[dict] | None) -> str:
    counts = compare_profile_counts(compare_profiles)
    if not counts["total"]:
        return ""
    summary = f"{counts['available']} perfiles disponibles"
    if counts["unavailable"]:
        summary += f" &middot; {counts['unavailable']} no disponibles"
    return summary


def _html_gift_table(gift_rows: list[dict]) -> str:
    has_social_reasons = any(row.get("reason") for row in gift_rows)
    reason_header = "<th>Por qu&eacute;</th>" if has_social_reasons else ""
    rows = ""
    for row in gift_rows:
        reason_cell = ""
        if has_social_reasons:
            reason = str(row.get("reason") or "—")
            reason_cell = (
                f'<td><span class="gift-reason">{_html_esc(reason)}</span></td>'
            )
        rows += (
            f'<tr><td>-{int(row["discount"])}%</td>'
            f'<td>{_html_esc(str(row["price_final"]))}</td>'
            f'<td>{_html_social_game_cell(row)}</td>{reason_cell}</tr>'
        )
    return (
        '<div class="table-wrap"><table class="deals-table"><thead><tr>'
        f'<th>%</th><th>Precio</th><th>Juego</th>{reason_header}'
        f'</tr></thead><tbody>{rows}</tbody></table></div>'
    )


def _html_shared_gift_table(shared_rows: list[dict]) -> str:
    has_social_reasons = any(row.get("reason") for row in shared_rows)
    reason_header = "<th>Por qu&eacute;</th>" if has_social_reasons else ""
    rows = ""
    for row in shared_rows:
        labels = row.get("friend_labels") or []
        wanted_by_count = int(row.get("wanted_by_count") or 0)
        friends = (
            ", ".join(labels) if labels else f"{wanted_by_count or 'Varios'} amigos"
        )
        reason_cell = ""
        if has_social_reasons:
            reason = str(row.get("reason") or "—")
            reason_cell = (
                f'<td><span class="gift-reason">{_html_esc(reason)}</span></td>'
            )
        rows += (
            f'<tr><td>{_html_esc(str(friends))}</td>'
            f'<td>-{int(row["discount"])}%</td>'
            f'<td>{_html_esc(str(row["price_final"]))}</td>'
            f'<td>{_html_social_game_cell(row)}</td>{reason_cell}</tr>'
        )
    return (
        '<div class="table-wrap"><table class="deals-table"><thead><tr>'
        f'<th>Amigos</th><th>%</th><th>Precio</th><th>Juego</th>{reason_header}'
        f'</tr></thead><tbody>{rows}</tbody></table></div>'
    )


def _html_multi_profile_gifts(
    compare_profiles: list[dict] | None,
    gift_ideas_by_friend: list[dict] | None,
    shared_gift_ideas: list[dict] | None,
) -> str:
    sections: list[str] = []
    shared_rows = normalize_shared_gift_idea_rows(shared_gift_ideas)
    if shared_rows:
        sections.append(
            '<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">'
            f'&#127873; Ideas compartidas ({len(shared_rows)} juegos)</h3>'
            '<p class="section-desc">Juegos en oferta que quieren 2+ amigos. '
            'Advisory-only: no cambia ranking ni abre compras.</p>'
            f'{_html_shared_gift_table(shared_rows)}'
        )
    elif shared_gift_ideas:
        sections.append(
            '<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">&#127873; Ideas compartidas</h3>'
            + _html_social_empty(
                "Hay datos de regalos compartidos, pero no hay items concretos para mostrar."
            )
        )

    friend_groups = normalize_gift_idea_groups(gift_ideas_by_friend)
    for group in friend_groups:
        friend_label = str(group["friend_label"])
        safe_label = _html_esc(friend_label)
        rows = group.get("rows") or []
        heading = (
            '<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">'
            f'&#127873; Ideas para {safe_label}</h3>'
        )
        if rows:
            sections.append(
                heading
                + f'<p class="section-desc">Juegos que {safe_label} quiere, '
                + 'est&aacute;n en oferta, y t&uacute; no los tienes.</p>'
                + _html_gift_table(rows)
            )
        else:
            sections.append(
                heading
                + _html_social_empty(
                    f"Hay datos de regalos para {friend_label}, pero no hay items concretos para mostrar."
                )
            )
    if gift_ideas_by_friend and not friend_groups:
        sections.append(
            '<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">&#127873; Ideas por amigo</h3>'
            + _html_social_empty(
                "Hay datos multi-perfil, pero no hay grupos renderizables para mostrar."
            )
        )
    if not sections:
        return ""

    profile_summary = _html_profile_summary(compare_profiles)
    summary_html = (
        f'<p class="section-desc">{profile_summary}</p>' if profile_summary else ""
    )
    return f'''<section style="margin-bottom:1.5rem" data-multi-profile-gift-section>
  <h2>&#128101; Regalos grupales</h2>
  <p class="section-desc">Sugerencias locales y advisory-only para comparar m&uacute;ltiples amigos.</p>
  {summary_html}
  {"".join(sections)}
</section>'''


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


def _html_deck_badge(category: int) -> str:
    labels = {
        3: ("Verificado", "verified"),
        2: ("Jugable", "playable"),
        1: ("No compatible", "unsupported"),
    }
    if category not in labels:
        return '<span class="badge deck-unknown">—</span>'
    text, cls = labels[category]
    return f'<span class="badge deck-{cls}">{text}</span>'


def _html_review_badge(review: dict | None) -> str:
    if not review:
        return '<span class="review-na">—</span>'
    pct = review["pct"]
    cls = "review-good" if pct >= 80 else "review-mixed" if pct >= 60 else "review-bad"
    return f'<span class="{cls}" title="{review["total"]:,} reviews">{_html_esc(review["desc"])} ({pct}%)</span>'


def _html_prio_badge(priority: int) -> str:
    if priority == 0:
        return ""
    cls = "prio-top" if priority <= 10 else "prio-mid" if priority <= 50 else ""
    if not cls:
        return ""
    return f' <span class="{cls}">#{priority}</span>'


def _html_metacritic_badge(score: int | None, *, with_label: bool = False) -> str:
    if score is None:
        return '<span class="review-na">—</span>'
    cls = "mc-good" if score >= 75 else "mc-mixed" if score >= 50 else "mc-bad"
    label = f"Metacritic {score}" if with_label else str(score)
    return f'<span class="badge {cls}" title="Metacritic">{label}</span>'


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

_FREE_WEEKEND_CONFIDENCE_LABELS = {
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
}

_EXTERNAL_OFFER_CONFIDENCE_LABELS = {
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
}
_EXTERNAL_OFFER_STORE_TYPE_LABELS = {
    "official_store": "Tienda oficial",
    "authorized_key_reseller": "Reseller autorizado",
}
_EXTERNAL_OFFER_VISIBLE_STORE_TYPES = {"official_store", "authorized_key_reseller"}
_EXTERNAL_OFFER_VISIBLE_STATES = {"highlight", "review"}
_EXTERNAL_OFFER_BLOCKING_RISKS = {
    "appid_missing",
    "unknown_store",
    "marketplace_keyshop",
    "aggregator_source",
    "low_confidence",
    "checkout_like_url",
    "unsafe_url_scheme",
    "invalid_price",
    "currency_missing",
    "invalid_currency",
}
_EXTERNAL_OFFER_CHECKOUT_RE = re.compile(
    r"(^|[/?#&=._-])(cart|checkout|add-to-cart|addtocart|payment|purchase)s?([/?#&=._-]|$)",
    re.IGNORECASE,
)

_TASTE_PRIORITY_CATEGORY_LABELS = {
    "compra_inmediata": "Prioridad alta para revisar",
    "espera_oferta": "Esperar mejor oferta",
    "riesgo_abandono": "Riesgo de abandono",
    "reemplaza_varios": "Solapa con varios juegos",
    "no_comprar_aun": "No priorizar aún",
}
_EXTERNAL_OFFER_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

_TOP_PICK_RECOMMENDATION_FILTERS = (
    "Comprar ahora",
    "Muy buena oferta",
    "Vale la pena",
    "Solo si ya lo traías en radar",
)


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


def _build_promo_context_html(active_promo_context: dict | None) -> str:
    if not isinstance(active_promo_context, dict):
        return ""
    primary = active_promo_context.get("primary")
    primary_title = ""
    if isinstance(primary, dict):
        primary_title = str(primary.get("title", "") or "").strip()
    primary_title = primary_title or str(active_promo_context.get("sale_name", "") or "").strip()
    if not primary_title:
        return ""

    category_labels = [
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

    categories_html = "".join(
        f'<span class="promo-context-pill">{_html_esc(label)}</span>'
        for label in category_labels
    )
    extra_html = (
        f'<div class="promo-context-extra">También activas: {_html_esc(", ".join(extra_titles[:4]))}</div>'
        if extra_titles
        else ""
    )
    simultaneous_hint = str(active_promo_context.get("simultaneous_hint") or "").strip()
    simultaneous_html = (
        f'<div class="promo-context-hint">Promos simultáneas: {_html_esc(simultaneous_hint)}</div>'
        if simultaneous_hint
        else ""
    )
    decision_hint = str(active_promo_context.get("decision_hint") or "").strip()
    decision_html = (
        f'<div class="promo-context-hint">Lectura sugerida: {_html_esc(decision_hint)}</div>'
        if decision_hint
        else ""
    )
    return f"""<div class="promo-context-card">
    <div><strong>Promo activa:</strong> {_html_esc(primary_title)}</div>
    <div class="promo-context-note">Contexto local: no es predicción ni cambia el score.</div>
    <div class="promo-context-pills">{categories_html}</div>
    {extra_html}
    {simultaneous_html}
    {decision_html}
  </div>"""


def _offer_reasons(item: dict, source_deal: dict | None = None) -> list[str]:
    reasons: list[str] = []
    for source in (item, source_deal or {}):
        raw_reasons = source.get("score_reasons") if isinstance(source, dict) else []
        if not isinstance(raw_reasons, list):
            continue
        for reason in raw_reasons:
            text = str(reason or "").strip()
            if text and text not in reasons:
                reasons.append(text)
    return reasons


def _offer_discount(item: dict, source_deal: dict | None = None) -> int:
    for source in (item, source_deal or {}):
        if not isinstance(source, dict):
            continue
        raw_discount = source.get("discount")
        if raw_discount in (None, ""):
            continue
        try:
            return int(raw_discount)
        except (TypeError, ValueError):
            continue
    return 0


def _offer_current_price(item: dict, source_deal: dict | None = None) -> float:
    for source in (item, source_deal or {}):
        if not isinstance(source, dict):
            continue
        price = str(source.get("price_final") or "")
        if price:
            return _html_price_raw(price)
    return 0.0


def _offer_near_historical_low(
    item: dict,
    *,
    min_hist: dict | None = None,
    source_deal: dict | None = None,
) -> bool:
    if not isinstance(min_hist, dict):
        return False
    try:
        low_price = float(min_hist.get("price") or 0)
    except (TypeError, ValueError):
        return False
    current_price = _offer_current_price(item, source_deal)
    return low_price > 0 and current_price > 0 and current_price <= low_price * 1.05


def _offer_has_active_promo_signal(
    *,
    reasons: list[str],
    discount: int,
    active_promo_context: dict | None,
) -> bool:
    if any("promo" in reason.lower() for reason in reasons):
        return True
    if not isinstance(active_promo_context, dict) or discount < 75:
        return False
    categories = [
        str(category or "") for category in active_promo_context.get("categories", [])
    ]
    return any(
        category in {"major_sale", "fest", "next_fest", "publisher_sale", "themed"}
        for category in categories
    )


def _offer_highlight_label(
    item: dict,
    *,
    min_hist: dict | None = None,
    source_deal: dict | None = None,
    active_promo_context: dict | None = None,
) -> tuple[str, str] | None:
    recommendation = str(item.get("recommendation") or "").strip()
    recommendation_lower = recommendation.lower()
    reasons = _offer_reasons(item, source_deal)
    reasons_lower = " · ".join(reasons).lower()
    discount = _offer_discount(item, source_deal)
    near_min = _offer_near_historical_low(item, min_hist=min_hist, source_deal=source_deal)

    if "esper" in recommendation_lower:
        return "Esperar mejor oferta", "señal conservadora"
    if "solo si" in recommendation_lower:
        return "Solo si ya estaba en tu radar", "señal conservadora"
    if "comprar" in recommendation_lower or "muy buena" in recommendation_lower:
        return "Muy buena oferta", recommendation or "señal del Top Pick"
    if near_min or "mínimo" in reasons_lower or "minimo" in reasons_lower:
        return "Cerca de mínimo histórico", "precio cerca del mínimo conocido"
    if _offer_has_active_promo_signal(
        reasons=reasons,
        discount=discount,
        active_promo_context=active_promo_context,
    ):
        return "Promo destacada", "contexto de promo activa"
    if discount >= 85:
        return "Muy buena oferta", "descuento fuerte"
    if "vale la pena" in recommendation_lower or discount >= 70:
        return "Buena para revisar hoy", recommendation or "descuento alto"
    return None


def _html_offer_highlight(
    item: dict,
    *,
    min_hist: dict | None = None,
    source_deal: dict | None = None,
    active_promo_context: dict | None = None,
) -> str:
    highlight = _offer_highlight_label(
        item,
        min_hist=min_hist,
        source_deal=source_deal,
        active_promo_context=active_promo_context,
    )
    if not highlight:
        return ""
    label, reason = highlight
    reason_html = (
        f'<span class="offer-highlight-reason">{_html_esc(reason)}</span>'
        if reason
        else ""
    )
    return (
        '<div class="offer-highlight" data-offer-highlight>'
        f'<span class="offer-highlight-label">{_html_esc(label)}</span>'
        f'{reason_html}'
        '</div>'
    )


def _free_weekend_confidence_label(confidence: str) -> str:
    key = str(confidence or "").strip().lower()
    return _FREE_WEEKEND_CONFIDENCE_LABELS.get(key, key.title() if key else "Sin dato")


def _free_weekend_items(payload: dict | None, *, limit: int = 8) -> tuple[list[dict], int, int]:
    if not isinstance(payload, dict):
        return [], 0, 0
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    summary = payload.get("summary")
    total = len(items)
    if isinstance(summary, dict):
        try:
            total = max(total, int(summary.get("count") or 0))
        except (TypeError, ValueError):
            total = len(items)
    return items[:limit], total, max(0, total - min(len(items), limit))


def _html_free_weekend_title(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    fallback = f"AppID {appid}" if appid else "Candidato sin título"
    title = str(item.get("title") or item.get("name") or fallback).strip()
    return _html_link(title, appid) if appid.isdigit() else _html_esc(title)


def _html_free_weekend_meta(item: dict) -> str:
    confidence = _free_weekend_confidence_label(str(item.get("confidence") or ""))
    valid_until = str(item.get("valid_until") or "").strip()
    observed_at = str(item.get("observed_at") or "").strip()
    validity = f"Vigente hasta {valid_until}" if valid_until else "Sin vigencia estructurada"
    parts = [f"Confianza {confidence}", validity]
    if observed_at:
        parts.append(f"Observado {observed_at}")
    return _html_esc(" · ".join(parts))


def _html_free_weekend_sources(item: dict) -> str:
    sources = item.get("sources") if isinstance(item, dict) else []
    compact = [str(source or "").strip() for source in sources if str(source or "").strip()]
    return _html_esc(", ".join(compact[:4]) or "Sin fuentes compactas")


def _free_weekend_cross_reasons(item: dict) -> list[str]:
    raw_reasons = item.get("cross_reasons") if isinstance(item, dict) else []
    if isinstance(raw_reasons, list):
        reasons = [str(reason or "").strip() for reason in raw_reasons if str(reason or "").strip()]
        if reasons:
            return reasons[:4]
    reasons: list[str] = []
    cross_signals = item.get("cross_signals") if isinstance(item.get("cross_signals"), dict) else {}
    if cross_signals.get("in_wishlist") is True:
        reasons.append("en tu wishlist")
    owned_or_family = str(cross_signals.get("owned_or_family") or "").strip()
    if owned_or_family == "owned":
        reasons.append("ya en biblioteca")
    elif owned_or_family == "family":
        reasons.append("disponible en biblioteca familiar")
    if cross_signals.get("similar_to_profile") is True:
        reasons.append("similar a tus gustos")
    return reasons[:4]


def _html_free_weekend_cross(item: dict) -> str:
    reasons = _free_weekend_cross_reasons(item)
    if not reasons:
        return ""
    return f'''<div class="free-weekend-item-cross">{"".join(f'<span>{_html_esc(reason)}</span>' for reason in reasons)}</div>'''


def _html_free_weekend_reason(item: dict) -> str:
    reason = str(item.get("reason") or "").strip()
    if reason:
        return _html_esc(reason)
    signals = item.get("signals") if isinstance(item.get("signals"), dict) else {}
    signal_parts = []
    if signals.get("discount_percent") is not None:
        signal_parts.append(f"descuento {signals.get('discount_percent')}%")
    if signals.get("final_price") is not None:
        signal_parts.append(f"precio final {signals.get('final_price')}")
    matched_text = str(signals.get("matched_text") or "").strip()
    if matched_text:
        signal_parts.append(f"texto: {matched_text}")
    return _html_esc(" · ".join(signal_parts) or "Revisar disponibilidad en Steam")


def _html_free_weekend_item(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    data_attr = f' data-free-weekend-appid="{_html_esc(appid)}"' if appid.isdigit() else ""
    return f'''<li class="free-weekend-item"{data_attr}>
  <div class="free-weekend-item-main">
    <strong>{_html_free_weekend_title(item)}</strong>
    <div class="free-weekend-item-meta">{_html_free_weekend_meta(item)}</div>
    <div class="free-weekend-item-reason">{_html_free_weekend_reason(item)}</div>
    {_html_free_weekend_cross(item)}
  </div>
  <span class="free-weekend-item-sources">{_html_free_weekend_sources(item)}</span>
</li>'''


def _html_free_weekend_now(payload: dict | None) -> str:
    items, total_items, hidden_count = _free_weekend_items(payload)
    source_policy = str(payload.get("source_policy") or "").strip() if isinstance(payload, dict) else ""
    policy_html = (
        f'<span class="free-weekend-policy">Política: {_html_esc(source_policy)}</span>'
        if source_policy
        else ""
    )
    if not items:
        body_html = '''<div class="free-weekend-empty">Sin candidatos locales de Free Weekend en el JSON actual. Este bloque no hace fetch live ni cambia score/cache; si falta vigencia o confianza, no asume disponibilidad.</div>'''
    else:
        more_html = (
            f'<div class="free-weekend-more">{hidden_count:,} más en el payload completo</div>'
            if hidden_count
            else ""
        )
        body_html = f'''<ol class="free-weekend-list">{"".join(_html_free_weekend_item(item) for item in items)}</ol>
  {more_html}'''
    count_text = f"{total_items:,} candidato(s)" if total_items else "Sin candidatos locales"
    return f'''<section class="free-weekend-now" data-free-weekend-now-section>
  <div class="free-weekend-head">
    <div>
      <h2>Free Weekend ahora</h2>
      <p class="section-desc"><strong>{_html_esc(count_text)}</strong> desde señales locales/cacheadas. Revisa confianza y vigencia antes de asumir disponibilidad; no cambia score, ranking ni caché de precios.</p>
    </div>
    <span class="free-weekend-head-badge">Solo señales locales</span>
  </div>
  {policy_html}
  {body_html}
</section>'''


def _external_offer_confidence_label(confidence: str) -> str:
    key = str(confidence or "").strip().lower()
    return _EXTERNAL_OFFER_CONFIDENCE_LABELS.get(key, key.title() if key else "Sin dato")


def _external_offer_store_type_label(store_type: str) -> str:
    key = str(store_type or "").strip()
    return _EXTERNAL_OFFER_STORE_TYPE_LABELS.get(key, key.replace("_", " ") or "Tienda")


def _external_offer_visibility_label(visibility: str) -> str:
    return "Destacada" if str(visibility or "").strip() == "highlight" else "Revisión"


def _external_offer_risk_flags(item: dict) -> set[str]:
    flags = item.get("risk_flags") if isinstance(item, dict) else []
    if not isinstance(flags, list):
        return set()
    return {str(flag or "").strip() for flag in flags if str(flag or "").strip()}


def _external_offer_price(item: dict) -> float | None:
    try:
        price = float(item.get("price"))
    except (TypeError, ValueError):
        return None
    return price if price >= 0 else None


def _external_offer_currency(item: dict) -> str:
    currency = str(item.get("currency") or "").strip().upper()
    return currency if _EXTERNAL_OFFER_CURRENCY_RE.match(currency) else ""


def _external_offer_is_visible(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    if str(item.get("visibility") or "").strip() not in _EXTERNAL_OFFER_VISIBLE_STATES:
        return False
    if str(item.get("store_type") or "").strip() not in _EXTERNAL_OFFER_VISIBLE_STORE_TYPES:
        return False
    if _EXTERNAL_OFFER_BLOCKING_RISKS & _external_offer_risk_flags(item):
        return False
    return _external_offer_price(item) is not None and bool(_external_offer_currency(item))


def _external_offer_items(payload: dict | None, *, limit: int = 8) -> tuple[list[dict], int, int]:
    if not isinstance(payload, dict):
        return [], 0, 0
    raw_items = payload.get("items")
    items = [item for item in raw_items if _external_offer_is_visible(item)] if isinstance(raw_items, list) else []
    total = len(items)
    return items[:limit], total, max(0, total - limit)


def _external_offer_safe_url(item: dict) -> str:
    if item.get("link_allowed") is not True:
        return ""
    url = str(item.get("url") or "").strip()
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    checkout_candidate = re.sub(r"[\s_]+", "-", unquote(url).lower())
    if _EXTERNAL_OFFER_CHECKOUT_RE.search(checkout_candidate):
        return ""
    return url


def _html_external_offer_title(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    fallback = f"AppID {appid}" if appid else "Oferta externa"
    name = str(item.get("name") or item.get("steam_name") or fallback).strip()
    return _html_link(name, appid) if appid.isdigit() else _html_esc(name)


def _html_external_offer_meta(item: dict) -> str:
    price = _external_offer_price(item)
    currency = _external_offer_currency(item)
    price_text = f"{currency} {price:.2f}" if price is not None and currency else "Sin precio válido"
    discount = item.get("discount_pct")
    try:
        discount_int = int(discount)
    except (TypeError, ValueError):
        discount_int = 0
    if discount_int:
        price_text += f" · -{discount_int}%"
    store_name = str(item.get("store_name") or item.get("store_id") or "Tienda externa").strip()
    store_type = _external_offer_store_type_label(str(item.get("store_type") or ""))
    return _html_esc(f"{store_name} · {store_type} · {price_text}")


def _html_external_offer_status(item: dict) -> str:
    parts = [
        f"Confianza {_external_offer_confidence_label(str(item.get('confidence') or ''))}",
    ]
    drm = str(item.get("drm") or "").strip()
    region = str(item.get("region") or "").strip()
    source = str(item.get("source") or "").strip()
    expires_at = str(item.get("expires_at") or "").strip()
    if drm:
        parts.append(f"DRM {drm}")
    if region:
        parts.append(f"Región {region}")
    if source:
        parts.append(f"fuente {source}")
    if expires_at:
        parts.append(f"vence {expires_at}")
    return _html_esc(" · ".join(parts))


def _html_external_offer_action(item: dict) -> str:
    url = _external_offer_safe_url(item)
    if not url:
        return '<span class="external-offer-link external-offer-link-disabled">Sin link seguro</span>'
    return f'<a class="external-offer-link" href="{_html_esc(url)}" target="_blank" rel="noopener noreferrer">Ver tienda (sin carrito)</a>'


def _external_offer_chip_labels(item: dict) -> list[str]:
    visibility = str(item.get("visibility") or "").strip()
    store_type = str(item.get("store_type") or "").strip()
    flags = _external_offer_risk_flags(item)
    labels: list[str] = []
    if visibility == "highlight":
        labels.append("Mejor fuera de Steam")
    if store_type == "official_store":
        labels.append("Tienda oficial")
    elif store_type == "authorized_key_reseller":
        labels.append("Tienda autorizada")
    if visibility == "review" or flags & {"drm_unknown", "region_unknown"}:
        labels.append("Revisar DRM/región")
    return list(dict.fromkeys(labels))


def _html_external_offer_chips(item: dict) -> str:
    labels = _external_offer_chip_labels(item)
    if not labels:
        return ""
    chips = "".join(
        f'<span class="external-offer-chip">{_html_esc(label)}</span>'
        for label in labels
    )
    return f'<div class="external-offer-chips">{chips}</div>'


def _html_external_offer_item(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    data_attr = f' data-external-offer-appid="{_html_esc(appid)}"' if appid.isdigit() else ""
    badge = _external_offer_visibility_label(str(item.get("visibility") or ""))
    return f'''<li class="external-offer-item"{data_attr}>
  <div class="external-offer-main">
    <strong>{_html_external_offer_title(item)}</strong>
    <div class="external-offer-meta">{_html_external_offer_meta(item)}</div>
    <div class="external-offer-status">{_html_external_offer_status(item)}</div>
    {_html_external_offer_chips(item)}
    <div class="external-offer-note">Comparativa informativa: no prueba ownership, no abre carrito/checkout ni verifica stock final.</div>
  </div>
  <div class="external-offer-side">
    <span class="external-offer-badge">{_html_esc(badge)}</span>
    {_html_external_offer_action(item)}
  </div>
</li>'''


def _html_external_offers(payload: dict | None) -> str:
    items, total_items, hidden_count = _external_offer_items(payload)
    if not items:
        return ""
    more_html = (
        f'<div class="external-offers-more">{hidden_count:,} más en el payload completo</div>'
        if hidden_count
        else ""
    )
    return f'''<section class="external-offers" data-external-offers-section>
  <div class="external-offers-head">
    <div>
      <h2>Comparativa externa</h2>
      <p class="section-desc"><strong>{total_items:,} oferta(s) externa(s) visibles</strong> desde el JSON local. Comparativa informativa: Steam Tools no compra, no abre carrito ni checkout, no verifica stock final, no prueba ownership y no cambia score, ranking ni wishlist hygiene.</p>
    </div>
    <span class="external-offers-head-badge">Solo tiendas oficiales/autorizadas · sin checkout</span>
  </div>
  <ol class="external-offers-list">{"".join(_html_external_offer_item(item) for item in items)}</ol>
  {more_html}
</section>'''


def _taste_priority_labels(payload: dict) -> dict[str, str]:
    labels = dict(_TASTE_PRIORITY_CATEGORY_LABELS)
    raw_labels = payload.get("category_labels")
    if isinstance(raw_labels, dict):
        labels.update({str(key): str(value) for key, value in raw_labels.items()})
    return labels


def _taste_priority_items(payload: dict | None, *, limit: int = 6) -> tuple[list[dict], int, int, dict[str, str]]:
    if not isinstance(payload, dict):
        return [], 0, 0, {}
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return [], 0, 0, {}
    items = [item for item in raw_items if isinstance(item, dict)]
    total = len(items)
    return items[:limit], total, max(0, total - limit), _taste_priority_labels(payload)


def _html_taste_priority_title(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    fallback = f"AppID {appid}" if appid else "Juego"
    name = str(item.get("name") or item.get("steam_name") or fallback).strip()
    return _html_link(name, appid) if appid.isdigit() else _html_esc(name)


def _html_taste_priority_score(item: dict) -> str:
    try:
        score = float(item.get("taste_priority"))
    except (TypeError, ValueError):
        return "—"
    return f"{score:.1f}"


def _html_taste_priority_category(item: dict, labels: dict[str, str]) -> str:
    category = str(item.get("category") or "").strip()
    label = labels.get(category) or category.replace("_", " ").strip().title() or "Sin categoría"
    return _html_esc(label)


def _html_taste_priority_signals(item: dict) -> str:
    reasons = item.get("reasons") if isinstance(item.get("reasons"), list) else []
    compact_reasons = [str(reason).strip() for reason in reasons if str(reason).strip()][:2]
    clusters = item.get("clusters") if isinstance(item.get("clusters"), list) else []
    cluster_labels = [
        str(cluster.get("label") or cluster.get("id") or "").strip()
        for cluster in clusters
        if isinstance(cluster, dict) and str(cluster.get("label") or cluster.get("id") or "").strip()
    ][:2]
    parts = compact_reasons or cluster_labels
    if not parts:
        return "—"
    return _html_esc(" · ".join(parts))


def _html_taste_priority_item(item: dict, labels: dict[str, str]) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    data_attr = f' data-taste-priority-appid="{_html_esc(appid)}"' if appid.isdigit() else ""
    category = _html_taste_priority_category(item, labels)
    return f'''<li class="taste-priority-item"{data_attr}>
  <div class="taste-priority-main">
    <strong>{_html_taste_priority_title(item)}</strong>
    <div class="taste-priority-meta">{category} · Índice {_html_taste_priority_score(item)}</div>
    <div class="taste-priority-signals">{_html_taste_priority_signals(item)}</div>
    <div class="taste-priority-note">Señal informativa: no cambia score, ranking ni Top Picks.</div>
  </div>
  <span class="taste-priority-badge">Advisory</span>
</li>'''


def _html_taste_priority(payload: dict | None) -> str:
    items, total_items, hidden_count, labels = _taste_priority_items(payload)
    if not items:
        return ""
    more_html = (
        f'<div class="taste-priority-more">{hidden_count:,} más en el payload completo</div>'
        if hidden_count
        else ""
    )
    return f'''<section class="taste-priority" data-taste-priority-section>
  <div class="taste-priority-head">
    <div>
      <h2>Prioridad por gustos</h2>
      <p class="section-desc"><strong>{total_items:,} juego(s)</strong> desde <code>taste_priority</code> local. Advisory-only: no cambia score, ranking, Top Picks, defaults, cache ni fetching.</p>
    </div>
    <span class="taste-priority-head-badge">Sin impacto en ranking</span>
  </div>
  <ol class="taste-priority-list">{"".join(_html_taste_priority_item(item, labels) for item in items)}</ol>
  {more_html}
</section>'''


def _html_top_pick_filter_controls() -> str:
    buttons = [
        '<button type="button" class="top-pick-filter-btn is-active" data-top-pick-filter="all" aria-pressed="true">Todos</button>'
    ]
    buttons.extend(
        f'<button type="button" class="top-pick-filter-btn" data-top-pick-filter="{_html_esc(label)}" aria-pressed="false">{_html_esc(label)}</button>'
        for label in _TOP_PICK_RECOMMENDATION_FILTERS
    )
    return f'''<div class="top-pick-filters" aria-label="Filtrar Top Picks por recomendación">
  <div class="top-pick-filter-head">
    <strong>Filtrar recomendación</strong>
    <span data-top-pick-filter-count></span>
  </div>
  <div class="top-pick-filter-buttons">{"".join(buttons)}</div>
  <div class="top-picks-empty" data-top-picks-empty>No hay Top Picks con esa recomendación.</div>
</div>'''


def _html_multiplayer_badges(categories: list[int]) -> str:
    cats = set(categories)
    parts = []
    if cats & {9, 38, 39}:
        parts.append('<span class="badge mp-coop">Co-op</span>')
    if cats & {36, 37}:
        parts.append('<span class="badge mp-pvp">PvP</span>')
    if not parts and 1 in cats:
        parts.append('<span class="badge mp-multi">Multi</span>')
    if not parts and 2 in cats:
        parts.append('<span class="badge mp-single">Single</span>')
    return " ".join(parts) if parts else '<span class="review-na">—</span>'


def _html_achievements_badge(ach: dict | None) -> str:
    if not ach:
        return '<span class="review-na">—</span>'
    return f'<span class="badge ach-badge" title="Avg global completion: {ach["avg_completion"]:.1f}%">🏆 {ach["count"]}</span>'


def _snapshot_prices(snapshots: list[dict]) -> list[float]:
    prices: list[float] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        try:
            prices.append(float(snapshot["price_raw"]) / 100)
        except (KeyError, TypeError, ValueError):
            continue
    return prices


def _has_price_movement_snapshots(snapshots: list[dict]) -> bool:
    prices = _snapshot_prices(snapshots)
    return len(prices) >= 2 and len(set(prices)) > 1


def _build_sparkline_svg(
    snapshots: list[dict], width: int = 80, height: int = 24
) -> str:
    prices = _snapshot_prices(snapshots)
    if len(prices) < 2 or len(set(prices)) <= 1:
        return ""
    mn, mx = min(prices), max(prices)
    rng = mx - mn if mx != mn else 1
    n = len(prices)
    points = []
    for i, p in enumerate(prices):
        x = round(i / (n - 1) * width, 1)
        y = round(height - (p - mn) / rng * (height - 2) - 1, 1)
        points.append(f"{x},{y}")
    polyline = " ".join(points)
    last_price = prices[-1]
    color = (
        "#6cc644"
        if last_price <= mn
        else "#f0b232"
        if last_price <= mn + rng * 0.3
        else "#c7d5e0"
    )
    lx, ly = points[-1].split(",")
    return (
        f'<svg width="{width}" height="{height}" style="vertical-align:middle" title="Historial: ${mn:.0f}-${mx:.0f}">'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="{lx}" cy="{ly}" r="2" fill="{color}"/></svg>'
    )


def _has_sparkline_history(price_history_games: dict[str, dict], deals: list[dict]) -> bool:
    return any(
        _has_price_movement_snapshots(
            (price_history_games.get(deal["appid"]) or {}).get("snapshots", [])
        )
        for deal in deals
    )


def _html_price_raw(price_str: str) -> float:
    m = re.search(r"[\d,.]+", price_str.replace(",", ""))
    return float(m.group()) if m else 0.0


def _build_share_payload(
    *,
    name: str,
    appid: str,
    price: str,
    original_price: str,
    discount: int,
    min_hist: str,
) -> dict[str, object]:
    """Build data-share-game payloads through the shared Share contract."""
    return normalize_share_payload(
        {
            "name": name,
            "appid": appid,
            "price": price,
            "price_original": original_price,
            "discount": discount,
            "min_hist": min_hist,
            "url": STORE_URL.format(appid=appid),
        }
    )


def _share_payload_attr(payload: dict[str, object]) -> str:
    return _html_esc(json.dumps(payload, ensure_ascii=False))


def _html_share_button(
    payload: dict[str, object],
    *,
    class_name: str = "share-btn-mini",
    title: str = "Compartir",
    style: str = "",
    label: str = "&#128279;",
) -> str:
    style_attr = f' style="{style}"' if style else ""
    return (
        f'<button class="{class_name}" type="button" '
        f'data-share-game="{_share_payload_attr(payload)}" '
        f'onclick="openShareModal(JSON.parse(this.dataset.shareGame))" '
        f'title="{_html_esc(title)}"{style_attr}>{label}</button>'
    )


def _shuffle_candidate_payload(game: dict, *, source_deal: dict | None = None) -> dict | None:
    source_deal = source_deal or {}
    appid = str(game.get("appid") or source_deal.get("appid") or "").strip()
    name = str(game.get("name") or source_deal.get("name") or "").strip()
    if not appid.isdigit() or not name:
        return None
    discount = int(game.get("discount") or source_deal.get("discount") or 0)
    score = game.get("personalized_score")
    if score is None:
        score = game.get("score") if game.get("score") is not None else game.get("base_score")
    recommendation = str(game.get("recommendation") or "").strip()
    reasons = [
        str(reason)
        for reason in (game.get("reasons") or game.get("score_reasons") or [])
        if reason
    ]
    reason = recommendation or (reasons[0] if reasons else "Buen candidato para revisar sin recorrer toda la lista.")
    score_label = "Personal" if game.get("personalized_score") is not None else "Score"
    score_text = f"{score_label} {score}" if score not in (None, "") else f"-{discount}% descuento"
    affinity = game.get("affinity_score")
    if affinity not in (None, "") and reason == "score base del reporte":
        reason = f"Afinidad +{affinity}"
    return {
        "appid": appid,
        "name": name,
        "discount": discount,
        "price_final": str(game.get("price_final") or source_deal.get("price_final") or "—"),
        "price_original": str(game.get("price_original") or source_deal.get("price_original") or ""),
        "score_text": score_text,
        "reason": reason,
        "url": STORE_URL.format(appid=appid),
        "image_url": HEADER_URL.format(appid=appid),
    }


def _shuffle_personalized_items(personalized_recommendations: dict | None) -> list[dict]:
    if not isinstance(personalized_recommendations, dict):
        return []
    return [item for item in personalized_recommendations.get("items", []) if isinstance(item, dict)]


def _build_shuffle_candidates(
    top_picks: list[dict],
    deals: list[dict],
    *,
    personalized_recommendations: dict | None = None,
    limit: int = 12,
) -> list[dict]:
    deals_by_appid = {str(deal.get("appid")): deal for deal in deals if deal.get("appid")}
    personalized_items = _shuffle_personalized_items(personalized_recommendations)
    source_games = personalized_items or top_picks or sorted(
        deals,
        key=lambda deal: (
            -float(deal.get("score") or 0),
            -int(deal.get("discount") or 0),
            int(deal.get("price_raw") or 0),
            str(deal.get("name") or "").lower(),
        ),
    )
    candidates = []
    seen: set[str] = set()
    for game in source_games:
        candidate = _shuffle_candidate_payload(
            game,
            source_deal=deals_by_appid.get(str(game.get("appid") or "")),
        )
        if not candidate or candidate["appid"] in seen:
            continue
        candidates.append(candidate)
        seen.add(candidate["appid"])
        if len(candidates) >= limit:
            break
    return candidates


def _html_shuffle_one_game(candidates: list[dict]) -> str:
    if not candidates:
        return ""
    first = candidates[0]
    action_html = (
        '<button type="button" class="btn-reset shuffle-next-btn" data-shuffle-next>Dame otro</button>'
        if len(candidates) > 1
        else '<span class="shuffle-single-note">Único candidato destacado</span>'
    )
    return f'''<section class="shuffle-one" data-shuffle-one data-shuffle-index="0" data-shuffle-candidates="{_share_payload_attr(candidates)}">
  <div class="shuffle-copy">
    <h2>&#127922; Shuffle 1 juego</h2>
    <p class="section-desc">Si no quieres revisar toda la tabla, empieza por esta recomendación. El botón rota entre candidatos ya calculados del reporte.</p>
  </div>
  <div class="shuffle-card">
    <a class="shuffle-image-link" data-shuffle-link href="{_html_esc(first['url'])}" target="_blank" rel="noopener noreferrer">
      <img class="shuffle-img" data-shuffle-image src="{_html_esc(first['image_url'])}" alt="" loading="lazy" onerror="this.style.display='none'">
    </a>
    <div class="shuffle-info">
      <a class="shuffle-name" data-shuffle-name href="{_html_esc(first['url'])}" target="_blank" rel="noopener noreferrer">{_html_esc(first['name'])}</a>
      <div class="shuffle-meta"><span data-shuffle-score>{_html_esc(first['score_text'])}</span> &middot; <span data-shuffle-discount>-{int(first['discount'])}%</span> &middot; <span data-shuffle-price>{_html_esc(first['price_final'])}</span></div>
      <div class="shuffle-reason" data-shuffle-reason>{_html_esc(first['reason'])}</div>
    </div>
    <div class="shuffle-actions">
      {action_html}
      <span class="shuffle-counter" data-shuffle-counter>1/{len(candidates)}</span>
    </div>
  </div>
</section>'''


def _html_recommended_collection_item(item: dict, *, featured: bool = False) -> str:
    appid = str(item.get("appid") or "").strip()
    name = str(item.get("name") or "Juego desconocido")
    reason = str(item.get("reason") or "Recomendado por las señales del reporte.")
    score = item.get("score")
    try:
        discount = int(item.get("discount") or 0)
    except (TypeError, ValueError):
        discount = 0
    price_final = str(item.get("price_final") or "")
    score_html = (
        f'<span class="collection-score">Score {_html_esc(str(score))}</span>'
        if score not in (None, "")
        else ""
    )
    discount_html = (
        f'<span class="collection-discount">-{discount}%</span>' if discount else ""
    )
    price_html = (
        f'<span class="collection-price">{_html_esc(price_final)}</span>'
        if price_final
        else ""
    )
    meta_html = "".join(part for part in (score_html, discount_html, price_html) if part)
    name_html = _html_link(name, appid) if appid.isdigit() else _html_esc(name)
    item_class = "recommended-collection-item"
    thumb_html = ""
    if featured and appid.isdigit():
        item_class += " collection-item-featured"
        thumb_html = f'''<a class="collection-item-thumb" href="{STORE_URL.format(appid=appid)}" target="_blank" rel="noopener noreferrer" aria-label="Abrir {_html_esc(name)} en Steam">
    <img src="{CAPSULE_URL.format(appid=appid)}" alt="" loading="lazy" onerror="this.style.display='none'">
  </a>'''
    return f'''<li class="{item_class}">
  {thumb_html}
  <div class="collection-item-main">
    <strong>{name_html}</strong>
    <div class="collection-item-reason">{_html_esc(reason)}</div>
  </div>
  <div class="collection-item-meta">{meta_html}</div>
</li>'''


def _recommended_collection_item_key(item: dict) -> str:
    appid = str(item.get("appid") or "").strip()
    if appid:
        return f"appid:{appid}"
    name = str(item.get("name") or "").strip().casefold()
    return f"name:{name}" if name else ""


def _html_recommended_collections(collections: list[dict]) -> str:
    collection_cards = []
    seen_item_keys: set[str] = set()
    for collection in collections or []:
        items = [item for item in collection.get("items", []) if isinstance(item, dict)]
        if not items:
            continue
        visible_items = []
        for item in items:
            item_key = _recommended_collection_item_key(item)
            if item_key and item_key in seen_item_keys:
                continue
            visible_items.append(item)
            if item_key:
                seen_item_keys.add(item_key)
        if not visible_items:
            continue
        collection_id = str(collection.get("id") or "collection")
        title = str(collection.get("title") or collection.get("label") or "Colección")
        description = str(
            collection.get("description") or "Juegos agrupados con señales ya calculadas."
        )
        items_html = "".join(
            _html_recommended_collection_item(item, featured=index == 0)
            for index, item in enumerate(visible_items)
        )
        collection_cards.append(f'''<article class="recommended-collection-card" data-recommended-collection="{_html_esc(collection_id)}">
  <h3>{_html_esc(title)}</h3>
  <p>{_html_esc(description)}</p>
  <ol>{items_html}</ol>
</article>''')
    if not collection_cards:
        return ""
    return f'''<section class="recommended-collections" data-recommended-collections-section>
  <h2>Colecciones recomendadas</h2>
  <p class="section-desc">Secciones curadas con datos ya calculados del reporte: score, descuento, compatibilidad, reviews y géneros/etiquetas disponibles. Si un juego encaja en varias secciones, se muestra solo en la primera tarjeta para reducir repetición.</p>
  <div class="recommended-collections-grid">{"".join(collection_cards)}</div>
</section>'''


def _html_personalized_profile(profile: dict) -> str:
    if not isinstance(profile, dict):
        return ""
    chips = []
    activity_terms = [
        str(term.get("term") or "").strip()
        for term in profile.get("activity_terms", [])
        if isinstance(term, dict) and term.get("term")
    ][:3]
    if activity_terms:
        chips.append(f"Actividad: {', '.join(activity_terms)}")
    chips.extend(_html_activity_summary_chips(profile.get("activity_summary") or {}))
    library_summary = profile.get("library_summary") or {}
    library_terms = [
        str(term.get("term") or "").strip()
        for term in library_summary.get("top_terms", [])
        if isinstance(term, dict) and term.get("term")
    ][:3]
    if library_terms:
        chips.append(f"Biblioteca: {', '.join(library_terms)}")
    total_hours = library_summary.get("total_hltb_hours")
    if total_hours:
        chips.append(f"HLTB: {total_hours}h")
    average_price = library_summary.get("average_price")
    if average_price is not None:
        chips.append(f"Precio prom.: ${average_price}")
    if not chips:
        return ""
    return f'''<div class="personalized-profile">{"".join(f'<span>{_html_esc(chip)}</span>' for chip in chips)}</div>'''


def _html_profile_positive_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _html_activity_summary_chips(summary: dict) -> list[str]:
    if not isinstance(summary, dict):
        return []
    chips: list[str] = []
    recent_hours = _html_profile_positive_number(summary.get("recent_hours"))
    total_hours = _html_profile_positive_number(summary.get("total_hours"))
    if recent_hours or total_hours:
        hours_parts = []
        if recent_hours:
            hours_parts.append(f"{recent_hours:.1f}h recientes")
        if total_hours:
            hours_parts.append(f"{total_hours:.1f}h total")
        chips.append(f"Actividad local: {' · '.join(hours_parts)}")
    for item in summary.get("top_played", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        total = _html_profile_positive_number(item.get("total_hours"))
        if name and total:
            chips.append(f"Más jugado: {name} ({total:.1f}h)")
            break
    return chips


def _html_personalized_item(item: dict, index: int) -> str:
    appid = str(item.get("appid") or "").strip()
    safe_appid = appid if appid.isdigit() else ""
    name = str(item.get("name") or "Juego desconocido")
    title_html = _html_link(name, safe_appid) if safe_appid else _html_esc(name)
    reasons = [str(reason) for reason in item.get("reasons", []) if str(reason).strip()]
    reasons_html = "".join(
        f"<li>{_html_esc(reason)}</li>" for reason in (reasons or ["score base del reporte"])
    )
    meta = []
    personalized_score = item.get("personalized_score")
    if isinstance(personalized_score, (int, float)):
        meta.append(f'<span>Personal {_html_esc(str(personalized_score))}</span>')
    affinity_score = item.get("affinity_score")
    if isinstance(affinity_score, (int, float)):
        meta.append(f'<span>Afinidad +{_html_esc(str(affinity_score))}</span>')
    try:
        discount = int(item.get("discount") or 0)
    except (TypeError, ValueError):
        discount = 0
    if discount:
        meta.append(f"<span>-{discount}%</span>")
    price_final = str(item.get("price_final") or "")
    if price_final:
        meta.append(f"<span>{_html_esc(price_final)}</span>")
    meta_html = f'''<div class="personalized-item-meta">{"".join(meta)}</div>''' if meta else ""
    image_html = ""
    if safe_appid:
        image_html = f'''<a class="personalized-item-thumb" href="{STORE_URL.format(appid=safe_appid)}" target="_blank" rel="noopener noreferrer" aria-label="Abrir {_html_esc(name)} en Steam">
      <img src="{CAPSULE_URL.format(appid=safe_appid)}" alt="" loading="lazy" onerror="this.style.display='none'">
    </a>'''
    data_attr = f' data-personalized-recommendation="{_html_esc(safe_appid)}"' if safe_appid else ""
    return f'''<article class="personalized-item-card"{data_attr}>
  <div class="personalized-item-rank">#{index}</div>
  {image_html}
  <div class="personalized-item-main">
    <h3>{title_html}</h3>
    {meta_html}
    <ul>{reasons_html}</ul>
  </div>
</article>'''


def _html_personalized_recommendations(payload: dict | None) -> str:
    if not isinstance(payload, dict):
        return ""
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    if not items:
        return ""
    cards = "".join(_html_personalized_item(item, index) for index, item in enumerate(items, 1))
    return f'''<section class="personalized-recommendations" data-personalized-recommendations-section>
  <h2>Recomendaciones personalizadas</h2>
  <p class="section-desc">Ranking explicable construido con score del reporte y señales opcionales de actividad, biblioteca y preferencias. No cambia el score global.</p>
  {_html_personalized_profile(payload.get("profile") or {})}
  <div class="personalized-recommendations-grid">{cards}</div>
</section>'''


def _html_recommendation_diagnostics_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    mode = str(payload.get("recommendation_mode") or "").strip()
    if mode not in _RECOMMENDATION_DIAGNOSTIC_MODE_LABELS:
        return None
    return {**payload, "recommendation_mode": mode}


def _html_diagnostic_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _html_diagnostic_percent(value) -> str:
    number = _html_diagnostic_float(value)
    return f"{number * 100:.0f}%" if number is not None else "—"


def _html_diagnostic_confidence(payload: dict) -> str:
    confidence = payload.get("recommendation_confidence")
    confidence = confidence if isinstance(confidence, dict) else {}
    level = str(confidence.get("level") or "").strip().lower()
    label = _RECOMMENDATION_DIAGNOSTIC_CONFIDENCE_LABELS.get(level, level.title())
    score = _html_diagnostic_float(confidence.get("score"))
    if label and score is not None:
        return f"{label} ({score * 100:.0f}%)"
    return label or "—"


def _html_diagnostic_signal_chips(payload: dict) -> str:
    sources = payload.get("signal_sources") if isinstance(payload, dict) else []
    if not isinstance(sources, list):
        return ""
    labels = [str(source).strip().replace("_", " ") for source in sources if str(source).strip()]
    return "".join(
        f'<span>{_html_esc(label)}</span>'
        for label in labels[:5]
    )


def _html_diagnostic_improvement_list(payload: dict) -> str:
    hints = payload.get("improve_recommendations")
    if not isinstance(hints, list):
        return ""
    items = [str(hint).strip() for hint in hints if str(hint).strip()][:4]
    if not items:
        return ""
    return f'''<ul class="recommendation-diagnostics-hints">{"".join(f'<li>{_html_esc(item)}</li>' for item in items)}</ul>'''


def _html_recommendation_diagnostics(payload: dict | None) -> str:
    diagnostics = _html_recommendation_diagnostics_payload(payload)
    if not diagnostics:
        return ""
    mode = diagnostics["recommendation_mode"]
    mode_label = _RECOMMENDATION_DIAGNOSTIC_MODE_LABELS[mode]
    metrics = [
        ("Fuerza conductual", _html_diagnostic_percent(diagnostics.get("behavioral_signal_strength"))),
        ("Dependencia score fallback", _html_diagnostic_percent(diagnostics.get("fallback_dependence"))),
        ("Impacto ranking", str(diagnostics.get("ranking_impact") or "none")),
    ]
    metrics_html = "".join(
        f'''<div class="recommendation-diagnostics-metric"><span>{_html_esc(label)}</span><strong>{_html_esc(value)}</strong></div>'''
        for label, value in metrics
    )
    signals_html = _html_diagnostic_signal_chips(diagnostics)
    signals_block = (
        f'<div class="recommendation-diagnostics-signals"><strong>Fuentes usadas</strong><div>{signals_html}</div></div>'
        if signals_html
        else ""
    )
    return f'''<section class="recommendation-diagnostics" data-recommendation-diagnostics-section>
  <div class="recommendation-diagnostics-head">
    <div>
      <h2>Diagnóstico de recomendaciones</h2>
      <p class="section-desc">Modo <strong>{_html_esc(mode_label)}</strong> · Confianza <strong>{_html_esc(_html_diagnostic_confidence(diagnostics))}</strong>. Advisory-only: no cambia score, ranking, Top Picks, defaults, cache ni fetching.</p>
    </div>
    <span class="recommendation-diagnostics-badge">Sin impacto en ranking</span>
  </div>
  <div class="recommendation-diagnostics-grid">{metrics_html}</div>
  {signals_block}
  {_html_diagnostic_improvement_list(diagnostics)}
</section>'''


def _selection_review_appid(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    return appid if appid.isdigit() else ""


def _selection_review_appid_set(values) -> list[str]:
    if isinstance(values, dict):
        raw_values = values.keys()
    else:
        raw_values = values or []
    appids = {
        str(value).strip()
        for value in raw_values
        if str(value).strip().isdigit()
    }
    return sorted(appids, key=lambda value: int(value))


def _selection_review_texts(values) -> list[str]:
    if not isinstance(values, list):
        return []
    texts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            texts.append(text)
    return texts


def _selection_review_number(value) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _selection_review_format_number(value) -> str:
    number = _selection_review_number(value)
    if number is None:
        return ""
    if abs(number - round(number)) < 0.05:
        return str(int(round(number)))
    return f"{number:.1f}"


def _selection_review_item_payload(item: dict, source_label: str) -> dict | None:
    appid = _selection_review_appid(item)
    if not appid:
        return None
    payload: dict[str, object] = {
        "appid": appid,
        "name": str(item.get("name") or item.get("steam_name") or f"App {appid}"),
        "source_labels": [source_label] if source_label else [],
    }
    for key in ("score", "base_score", "personalized_score", "affinity_score"):
        number = _selection_review_number(item.get(key))
        if number is not None:
            payload[key] = round(number, 1)
    discount = _selection_review_number(item.get("discount"))
    if discount is not None:
        payload["discount"] = int(discount)
    price_final = str(item.get("price_final") or item.get("price") or "").strip()
    if price_final:
        payload["price_final"] = price_final
    reasons = _selection_review_texts(item.get("reasons"))
    reasons.extend(_selection_review_texts(item.get("score_reasons")))
    payload["reasons"] = _selection_review_texts(reasons)
    return payload


def _selection_review_collection_reason(collection: dict, item: dict) -> str:
    label = str(collection.get("label") or collection.get("title") or collection.get("id") or "").strip()
    reason = str(item.get("reason") or "").strip()
    if label and reason:
        return f"{label}: {reason}"
    if label:
        return f"aparece en {label}"
    return reason


def _merge_selection_review_context(
    contexts: dict[str, dict],
    item: dict,
    source_label: str,
    *,
    collection_reason: str = "",
) -> None:
    payload = _selection_review_item_payload(item, source_label)
    if not payload:
        return
    appid = str(payload["appid"])
    current = dict(contexts.get(appid, {}))
    for key, value in payload.items():
        if key in {"reasons", "source_labels"}:
            current[key] = _selection_review_texts([*(current.get(key) or []), *(value or [])])
        elif value not in (None, "", []):
            current[key] = value
    if collection_reason:
        current["collection_reasons"] = _selection_review_texts(
            [*(current.get("collection_reasons") or []), collection_reason]
        )
    contexts[appid] = current


def _selection_review_context_items(
    deals: list[dict],
    top_picks: list[dict],
    recommended_collections: list[dict],
    personalized_recommendations: dict | None,
) -> dict[str, dict]:
    contexts: dict[str, dict] = {}
    for deal in deals or []:
        _merge_selection_review_context(contexts, deal, "Oferta")
    seen_collection_item_keys: set[str] = set()
    for collection in recommended_collections or []:
        if not isinstance(collection, dict):
            continue
        items = collection.get("items") if isinstance(collection.get("items"), list) else []
        for item in (entry for entry in items if isinstance(entry, dict)):
            item_key = _recommended_collection_item_key(item)
            if item_key and item_key in seen_collection_item_keys:
                continue
            if item_key:
                seen_collection_item_keys.add(item_key)
            _merge_selection_review_context(
                contexts,
                item,
                "Colección",
                collection_reason=_selection_review_collection_reason(collection, item),
            )
    for pick in top_picks or []:
        _merge_selection_review_context(contexts, pick, "Top Picks")
    for item in _shuffle_personalized_items(personalized_recommendations):
        _merge_selection_review_context(contexts, item, "Personalizado")
    return contexts


def _selection_review_candidate_meta(item: dict) -> str:
    meta = []
    personalized_score = _selection_review_format_number(item.get("personalized_score"))
    if personalized_score:
        meta.append(f"Personal {personalized_score}")
    base_score = _selection_review_format_number(item.get("score") if item.get("score") is not None else item.get("base_score"))
    if base_score:
        meta.append(f"Score {base_score}")
    affinity = _selection_review_format_number(item.get("affinity_score"))
    if affinity:
        meta.append(f"Afinidad +{affinity}")
    discount = _selection_review_number(item.get("discount"))
    if discount and discount > 0:
        meta.append(f"-{int(discount)}%")
    price_final = str(item.get("price_final") or "").strip()
    if price_final:
        meta.append(price_final)
    return " · ".join(meta)


def _selection_review_candidate_list(
    contexts: dict[str, dict],
    deals: list[dict],
    top_picks: list[dict],
    personalized_recommendations: dict | None,
    *,
    limit: int = 8,
) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()

    def add_candidates(items: list[dict], source_label: str, item_limit: int) -> None:
        for item in (entry for entry in items[:item_limit] if isinstance(entry, dict)):
            appid = _selection_review_appid(item)
            if not appid or appid in seen:
                continue
            context = contexts.get(appid, item)
            candidates.append(
                {
                    "appid": appid,
                    "name": str(context.get("name") or item.get("name") or f"App {appid}"),
                    "source_label": source_label,
                    "meta": _selection_review_candidate_meta(context),
                }
            )
            seen.add(appid)
            if len(candidates) >= limit:
                return

    add_candidates(_shuffle_personalized_items(personalized_recommendations), "Personalizado", 4)
    if len(candidates) < limit:
        add_candidates(top_picks or [], "Top Picks", 6)
    if len(candidates) < limit:
        add_candidates(deals or [], "Ofertas", limit)
    return candidates[:limit]


def _selection_review_payload(
    deals: list[dict],
    top_picks: list[dict],
    recommended_collections: list[dict],
    personalized_recommendations: dict | None,
    owned,
    family_appids,
) -> dict[str, object]:
    contexts = _selection_review_context_items(
        deals,
        top_picks,
        recommended_collections,
        personalized_recommendations,
    )
    return {
        "items": list(contexts.values()),
        "owned_appids": _selection_review_appid_set(owned),
        "family_appids": _selection_review_appid_set(family_appids),
        "candidates": _selection_review_candidate_list(
            contexts,
            deals,
            top_picks,
            personalized_recommendations,
        ),
    }


def _html_selection_review(
    deals: list[dict],
    top_picks: list[dict],
    recommended_collections: list[dict],
    personalized_recommendations: dict | None,
    owned,
    family_appids,
) -> str:
    payload = _selection_review_payload(
        deals,
        top_picks,
        recommended_collections,
        personalized_recommendations,
        owned,
        family_appids,
    )
    candidates = [item for item in payload.get("candidates", []) if isinstance(item, dict)]
    if candidates:
        candidates_html = '<div class="selection-review-candidates">' + "".join(
            f'''<label class="selection-review-candidate">
      <input type="checkbox" data-selection-candidate="{_html_esc(str(candidate.get("appid") or ""))}" data-selection-name="{_html_esc(str(candidate.get("name") or ""))}">
      <span>
        <strong>{_html_esc(str(candidate.get("name") or "Juego"))}</strong>
        <small>{_html_esc(" · ".join(part for part in (str(candidate.get("source_label") or ""), str(candidate.get("meta") or "")) if part))}</small>
      </span>
    </label>'''
            for candidate in candidates
        ) + "</div>"
    else:
        candidates_html = '<div class="selection-review-empty">No hay candidatos marcables; pega AppIDs o URLs de Steam.</div>'
    return f'''<section class="selection-review" data-selection-review data-selection-review-context="{_share_payload_attr(payload)}">
  <div class="selection-review-head">
    <div>
      <h2>Evalúa mi selección</h2>
      <p class="section-desc">Simulación local/offline: marca juegos del reporte o pega AppIDs/URLs para recibir Conservar, Dudar o Quitar.</p>
      <p class="selection-review-policy">Sin red y sin API: usa únicamente datos ya embebidos en este HTML; no abre checkout/carrito, no compra nada y no modifica tu wishlist.</p>
    </div>
    <span class="selection-review-badge">Solo simulación</span>
  </div>
  {candidates_html}
  <label class="selection-review-input-label" for="selection-review-input">AppIDs o URLs de Steam</label>
  <textarea id="selection-review-input" class="selection-review-input" rows="3" data-selection-input placeholder="Pega AppIDs o URLs de Steam, uno por línea"></textarea>
  <div class="selection-review-actions">
    <button type="button" class="btn-reset selection-review-evaluate" data-selection-evaluate>Evaluar selección</button>
    <span class="selection-review-status" data-selection-status>Listo para evaluar con datos del reporte.</span>
  </div>
  <div class="selection-review-results" data-selection-results></div>
</section>'''


def _html_wishlist_hygiene_name(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    fallback_name = f"AppID {appid}" if appid else "Entrada sin appid"
    name = str(
        item.get("name")
        or item.get("steam_name")
        or fallback_name
    ).strip()
    return _html_link(name, appid) if appid.isdigit() else _html_esc(name)


def _html_wishlist_hygiene_is_appid_only(item: dict) -> bool:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    return bool(
        appid
        and (
            item.get("missing_local_name") is True
            or not str(item.get("name") or item.get("steam_name") or "").strip()
        )
    )


def _html_wishlist_hygiene_missing_name_reason() -> str:
    return "No tenemos nombre local para este AppID; revisa si quieres mantenerlo en wishlist"


def _html_wishlist_hygiene_signals(item: dict) -> str:
    signals = item.get("signals") if isinstance(item, dict) else []
    labels = [
        _wishlist_hygiene_signal_label(signal)
        for signal in signals
        if str(signal or "").strip()
    ][:4]
    if not labels:
        labels = ["revisar"]
    return "".join(
        f'<span class="wishlist-hygiene-signal">{_html_esc(label)}</span>'
        for label in labels
    )


def _html_wishlist_hygiene_reasons(item: dict) -> str:
    reasons = item.get("reasons") if isinstance(item, dict) else []
    compact = [str(reason or "").strip() for reason in reasons if str(reason or "").strip()]
    missing_reason = _html_wishlist_hygiene_missing_name_reason()
    if _html_wishlist_hygiene_is_appid_only(item) and not any(
        "No tenemos nombre local" in reason for reason in compact
    ):
        compact.insert(0, missing_reason)
    return _html_esc(" · ".join(compact[:2]) or "revisar manualmente antes de limpiar")


def _html_wishlist_hygiene_steam_link(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    if not appid.isdigit():
        return ""
    safe_appid = _html_esc(appid)
    return (
        f'<a class="wishlist-hygiene-steam-link" href="https://store.steampowered.com/app/{safe_appid}/" '
        'target="_blank" rel="noopener noreferrer">Abrir en Steam</a>'
    )


def _html_wishlist_hygiene_item(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    data_attr = f' data-wishlist-hygiene-item="{_html_esc(appid)}"' if appid.isdigit() else ""
    action_label = "Solo revisión" if item.get("action") == "review" else "Revisar"
    return f'''<li class="wishlist-hygiene-item"{data_attr}>
  <div class="wishlist-hygiene-main">
        <strong>{_html_wishlist_hygiene_name(item)}</strong>
        <div class="wishlist-hygiene-signals">{_html_wishlist_hygiene_signals(item)}</div>
        <div class="wishlist-hygiene-reasons">{_html_wishlist_hygiene_reasons(item)}</div>
        {_html_wishlist_hygiene_steam_link(item)}
  </div>
  <span class="wishlist-hygiene-badge">{_html_esc(action_label)}</span>
</li>'''


def _html_wishlist_hygiene(payload: dict | None) -> str:
    items, total_items, hidden_count = _wishlist_hygiene_items(payload)
    if not items:
        return ""
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    wishlist_total = summary.get("total_wishlist_items") if isinstance(summary, dict) else None
    total_hint = f" de {int(wishlist_total):,} en wishlist" if isinstance(wishlist_total, int) else ""
    more_html = (
        f'<div class="wishlist-hygiene-more">{hidden_count:,} más en el payload completo</div>'
        if hidden_count
        else ""
    )
    return f'''<section class="wishlist-hygiene" data-wishlist-hygiene-section>
  <div class="wishlist-hygiene-head">
    <div>
      <h2>Revisar wishlist</h2>
      <p class="section-desc"><strong>{total_items:,} sugerencias{_html_esc(total_hint)}</strong>. Sugerencias locales advisory-only: no borra ni auto-excluye juegos, y no cambia el score.</p>
    </div>
    <span class="wishlist-hygiene-head-badge">Solo revisión</span>
  </div>
  <ol class="wishlist-hygiene-list">{"".join(_html_wishlist_hygiene_item(item) for item in items)}</ol>
  {more_html}
</section>'''


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


def _smart_alert_digest_sections(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    if payload.get("dry_run") is not True or payload.get("send_ready") is not False:
        return []
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, dict)]


def _html_smart_alert_item_label(item: dict) -> str:
    title = str(item.get("title") or "").strip()
    if title:
        return _html_esc(title)
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    name = str(item.get("name") or item.get("steam_name") or f"AppID {appid}").strip()
    return _html_link(name, appid) if is_numeric_appid(appid) else _html_esc(name)


def _html_smart_alert_item_meta(item: dict) -> str:
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
    return _html_esc(" · ".join(details))


def _html_smart_alert_item(item: dict) -> str:
    meta = _html_smart_alert_item_meta(item)
    return f'''<li class="smart-alert-item">
  <strong>{_html_smart_alert_item_label(item)}</strong>
  {f'<span>{meta}</span>' if meta else ''}
</li>'''


def _html_smart_alert_digest(payload: dict | None) -> str:
    sections = _smart_alert_digest_sections(payload)
    if not sections:
        return ""
    total_count = _safe_int(payload.get("total_count"), 0) if isinstance(payload, dict) else 0
    section_html = []
    for section in sections:
        items = [item for item in section.get("items", []) if isinstance(item, dict)]
        hidden_count = _safe_int(section.get("hidden_count"), 0)
        hidden_html = f'<div class="smart-alert-more">+{hidden_count:,} más en el JSON</div>' if hidden_count else ""
        examples = (
            f'<ol class="smart-alert-items">{"".join(_html_smart_alert_item(item) for item in items[:3])}</ol>'
            if items
            else '<div class="smart-alert-empty">Ver JSON completo</div>'
        )
        section_html.append(f'''<article class="smart-alert-section" data-smart-alert-section="{_html_esc(str(section.get('id') or ''))}">
  <div class="smart-alert-section-head">
    <strong>{_html_esc(str(section.get("label") or section.get("id") or "Sección"))}</strong>
    <span>{_safe_int(section.get("count"), 0):,}</span>
  </div>
  {examples}
  {hidden_html}
</article>''')
    return f'''<section class="smart-alert-digest" data-smart-alert-digest>
  <div class="smart-alert-digest-head">
    <div>
      <h2>Alertas inteligentes — preview local</h2>
      <p class="section-desc"><strong>{total_count:,} señales agrupadas</strong> en digest dry-run. No envía Telegram/Discord, no habilita notificaciones por juego y requiere revisión antes de conectar canales externos.</p>
    </div>
    <span class="smart-alert-digest-badge">Dry-run</span>
  </div>
  <div class="smart-alert-sections">{"".join(section_html)}</div>
</section>'''


def _html_budget_pick_context(pick: dict) -> str:
    recommendation = _html_esc(pick.get("recommendation", ""))
    reasons = _html_esc(" · ".join(pick.get("score_reasons", [])))
    if not recommendation and not reasons:
        return ""
    return (
        f'<div class="pick-recommendation" style="margin-top:.25rem">{recommendation}</div>'
        f'<div class="pick-why">{reasons}</div>'
    )


def _budget_option_payload(pick: dict, *, total_spent: float, remaining: float) -> dict:
    appid = str(pick.get("appid", ""))
    return {
        "appid": appid,
        "name": str(pick.get("name", "")),
        "price_final": str(pick.get("price_final", "—")),
        "discount": int(pick.get("discount") or 0),
        "score": pick.get("score", "—"),
        "recommendation": str(pick.get("recommendation", "")),
        "score_reasons": list(pick.get("score_reasons") or []),
        "swap_total_spent": round(float(total_spent or 0), 2),
        "swap_remaining": round(float(remaining or 0), 2),
        "url": STORE_URL.format(appid=appid),
        "image_url": CAPSULE_URL.format(appid=appid),
        "is_original": True,
    }


def _budget_replacement_payload(replacement: dict) -> dict:
    appid = str(replacement.get("appid", ""))
    return {
        "appid": appid,
        "name": str(replacement.get("name", "")),
        "price_final": str(replacement.get("price_final", "—")),
        "discount": int(replacement.get("discount") or 0),
        "score": replacement.get("score", "—"),
        "recommendation": str(replacement.get("recommendation", "")),
        "score_reasons": list(replacement.get("score_reasons") or []),
        "swap_total_spent": round(
            float(replacement.get("swap_total_spent", 0) or 0), 2
        ),
        "swap_remaining": round(
            float(replacement.get("swap_remaining", 0) or 0), 2
        ),
        "url": STORE_URL.format(appid=appid),
        "image_url": CAPSULE_URL.format(appid=appid),
        "is_original": False,
    }


def _html_budget_reroll_button(pick: dict, *, variant: dict) -> str:
    replacements = pick.get("replacement_candidates") or []
    if not replacements:
        return ""
    options = [
        _budget_option_payload(
            pick,
            total_spent=variant.get("total_spent", 0),
            remaining=variant.get("remaining", 0),
        )
    ]
    options.extend(_budget_replacement_payload(replacement) for replacement in replacements)
    row_key = f'{variant.get("id", "variant")}::{pick.get("appid", "")}'
    return (
        f'<button type="button" class="btn-reset budget-reroll-inline" '
        f'data-budget-row-key="{_html_esc(row_key)}" '
        f'data-budget-options="{_share_payload_attr(options)}" '
        f'title="Prueba otra opción para este lugar sin romper el presupuesto">Reroll</button>'
    )


def _html_budget_variant_controls(variants: list[dict], *, selected_variant: str | None) -> str:
    if not variants:
        return ""
    buttons = []
    for variant in variants:
        label = _html_esc(variant.get("label") or variant.get("id") or "Variante")
        description = _html_esc(variant.get("description", ""))
        button_class = (
            "btn-reset budget-variant-btn is-active"
            if variant.get("id") == selected_variant
            else "btn-reset budget-variant-btn"
        )
        buttons.append(
            f'''<button type="button" class="{button_class}"
  data-budget-variant-btn="{_html_esc(str(variant.get("id") or ""))}"
  data-budget-label="{label}"
  data-budget-budget="{float(variant.get("budget", 0) or 0):.2f}"
  data-budget-games="{int(variant.get("games_count", 0) or 0)}"
  data-budget-total="{float(variant.get("total_spent", 0) or 0):.2f}"
  data-budget-remaining="{float(variant.get("remaining", 0) or 0):.2f}"
  data-budget-savings="{float(variant.get("total_savings", 0) or 0):.2f}"
  title="Cambiar toda la lista manteniendo el mismo presupuesto">
  <strong>{label}</strong>
  <span>{description}</span>
</button>'''
        )
    return f'''<div class="budget-reroll-all">
  <h3 style="font-size:.95rem;margin:0 0 .35rem">&#128257; Rerrollear todos</h3>
  <p class="section-desc">Prueba otra lista con variantes chica, media y grande. Todas respetan el mismo presupuesto.</p>
  <div class="budget-variant-switcher">{"".join(buttons)}</div>
</div>'''


def _budget_variant_rows(variant: dict) -> list[dict]:
    if not isinstance(variant, dict):
        return []
    selected = variant.get("selected")
    if isinstance(selected, list) and selected:
        return selected
    items = variant.get("items")
    if isinstance(items, list) and items:
        return items
    return []


def _html_budget_variant_panel(variant: dict, *, is_selected: bool) -> str:
    budget_rows = ""
    variant_rows = _budget_variant_rows(variant)
    for idx, pick in enumerate(variant_rows, 1):
        pick_data = pick if isinstance(pick, dict) else {}
        appid = str(pick_data.get("appid") or "")
        pick_name = str(pick_data.get("name") or appid or "Juego sin nombre")
        capsule = CAPSULE_URL.format(appid=appid)
        pick_context = _html_budget_pick_context(pick_data)
        reroll_button = _html_budget_reroll_button(pick_data, variant=variant)
        row_key = f'{variant.get("id", "variant")}::{appid}'
        budget_rows += f'''<tr data-budget-row="{_html_esc(row_key)}">
  <td><div class="budget-row-index"><span>{idx}</span>{reroll_button}</div></td>
  <td class="budget-value-score">{_html_esc(str(pick_data.get("score", "—")))}</td>
  <td class="budget-value-discount">-{_html_esc(str(pick_data.get("discount", 0)))}%</td>
  <td class="budget-value-price">{_html_esc(str(pick_data.get("price_final", "—")))}</td>
  <td>
    <div class="game-cell">
      <img class="game-thumb" src="{capsule}" alt="" loading="lazy" onerror="this.style.display='none'">
      <span>
        <a class="budget-value-link" href="{STORE_URL.format(appid=appid)}" target="_blank" rel="noopener noreferrer">{_html_esc(pick_name)}</a>
        <span class="budget-value-context">{pick_context}</span>
        <div class="budget-reroll-preview hidden"></div>
      </span>
    </div>
  </td>
</tr>'''
    panel_class = "budget-variant-panel" if is_selected else "budget-variant-panel hidden"
    summary = (
        f'{variant.get("games_count", 0)} juegos &middot; ${variant.get("total_spent", 0):.0f} gastados '
        f'&middot; ${variant.get("remaining", 0):.0f} restante'
    )
    rows_html = (
        '<div class="table-wrap"><table class="deals-table"><thead><tr><th>#</th><th>Score</th><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>'
        f'{budget_rows}</tbody></table></div>'
        if budget_rows
        else '<p class="section-desc budget-empty-state">Esta variante no trae filas de juegos en el JSON local. Revisa el JSON técnico o regenera el reporte; no se muestra una tabla vacía.</p>'
    )
    return f'''<div class="{panel_class}" data-budget-panel="{_html_esc(str(variant.get("id") or ""))}">
  <p class="section-desc budget-panel-desc">{summary}</p>
  <div class="budget-reroll-help">Usa <strong>Reroll</strong> junto al número para cambiar este juego sin romper el presupuesto.</div>
  {rows_html}
</div>'''


def _html_budget_variant_panels(variants: list[dict], *, selected_variant: str | None) -> str:
    if not variants:
        return ""
    return "".join(
        _html_budget_variant_panel(
            variant, is_selected=variant.get("id") == selected_variant
        )
        for variant in variants
    )


def _html_budget_variants_with_fallback_rows(budget_data: dict) -> list[dict]:
    variants = budget_data.get("variants") or []
    if not variants:
        return [budget_data]

    root_selection = budget_data.get("selected")
    if not isinstance(root_selection, list) or not root_selection:
        return variants

    selected_variant = str(budget_data.get("selected_variant") or "").strip()
    single_variant_without_selection = not selected_variant and len(variants) == 1
    return [
        {**variant, "selected": root_selection}
        if not _budget_variant_rows(variant)
        and (
            (selected_variant and str(variant.get("id") or "").strip() == selected_variant)
            or single_variant_without_selection
        )
        else variant
        for variant in variants
    ]


def _html_recommendation_guide() -> str:
    return """<div class="recommendation-guide">
  <div class="recommendation-guide-title">Cómo leer la recomendación rápida</div>
  <div class="recommendation-guide-grid">
    <div class="recommendation-guide-item">
      <strong>Comprar ahora</strong>
      <span>Muy buena combinación de descuento, señales de calidad y prioridad en tu wishlist.</span>
    </div>
    <div class="recommendation-guide-item">
      <strong>Muy buena oferta</strong>
      <span>Buen balance para revisar pronto: alto valor, aunque no siempre sea prioridad absoluta.</span>
    </div>
    <div class="recommendation-guide-item">
      <strong>Vale la pena</strong>
      <span>Se ve sólido para revisar pronto, aunque no necesariamente sea lo más urgente del run.</span>
    </div>
    <div class="recommendation-guide-item">
      <strong>Solo si ya lo traías en radar</strong>
      <span>Puede seguir siendo buen deal, pero hoy no sobresale tanto frente a otras opciones.</span>
    </div>
  </div>
</div>"""


def _html_min_hist_jump_button(appid: str) -> str:
    return (
        f'<button type="button" class="min-hist-jump-btn" '
        f'onclick="focusTrendCell(\'{_html_esc(appid)}\')" '
        'title="Ir rápido al historial local de este juego">&#10148; Ver historial</button>'
    )


_HTML_CSS = """
:root {
  --bg-primary: #1b2838; --bg-secondary: #2a475e; --bg-card: #16202d;
  --bg-hover: #1a3a5c; --text-primary: #c7d5e0; --text-secondary: #8f98a0;
  --accent-blue: #66c0f4; --accent-green: #6cc644; --accent-yellow: #f0b232;
  --accent-red: #c7322e; --gold: #d4a84b; --border: #2a475e;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg-primary); color: var(--text-primary); line-height: 1.5; padding: 1rem; max-width: 1400px; margin: 0 auto; }
a { color: var(--accent-blue); text-decoration: none; }
a:hover { text-decoration: underline; }
.stats-bar { background: var(--bg-secondary); border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; }
.stats-bar h1 { font-size: 1.4rem; margin-bottom: .3rem; }
.stats-meta { color: var(--text-secondary); font-size: .85rem; margin-bottom: .6rem; }
.sale-badge { color: var(--accent-yellow); font-weight: bold; }
.promo-context-card { background: rgba(240,178,50,.08); border: 1px solid rgba(240,178,50,.28); border-radius: 8px; padding: .6rem .75rem; margin: .6rem 0; font-size: .84rem; }
.promo-context-pills { display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .35rem; }
.promo-context-pill { color: #000; background: var(--accent-yellow); border-radius: 999px; padding: .1rem .5rem; font-size: .76rem; font-weight: 700; }
.promo-context-extra { color: var(--text-secondary); margin-top: .35rem; }
.stats-pills { display: flex; flex-wrap: wrap; gap: .4rem; }
.pill { background: var(--bg-primary); border: 1px solid var(--border); border-radius: 12px; padding: .15rem .6rem; font-size: .8rem; }
.pill-accent { background: var(--accent-blue); color: #000; border-color: var(--accent-blue); font-weight: 600; }
.pill-new { background: var(--accent-green); color: #000; border-color: var(--accent-green); }
.top-picks { margin-bottom: 1.5rem; }
.top-picks h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.section-desc { color: var(--text-secondary); font-size: .8rem; margin-bottom: .8rem; }
.picks-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: .6rem; }
a.pick-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 0; position: relative; overflow: hidden; display: flex; flex-direction: column; text-decoration: none; color: inherit; cursor: pointer; transition: border-color .2s, transform .1s; }
a.pick-card:hover { border-color: var(--accent-blue); transform: translateY(-2px); text-decoration: none; }
.pick-img { width: 100%; aspect-ratio: 460/215; object-fit: cover; display: block; }
.pick-body { padding: .5rem .7rem .7rem; flex: 1; }
.pick-card:hover { border-color: var(--accent-blue); }
.rank-gold { border-color: var(--gold); }
.rank-silver { border-color: #aaa; }
.rank-bronze { border-color: #cd7f32; }
.pick-rank { position: absolute; top: .3rem; right: .5rem; font-size: .75rem; color: var(--text-secondary); font-weight: bold; }
.pick-score { font-size: 1.5rem; font-weight: bold; color: var(--accent-blue); }
.pick-name { font-size: .85rem; margin: .3rem 0; }
.pick-details { font-size: .8rem; }
.pick-discount { color: var(--accent-green); font-weight: bold; margin-right: .5rem; }
.pick-price { color: var(--text-secondary); }
.pick-meta { font-size: .75rem; color: var(--text-secondary); margin-top: .3rem; }
.pick-recommendation { margin-top: .45rem; font-size: .72rem; font-weight: 700; color: var(--accent-green); text-transform: uppercase; letter-spacing: .03em; }
.pick-why { margin-top: .25rem; font-size: .73rem; color: var(--text-secondary); line-height: 1.35; }
.offer-highlight { display: flex; flex-wrap: wrap; align-items: center; gap: .3rem; margin-top: .4rem; font-size: .72rem; line-height: 1.35; }
.offer-highlight-label { border: 1px solid rgba(108,198,68,.4); border-radius: 999px; color: var(--accent-green); background: rgba(108,198,68,.08); padding: .08rem .45rem; font-weight: 800; letter-spacing: .02em; }
.offer-highlight-reason { color: var(--text-secondary); }
.filter-panel { background: var(--bg-secondary); border-radius: 8px; padding: .8rem 1.2rem; margin-bottom: 1.5rem; }
.filter-panel summary { cursor: pointer; font-weight: bold; font-size: 1rem; }
.filter-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem; margin-top: .8rem; }
.filter-group label { display: block; font-size: .8rem; color: var(--text-secondary); margin-bottom: .2rem; }
.filter-group input[type=text], .filter-group select { width: 100%; padding: .3rem .5rem; background: var(--bg-primary); color: var(--text-primary); border: 1px solid var(--border); border-radius: 4px; font-size: .85rem; }
.filter-group input[type=range] { width: 100%; }
.filter-group output { color: var(--accent-blue); font-weight: 600; }
.btn-reset { background: var(--bg-primary); color: var(--text-primary); border: 1px solid var(--border); border-radius: 4px; padding: .3rem .8rem; cursor: pointer; font-size: .85rem; }
.btn-reset:hover { border-color: var(--accent-blue); }
.tier-section { margin-bottom: 1rem; }
.tier-section summary { cursor: pointer; }
.tier-header { font-size: 1.1rem; font-weight: bold; padding: .5rem 0; }
.tier-count { font-weight: normal; color: var(--text-secondary); }
.table-wrap { overflow-x: auto; }
.deals-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.deals-table th { background: var(--bg-secondary); padding: .4rem .5rem; text-align: left; cursor: pointer; white-space: nowrap; user-select: none; border-bottom: 2px solid var(--border); }
.deals-table th:hover { color: var(--accent-blue); }
.sort-arrow { font-size: .65rem; color: var(--text-secondary); margin-left: .2rem; }
.deals-table td { padding: .35rem .5rem; border-bottom: 1px solid var(--border); }
.deals-table tbody tr:hover { background: var(--bg-hover); }
.game-cell { display: flex; align-items: center; gap: .5rem; }
.game-thumb { width: 120px; height: 45px; object-fit: cover; border-radius: 3px; flex-shrink: 0; transition: transform .2s ease; position: relative; z-index: 1; }
.game-thumb:hover { transform: scale(2.5); z-index: 100; box-shadow: 0 4px 16px rgba(0,0,0,.6); border-radius: 4px; }
.badge { display: inline-block; padding: .1rem .4rem; border-radius: 3px; font-size: .75rem; font-weight: 600; }
.deck-verified { background: #1a3d1a; color: var(--accent-green); }
.deck-playable { background: #3d3a1a; color: var(--accent-yellow); }
.deck-unsupported { background: #3d1a1a; color: var(--accent-red); }
.new-badge { background: var(--accent-green); color: #000; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .6; } }
.review-good { color: var(--accent-green); }
.review-mixed { color: var(--accent-yellow); }
.review-bad { color: var(--accent-red); }
.review-na { color: var(--text-secondary); }
.prio-top { background: var(--gold); color: #000; padding: .05rem .3rem; border-radius: 3px; font-size: .7rem; font-weight: bold; }
.prio-mid { color: var(--text-secondary); font-size: .75rem; }
.mc-good { background: #1a3d1a; color: var(--accent-green); }
.mc-mixed { background: #3d3a1a; color: var(--accent-yellow); }
.mc-bad { background: #3d1a1a; color: var(--accent-red); }
.mp-coop { background: #1a3d3d; color: #6cc6c6; }
.mp-pvp { background: #3d1a1a; color: #c66c6c; }
.mp-multi { background: #2a2a3d; color: #8f98c0; }
.mp-single { background: #2a2a3d; color: #8f98c0; }
.ach-badge { background: #3d3a1a; color: var(--accent-yellow); }
.wl-card { display: flex; align-items: center; gap: .6rem; background: var(--bg-card); border: 2px solid var(--accent-green); border-radius: 6px; padding: .6rem; }
.wl-info { flex: 1; }
@media (max-width: 1023px) { .picks-grid { grid-template-columns: repeat(3, 1fr); } .filter-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 767px) { .picks-grid { grid-template-columns: repeat(2, 1fr); } .filter-grid { grid-template-columns: 1fr; } .deals-table { font-size: .75rem; } .game-thumb { width: 80px; height: 30px; } }
.dashboard { background: var(--bg-secondary); border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; }
.dashboard summary { cursor: pointer; font-weight: bold; font-size: 1.1rem; }
.dash-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-top: .8rem; }
.dash-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: .8rem; }
.dash-card h3 { font-size: .9rem; margin-bottom: .5rem; }
.hbar-row { display: flex; align-items: center; gap: .4rem; margin-bottom: .3rem; }
.hbar-label { width: 4.5rem; font-size: .75rem; color: var(--text-secondary); text-align: right; flex-shrink: 0; }
.hbar-track { flex: 1; background: var(--bg-primary); border-radius: 3px; height: 1.1rem; overflow: hidden; }
.hbar-fill { height: 100%; border-radius: 3px; display: flex; align-items: center; padding-left: .3rem; font-size: .65rem; font-weight: 600; color: #000; }
.hbar-value { font-size: .75rem; color: var(--text-secondary); width: 2.5rem; text-align: right; flex-shrink: 0; }
.stacked-bar { display: flex; height: 1.5rem; border-radius: 4px; overflow: hidden; margin-bottom: .4rem; }
.stacked-seg { display: flex; align-items: center; justify-content: center; font-size: .6rem; font-weight: 600; color: #000; }
.stacked-legend { display: flex; flex-wrap: wrap; gap: .4rem; }
.legend-item { display: flex; align-items: center; gap: .2rem; font-size: .7rem; color: var(--text-secondary); }
.legend-dot { width: .5rem; height: .5rem; border-radius: 50%; }
.fin-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: .5rem; }
.fin-item { text-align: center; padding: .4rem; }
.fin-value { font-size: 1.2rem; font-weight: bold; color: var(--accent-blue); }
.fin-savings { color: var(--accent-green); }
.fin-label { font-size: .7rem; color: var(--text-secondary); margin-top: .2rem; }
@media (max-width: 1023px) { .dash-grid { grid-template-columns: 1fr; } .fin-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 767px) { .fin-grid { grid-template-columns: repeat(2, 1fr); } }
.pick-card { position: relative; }
.top-pick-filters { margin: .75rem 0 1rem; padding: .75rem .85rem; border: 1px solid var(--border); border-radius: 8px; background: rgba(12,20,30,.2); }
.top-pick-filter-head { display: flex; align-items: center; justify-content: space-between; gap: .6rem; margin-bottom: .55rem; font-size: .8rem; color: var(--text-secondary); }
.top-pick-filter-head strong { color: var(--text-primary); }
.top-pick-filter-buttons { display: flex; flex-wrap: wrap; gap: .45rem; }
.top-pick-filter-btn { border: 1px solid var(--border); border-radius: 999px; background: var(--bg-primary); color: var(--text-secondary); padding: .32rem .7rem; font-size: .76rem; cursor: pointer; }
.top-pick-filter-btn:hover, .top-pick-filter-btn.is-active { border-color: var(--accent-blue); color: var(--accent-blue); }
.top-pick-filter-btn:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 2px; }
.top-picks-empty { display: none; margin-top: .55rem; color: var(--accent-yellow); font-size: .78rem; }
.top-picks-empty.is-visible { display: block; }
.shuffle-one { margin: 0 0 1.5rem; padding: 1rem; border: 1px solid var(--border); border-radius: 10px; background: linear-gradient(135deg, rgba(102,192,244,.08), rgba(12,20,30,.28)); }
.shuffle-one h2 { font-size: 1.15rem; margin-bottom: .25rem; }
.shuffle-card { display: grid; grid-template-columns: 220px minmax(0, 1fr) auto; gap: .9rem; align-items: center; margin-top: .7rem; }
.shuffle-image-link { display: block; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
.shuffle-img { width: 100%; aspect-ratio: 460/215; object-fit: cover; display: block; }
.shuffle-name { display: inline-block; font-size: 1rem; font-weight: 700; margin-bottom: .25rem; }
.shuffle-meta { color: var(--text-secondary); font-size: .82rem; }
.shuffle-meta [data-shuffle-score] { color: var(--accent-blue); font-weight: 700; }
.shuffle-meta [data-shuffle-discount] { color: var(--accent-green); font-weight: 700; }
.shuffle-reason { margin-top: .35rem; color: var(--accent-yellow); font-size: .8rem; line-height: 1.4; }
.shuffle-actions { display: flex; flex-direction: column; gap: .35rem; align-items: flex-end; }
.shuffle-next-btn:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 2px; }
.shuffle-counter, .shuffle-single-note { color: var(--text-secondary); font-size: .75rem; }
@media (max-width: 767px) { .shuffle-card { grid-template-columns: 1fr; } .shuffle-actions { align-items: stretch; } }
.recommended-collections { margin: 0 0 1.5rem; }
.recommended-collections h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.recommended-collections-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: .75rem; }
.recommended-collection-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: .85rem; }
.recommended-collection-card h3 { font-size: .95rem; color: var(--accent-blue); margin-bottom: .25rem; }
.recommended-collection-card p { color: var(--text-secondary); font-size: .76rem; line-height: 1.4; margin-bottom: .65rem; }
.recommended-collection-card ol { list-style: none; display: flex; flex-direction: column; gap: .55rem; }
.recommended-collection-item { display: flex; align-items: flex-start; justify-content: space-between; gap: .65rem; padding-top: .55rem; border-top: 1px solid rgba(102,192,244,.12); }
.recommended-collection-item:first-child { padding-top: 0; border-top: 0; }
.collection-item-featured { align-items: center; }
.collection-item-thumb { flex: 0 0 82px; display: block; border: 1px solid rgba(102,192,244,.18); border-radius: 6px; overflow: hidden; background: var(--bg-primary); }
.collection-item-thumb img { display: block; width: 100%; aspect-ratio: 231/87; object-fit: cover; }
.collection-item-main { min-width: 0; }
.collection-item-main strong { display: block; font-size: .82rem; line-height: 1.3; }
.collection-item-reason { color: var(--text-secondary); font-size: .74rem; line-height: 1.35; margin-top: .2rem; }
.collection-item-meta { display: flex; flex-direction: column; align-items: flex-end; gap: .18rem; white-space: nowrap; font-size: .73rem; }
.collection-score { color: var(--accent-blue); font-weight: 700; }
.collection-discount { color: var(--accent-green); font-weight: 700; }
.collection-price { color: var(--text-secondary); }
@media (max-width: 767px) { .recommended-collection-item { flex-direction: column; gap: .3rem; } .collection-item-thumb { flex-basis: auto; width: 92px; } .collection-item-meta { align-items: flex-start; flex-direction: row; flex-wrap: wrap; } }
.personalized-recommendations { margin: 0 0 1.5rem; padding: 1rem; border: 1px solid rgba(108,198,68,.24); border-radius: 10px; background: linear-gradient(135deg, rgba(108,198,68,.08), rgba(12,20,30,.25)); }
.personalized-recommendations h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.personalized-profile { display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: .8rem; }
.personalized-profile span { border: 1px solid rgba(108,198,68,.28); border-radius: 999px; color: var(--text-secondary); background: rgba(12,20,30,.28); padding: .16rem .55rem; font-size: .74rem; }
.personalized-recommendations-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: .75rem; }
.personalized-item-card { position: relative; display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: .75rem; align-items: start; background: var(--bg-card); border: 1px solid rgba(108,198,68,.24); border-radius: 8px; padding: .75rem; overflow: hidden; }
.personalized-item-rank { position: absolute; top: .35rem; right: .55rem; color: var(--text-secondary); font-size: .72rem; font-weight: 700; }
.personalized-item-thumb { display: block; border: 1px solid rgba(102,192,244,.18); border-radius: 6px; overflow: hidden; background: var(--bg-primary); }
.personalized-item-thumb img { display: block; width: 100%; aspect-ratio: 231/87; object-fit: cover; }
.personalized-item-main h3 { font-size: .9rem; margin-right: 1.6rem; margin-bottom: .3rem; }
.personalized-item-meta { display: flex; flex-wrap: wrap; gap: .3rem; color: var(--text-secondary); font-size: .72rem; margin-bottom: .35rem; }
.personalized-item-meta span:first-child { color: var(--accent-green); font-weight: 700; }
.personalized-item-main ul { margin-left: 1rem; color: var(--text-secondary); font-size: .75rem; line-height: 1.35; }
@media (max-width: 767px) { .personalized-item-card { grid-template-columns: 1fr; } }
.recommendation-diagnostics { margin: 0 0 1.5rem; padding: 1rem; border: 1px solid rgba(102,192,244,.25); border-radius: 10px; background: linear-gradient(135deg, rgba(102,192,244,.08), rgba(12,20,30,.25)); }
.recommendation-diagnostics-head { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
.recommendation-diagnostics h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.recommendation-diagnostics-badge { white-space: nowrap; border: 1px solid rgba(102,192,244,.36); border-radius: 999px; color: var(--accent-blue); background: rgba(12,20,30,.32); padding: .16rem .55rem; font-size: .74rem; font-weight: 700; }
.recommendation-diagnostics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .55rem; margin-top: .75rem; }
.recommendation-diagnostics-metric { background: var(--bg-card); border: 1px solid rgba(102,192,244,.2); border-radius: 8px; padding: .65rem .75rem; }
.recommendation-diagnostics-metric span, .recommendation-diagnostics-signals strong { display: block; color: var(--text-secondary); font-size: .72rem; line-height: 1.35; }
.recommendation-diagnostics-metric strong { display: block; margin-top: .16rem; color: var(--accent-blue); font-size: .9rem; }
.recommendation-diagnostics-signals { margin-top: .65rem; color: var(--text-secondary); font-size: .74rem; }
.recommendation-diagnostics-signals div { display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .3rem; }
.recommendation-diagnostics-signals span { border: 1px solid rgba(102,192,244,.28); border-radius: 999px; color: var(--accent-blue); background: rgba(12,20,30,.28); padding: .14rem .5rem; font-size: .72rem; }
.recommendation-diagnostics-hints { margin: .65rem 0 0 1rem; color: var(--text-secondary); font-size: .75rem; line-height: 1.4; }
@media (max-width: 767px) { .recommendation-diagnostics-head { flex-direction: column; } .recommendation-diagnostics-badge { align-self: flex-start; } }
.taste-priority { margin: 0 0 1.5rem; padding: 1rem; border: 1px solid rgba(240,178,50,.3); border-radius: 10px; background: linear-gradient(135deg, rgba(240,178,50,.09), rgba(12,20,30,.25)); }
.taste-priority-head { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
.taste-priority h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.taste-priority-head-badge, .taste-priority-badge { white-space: nowrap; border: 1px solid rgba(240,178,50,.45); border-radius: 999px; color: var(--accent-yellow); background: rgba(12,20,30,.32); padding: .16rem .55rem; font-size: .74rem; font-weight: 700; }
.taste-priority-list { list-style: none; display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: .7rem; }
.taste-priority-item { display: flex; justify-content: space-between; gap: .75rem; background: var(--bg-card); border: 1px solid rgba(240,178,50,.24); border-radius: 8px; padding: .75rem; }
.taste-priority-main { min-width: 0; }
.taste-priority-main strong { display: block; font-size: .86rem; line-height: 1.3; margin-bottom: .35rem; }
.taste-priority-meta { color: var(--accent-yellow); font-size: .74rem; line-height: 1.4; margin-bottom: .25rem; }
.taste-priority-signals, .taste-priority-note, .taste-priority-more { color: var(--text-secondary); font-size: .74rem; line-height: 1.4; }
.taste-priority-badge { align-self: flex-start; }
.taste-priority-more { margin-top: .6rem; }
@media (max-width: 767px) { .taste-priority-head, .taste-priority-item { flex-direction: column; } .taste-priority-head-badge { align-self: flex-start; } }
.selection-review { margin: 0 0 1.5rem; padding: 1rem; border: 1px solid rgba(102,192,244,.28); border-radius: 10px; background: linear-gradient(135deg, rgba(102,192,244,.08), rgba(12,20,30,.25)); }
.selection-review-head { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
.selection-review h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.selection-review-policy, .selection-review-empty, .selection-review-status { color: var(--text-secondary); font-size: .75rem; line-height: 1.4; }
.selection-review-policy { margin: -.35rem 0 .7rem; }
.selection-review-badge { white-space: nowrap; border: 1px solid rgba(102,192,244,.4); border-radius: 999px; color: var(--accent-blue); background: rgba(12,20,30,.32); padding: .16rem .55rem; font-size: .74rem; font-weight: 700; }
.selection-review-candidates { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: .55rem; margin-bottom: .75rem; }
.selection-review-candidate { display: flex; gap: .5rem; align-items: flex-start; background: var(--bg-card); border: 1px solid rgba(102,192,244,.2); border-radius: 8px; padding: .65rem; cursor: pointer; }
.selection-review-candidate input { margin-top: .18rem; }
.selection-review-candidate strong, .selection-review-candidate small { display: block; }
.selection-review-candidate strong { font-size: .82rem; line-height: 1.3; }
.selection-review-candidate small { margin-top: .18rem; color: var(--text-secondary); font-size: .72rem; line-height: 1.35; }
.selection-review-input-label { display: block; margin: .25rem 0 .25rem; color: var(--text-secondary); font-size: .76rem; }
.selection-review-input { width: 100%; min-height: 5rem; resize: vertical; background: var(--bg-primary); color: var(--text-primary); border: 1px solid var(--border); border-radius: 6px; padding: .55rem .65rem; font: inherit; font-size: .82rem; }
.selection-review-input:focus-visible, .selection-review-evaluate:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 2px; }
.selection-review-actions { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; margin: .65rem 0; }
.selection-review-summary { display: flex; flex-wrap: wrap; gap: .35rem; margin: .35rem 0 .65rem; }
.selection-review-summary span { border: 1px solid rgba(102,192,244,.28); border-radius: 999px; color: var(--accent-blue); background: rgba(12,20,30,.32); padding: .14rem .5rem; font-size: .73rem; font-weight: 700; }
.selection-review-result-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: .6rem; }
.selection-review-result { display: flex; gap: .65rem; align-items: flex-start; background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: .72rem; }
.selection-review-result-conservar { border-color: rgba(108,198,68,.38); }
.selection-review-result-dudar { border-color: rgba(240,178,50,.38); }
.selection-review-result-quitar { border-color: rgba(199,50,46,.4); }
.selection-review-result-badge { flex: 0 0 auto; border-radius: 999px; padding: .12rem .45rem; font-size: .7rem; font-weight: 800; color: #000; background: var(--accent-yellow); }
.selection-review-result-conservar .selection-review-result-badge { background: var(--accent-green); }
.selection-review-result-quitar .selection-review-result-badge { background: var(--accent-red); color: #fff; }
.selection-review-result-main { min-width: 0; }
.selection-review-result-main strong, .selection-review-result-main span { display: block; }
.selection-review-result-main strong { font-size: .84rem; line-height: 1.3; margin-bottom: .2rem; }
.selection-review-result-meta, .selection-review-result-signals, .selection-review-result-reasons, .selection-review-result-confidence, .selection-review-result-next-step, .selection-review-result-why-group { color: var(--text-secondary); font-size: .74rem; line-height: 1.35; }
.selection-review-result-confidence { color: var(--accent-green); font-weight: 700; }
.selection-review-result-next-step strong, .selection-review-result-why-group strong { color: var(--text-primary); font-size: inherit; margin: 0; }
.selection-review-result-why { display: grid !important; gap: .12rem; margin-top: .2rem; }
@media (max-width: 767px) { .selection-review-head, .selection-review-result { flex-direction: column; } .selection-review-badge { align-self: flex-start; } }
.wishlist-hygiene { margin: 0 0 1.5rem; padding: 1rem; border: 1px solid rgba(240,178,50,.28); border-radius: 10px; background: linear-gradient(135deg, rgba(240,178,50,.08), rgba(12,20,30,.25)); }
.wishlist-hygiene-head { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
.wishlist-hygiene h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.wishlist-hygiene-head-badge, .wishlist-hygiene-badge { white-space: nowrap; border: 1px solid rgba(240,178,50,.4); border-radius: 999px; color: var(--accent-yellow); background: rgba(12,20,30,.32); padding: .16rem .55rem; font-size: .74rem; font-weight: 700; }
.wishlist-hygiene-list { list-style: none; display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: .7rem; }
.wishlist-hygiene-item { display: flex; justify-content: space-between; gap: .75rem; background: var(--bg-card); border: 1px solid rgba(240,178,50,.22); border-radius: 8px; padding: .75rem; }
.wishlist-hygiene-main { min-width: 0; }
.wishlist-hygiene-main strong { display: block; font-size: .86rem; line-height: 1.3; margin-bottom: .35rem; }
.wishlist-hygiene-signals { display: flex; flex-wrap: wrap; gap: .25rem; margin-bottom: .35rem; }
.wishlist-hygiene-signal { border-radius: 999px; color: #000; background: var(--accent-yellow); padding: .1rem .45rem; font-size: .7rem; font-weight: 700; }
.wishlist-hygiene-reasons, .wishlist-hygiene-more { color: var(--text-secondary); font-size: .75rem; line-height: 1.4; }
.wishlist-hygiene-more { margin-top: .6rem; }
@media (max-width: 767px) { .wishlist-hygiene-head, .wishlist-hygiene-item { flex-direction: column; } .wishlist-hygiene-head-badge, .wishlist-hygiene-badge { align-self: flex-start; } }
.free-weekend-now { margin: 0 0 1.5rem; padding: 1rem; border: 1px solid rgba(108,198,68,.28); border-radius: 10px; background: linear-gradient(135deg, rgba(108,198,68,.08), rgba(12,20,30,.25)); }
.free-weekend-head { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
.free-weekend-now h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.free-weekend-head-badge { white-space: nowrap; border: 1px solid rgba(108,198,68,.4); border-radius: 999px; color: var(--accent-green); background: rgba(12,20,30,.32); padding: .16rem .55rem; font-size: .74rem; font-weight: 700; }
.free-weekend-policy, .free-weekend-empty, .free-weekend-more { color: var(--text-secondary); font-size: .75rem; line-height: 1.4; }
.free-weekend-policy { display: block; margin: -.35rem 0 .7rem; }
.free-weekend-list { list-style: none; display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: .7rem; }
.free-weekend-item { display: flex; justify-content: space-between; gap: .75rem; background: var(--bg-card); border: 1px solid rgba(108,198,68,.22); border-radius: 8px; padding: .75rem; }
.free-weekend-item-main { min-width: 0; }
.free-weekend-item-main strong { display: block; font-size: .86rem; line-height: 1.3; margin-bottom: .35rem; }
.free-weekend-item-meta { color: var(--accent-green); font-size: .74rem; line-height: 1.4; margin-bottom: .25rem; }
.free-weekend-item-reason, .free-weekend-item-sources { color: var(--text-secondary); font-size: .74rem; line-height: 1.4; }
.free-weekend-item-cross { display: flex; flex-wrap: wrap; gap: .25rem; margin-top: .4rem; }
.free-weekend-item-cross span { border: 1px solid rgba(108,198,68,.32); border-radius: 999px; color: var(--accent-green); background: rgba(12,20,30,.3); padding: .1rem .45rem; font-size: .7rem; font-weight: 700; }
.free-weekend-item-sources { flex: 0 0 8.5rem; text-align: right; }
.free-weekend-more { margin-top: .6rem; }
@media (max-width: 767px) { .free-weekend-head, .free-weekend-item { flex-direction: column; } .free-weekend-head-badge { align-self: flex-start; } .free-weekend-item-sources { flex-basis: auto; text-align: left; } }
.external-offers { margin: 0 0 1.5rem; padding: 1rem; border: 1px solid rgba(102,192,244,.28); border-radius: 10px; background: linear-gradient(135deg, rgba(102,192,244,.08), rgba(12,20,30,.25)); }
.external-offers-head { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
.external-offers h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.external-offers-head-badge, .external-offer-badge { white-space: nowrap; border: 1px solid rgba(102,192,244,.4); border-radius: 999px; color: var(--accent-blue); background: rgba(12,20,30,.32); padding: .16rem .55rem; font-size: .74rem; font-weight: 700; }
.external-offers-list { list-style: none; display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: .7rem; }
.external-offer-item { display: flex; justify-content: space-between; gap: .75rem; background: var(--bg-card); border: 1px solid rgba(102,192,244,.22); border-radius: 8px; padding: .75rem; }
.external-offer-main { min-width: 0; }
.external-offer-main strong { display: block; font-size: .86rem; line-height: 1.3; margin-bottom: .35rem; }
.external-offer-meta { color: var(--accent-blue); font-size: .74rem; line-height: 1.4; margin-bottom: .25rem; }
.external-offer-status, .external-offer-note, .external-offers-more { color: var(--text-secondary); font-size: .74rem; line-height: 1.4; }
.external-offer-chips { display: flex; flex-wrap: wrap; gap: .28rem; margin: .4rem 0 .1rem; }
.external-offer-chip { border: 1px solid rgba(102,192,244,.28); border-radius: 999px; color: var(--accent-blue); background: rgba(102,192,244,.08); padding: .1rem .42rem; font-size: .7rem; font-weight: 700; }
.external-offer-side { display: flex; flex-direction: column; align-items: flex-end; gap: .45rem; }
.external-offer-link { color: var(--accent-blue); font-size: .74rem; font-weight: 700; text-decoration: none; }
.external-offer-link-disabled { color: var(--text-secondary); font-weight: 600; }
.external-offers-more { margin-top: .6rem; }
@media (max-width: 767px) { .external-offers-head, .external-offer-item { flex-direction: column; } .external-offers-head-badge, .external-offer-side { align-self: flex-start; align-items: flex-start; } }
.smart-alert-digest { margin: 0 0 1.5rem; padding: 1rem; border: 1px solid rgba(102,192,244,.26); border-radius: 10px; background: linear-gradient(135deg, rgba(102,192,244,.08), rgba(12,20,30,.25)); }
.smart-alert-digest-head { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
.smart-alert-digest h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.smart-alert-digest-badge { white-space: nowrap; border: 1px solid rgba(102,192,244,.4); border-radius: 999px; color: var(--accent-blue); background: rgba(12,20,30,.32); padding: .16rem .55rem; font-size: .74rem; font-weight: 700; }
.smart-alert-sections { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: .7rem; }
.smart-alert-section { background: var(--bg-card); border: 1px solid rgba(102,192,244,.22); border-radius: 8px; padding: .75rem; }
.smart-alert-section-head { display: flex; justify-content: space-between; gap: .6rem; margin-bottom: .5rem; }
.smart-alert-section-head strong { color: var(--text-primary); font-size: .86rem; }
.smart-alert-section-head span { color: var(--accent-blue); font-weight: 700; }
.smart-alert-items { list-style: none; display: grid; gap: .45rem; }
.smart-alert-item strong, .smart-alert-item a { display: block; color: var(--text-primary); font-size: .8rem; text-decoration: none; }
.smart-alert-item span, .smart-alert-more, .smart-alert-empty { color: var(--text-secondary); font-size: .74rem; line-height: 1.4; }
.smart-alert-more { margin-top: .45rem; }
@media (max-width: 767px) { .smart-alert-digest-head { flex-direction: column; } .smart-alert-digest-badge { align-self: flex-start; } }
.share-btn-mini { position: absolute; top: .4rem; right: .4rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: 4px; padding: .3rem .5rem; cursor: pointer; font-size: .9rem; opacity: 0.6; transition: opacity .2s; }
.share-btn-mini:hover { opacity: 1; background: var(--accent-blue); }
.share-modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center; }
.share-modal.active { display: flex; }
.share-modal-content { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; max-width: 420px; width: 90%; }
.share-modal h3 { color: var(--accent-blue); margin-bottom: 1rem; font-size: 1.1rem; }
.share-game-info { background: var(--bg-primary); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
.share-game-name { font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem; }
.share-game-price { color: var(--accent-green); font-size: 1.2rem; font-weight: 700; }
.share-game-price span { text-decoration: line-through; color: var(--text-secondary); font-weight: 400; font-size: 0.9rem; }
.share-game-minhist { font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.3rem; }
.share-game-minhist span { color: var(--accent-yellow); }
.share-actions { display: flex; flex-direction: column; gap: 0.6rem; }
.share-btn { padding: 0.6rem 1rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer; text-align: center; }
.share-btn-copy-app { background: var(--accent-blue); color: #000; border: none; }
.share-btn-copy-app:hover { background: #4db8e8; }
.share-btn-copy-steam { background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border); }
.share-btn-copy-steam:hover { border-color: var(--accent-blue); }
.share-btn-open { background: var(--bg-primary); color: var(--text-secondary); border: 1px solid var(--border); }
.share-btn-close { background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border); margin-top: 0.1rem; }
.share-btn-close:hover { border-color: var(--accent-blue); }
.budget-reroll-all { margin: .9rem 0 .85rem; }
.budget-variant-switcher { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .6rem; }
.budget-variant-btn { text-align: left; min-height: 96px; }
.budget-variant-btn.is-active { border-color: var(--accent-blue); box-shadow: 0 0 0 1px rgba(102,192,244,.18) inset; }
.budget-variant-btn strong, .budget-variant-btn span { display: block; }
.budget-variant-btn strong { margin-bottom: .22rem; color: var(--text-primary); font-size: .82rem; }
.budget-variant-btn span { color: var(--text-secondary); font-size: .75rem; line-height: 1.4; }
.budget-variant-panel { margin-top: .8rem; }
.budget-panel-desc { margin-bottom: .45rem; }
.budget-reroll-help { margin-bottom: .7rem; color: var(--text-secondary); font-size: .78rem; line-height: 1.45; }
.budget-row-index { display: flex; align-items: center; gap: .4rem; }
.budget-reroll-inline { padding: .2rem .55rem; font-size: .72rem; }
.budget-value-context { display: block; }
.budget-reroll-preview { margin-top: .28rem; color: var(--accent-yellow); font-size: .73rem; line-height: 1.4; }
.min-hist-cell { display: inline-flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
.min-hist-jump-btn { background: var(--bg-primary); color: var(--accent-blue); border: 1px solid var(--border); border-radius: 999px; padding: .12rem .5rem; font-size: .7rem; cursor: pointer; }
.min-hist-jump-btn:hover { border-color: var(--accent-blue); }
.min-hist-jump-btn:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 2px; }
.trend-focus { outline: 2px solid var(--accent-blue); outline-offset: 2px; background: rgba(102,192,244,.08); border-radius: 6px; transition: background .2s ease; }
.recommendation-guide { margin: 0 0 1rem; padding: .85rem .95rem; border-radius: 8px; border: 1px solid var(--border); background: linear-gradient(180deg, var(--bg-secondary), var(--bg-primary)); }
.recommendation-guide-title { margin-bottom: .6rem; color: var(--accent-blue); font-size: .82rem; font-weight: 700; }
.recommendation-guide-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .6rem; }
.recommendation-guide-item { padding: .65rem .7rem; border-radius: 8px; border: 1px solid rgba(102, 192, 244, 0.18); background: rgba(12, 20, 30, 0.18); }
.recommendation-guide-item strong { display: block; margin-bottom: .25rem; color: var(--text-primary); font-size: .79rem; }
.recommendation-guide-item span { display: block; color: var(--text-secondary); font-size: .76rem; line-height: 1.45; }
"""

_HTML_JS = """
const sortState = {};
const DEAL_FILTER_TABLE_SELECTOR = '[data-deals-filter-table]';
const DEAL_FILTER_ROW_SELECTOR = '[data-deal-row]';
function parseFiniteNumber(value) {
  const number = Number.parseFloat(value);
  return Number.isFinite(number) ? number : null;
}
function setAverageStat(id, label, total, count, formatter) {
  const el = document.getElementById(id);
  if (!el) return;
  if (count <= 0) {
    el.textContent = label + ': sin datos';
    return;
  }
  el.textContent = label + ': ' + formatter(Math.round(total / count));
}
function sortTable(tableId, colIdx, dataType) {
  const table = document.getElementById(tableId);
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const key = tableId + '-' + colIdx;
  sortState[key] = sortState[key] === 'asc' ? 'desc' : 'asc';
  const dir = sortState[key] === 'asc' ? 1 : -1;
  table.querySelectorAll('th .sort-arrow').forEach(s => s.textContent = '\\u25b2\\u25bc');
  const th = table.querySelectorAll('th')[colIdx];
  if (th) th.querySelector('.sort-arrow').textContent = dir === 1 ? '\\u25b2' : '\\u25bc';
  function parseVal(row) {
    const text = row.children[colIdx] ? row.children[colIdx].textContent.trim() : '';
    if (dataType === 'num' || dataType === 'price') return parseFloat(text.replace(/[^0-9.\\-]/g, '')) || 0;
    return text.toLowerCase();
  }
  rows.sort((a, b) => { const va = parseVal(a), vb = parseVal(b); return (typeof va === 'number' ? va - vb : va.localeCompare(vb)) * dir; });
  rows.forEach(r => tbody.appendChild(r));
}
function applyFilters() {
  const discMinRaw = parseFiniteNumber(document.getElementById('f-discount').value);
  const priceMaxRaw = parseFiniteNumber(document.getElementById('f-price-max').value);
  const deck = document.getElementById('f-deck').value;
  const revMinRaw = parseFiniteNumber(document.getElementById('f-reviews').value);
  const discMin = discMinRaw === null ? 0 : discMinRaw;
  const priceMax = priceMaxRaw === null ? 2000 : priceMaxRaw;
  const revMin = revMinRaw === null ? 0 : revMinRaw;
  const search = document.getElementById('f-search').value.toLowerCase();
  const newOnly = document.getElementById('f-new-only').checked;
  let totalV = 0, totalD = 0, totalP = 0, discountCount = 0, priceCount = 0;
  document.querySelectorAll(DEAL_FILTER_ROW_SELECTOR).forEach(row => {
    const d = row.dataset;
    const discount = parseFiniteNumber(d.discount);
    const price = parseFiniteNumber(d.price);
    let show = true;
    if (discount === null || discount < discMin) show = false;
    if (priceMax < 2000 && (price === null || price > priceMax)) show = false;
    if (deck !== 'all' && d.deck !== deck) show = false;
    const rv = parseFiniteNumber(d.review);
    if (rv !== null && rv >= 0 && rv < revMin) show = false;
    if (search && !d.name.includes(search)) show = false;
    if (newOnly && d.new !== '1') show = false;
    row.style.display = show ? '' : 'none';
    if (show) {
      totalV++;
      if (discount !== null) { discountCount++; totalD += discount; }
      if (price !== null) { priceCount++; totalP += price; }
    }
  });
  const sd = document.getElementById('stat-deals'); if (sd) sd.textContent = totalV.toLocaleString() + ' deals visibles';
  setAverageStat('stat-avg-disc', 'Promedio', totalD, discountCount, value => '-' + value + '%');
  setAverageStat('stat-avg-price', 'Precio medio', totalP, priceCount, value => '$' + value);
  document.querySelectorAll('.tier-section').forEach(s => {
    const t = s.querySelector(DEAL_FILTER_TABLE_SELECTOR);
    if (t) { const v = t.querySelectorAll('tbody tr:not([style*=\"display: none\"])').length; const c = s.querySelector('.visible-count'); if (c) c.textContent = v; }
  });
}
function resetFilters() {
  document.getElementById('f-search').value = '';
  document.getElementById('f-discount').value = 50;
  document.getElementById('f-price-max').value = 2000;
  document.getElementById('f-deck').value = 'all';
  document.getElementById('f-reviews').value = 0;
  document.getElementById('f-new-only').checked = false;
  document.querySelectorAll('.filter-group output').forEach(o => { if (o.id === 'f-disc-val') o.textContent = '50%'; else if (o.id === 'f-price-val') o.textContent = 'Sin limite'; else if (o.id === 'f-rev-val') o.textContent = '0%'; });
  applyFilters();
}
function applyTopPickRecommendationFilter(section, selectedRecommendation) {
  const cards = Array.from(section.querySelectorAll('[data-top-pick-card]'));
  const normalized = selectedRecommendation || 'all';
  let visible = 0;
  cards.forEach((card) => {
    const show = normalized === 'all' || card.dataset.recommendation === normalized;
    card.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  section.querySelectorAll('[data-top-pick-filter]').forEach((btn) => {
    const active = btn.dataset.topPickFilter === normalized;
    btn.classList.toggle('is-active', active);
    btn.setAttribute('aria-pressed', String(active));
  });
  const countEl = section.querySelector('[data-top-pick-filter-count]');
  if (countEl) countEl.textContent = `${visible}/${cards.length} visibles`;
  const emptyEl = section.querySelector('[data-top-picks-empty]');
  if (emptyEl) emptyEl.classList.toggle('is-visible', visible === 0);
}
function bindTopPickRecommendationFilters() {
  document.querySelectorAll('[data-top-picks-section]').forEach((section) => {
    if (section.dataset.boundRecommendationFilter === '1') return;
    section.dataset.boundRecommendationFilter = '1';
    section.querySelectorAll('[data-top-pick-filter]').forEach((btn) => {
      btn.addEventListener('click', () => applyTopPickRecommendationFilter(section, btn.dataset.topPickFilter || 'all'));
    });
    applyTopPickRecommendationFilter(section, 'all');
  });
}
function applyShuffleCandidate(section, candidate, index, total) {
  if (!section || !candidate) return;
  section.dataset.shuffleIndex = String(index);
  section.querySelectorAll('[data-shuffle-link]').forEach((link) => { link.href = candidate.url || '#'; });
  const image = section.querySelector('[data-shuffle-image]');
  if (image && candidate.image_url) {
    image.style.display = '';
    image.src = candidate.image_url;
  }
  const name = section.querySelector('[data-shuffle-name]');
  if (name) name.textContent = candidate.name || 'Juego';
  const score = section.querySelector('[data-shuffle-score]');
  if (score) score.textContent = candidate.score_text || 'Sin score';
  const discount = section.querySelector('[data-shuffle-discount]');
  if (discount) discount.textContent = `-${Number(candidate.discount || 0)}%`;
  const price = section.querySelector('[data-shuffle-price]');
  if (price) price.textContent = candidate.price_final || '—';
  const reason = section.querySelector('[data-shuffle-reason]');
  if (reason) reason.textContent = candidate.reason || 'Buen candidato para revisar.';
  const counter = section.querySelector('[data-shuffle-counter]');
  if (counter) counter.textContent = `${index + 1}/${total}`;
}
function bindShuffleOneGame() {
  document.querySelectorAll('[data-shuffle-one]').forEach((section) => {
    if (section.dataset.boundShuffle === '1') return;
    section.dataset.boundShuffle = '1';
    let candidates = [];
    try { candidates = JSON.parse(section.dataset.shuffleCandidates || '[]'); } catch (e) { candidates = []; }
    if (!candidates.length) return;
    const btn = section.querySelector('[data-shuffle-next]');
    if (btn) {
      btn.addEventListener('click', () => {
        const current = Number(section.dataset.shuffleIndex || '0');
        const next = (current + 1) % candidates.length;
        applyShuffleCandidate(section, candidates[next], next, candidates.length);
      });
    }
    applyShuffleCandidate(section, candidates[0], 0, candidates.length);
  });
}
function escapeSelectionHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function selectionReviewNumber(value, fallback = 0) {
  if (value == null || value === '') return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}
function selectionReviewTexts(values) {
  const seen = new Set();
  const result = [];
  (Array.isArray(values) ? values : []).forEach((value) => {
    const text = String(value || '').trim();
    const key = text.toLowerCase();
    if (text && !seen.has(key)) {
      seen.add(key);
      result.push(text);
    }
  });
  return result;
}
function parseSelectionReviewContext(section) {
  try {
    const payload = JSON.parse(section.dataset.selectionReviewContext || '{}');
    return payload && typeof payload === 'object' ? payload : {};
  } catch (error) {
    return {};
  }
}
function selectionReviewContextByAppid(context) {
  const byAppid = {};
  (Array.isArray(context.items) ? context.items : []).forEach((item) => {
    const appid = String(item && (item.appid || item.steam_appid) || '').trim();
    if (/^\\d+$/.test(appid)) byAppid[appid] = item;
  });
  return byAppid;
}
function selectionReviewRecordsFromText(text) {
  const seen = new Set();
  const records = [];
  String(text || '').split(/\\n+/).forEach((line) => {
    const match = String(line).match(/(?:store\\.steampowered\\.com\\/app\\/|\\bapp\\/)?(\\d{1,12})(?!\\d)/i);
    const appid = match ? match[1] : '';
    if (!appid || seen.has(appid)) return;
    seen.add(appid);
    records.push({appid});
  });
  return records;
}
function selectionReviewRecordsFromPanel(panel) {
  const seen = new Set();
  const records = [];
  panel.querySelectorAll('[data-selection-candidate]:checked').forEach((input) => {
    const appid = input.dataset.selectionCandidate || '';
    if (!/^\\d+$/.test(appid) || seen.has(appid)) return;
    seen.add(appid);
    records.push({appid, name: input.dataset.selectionName || ''});
  });
  selectionReviewRecordsFromText(panel.querySelector('[data-selection-input]')?.value || '').forEach((record) => {
    if (!record.appid || seen.has(record.appid)) return;
    seen.add(record.appid);
    records.push(record);
  });
  return records.slice(0, 50);
}
function selectionReviewHasScore(item) {
  return item && (item.base_score != null || item.score != null);
}
function selectionReviewBaseScore(item) {
  if (!item) return 50;
  if (item.base_score != null) return selectionReviewNumber(item.base_score, 50);
  if (item.score != null) return selectionReviewNumber(item.score, 50);
  return 50;
}
function selectionReviewDecision(appid, item, ownedSet, familySet) {
  if (!appid || ownedSet.has(appid) || familySet.has(appid)) return 'quitar';
  const baseScore = selectionReviewBaseScore(item);
  const affinityScore = selectionReviewNumber(item && item.affinity_score, 0);
  if (item && item.personalized_score != null && selectionReviewNumber(item.personalized_score, 0) >= 85) return 'conservar';
  if (affinityScore >= 24 || baseScore >= 85) return 'conservar';
  if (baseScore < 45 && affinityScore <= 0) return 'quitar';
  return 'dudar';
}
function selectionReviewReasons(appid, item, decision, ownedSet, familySet) {
  const reasons = [];
  if (!appid) reasons.push('entrada sin appid válido');
  if (ownedSet.has(appid)) reasons.push('ya está en tu biblioteca');
  if (familySet.has(appid)) reasons.push('ya disponible en biblioteca familiar');
  selectionReviewTexts(item && item.reasons).forEach((reason) => {
    if (reason !== 'score base del reporte') reasons.push(reason);
  });
  const affinityScore = selectionReviewNumber(item && item.affinity_score, 0);
  if (item && item.personalized_score != null && selectionReviewNumber(item.personalized_score, 0) >= 80) {
    reasons.push(`score personal alto: ${selectionReviewNumber(item.personalized_score, 0).toFixed(1)}`);
  } else if (affinityScore > 0) {
    reasons.push(`afinidad positiva: ${affinityScore.toFixed(1)}`);
  }
  const baseScore = selectionReviewBaseScore(item);
  if (baseScore >= 80) reasons.push(`score del reporte fuerte: ${baseScore.toFixed(1)}`);
  const discount = selectionReviewNumber(item && item.discount, 0);
  if (discount >= 70) reasons.push(`descuento fuerte: ${Math.round(discount)}%`);
  selectionReviewTexts(item && item.collection_reasons).forEach((reason) => reasons.push(reason));
  if (!reasons.length) {
    const fallback = {
      conservar: 'señales positivas del reporte',
      dudar: 'no hay señales suficientes para priorizarlo',
      quitar: 'score bajo y sin afinidad visible',
    };
    reasons.push(fallback[decision] || fallback.dudar);
  }
  return selectionReviewTexts(reasons).slice(0, 2);
}
function selectionReviewSignals(appid, item, ownedSet, familySet) {
  const signals = [];
  if (!appid) signals.push('invalid_appid');
  if (ownedSet.has(appid)) signals.push('owned');
  if (familySet.has(appid)) signals.push('family');
  if (item && item.personalized_score != null) signals.push('personalized_score');
  if (item && item.affinity_score != null) signals.push('affinity');
  if (selectionReviewHasScore(item)) signals.push('report_score');
  if (item && item.discount != null) signals.push('discount');
  if (item && item.price_final) signals.push('price');
  if (item && Array.isArray(item.reasons) && item.reasons.length) signals.push('reasons');
  if (item && Array.isArray(item.collection_reasons) && item.collection_reasons.length) signals.push('recommended_collection');
  return selectionReviewTexts(signals).length ? selectionReviewTexts(signals) : ['selection_only'];
}
function selectionReviewConfidence(appid, item, decision, ownedSet, familySet, signals) {
  if (!appid || ownedSet.has(appid) || familySet.has(appid)) return 'high';
  const baseScore = selectionReviewBaseScore(item);
  const affinityScore = selectionReviewNumber(item && item.affinity_score, 0);
  if (decision === 'conservar') {
    if (item && item.personalized_score != null && selectionReviewNumber(item.personalized_score, 0) >= 85) return 'high';
    if (affinityScore >= 24 || baseScore >= 85) return 'high';
    return 'medium';
  }
  if (decision === 'quitar') return selectionReviewHasScore(item) ? 'medium' : 'low';
  if (selectionReviewTexts(signals).join('|') !== 'selection_only' || selectionReviewHasScore(item)) return 'medium';
  return 'low';
}
function selectionReviewNextStep(decision, appid, ownedSet, familySet) {
  if (!appid) return 'Corrige o elimina esta entrada de la selección local.';
  if (ownedSet.has(appid) || familySet.has(appid)) return 'Puedes quitarla de esta selección local; ya aparece disponible.';
  if (decision === 'conservar') return 'Buena candidata para mantener en tu selección local.';
  if (decision === 'quitar') return 'Probablemente puedes quitarla de esta selección local.';
  return 'Revisa si encaja con tu backlog antes de decidir.';
}
function selectionReviewWhyGroups(appid, item, decision, ownedSet, familySet, reasons, signals) {
  const positive = [];
  const caution = [];
  const context = [];
  if (!appid) caution.push('entrada sin appid válido');
  if (ownedSet.has(appid)) caution.push('ya está en tu biblioteca');
  if (familySet.has(appid)) caution.push('ya disponible en biblioteca familiar');
  const target = decision === 'conservar' ? positive : decision === 'quitar' ? caution : context;
  selectionReviewTexts(reasons).forEach((reason) => target.push(reason));
  if (selectionReviewTexts(signals).includes('selection_only')) context.push('solo aparece en tu selección manual');
  if (item && (item.price_final || item.price)) context.push('precio visible en el último reporte');
  return {
    positive: selectionReviewTexts(positive).slice(0, 3),
    caution: selectionReviewTexts(caution).slice(0, 3),
    context: selectionReviewTexts(context).slice(0, 3),
  };
}
function buildLocalSelectionReview(records, context) {
  const byAppid = selectionReviewContextByAppid(context || {});
  const ownedSet = new Set(Array.isArray(context.owned_appids) ? context.owned_appids.map(String) : []);
  const familySet = new Set(Array.isArray(context.family_appids) ? context.family_appids.map(String) : []);
  const seen = new Set();
  let duplicateCount = 0;
  const items = [];
  (Array.isArray(records) ? records : []).forEach((record) => {
    const appid = String(record && record.appid || '').trim();
    if (appid && seen.has(appid)) {
      duplicateCount += 1;
      return;
    }
    if (appid) seen.add(appid);
    const source = {...(byAppid[appid] || {}), ...(record || {})};
    const decision = selectionReviewDecision(appid, source, ownedSet, familySet);
    const signals = selectionReviewSignals(appid, source, ownedSet, familySet);
    const reasons = selectionReviewReasons(appid, source, decision, ownedSet, familySet);
    items.push({
      appid,
      name: source.name || source.steam_name || (appid ? `App ${appid}` : 'Entrada inválida'),
      decision,
      confidence: selectionReviewConfidence(appid, source, decision, ownedSet, familySet, signals),
      next_step: selectionReviewNextStep(decision, appid, ownedSet, familySet),
      base_score: selectionReviewHasScore(source) ? Number(selectionReviewBaseScore(source).toFixed(1)) : null,
      affinity_score: source.affinity_score != null ? Number(selectionReviewNumber(source.affinity_score, 0).toFixed(1)) : null,
      personalized_score: source.personalized_score != null ? Number(selectionReviewNumber(source.personalized_score, 0).toFixed(1)) : null,
      discount: source.discount != null ? Math.round(selectionReviewNumber(source.discount, 0)) : null,
      price_final: source.price_final || source.price || '',
      signals,
      reasons,
      why: selectionReviewWhyGroups(appid, source, decision, ownedSet, familySet, reasons, signals),
    });
  });
  const summary = {total_items: items.length, duplicate_count: duplicateCount, conservar: 0, dudar: 0, quitar: 0};
  items.forEach((item) => { summary[item.decision] = (summary[item.decision] || 0) + 1; });
  return {items, summary, source_signals: ['selection', 'score', 'personalized_recommendations', 'recommended_collections', 'owned_family']};
}
function selectionReviewSignalLabel(signal) {
  const labels = {
    invalid_appid: 'Entrada inválida',
    owned: 'Ya lo tienes',
    family: 'Biblioteca familiar',
    personalized_score: 'Score personal',
    affinity: 'Afinidad',
    report_score: 'Score reporte',
    discount: 'Descuento',
    price: 'Precio',
    reasons: 'Razones',
    recommended_collection: 'Colección recomendada',
    selection_only: 'Solo selección',
  };
  const key = String(signal || '').trim();
  return labels[key] || key.replace(/_/g, ' ');
}
function selectionReviewConfidenceLabel(confidence) {
  const labels = {high: 'Alta', medium: 'Media', low: 'Baja'};
  const key = String(confidence || '').trim().toLowerCase();
  return labels[key] || '';
}
function selectionReviewWhyItems(why, key) {
  if (!why || typeof why !== 'object') return [];
  return Array.isArray(why[key]) ? why[key].map(value => String(value || '').trim()).filter(Boolean).slice(0, 3) : [];
}
function renderSelectionReviewWhyGroup(label, items, key) {
  if (!items.length) return '';
  return `
    <span class="selection-review-result-why-group" data-selection-why="${escapeSelectionHtml(key)}">
      <strong>${escapeSelectionHtml(label)}:</strong> ${escapeSelectionHtml(items.join(' · '))}
    </span>
  `;
}
function renderSelectionReviewItem(item) {
  const source = item && typeof item === 'object' ? item : {};
  const decision = ['conservar', 'dudar', 'quitar'].includes(source.decision) ? source.decision : 'dudar';
  const labels = {conservar: 'Conservar', dudar: 'Dudar', quitar: 'Quitar'};
  const appid = String(source.appid || '').trim();
  const safeAppid = /^\\d+$/.test(appid) ? appid : '';
  const name = source.name || (appid ? `App ${appid}` : 'Entrada inválida');
  const reasons = Array.isArray(source.reasons) && source.reasons.length ? source.reasons.slice(0, 2).join(' · ') : 'Sin razones disponibles';
  const meta = [];
  if (Number.isFinite(Number(source.personalized_score))) meta.push(`Personal ${source.personalized_score}`);
  if (Number.isFinite(Number(source.base_score))) meta.push(`Score ${source.base_score}`);
  if (Number.isFinite(Number(source.affinity_score))) meta.push(`Afinidad +${source.affinity_score}`);
  if (Number.isFinite(Number(source.discount))) meta.push(`-${source.discount}%`);
  if (source.price_final) meta.push(source.price_final);
  const signals = Array.isArray(source.signals) ? source.signals.map(selectionReviewSignalLabel).filter(Boolean).slice(0, 4) : [];
  const confidence = selectionReviewConfidenceLabel(source.confidence);
  const nextStep = String(source.next_step || '').trim();
  const whyGroups = [
    renderSelectionReviewWhyGroup('A favor', selectionReviewWhyItems(source.why, 'positive'), 'positive'),
    renderSelectionReviewWhyGroup('Cuidado', selectionReviewWhyItems(source.why, 'caution'), 'caution'),
    renderSelectionReviewWhyGroup('Contexto', selectionReviewWhyItems(source.why, 'context'), 'context'),
  ].filter(Boolean).join('');
  const nameHtml = safeAppid
    ? `<a href="https://store.steampowered.com/app/${escapeSelectionHtml(safeAppid)}/" target="_blank" rel="noopener noreferrer">${escapeSelectionHtml(name)}</a>`
    : `<span>${escapeSelectionHtml(name)}</span>`;
  return `
    <article class="selection-review-result selection-review-result-${escapeSelectionHtml(decision)}" data-selection-decision="${escapeSelectionHtml(decision)}">
      <div class="selection-review-result-badge">${escapeSelectionHtml(labels[decision])}</div>
      <div class="selection-review-result-main">
        <strong>${nameHtml}</strong>
        ${meta.length ? `<span class="selection-review-result-meta">${escapeSelectionHtml(meta.join(' · '))}</span>` : ''}
        ${confidence ? `<span class="selection-review-result-confidence">Confianza: ${escapeSelectionHtml(confidence)}</span>` : ''}
        ${signals.length ? `<span class="selection-review-result-signals">Señales: ${escapeSelectionHtml(signals.join(' · '))}</span>` : ''}
        <span class="selection-review-result-reasons">${escapeSelectionHtml(reasons)}</span>
        ${nextStep ? `<span class="selection-review-result-next-step"><strong>Siguiente paso:</strong> ${escapeSelectionHtml(nextStep)}</span>` : ''}
        ${whyGroups ? `<span class="selection-review-result-why">${whyGroups}</span>` : ''}
      </div>
    </article>
  `;
}
function renderSelectionReviewResults(panel, review) {
  const resultsEl = panel.querySelector('[data-selection-results]');
  if (!resultsEl) return;
  const items = Array.isArray(review && review.items) ? review.items : [];
  if (!items.length) {
    resultsEl.innerHTML = '<div class="selection-review-empty">No hubo juegos válidos para evaluar.</div>';
    return;
  }
  const summary = review.summary || {};
  const duplicateCopy = summary.duplicate_count ? `<span>Duplicados omitidos: ${escapeSelectionHtml(summary.duplicate_count)}</span>` : '';
  resultsEl.innerHTML = `
    <div class="selection-review-summary">
      <span>Conservar: ${escapeSelectionHtml(summary.conservar || 0)}</span>
      <span>Dudar: ${escapeSelectionHtml(summary.dudar || 0)}</span>
      <span>Quitar: ${escapeSelectionHtml(summary.quitar || 0)}</span>
      ${duplicateCopy}
    </div>
    <div class="selection-review-result-list">${items.map(renderSelectionReviewItem).join('')}</div>
  `;
}
function evaluateSelectionReview(panel, button) {
  const statusEl = panel.querySelector('[data-selection-status]');
  const records = selectionReviewRecordsFromPanel(panel);
  if (!records.length) {
    if (statusEl) statusEl.textContent = 'Marca al menos un juego o pega un AppID/URL.';
    return;
  }
  const originalLabel = button ? button.textContent : '';
  if (button) {
    button.disabled = true;
    button.textContent = 'Evaluando...';
  }
  const review = buildLocalSelectionReview(records, parseSelectionReviewContext(panel));
  renderSelectionReviewResults(panel, review);
  if (statusEl) statusEl.textContent = `Evaluación local lista: ${review.summary.total_items} juego(s).`;
  if (button) {
    button.disabled = false;
    button.textContent = originalLabel || 'Evaluar selección';
  }
}
function bindSelectionReviewActions() {
  document.querySelectorAll('[data-selection-review]').forEach((panel) => {
    if (panel.dataset.boundSelectionReview === '1') return;
    panel.dataset.boundSelectionReview = '1';
    const button = panel.querySelector('[data-selection-evaluate]');
    if (button) button.addEventListener('click', () => evaluateSelectionReview(panel, button));
  });
}
document.addEventListener('DOMContentLoaded', () => {
  applyFilters();
  bindTopPickRecommendationFilters();
  bindShuffleOneGame();
  bindSelectionReviewActions();
  bindShareModalInteractions();
  bindBudgetHtmlInteractions();
});
function copyForSheets() {
  const rows = [];
  document.querySelectorAll(DEAL_FILTER_TABLE_SELECTOR).forEach(table => {
    if (!rows.length) {
      const ths = Array.from(table.querySelectorAll('th')).map(th => th.textContent.replace(/[▲▼]/g,'').trim());
      rows.push(ths.join('\\t'));
    }
    table.querySelectorAll('tbody tr').forEach(tr => {
      if (tr.style.display === 'none') return;
      const cells = Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim().replace(/\\t/g,' '));
      rows.push(cells.join('\\t'));
    });
  });
  const tsv = rows.join('\\n');
  navigator.clipboard.writeText(tsv).then(() => {
    const btn = document.querySelector('[onclick*=copyForSheets]');
    const orig = btn.innerHTML;
    btn.innerHTML = '&#9989; ¡Copiado!';
    setTimeout(() => btn.innerHTML = orig, 2000);
  }).catch(() => alert('No se pudo copiar al clipboard'));
}
let currentShareData = null;
let currentSteamUrl = '';
function parseShareMoney(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  const cleaned = String(value).trim().replace(/[^\\d.,-]/g, '').replace(/,/g, '');
  if (!cleaned) return null;
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}
function formatShareMoney(value) {
  const amount = parseShareMoney(value);
  if (amount == null) return '';
  return '$' + (Math.abs(amount - Math.round(amount)) < 0.001 ? amount.toFixed(0) : amount.toFixed(2));
}
function buildShareGamePayload(game) {
  const source = game && typeof game === 'object' ? game : {};
  const appid = String(source.appid || source.steam_appid || '').trim();
  if (!appid) return null;
  const name = source.name || source.steam_name || 'Juego desconocido';
  const currentPrice = parseShareMoney(source.price ?? source.price_final);
  const originalPrice = parseShareMoney(source.price_original ?? source.original_price) ?? currentPrice;
  const discount = Number(source.discount || 0) || 0;
  const minHist = parseShareMoney(source.min_hist ?? source.historical_low ?? source.min_historical);
  const steamUrl = 'https://store.steampowered.com/app/' + appid + '/';
  const priceLabel = formatShareMoney(currentPrice);
  const originalLabel = formatShareMoney(originalPrice != null ? originalPrice : currentPrice);
  const minHistLabel = formatShareMoney(minHist);
  return {
    name,
    discount,
    steamUrl,
    displayPrice: priceLabel ? (priceLabel + ' MXN') : 'Precio no disponible',
    displayOriginalPrice: originalPrice != null && currentPrice != null && originalPrice > currentPrice ? (originalLabel + ' MXN') : '',
    displayMinHist: minHistLabel ? (minHistLabel + ' MXN') : '',
    payload: {
      v: Number(source.v || 1) || 1,
      name,
      steam_name: source.steam_name || name,
      appid,
      steam_appid: appid,
      price: priceLabel || '',
      price_final: priceLabel || '',
      price_original: originalLabel || priceLabel || '',
      original_price: originalLabel || priceLabel || '',
      discount,
      min_hist: minHistLabel || '',
      min_historical: minHistLabel || '',
      historical_low: minHistLabel || '',
      steam_url: steamUrl,
      url: steamUrl,
    },
  };
}
function encodeSharePayload(data) {
  const json = JSON.stringify(data || {});
  try {
    return btoa(unescape(encodeURIComponent(json)));
  } catch (e) {
    try {
      return btoa(json);
    } catch (e2) {
      return '';
    }
  }
}
function copyTextWithFallback(text) {
  if (!text) return Promise.reject(new Error('empty-text'));
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      const ok = document.execCommand('copy');
      textarea.remove();
      if (ok) resolve();
      else reject(new Error('copy-failed'));
    } catch (err) {
      textarea.remove();
      reject(err);
    }
  });
}
function flashShareButton(button, successLabel, defaultLabel) {
  if (!button) return;
  button.textContent = successLabel;
  setTimeout(() => {
    button.textContent = defaultLabel;
  }, 2000);
}
function openShareModal(game) {
  const shareGame = buildShareGamePayload(game);
  if (!shareGame) return;
  currentShareData = shareGame.payload;
  currentSteamUrl = shareGame.steamUrl;
  document.getElementById('share-name').textContent = shareGame.name;
  document.getElementById('share-price').innerHTML =
    (shareGame.displayOriginalPrice ? '<span>' + shareGame.displayOriginalPrice + ' </span>' : '') +
    shareGame.displayPrice +
    (shareGame.discount ? ' (' + shareGame.discount + '% OFF)' : '');
  document.getElementById('share-minhist').innerHTML = shareGame.displayMinHist
    ? 'Mínimo histórico en Steam: <span>' + shareGame.displayMinHist + '</span> · Te ayuda a ver si la oferta actual está cerca de su mejor precio.'
    : 'Sin dato de mínimo histórico. Si agregas ITAD tendrás esa referencia en más reportes.';
  document.getElementById('share-modal').classList.add('active');
}
function closeShareModal() {
  document.getElementById('share-modal').classList.remove('active');
  currentShareData = null;
  currentSteamUrl = '';
}
function copyShareLink() {
  if (!currentShareData) return;
  const encoded = encodeSharePayload(currentShareData);
  if (!encoded) return;
  const shareUrl = 'steamtools://share?data=' + encoded;
  copyTextWithFallback(shareUrl).then(() => {
    const btn = document.getElementById('btn-copy-app');
    flashShareButton(btn, '¡Copiado!', 'Copiar link steamtools://');
  }).catch(() => {
    window.prompt('Copia este link:', shareUrl);
  });
}
function copySteamLink() {
  if (!currentSteamUrl) return;
  copyTextWithFallback(currentSteamUrl).then(() => {
    const btn = document.querySelector('.share-btn-copy-steam');
    flashShareButton(btn, '¡Copiado!', 'Copiar link de Steam');
  }).catch(() => {
    window.prompt('Copia este link de Steam:', currentSteamUrl);
  });
}
function openInSteam() {
  if (currentSteamUrl) window.open(currentSteamUrl, '_blank');
}
function bindShareModalInteractions() {
  const modal = document.getElementById('share-modal');
  if (!modal || modal.dataset.bound === '1') return;
  modal.dataset.bound = '1';
  modal.addEventListener('click', (ev) => {
    if (ev.target === modal) closeShareModal();
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && modal.classList.contains('active')) {
      closeShareModal();
    }
  });
}
function formatBudgetCurrency(value) {
  const amount = Number(value) || 0;
  return '$' + amount.toFixed(0);
}
function escapeBudgetHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function renderBudgetContext(option) {
  const recommendation = option && option.recommendation ? `<div class="pick-recommendation" style="margin-top:.25rem">${escapeBudgetHtml(option.recommendation)}</div>` : '';
  const reasons = option && Array.isArray(option.score_reasons) && option.score_reasons.length
    ? `<div class="pick-why">${escapeBudgetHtml(option.score_reasons.join(' · '))}</div>`
    : '';
  return recommendation + reasons;
}
function renderBudgetPreview(option) {
  if (!option || option.is_original) return '';
  return `Preview · Nuevo total: ${escapeBudgetHtml(formatBudgetCurrency(option.swap_total_spent))} · Restante: ${escapeBudgetHtml(formatBudgetCurrency(option.swap_remaining))}`;
}
function applyBudgetOption(row, option) {
  if (!row || !option) return;
  const scoreEl = row.querySelector('.budget-value-score');
  const discountEl = row.querySelector('.budget-value-discount');
  const priceEl = row.querySelector('.budget-value-price');
  const linkEl = row.querySelector('.budget-value-link');
  const imageEl = row.querySelector('.game-thumb');
  const contextEl = row.querySelector('.budget-value-context');
  const previewEl = row.querySelector('.budget-reroll-preview');
  if (scoreEl) scoreEl.textContent = String(option.score ?? '—');
  if (discountEl) discountEl.textContent = `-${Number(option.discount || 0)}%`;
  if (priceEl) priceEl.textContent = option.price_final || '—';
  if (linkEl) {
    linkEl.textContent = option.name || 'Juego';
    linkEl.href = option.url || '#';
  }
  if (imageEl && option.image_url) {
    imageEl.style.display = '';
    imageEl.src = option.image_url;
  }
  if (contextEl) contextEl.innerHTML = renderBudgetContext(option);
  if (previewEl) {
    const previewText = renderBudgetPreview(option);
    previewEl.innerHTML = previewText;
    previewEl.classList.toggle('hidden', !previewText);
  }
}
function activateBudgetVariant(variantId) {
  const buttons = Array.from(document.querySelectorAll('[data-budget-variant-btn]'));
  const panels = Array.from(document.querySelectorAll('[data-budget-panel]'));
  const activeButton = buttons.find(btn => btn.dataset.budgetVariantBtn === variantId) || buttons[0];
  if (!activeButton) return;
  buttons.forEach((btn) => btn.classList.toggle('is-active', btn === activeButton));
  panels.forEach((panel) => panel.classList.toggle('hidden', panel.dataset.budgetPanel !== activeButton.dataset.budgetVariantBtn));
  const summaryCopy = document.getElementById('budget-summary-copy');
  const progressFill = document.getElementById('budget-progress-fill');
  const progressText = document.getElementById('budget-progress-text');
  const badge = document.getElementById('budget-current-variant');
  const budget = Number(activeButton.dataset.budgetBudget || 0);
  const total = Number(activeButton.dataset.budgetTotal || 0);
  const remaining = Number(activeButton.dataset.budgetRemaining || 0);
  const savings = Number(activeButton.dataset.budgetSavings || 0);
  const games = Number(activeButton.dataset.budgetGames || 0);
  const pct = budget > 0 ? Math.round((total / budget) * 100) : 0;
  if (summaryCopy) summaryCopy.innerHTML = `Con ${escapeBudgetHtml(formatBudgetCurrency(budget))} MXN puedes comprar ${escapeBudgetHtml(games)} juegos &middot; Ahorro: ${escapeBudgetHtml(formatBudgetCurrency(savings))} &middot; Restante: ${escapeBudgetHtml(formatBudgetCurrency(remaining))}`;
  if (progressFill) progressFill.style.width = pct + '%';
  if (progressText) progressText.textContent = `${formatBudgetCurrency(total)} / ${formatBudgetCurrency(budget)} (${pct}%)`;
  if (badge) badge.textContent = activeButton.dataset.budgetLabel || 'Lista actual';
}
function bindBudgetRowRerolls() {
  document.querySelectorAll('[data-budget-options]').forEach((btn) => {
    if (btn.dataset.bound === '1') return;
    btn.dataset.bound = '1';
    btn.dataset.currentIndex = '0';
    btn.addEventListener('click', () => {
      const options = JSON.parse(btn.dataset.budgetOptions || '[]');
      if (!options.length) return;
      const nextIndex = (Number(btn.dataset.currentIndex || '0') + 1) % options.length;
      btn.dataset.currentIndex = String(nextIndex);
      const row = document.querySelector(`[data-budget-row="${btn.dataset.budgetRowKey}"]`);
      applyBudgetOption(row, options[nextIndex]);
      btn.textContent = nextIndex === 0 ? 'Reroll' : `Reroll ${nextIndex}/${options.length - 1}`;
    });
  });
}
function bindBudgetHtmlInteractions() {
  const buttons = Array.from(document.querySelectorAll('[data-budget-variant-btn]'));
  if (!buttons.length) return;
  buttons.forEach((btn) => {
    if (btn.dataset.bound === '1') return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => activateBudgetVariant(btn.dataset.budgetVariantBtn));
  });
  bindBudgetRowRerolls();
  const activeButton = buttons.find((btn) => btn.classList.contains('is-active')) || buttons[0];
  activateBudgetVariant(activeButton.dataset.budgetVariantBtn);
}
function focusTrendCell(appid) {
  if (!appid) return;
  const target = document.querySelector('[data-trend-cell="' + appid + '"]');
  if (!target) return;
  target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
  target.classList.remove('trend-focus');
  void target.offsetWidth;
  target.classList.add('trend-focus');
  setTimeout(() => target.classList.remove('trend-focus'), 1600);
}
"""


def _build_dashboard_html(
    deals,
    reviews,
    deck_compat_data,
    tags_data,
    protondb_data,
    *,
    group_by_tier,
    group_deals_by_tag,
):
    if not deals:
        return ""
    total = len(deals)
    total_orig = sum(_html_price_raw(d.get("price_original", "")) for d in deals)
    total_final = sum(_html_price_raw(d["price_final"]) for d in deals)
    total_savings = total_orig - total_final
    avg_disc = sum(d["discount"] for d in deals) / total
    prices = sorted(_html_price_raw(d["price_final"]) for d in deals)
    median_price = prices[len(prices) // 2] if prices else 0

    fin_html = f"""<div class="dash-card" style="grid-column:1/-1">
  <h3>&#128176; Resumen Financiero</h3>
  <div class="fin-grid">
    <div class="fin-item"><div class="fin-value">${total_orig:,.0f}</div><div class="fin-label">Precio original</div></div>
    <div class="fin-item"><div class="fin-value">${total_final:,.0f}</div><div class="fin-label">En oferta</div></div>
    <div class="fin-item"><div class="fin-value fin-savings">${total_savings:,.0f}</div><div class="fin-label">Ahorro total</div></div>
    <div class="fin-item"><div class="fin-value">-{avg_disc:.0f}%</div><div class="fin-label">Descuento promedio</div></div>
    <div class="fin-item"><div class="fin-value">${median_price:.0f}</div><div class="fin-label">Precio mediana</div></div>
  </div>
</div>"""

    tier_colors = {
        "90%+": "#6cc644",
        "80–89%": "#4eaa5a",
        "70–79%": "#f0b232",
        "60–69%": "#e89030",
        "50–59%": "#c7322e",
    }
    tiers = group_by_tier(deals)
    max_t = max((len(ds) for _, ds in tiers), default=1) or 1
    bars_html = ""
    for name, ds in tiers:
        pct = len(ds) / max_t * 100
        color = tier_colors.get(name, "#66c0f4")
        bars_html += f'<div class="hbar-row"><span class="hbar-label">{name}</span><div class="hbar-track"><div class="hbar-fill" style="width:{pct}%;background:{color}">{len(ds)}</div></div><span class="hbar-value">{len(ds)}</span></div>\n'
    disc_html = f'<div class="dash-card"><h3>&#128200; Descuentos</h3>{bars_html}</div>'

    dk_counts = {3: 0, 2: 0, 1: 0, 0: 0}
    for d in deals:
        deck_category = deck_compat_data.get(d["appid"], 0)
        dk_counts[deck_category] = dk_counts.get(deck_category, 0) + 1
    dk_colors = {
        3: ("#6cc644", "Verificado"),
        2: ("#f0b232", "Jugable"),
        1: ("#c7322e", "No compatible"),
        0: ("#555", "Unknown"),
    }
    dk_segs = ""
    dk_legend = ""
    for cat in (3, 2, 1, 0):
        if dk_counts[cat] > 0:
            pct = dk_counts[cat] / total * 100
            color, label = dk_colors[cat]
            dk_segs += f'<div class="stacked-seg" style="width:{pct}%;background:{color}">{dk_counts[cat] if pct > 5 else ""}</div>'
            dk_legend += f'<span class="legend-item"><span class="legend-dot" style="background:{color}"></span>{label} ({dk_counts[cat]})</span>'

    pdb_counts = {}
    for d in deals:
        pdb = (protondb_data or {}).get(d["appid"])
        if pdb:
            tier = pdb.get("tier", "")
            pdb_counts[tier] = pdb_counts.get(tier, 0) + 1
    pdb_colors = {
        "native": "#6cc644",
        "platinum": "#b4c7dc",
        "gold": "#d4a84b",
        "silver": "#a8a8a8",
        "bronze": "#cd7f32",
        "borked": "#c7322e",
    }
    pdb_segs = ""
    pdb_legend = ""
    for tier in ("native", "platinum", "gold", "silver", "bronze", "borked"):
        count = pdb_counts.get(tier, 0)
        if count > 0:
            pct = count / total * 100
            pdb_segs += f'<div class="stacked-seg" style="width:{pct}%;background:{pdb_colors[tier]}">{count if pct > 5 else ""}</div>'
            pdb_legend += f'<span class="legend-item"><span class="legend-dot" style="background:{pdb_colors[tier]}"></span>{tier.title()} ({count})</span>'

    compat_html = f"""<div class="dash-card"><h3>&#127918; Compatibilidad Steam Deck y Linux</h3>
  <div style="margin-bottom:.6rem"><div style="font-size:.75rem;color:var(--text-secondary);margin-bottom:.2rem">Steam Deck</div><div class="stacked-bar">{dk_segs}</div><div class="stacked-legend">{dk_legend}</div></div>
  <div><div style="font-size:.75rem;color:var(--text-secondary);margin-bottom:.2rem">ProtonDB</div><div class="stacked-bar">{pdb_segs}</div><div class="stacked-legend">{pdb_legend}</div></div>
</div>"""

    tags_html = ""
    if tags_data:
        tag_groups = group_deals_by_tag(deals, tags_data)
        if tag_groups:
            max_tg = len(tag_groups[0][1]) if tag_groups else 1
            tg_bars = ""
            for tag_name, tag_deals in tag_groups[:8]:
                pct = len(tag_deals) / max_tg * 100
                tg_bars += f'<div class="hbar-row"><span class="hbar-label">{_html_esc(tag_name)}</span><div class="hbar-track"><div class="hbar-fill" style="width:{pct}%;background:var(--accent-blue)">{len(tag_deals)}</div></div><span class="hbar-value">{len(tag_deals)}</span></div>\n'
            tags_html = f'<div class="dash-card"><h3>&#127991; Top Etiquetas</h3>{tg_bars}</div>'

    return f"""<details open class="dashboard">
  <summary>&#128202; Dashboard</summary>
  <div class="dash-grid">
    {fin_html}
    {disc_html}
    {compat_html}
    {tags_html}
  </div>
</details>"""


def generate_html(
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
    tags_data: dict[str, dict] | None = None,
    protondb_data: dict[str, dict] | None = None,
    achievements_data: dict[str, dict] | None = None,
    watchlist_alerts: list[dict] | None = None,
    budget_result: dict | None = None,
    compare_data: dict | None = None,
    gift_ideas: list[dict] | None = None,
    compare_profiles: list[dict] | None = None,
    gift_ideas_by_friend: list[dict] | None = None,
    shared_gift_ideas: list[dict] | None = None,
    recommended_collections: list[dict] | None = None,
    personalized_recommendations: dict | None = None,
    wishlist_hygiene: dict | None = None,
    play_access: dict | None = None,
    local_trends: dict[str, dict] | None = None,
    price_history: dict | None = None,
    profile_display_name: str | None = None,
    active_promo_context: dict | None = None,
    smart_alert_digest: dict | None = None,
    free_weekend_now: dict | None = None,
    external_offers: dict | None = None,
    taste_priority: dict | None = None,
    recommendation_diagnostics: dict | None = None,
    *,
    group_by_tier,
    group_deals_by_tag,
) -> str:
    del (
        backlog_on_sale,
        have_on_sale,
        genres,
        hltb_used,
        local_trends,
        play_access,
    )

    today_obj = date.today()
    today = f"{today_obj.day} de {MESES[today_obj.month]} de {today_obj.year}"
    priorities = priorities or {}
    historical_lows = historical_lows or {}
    previous_appids = previous_appids or set()
    reviews = reviews or {}
    deck_compat_data = deck_compat or {}
    current_prices = current_prices or {}
    top_picks = top_picks or []
    recommended_collections = recommended_collections or []
    personalized_recommendations = personalized_recommendations or {"items": []}
    wishlist_hygiene = wishlist_hygiene or {"items": []}
    smart_alert_digest = smart_alert_digest if isinstance(smart_alert_digest, dict) else None
    external_offers = external_offers if isinstance(external_offers, dict) else None
    taste_priority = taste_priority if isinstance(taste_priority, dict) else None
    recommendation_diagnostics = (
        recommendation_diagnostics if isinstance(recommendation_diagnostics, dict) else None
    )
    achievements_data = achievements_data or {}
    watchlist_alerts = watchlist_alerts or []
    price_history_games = (price_history or {}).get("games", {})
    has_itad = bool(historical_lows)
    has_best = bool(current_prices)
    has_ach = bool(achievements_data)
    has_sparklines = _has_sparkline_history(price_history_games, deals)
    deals_by_appid = {deal["appid"]: deal for deal in deals}
    profile_label = profile_display_name or vanity

    total_deals = len(deals)
    avg_disc = sum(d["discount"] for d in deals) / total_deals if total_deals else 0
    avg_price = (
        sum(_html_price_raw(d["price_final"]) for d in deals) / total_deals
        if total_deals
        else 0
    )
    avg_disc_text = f"-{avg_disc:.0f}%" if total_deals else "sin datos"
    avg_price_text = f"${avg_price:.0f}" if total_deals else "sin datos"
    verified = sum(1 for d in deals if deck_compat_data.get(d["appid"]) == 3)
    new_count = (
        sum(1 for d in deals if previous_appids and d["appid"] not in previous_appids)
        if previous_appids
        else 0
    )

    parts = []
    sale_html = (
        f'Evento: <span class="sale-badge">&#127991; {_html_esc(sale_name)}</span> | '
        if sale_name
        else ""
    )
    pills = [
        f'<span class="pill">{len(wishlist_appids):,} en wishlist</span>',
        f'<span class="pill pill-accent" id="stat-deals">{total_deals:,} deals (&ge;{min_discount}%)</span>',
        f'<span class="pill" id="stat-avg-disc">Promedio: {avg_disc_text}</span>',
        f'<span class="pill" id="stat-avg-price">Precio medio: {avg_price_text}</span>',
        f'<span class="pill">{verified} verificados para Steam Deck</span>',
    ]
    if new_count:
        pills.append(f'<span class="pill pill-new">{new_count} ofertas nuevas</span>')
    parts.append(f"""<header class="stats-bar">
  <h1>Ofertas de Steam &mdash; {_html_esc(profile_label)}</h1>
  <div class="stats-meta">{sale_html}{today} | Precios en MXN</div>
  {_build_promo_context_html(active_promo_context)}
  <div class="stats-pills">{"".join(pills)}</div>
</header>""")

    parts.append(
        _build_dashboard_html(
            deals,
            reviews,
            deck_compat_data,
            tags_data or {},
            protondb_data or {},
            group_by_tier=group_by_tier,
            group_deals_by_tag=group_deals_by_tag,
        )
    )

    parts.append(
        _html_shuffle_one_game(
            _build_shuffle_candidates(
                top_picks,
                deals,
                personalized_recommendations=personalized_recommendations,
            )
        )
    )

    if top_picks:
        cards = []
        for idx, tp in enumerate(top_picks, 1):
            rank_cls = (
                "rank-gold"
                if idx == 1
                else "rank-silver"
                if idx == 2
                else "rank-bronze"
                if idx == 3
                else ""
            )
            rev_html = _html_review_badge(tp.get("review"))
            dk_html = _html_deck_badge(tp.get("deck", 0))
            mc_html = _html_metacritic_badge(
                tp.get("metacritic_score"), with_label=True
            )
            mp_html = _html_multiplayer_badges(tp.get("categories", []))
            prio_html = _html_prio_badge(tp.get("priority", 0))
            header_img = HEADER_URL.format(appid=tp["appid"])
            store_url = STORE_URL.format(appid=tp["appid"])
            source_deal = deals_by_appid.get(tp["appid"], {})
            min_hist = historical_lows.get(tp["appid"])
            min_hist_str = f"${min_hist['price']:.0f}" if min_hist else ""
            original_price = str(
                tp.get("price_original")
                or source_deal.get("price_original")
                or tp.get("price_final")
                or ""
            )
            display_discount = int(tp.get("discount") or source_deal.get("discount") or 0)
            display_price = str(tp.get("price_final") or source_deal.get("price_final") or "")
            recommendation = _html_esc(tp.get("recommendation", ""))
            recommendation_filter = _html_esc(tp.get("recommendation") or "Sin recomendación")
            why_text = _html_esc(" · ".join(tp.get("score_reasons", [])))
            highlight_html = _html_offer_highlight(
                tp,
                min_hist=min_hist,
                source_deal=source_deal,
                active_promo_context=active_promo_context,
            )
            why_html = (
                f'<div class="pick-recommendation">{recommendation}</div><div class="pick-why">{why_text}</div>'
                if recommendation or why_text
                else ""
            )
            share_payload = _build_share_payload(
                name=tp["name"],
                appid=tp["appid"],
                price=display_price,
                original_price=original_price,
                discount=display_discount,
                min_hist=min_hist_str,
            )
            cards.append(f'''<div class="pick-card {rank_cls}" data-top-pick-card data-recommendation="{recommendation_filter}">
  <a href="{store_url}" target="_blank" rel="noopener noreferrer" style="display:block">
    <img class="pick-img" src="{header_img}" alt="" loading="lazy" onerror="this.style.display='none'">
    <div class="pick-body">
      <div class="pick-rank">#{idx}</div>
      <div class="pick-score" title="Score = recomendación compuesta para priorizar qué revisar primero.">Score {_html_esc(str(tp["score"]))}</div>
      <div class="pick-name">{_html_esc(tp["name"])}{prio_html}</div>
      <div class="pick-details"><span class="pick-discount">-{display_discount}%</span><span class="pick-price">{_html_esc(display_price)}</span></div>
      <div class="pick-meta">{rev_html} &middot; {mc_html} &middot; {dk_html} &middot; {mp_html}</div>
      {highlight_html}
      {why_html}
    </div>
  </a>
  {_html_share_button(share_payload)}
</div>''')
        parts.append(f"""<section class="top-picks" data-top-picks-section>
  <h2>&#127942; {len(top_picks)} juegos destacados</h2>
  <p class="section-desc">Score = recomendación compuesta para priorizar qué revisar primero. Combina reviews (26%) + descuento (22%) + prioridad (18%) + $/hora HLTB (14%) + Deck (10%) + Metacritic (5%) + antigüedad (5%).</p>
  {_html_top_pick_filter_controls()}
  {_html_recommendation_guide()}
  <div class="picks-grid">{"".join(cards)}</div>
</section>""")

    parts.append(_html_recommended_collections(recommended_collections))
    parts.append(_html_personalized_recommendations(personalized_recommendations))
    parts.append(_html_recommendation_diagnostics(recommendation_diagnostics))
    parts.append(_html_taste_priority(taste_priority))
    parts.append(
        _html_selection_review(
            deals,
            top_picks,
            recommended_collections,
            personalized_recommendations,
            owned,
            family_appids,
        )
    )
    parts.append(_html_free_weekend_now(free_weekend_now))
    parts.append(_html_external_offers(external_offers))
    parts.append(_html_wishlist_hygiene(wishlist_hygiene))
    parts.append(_html_smart_alert_digest(smart_alert_digest))

    if watchlist_alerts:
        wl_rows = []
        for wa in watchlist_alerts:
            savings = wa["target_price"] - (wa.get("price_raw", 0) / 100)
            savings_html = (
                f'<span style="color:var(--accent-green)">+${savings:.0f}</span>'
                if savings > 0
                else ""
            )
            capsule = CAPSULE_URL.format(appid=wa["appid"])
            wl_rows.append(f'''<div class="wl-card">
  <img src="{capsule}" alt="" loading="lazy" style="width:120px;height:45px;border-radius:4px;object-fit:cover" onerror="this.style.display='none'">
  <div class="wl-info">
    <div><strong>{_html_link(wa["name"], wa["appid"])}</strong></div>
    <div style="font-size:.85rem">{_html_esc(wa["price_final"])} <span style="color:var(--text-secondary)">(objetivo: ${wa["target_price"]:.0f})</span> {savings_html}</div>
    <div style="font-size:.8rem"><span class="pick-discount">-{wa["discount"]}%</span></div>
  </div>
</div>''')
        parts.append(f"""<section class="top-picks" style="margin-bottom:1.5rem">
  <h2>&#127919; Watchlist Alerts</h2>
  <p class="section-desc">{len(watchlist_alerts)} juegos alcanzaron tu precio objetivo</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.6rem">{"".join(wl_rows)}</div>
</section>""")

    if budget_result:
        budget_data = budget_result
        variants = budget_data.get("variants") or []
        panel_variants = _html_budget_variants_with_fallback_rows(budget_data)
        selected_variant = budget_data.get("selected_variant")
        if not selected_variant and len(panel_variants) == 1:
            selected_variant = panel_variants[0].get("id")
        pct_used = (
            budget_data["total_spent"] / budget_data["budget"] * 100
            if budget_data["budget"] > 0
            else 0
        )
        variant_controls_html = _html_budget_variant_controls(
            variants, selected_variant=selected_variant
        )
        variant_panels_html = _html_budget_variant_panels(
            panel_variants, selected_variant=selected_variant
        )
        current_variant = next(
            (
                variant
                for variant in panel_variants
                if variant.get("id") == selected_variant
            ),
            None,
        )
        current_variant_label = _html_esc(
            (current_variant or {}).get("label") or "Lista actual"
        )
        parts.append(f"""<section style="margin-bottom:1.5rem">
  <h2>&#128176; Tu Presupuesto Ideal &mdash; ${budget_data["budget"]:.0f} MXN</h2>
  <p class="section-desc" id="budget-summary-copy">Con ${budget_data["budget"]:.0f} MXN puedes comprar {budget_data["games_count"]} juegos &middot; Ahorro: ${budget_data["total_savings"]:.0f} &middot; Restante: ${budget_data["remaining"]:.0f}</p>
  <div style="background:var(--bg-secondary);border-radius:6px;height:24px;margin-bottom:.8rem;overflow:hidden;position:relative">
    <div id="budget-progress-fill" style="height:100%;width:{pct_used:.0f}%;background:linear-gradient(90deg,var(--accent-blue),#4b9cd3);border-radius:6px"></div>
    <div id="budget-progress-text" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:600;color:var(--text-primary)">${budget_data["total_spent"]:.0f} / ${budget_data["budget"]:.0f} ({pct_used:.0f}%)</div>
  </div>
  <p class="section-desc">Variante activa: <strong id="budget-current-variant">{current_variant_label}</strong></p>
  {variant_controls_html}
  {variant_panels_html}
</section>""")

    if compare_data:
        friend = str(
            compare_data.get("friend_name") or compare_data.get("friend_vanity", "?")
        ).strip() or "?"
        overlap_count = compare_overlap_count(compare_data)
        overlap_deals = normalize_overlap_deal_rows(deals, compare_data)
        comp_html = f"""<section style="margin-bottom:1.5rem">
  <h2>&#128101; Wishlist Comparison &mdash; {_html_esc(friend)}</h2>
  <p class="section-desc">{overlap_count} juegos en com&uacute;n"""
        if overlap_deals:
            comp_html += f" &middot; {len(overlap_deals)} en oferta"
        comp_html += "</p>"
        if overlap_deals:
            ol_rows = ""
            for row in overlap_deals:
                ol_rows += f'<tr><td>-{int(row["discount"])}%</td><td>{_html_esc(str(row["price_final"]))}</td><td>{_html_social_game_cell(row)}</td></tr>'
            comp_html += f'<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">En com&uacute;n y en oferta</h3><div class="table-wrap"><table class="deals-table"><thead><tr><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>{ol_rows}</tbody></table></div>'
        elif overlap_count:
            comp_html += _html_social_empty(
                "Hay juegos en común, pero ninguno tiene una oferta renderizable en este reporte."
            )
        gift_ideas_list = gift_ideas or []
        gift_rows = normalize_gift_idea_rows(gift_ideas_list)
        if gift_rows:
            comp_html += f'<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">&#127873; Gift Ideas para {_html_esc(friend)}</h3>{_html_gift_table(gift_rows)}'
        elif gift_ideas_list:
            comp_html += '<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">&#127873; Gift Ideas para ' + _html_esc(friend) + '</h3>'
            comp_html += _html_social_empty(
                "Hay datos de regalos, pero no hay items concretos para mostrar."
            )
        comp_html += "</section>"
        parts.append(comp_html)

    multi_profile_gifts_html = _html_multi_profile_gifts(
        compare_profiles,
        gift_ideas_by_friend,
        shared_gift_ideas,
    )
    if multi_profile_gifts_html:
        parts.append(multi_profile_gifts_html)

    parts.append(f'''<details open class="filter-panel">
  <summary>&#128269; Filtros</summary>
  <div class="filter-grid">
    <div class="filter-group"><label>Buscar juego</label><input type="text" id="f-search" placeholder="Nombre..." oninput="applyFilters()"></div>
    <div class="filter-group"><label>Descuento min: <output id="f-disc-val">{min_discount}%</output></label><input type="range" id="f-discount" min="50" max="100" value="{min_discount}" oninput="document.getElementById('f-disc-val').textContent=this.value+'%';applyFilters()"></div>
    <div class="filter-group"><label>Precio max: <output id="f-price-val">Sin limite</output></label><input type="range" id="f-price-max" min="0" max="2000" value="2000" step="10" oninput="document.getElementById('f-price-val').textContent=this.value>=2000?'Sin limite':'$'+this.value;applyFilters()"></div>
    <div class="filter-group"><label>Steam Deck</label><select id="f-deck" onchange="applyFilters()"><option value="all">Todos</option><option value="3">Verificado</option><option value="2">Jugable</option><option value="1">No compatible</option></select></div>
    <div class="filter-group"><label>Reseñas mín.: <output id="f-rev-val">0%</output></label><input type="range" id="f-reviews" min="0" max="100" value="0" oninput="document.getElementById('f-rev-val').textContent=this.value+'%';applyFilters()"></div>
    <div class="filter-group"><label><input type="checkbox" id="f-new-only" onchange="applyFilters()"> Solo nuevos</label></div>
    <div class="filter-group"><button onclick="resetFilters()" class="btn-reset">Limpiar filtros</button> <button onclick="copyForSheets()" class="btn-reset" title="Copiar datos visibles como TSV para pegar en Google Sheets/Excel">&#128203; Copiar para Sheets</button></div>
  </div>
</details>''')

    for tier_name, tier_deals in group_by_tier(deals):
        tier_deals.sort(
            key=lambda d: (
                priorities.get(d["appid"], 0) == 0,
                priorities.get(d["appid"], 9999),
            )
        )
        tid = re.sub(r"[^a-z0-9]", "", tier_name.lower())
        cols = [
            ("", "text"),
            ("%", "num"),
            ("Precio", "price"),
            ("Precio original", "price"),
            ("Reseñas", "num"),
            ("Metacritic", "num"),
            ("Compatibilidad", "text"),
            ("Tipo de juego", "text"),
        ]
        if has_ach:
            cols.append(("Logros", "num"))
        if has_sparklines:
            cols.append(("Historial local", "text"))
        if has_itad:
            cols.append(("Mín. histórico", "price"))
        if has_best:
            cols.append(("Mejor precio", "price"))
        cols.append(("Juego", "text"))

        ths = "".join(
            f"<th onclick=\"sortTable('t-{tid}',{i},'{col_type}')\">{_html_esc(header)} <span class=\"sort-arrow\">&#9650;&#9660;</span></th>"
            for i, (header, col_type) in enumerate(cols)
        )

        rows = []
        for d in tier_deals:
            appid = d["appid"]
            is_new = bool(previous_appids and appid not in previous_appids)
            new_html = '<span class="badge new-badge">NUEVO</span>' if is_new else ""
            rev = reviews.get(appid)
            rev_pct = rev["pct"] if rev else -1
            dk = deck_compat_data.get(appid, 0)
            prio = priorities.get(appid, 0)
            price_num = _html_price_raw(d["price_final"])
            mc = d.get("metacritic_score")
            mp_cats = d.get("categories", [])
            game_hist = price_history_games.get(appid, {}) if has_sparklines else {}
            snaps = game_hist.get("snapshots", []) if has_sparklines else []
            has_trend_movement = _has_price_movement_snapshots(snaps)
            cells = [
                f"<td>{new_html}</td>",
                f"<td>-{d['discount']}%</td>",
                f"<td>{_html_esc(d['price_final'])}</td>",
                f"<td>{_html_esc(d['price_original'])}</td>",
                f"<td>{_html_review_badge(rev)}</td>",
                f"<td>{_html_metacritic_badge(mc)}</td>",
                f"<td>{_html_deck_badge(dk)}</td>",
                f"<td>{_html_multiplayer_badges(mp_cats)}</td>",
            ]
            if has_ach:
                ach = achievements_data.get(appid)
                cells.append(f"<td>{_html_achievements_badge(ach)}</td>")
            if has_sparklines:
                spark = _build_sparkline_svg(snaps) if has_trend_movement else "—"
                cells.append(
                    f"<td data-trend-cell=\"{_html_esc(appid)}\">{spark}</td>"
                )
            if has_itad:
                low = historical_lows.get(appid)
                if low:
                    low_txt = f"${low['price']:.0f} ({low['date']})"
                    trend_jump = (
                        _html_min_hist_jump_button(appid) if has_trend_movement else ""
                    )
                    cells.append(
                        f"<td><div class=\"min-hist-cell\"><span>{_html_esc(low_txt)}</span>{trend_jump}</div></td>"
                    )
                else:
                    cells.append("<td>—</td>")
            if has_best:
                bp = current_prices.get(appid)
                if bp:
                    bp_html = f'${bp["price"]:.0f} en <a href="{bp["url"]}" target="_blank" rel="noopener noreferrer">{_html_esc(bp["store"])} </a>'
                    cells.append(f"<td>{bp_html}</td>")
                else:
                    cells.append("<td>—</td>")
            capsule_img = CAPSULE_URL.format(appid=appid)
            desc_attr = (
                f' title="{_html_esc(d.get("description", ""))}"'
                if d.get("description")
                else ""
            )
            min_hist = historical_lows.get(appid)
            min_hist_str = f"${min_hist['price']:.0f}" if min_hist else ""
            highlight_html = _html_offer_highlight(
                d,
                min_hist=min_hist,
                active_promo_context=active_promo_context,
            )
            share_payload = _build_share_payload(
                name=d["name"],
                appid=appid,
                price=str(d.get("price_final") or ""),
                original_price=str(d.get("price_original") or d.get("price_final") or ""),
                discount=int(d.get("discount") or 0),
                min_hist=min_hist_str,
            )
            name_html = (
                f'<div class="game-cell">'
                f'<img class="game-thumb" src="{capsule_img}" alt="" loading="lazy" onerror="this.style.display=\'none\'">'
                f"<span{desc_attr}>{_html_link(d['name'], appid)}{_html_prio_badge(prio)}{highlight_html}</span>"
                f'{_html_share_button(share_payload, style="margin-left:.4rem;position:relative;top:-1px")}'
                f"</div>"
            )
            cells.append(f"<td>{name_html}</td>")

            data_attrs = f'data-discount="{d["discount"]}" data-price="{price_num}" data-deck="{dk}" data-review="{rev_pct}" data-name="{_html_esc(d["name"].lower())}" data-new="{"1" if is_new else "0"}"'
            rows.append(f"<tr data-deal-row {data_attrs}>{''.join(cells)}</tr>")

        note_parts = []
        if has_sparklines:
            note_parts.append(
                "Historial local = movimiento del precio en tus corridas previas; no es predicción."
            )
        if has_itad:
            note_parts.append(
                "Mín. histórico = mejor precio detectado antes en Steam."
            )
        note_parts.append(
            "Tipo de juego = si se juega solo, cooperativo, PvP o multijugador."
        )
        if has_itad and has_sparklines:
            note_parts.append(
                "Usa ➡ Ver historial junto a Mín. histórico para saltar rápido al movimiento local del precio."
            )
        note_html = (
            f'<p class="section-desc">{" · ".join(note_parts)}</p>'
            if note_parts
            else ""
        )

        parts.append(f"""<details open class="tier-section">
  <summary class="tier-header">{_html_esc(tier_name)} de Descuento <span class="tier-count">(<span class="visible-count">{len(tier_deals)}</span> juegos)</span></summary>
  {note_html}
  <div class="table-wrap"><table class="deals-table" id="t-{tid}" data-deals-filter-table><thead><tr>{ths}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
</details>""")

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Steam Deals &mdash; {_html_esc(profile_label)}</title><style>{_HTML_CSS}</style></head>
<body>
{"".join(parts)}
<div class="share-modal" id="share-modal">
  <div class="share-modal-content">
    <h3>Compartir oferta</h3>
    <div class="share-game-info">
      <div class="share-game-name" id="share-name"></div>
      <div class="share-game-price" id="share-price"></div>
      <div class="share-game-minhist" id="share-minhist"></div>
    </div>
    <div class="share-actions">
      <button type="button" class="share-btn share-btn-copy-app" id="btn-copy-app" onclick="copyShareLink()">Copiar link steamtools://</button>
      <button type="button" class="share-btn share-btn-copy-steam" onclick="copySteamLink()">Copiar link de Steam</button>
      <button type="button" class="share-btn share-btn-open" onclick="openInSteam()">Abrir en Steam</button>
    </div>
    <button type="button" class="share-btn share-btn-close" onclick="closeShareModal()">Cerrar</button>
  </div>
</div>
<script>{_HTML_JS}</script>
</body>
</html>"""
