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
    normalize_gift_idea_groups,
    normalize_shared_gift_idea_rows,
)


STORE_URL = "https://store.steampowered.com/app/{appid}/"
CAPSULE_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_231x87.jpg"
HEADER_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"

_SCORE_EXPLANATION = (
    "Score = recomendación compuesta para priorizar qué revisar primero."
)

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
_EXTERNAL_OFFER_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


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
    return html_escape(json.dumps(payload, ensure_ascii=False))


def _render_share_button(payload: dict[str, object]) -> str:
    return (
        '<button type="button" class="share-btn-inline" '
        f'data-share-game="{_share_payload_attr(payload)}" '
        'onclick="openShareModal(JSON.parse(this.dataset.shareGame))">'
        '&#128279; Compartir</button>'
    )


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    price = _safe_float(item.get("price"))
    if price is None or price < 0:
        return None
    return price


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


def _render_external_offer_title(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    fallback = f"AppID {appid}" if appid else "Oferta externa"
    name = str(item.get("name") or item.get("steam_name") or fallback).strip()
    if appid.isdigit():
        return f'<a href="{STORE_URL.format(appid=appid)}" target="_blank" rel="noopener noreferrer">{html_escape(name)}</a>'
    return html_escape(name)


def _external_offer_price_text(item: dict) -> str:
    price = _external_offer_price(item)
    currency = _external_offer_currency(item)
    price_text = f"{currency} {price:.2f}" if price is not None and currency else "Sin precio válido"
    discount = _safe_int(item.get("discount_pct"))
    if discount:
        price_text += f" · -{discount}%"
    return price_text


def _render_external_offer_meta(item: dict) -> str:
    store_name = str(item.get("store_name") or item.get("store_id") or "Tienda externa").strip()
    store_type = _external_offer_store_type_label(str(item.get("store_type") or ""))
    return html_escape(f"{store_name} · {store_type} · {_external_offer_price_text(item)}")


def _render_external_offer_status(item: dict) -> str:
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
    return html_escape(" · ".join(parts))


def _render_external_offer_action(item: dict) -> str:
    url = _external_offer_safe_url(item)
    if not url:
        return '<span class="external-offer-link external-offer-link-disabled">Sin link seguro</span>'
    return f'<a class="external-offer-link" href="{html_escape(url)}" target="_blank" rel="noopener noreferrer">Ver tienda (sin carrito)</a>'


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


def _render_external_offer_chips(item: dict) -> str:
    labels = _external_offer_chip_labels(item)
    if not labels:
        return ""
    chips = "".join(
        f'<span class="external-offer-chip">{html_escape(label)}</span>'
        for label in labels
    )
    return f'<div class="external-offer-chips">{chips}</div>'


def _render_external_offer_item(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    data_attr = f' data-external-offer-appid="{html_escape(appid)}"' if appid.isdigit() else ""
    badge = _external_offer_visibility_label(str(item.get("visibility") or ""))
    return f'''<li class="external-offer-item"{data_attr}>
  <div class="external-offer-main">
    <strong>{_render_external_offer_title(item)}</strong>
    <div class="external-offer-meta">{_render_external_offer_meta(item)}</div>
    <div class="external-offer-status">{_render_external_offer_status(item)}</div>
    {_render_external_offer_chips(item)}
    <div class="external-offer-note">Comparativa informativa: no prueba ownership, no abre carrito/checkout ni verifica stock final.</div>
  </div>
  <div class="external-offer-side">
    <span class="external-offer-badge">{html_escape(badge)}</span>
    {_render_external_offer_action(item)}
  </div>
</li>'''


def _render_external_offers(payload: dict | None) -> str:
    items, total_items, hidden_count = _external_offer_items(payload)
    if not items:
        return ""
    more_html = (
        f'<div class="external-offers-more">{hidden_count:,} más en el payload completo</div>'
        if hidden_count
        else ""
    )
    cards = "".join(_render_external_offer_item(item) for item in items)
    return f'''<section class="external-offers" data-external-offers-section>
  <div class="external-offers-head">
    <div>
      <h2 style="margin:1rem 0 .35rem">Comparativa externa</h2>
      <p><strong>{total_items:,} oferta(s) externa(s) visibles</strong> desde el JSON local. Comparativa informativa: Steam Tools no compra, no abre carrito ni checkout, no verifica stock final, no prueba ownership y no cambia score, ranking ni wishlist hygiene.</p>
    </div>
    <span class="external-offers-head-badge">Solo tiendas oficiales/autorizadas · sin checkout</span>
  </div>
  <ol class="external-offers-list">{cards}</ol>
  {more_html}
</section>'''


_STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: system-ui, sans-serif;
  background: #1b2838;
  color: #c7d5e0;
  padding: 1rem;
  max-width: 1000px;
  margin: 0 auto;
}
a { color: #66c0f4; text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 1.3rem; margin-bottom: .3rem; }
table { width: 100%; border-collapse: collapse; font-size: .85rem; margin-top: .5rem; }
th {
  background: #2a475e;
  padding: .4rem .5rem;
  text-align: left;
  border-bottom: 2px solid #2a475e;
}
td { padding: .35rem .5rem; border-bottom: 1px solid #2a475e; }
tr:hover { background: #1a3a5c; }
.meta { color: #8f98a0; font-size: .85rem; margin-bottom: 1rem; }
.share-trigger-wrap { display:flex; align-items:center; gap:.45rem; justify-content:space-between; }
.share-btn-inline { background:#16202d; color:#c7d5e0; border:1px solid #2a475e; border-radius:6px; padding:.35rem .6rem; font-size:.74rem; font-weight:600; cursor:pointer; }
.share-btn-inline:hover { border-color:#66c0f4; color:#66c0f4; }
.share-card { background:#16202d; border:1px solid #2a475e; border-radius:6px; overflow:hidden; display:flex; flex-direction:column; }
.share-card-body { padding:.4rem .6rem; }
.share-card-actions { padding:0 .6rem .6rem; display:flex; justify-content:flex-end; }
.recommended-collections { margin: 1rem 0 .5rem; }
.recommended-collections > p { color:#8f98a0; font-size:.78rem; margin:0 0 .55rem; }
.recommended-collections-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:.5rem; }
.recommended-collection-card { background:#16202d; border:1px solid #2a475e; border-radius:8px; padding:.65rem; }
.recommended-collection-card h3 { color:#66c0f4; font-size:.95rem; margin-bottom:.25rem; }
.recommended-collection-card p { color:#8f98a0; font-size:.76rem; margin-bottom:.45rem; }
.recommended-collection-card ol { list-style:none; display:flex; flex-direction:column; gap:.45rem; }
.recommended-collection-item { border-top:1px solid #2a475e; padding-top:.45rem; display:flex; gap:.5rem; align-items:flex-start; }
.collection-item-thumb { flex:0 0 92px; width:92px; height:35px; border-radius:4px; overflow:hidden; border:1px solid #2a475e; background:#1b2838; }
.collection-item-thumb img { width:100%; height:100%; object-fit:cover; display:block; }
.collection-item-body { flex:1; min-width:0; }
.collection-item-main { display:flex; justify-content:space-between; gap:.5rem; align-items:flex-start; }
.collection-item-reason { color:#8f98a0; font-size:.74rem; margin-top:.12rem; }
.collection-item-meta { display:flex; gap:.35rem; flex-wrap:wrap; justify-content:flex-end; font-size:.72rem; color:#c7d5e0; }
.collection-discount { color:#6cc644; font-weight:700; }
.collection-score { color:#f0b232; }
.collection-price { color:#c7d5e0; }
.collection-share { display:flex; justify-content:flex-end; margin-top:.35rem; }
.personalized-recommendations { margin: 1rem 0 .5rem; }
.personalized-recommendations > p { color:#8f98a0; font-size:.78rem; margin:0 0 .55rem; }
.personalized-profile { display:flex; flex-wrap:wrap; gap:.35rem; margin:0 0 .55rem; }
.personalized-profile span { background:#1b2838; border:1px solid #2a475e; border-radius:999px; padding:.18rem .45rem; font-size:.72rem; color:#c7d5e0; }
.personalized-recommendations-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:.5rem; }
.personalized-recommendation-card { background:#16202d; border:1px solid rgba(108,198,68,.35); border-radius:8px; padding:.65rem; }
.personalized-recommendation-card h3 { color:#66c0f4; font-size:.95rem; margin-bottom:.25rem; }
.personalized-rank { color:#6cc644; font-size:.78rem; font-weight:700; margin-bottom:.25rem; }
.personalized-item-thumb { display:block; width:100%; aspect-ratio:231/87; border-radius:5px; overflow:hidden; border:1px solid #2a475e; background:#1b2838; margin-bottom:.45rem; }
.personalized-item-thumb img { width:100%; height:100%; object-fit:cover; display:block; }
.personalized-meta { display:flex; flex-wrap:wrap; gap:.35rem; color:#c7d5e0; font-size:.72rem; margin:.25rem 0; }
.personalized-meta span:first-child { color:#f0b232; }
.personalized-reasons { color:#8f98a0; font-size:.74rem; margin:.35rem 0 0; padding-left:1rem; }
.personalized-behavioral-note { margin-top:.5rem; padding:.5rem .55rem; border:1px solid rgba(102,192,244,.22); border-left:3px solid #66c0f4; border-radius:6px; background:rgba(102,192,244,.06); color:#8f98a0; font-size:.72rem; line-height:1.35; }
.personalized-behavioral-note strong { display:block; color:#66c0f4; font-size:.74rem; margin-bottom:.18rem; }
.personalized-behavioral-note p { margin:0 0 .28rem; }
.personalized-behavioral-note ul { margin:.22rem 0 0; padding-left:1rem; }
.personalized-behavioral-cues { display:flex; flex-wrap:wrap; gap:.22rem; margin-top:.3rem; }
.personalized-behavioral-cues span { border:1px solid rgba(102,192,244,.25); border-radius:999px; padding:.1rem .35rem; background:rgba(27,40,56,.65); }
.personalized-behavioral-note small { display:block; margin-top:.32rem; opacity:.86; }
.personalized-share { display:flex; justify-content:flex-end; margin-top:.45rem; }
.gift-ideas { margin: 1rem 0 .5rem; }
.gift-ideas > p { color:#8f98a0; font-size:.78rem; margin:0 0 .55rem; }
.gift-ideas-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:.5rem; }
.gift-group { border-top:1px solid #2a475e; padding-top:.65rem; margin-top:.65rem; }
.gift-group h3 { color:#f0b232; font-size:.98rem; margin-bottom:.22rem; }
.gift-group > p, .gift-group-summary, .gift-empty, .gift-group-more { color:#8f98a0; font-size:.76rem; margin:0 0 .5rem; }
.gift-idea-card { background:#16202d; border:1px solid rgba(240,178,50,.35); border-radius:8px; padding:.65rem; }
.gift-idea-card h3 { color:#66c0f4; font-size:.95rem; margin-bottom:.25rem; }
.gift-rank { color:#f0b232; font-size:.78rem; font-weight:700; margin-bottom:.25rem; }
.gift-meta { display:flex; flex-wrap:wrap; gap:.35rem; color:#c7d5e0; font-size:.72rem; margin:.25rem 0; }
.gift-meta span:first-child { color:#6cc644; }
.gift-friends { color:#c7d5e0; font-size:.73rem; margin:.25rem 0; }
.gift-reasons { color:#8f98a0; font-size:.74rem; margin:.35rem 0 0; padding-left:1rem; }
.gift-share { display:flex; justify-content:flex-end; margin-top:.45rem; }
.external-offers { margin:1rem 0 .5rem; }
.external-offers-head { display:flex; justify-content:space-between; gap:.75rem; align-items:flex-start; }
.external-offers-head p { color:#8f98a0; font-size:.78rem; margin:0 0 .55rem; }
.external-offers-head-badge { border:1px solid rgba(102,192,244,.45); border-radius:999px; color:#66c0f4; font-size:.68rem; font-weight:700; padding:.18rem .45rem; white-space:nowrap; }
.external-offers-list { list-style:none; display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:.5rem; }
.external-offer-item { background:#16202d; border:1px solid rgba(102,192,244,.35); border-radius:8px; padding:.65rem; display:flex; gap:.6rem; justify-content:space-between; }
.external-offer-main { min-width:0; }
.external-offer-main strong { color:#66c0f4; font-size:.92rem; }
.external-offer-meta { color:#c7d5e0; font-size:.74rem; margin:.25rem 0 .1rem; }
.external-offer-status, .external-offer-note, .external-offers-more { color:#8f98a0; font-size:.72rem; line-height:1.35; }
.external-offer-chips { display:flex; flex-wrap:wrap; gap:.25rem; margin:.35rem 0 .08rem; }
.external-offer-chip { border:1px solid rgba(102,192,244,.35); border-radius:999px; color:#66c0f4; background:rgba(102,192,244,.08); font-size:.68rem; font-weight:700; padding:.1rem .38rem; }
.external-offer-side { display:flex; flex-direction:column; gap:.35rem; align-items:flex-end; min-width:max-content; }
.external-offer-badge { background:rgba(108,198,68,.13); border:1px solid rgba(108,198,68,.35); border-radius:999px; color:#6cc644; font-size:.68rem; font-weight:700; padding:.14rem .38rem; }
.external-offer-link { border:1px solid #2a475e; border-radius:6px; color:#66c0f4; font-size:.72rem; font-weight:700; padding:.25rem .45rem; }
.external-offer-link-disabled { color:#8f98a0; }
.external-offers-more { margin-top:.45rem; }
.share-modal {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  z-index: 1000;
  align-items: center;
  justify-content: center;
}
.share-modal.active { display: flex; }
.share-modal-content {
  background: #16202d;
  border: 1px solid #2a475e;
  border-radius: 12px;
  padding: 1.5rem;
  max-width: 420px;
  width: 90%;
}
.share-modal h3 { color: #66c0f4; margin-bottom: 1rem; font-size: 1.1rem; }
.share-game-info { background: #1b2838; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
.share-game-name { font-weight: 600; font-size: 1rem; margin-bottom: .5rem; }
.share-game-price { color: #6cc644; font-size: 1.2rem; font-weight: 700; }
.share-game-price span {
  text-decoration: line-through;
  color: #8f98a0;
  font-weight: 400;
  font-size: .9rem;
}
.share-game-minhist { font-size: .8rem; color: #8f98a0; margin-top: .3rem; }
.share-game-minhist span { color: #f0b232; }
.share-actions { display: flex; flex-direction: column; gap: .6rem; }
.share-btn {
  padding: .6rem 1rem;
  border-radius: 6px;
  font-size: .85rem;
  font-weight: 600;
  cursor: pointer;
  text-align: center;
}
.share-btn-copy-app { background: #66c0f4; color: #000; border: none; }
.share-btn-copy-app:hover { background: #4db8e8; }
.share-btn-copy-steam { background: #2a475e; color: #c7d5e0; border: 1px solid #2a475e; }
.share-btn-copy-steam:hover { border-color: #66c0f4; }
.share-btn-open { background: #1b2838; color: #8f98a0; border: 1px solid #2a475e; }
.share-btn-close { background: #2a475e; color: #c7d5e0; border: 1px solid #2a475e; margin-top: .1rem; }
.share-btn-close:hover { border-color: #66c0f4; }
"""

_SCRIPT = """
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
  if (currentSteamUrl) {
    window.open(currentSteamUrl, '_blank');
  }
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

document.addEventListener('DOMContentLoaded', bindShareModalInteractions);
"""


def _render_deal_row(
    deal: dict,
    reviews: dict[str, dict],
    deck_compat: dict[str, int],
    historical_lows: dict[str, dict],
) -> str:
    appid = deal["appid"]
    review = reviews.get(appid)
    review_text = f"{review['desc']} ({review['pct']}%)" if review else ""
    deck_text = {3: "Verificado", 2: "Jugable"}.get(deck_compat.get(appid, 0), "")
    capsule = CAPSULE_URL.format(appid=appid)
    store = STORE_URL.format(appid=appid)
    low = historical_lows.get(appid)
    min_hist = f"${low['price']:.0f}" if low else ""
    share_payload = _build_share_payload(
        name=deal["name"],
        appid=appid,
        price=str(deal.get("price_final") or ""),
        original_price=str(deal.get("price_original") or deal.get("price_final") or ""),
        discount=int(deal.get("discount") or 0),
        min_hist=min_hist,
    )
    return (
        f"<tr><td>-{deal['discount']}%</td><td>{html_escape(deal['price_final'])}</td>"
        f"<td>{review_text}</td><td>{deck_text}</td>"
        f'<td><div class="share-trigger-wrap">'
        f'<div style="display:flex;align-items:center;gap:.4rem">'
        f'<img src="{capsule}" style="width:80px;height:30px;object-fit:cover;border-radius:3px" '
        f'loading="lazy" onerror="this.style.display=\'none\'">'
        f'<a href="{store}" target="_blank" rel="noopener noreferrer">{html_escape(deal["name"])}</a>'
        f"</div>{_render_share_button(share_payload)}</div></td></tr>\n"
    )


def _render_top_pick_card(
    top_pick: dict,
    *,
    source_deal: dict | None = None,
    historical_lows: dict[str, dict] | None = None,
) -> str:
    header = HEADER_URL.format(appid=top_pick["appid"])
    store = STORE_URL.format(appid=top_pick["appid"])
    metacritic_score = top_pick.get("metacritic_score")
    source_deal = source_deal or {}
    historical_lows = historical_lows or {}
    low = historical_lows.get(top_pick["appid"])
    min_hist = f"${low['price']:.0f}" if low else ""
    share_payload = _build_share_payload(
        name=top_pick["name"],
        appid=top_pick["appid"],
        price=str(top_pick.get("price_final") or source_deal.get("price_final") or ""),
        original_price=str(
            top_pick.get("price_original")
            or source_deal.get("price_original")
            or top_pick.get("price_final")
            or ""
        ),
        discount=int(top_pick.get("discount") or 0),
        min_hist=min_hist,
    )
    metacritic_html = (
        f'<div style="font-size:.75rem;color:#8f98a0;margin-top:.15rem">Metacritic {metacritic_score}</div>'
        if metacritic_score is not None
        else ""
    )
    score_title = html_escape(_SCORE_EXPLANATION)
    return (
        f'<div class="share-card">'
        f'<a href="{store}" target="_blank" rel="noopener noreferrer" '
        f'style="text-decoration:none;color:inherit;display:flex;flex-direction:column">'
        f'<img src="{header}" style="width:100%;aspect-ratio:460/215;object-fit:cover" loading="lazy">'
        f'<div class="share-card-body">'
        f'<div style="font-size:1.2rem;font-weight:bold;color:#66c0f4" title="{score_title}">'
        f'Score {top_pick["score"]}</div><div style="font-size:.8rem;margin:.2rem 0">{html_escape(top_pick["name"])}</div>'
        f'<div style="font-size:.8rem"><span style="color:#6cc644">-{top_pick["discount"]}%</span> '
        f"{html_escape(top_pick['price_final'])}</div>{metacritic_html}</div></a>"
        f'<div class="share-card-actions">{_render_share_button(share_payload)}</div>'
        f"</div>"
    )


def _render_steam_capsule_thumb(appid: str, name: str, class_name: str) -> str:
    if not appid.isdigit():
        return ""
    safe_name = html_escape(name)
    return (
        f'<a class="{class_name}" href="{STORE_URL.format(appid=appid)}" '
        f'target="_blank" rel="noopener noreferrer" aria-label="Abrir {safe_name} en Steam">'
        f'<img src="{CAPSULE_URL.format(appid=appid)}" alt="" loading="lazy" '
        'onerror="this.style.display=\'none\'">'
        '</a>'
    )


def _render_collection_item(item: dict) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    name = str(item.get("name") or item.get("steam_name") or "Juego desconocido")
    reason = str(item.get("reason") or "Recomendado por las señales del reporte.")
    score = item.get("score")
    discount = _safe_int(item.get("discount"))
    price_final = str(item.get("price_final") or item.get("price") or "")
    name_html = (
        f'<a href="{STORE_URL.format(appid=appid)}" target="_blank" rel="noopener noreferrer">'
        f"{html_escape(name)}</a>"
        if appid.isdigit()
        else html_escape(name)
    )
    score_html = (
        f'<span class="collection-score">Score {html_escape(str(score))}</span>'
        if score not in (None, "")
        else ""
    )
    discount_html = (
        f'<span class="collection-discount">-{discount}%</span>' if discount else ""
    )
    price_html = (
        f'<span class="collection-price">{html_escape(price_final)}</span>'
        if price_final
        else ""
    )
    meta_html = "".join(part for part in (score_html, discount_html, price_html) if part)
    share_html = ""
    if appid.isdigit():
        share_payload = _build_share_payload(
            name=name,
            appid=appid,
            price=price_final,
            original_price=str(item.get("price_original") or price_final),
            discount=discount,
            min_hist=str(item.get("min_hist") or item.get("historical_low") or ""),
        )
        share_html = (
            f'<div class="collection-share">{_render_share_button(share_payload)}</div>'
        )
    item_main = (
        f'<div><strong>{name_html}</strong>'
        f'<div class="collection-item-reason">{html_escape(reason)}</div></div>'
    )
    thumb_html = _render_steam_capsule_thumb(appid, name, "collection-item-thumb")
    return f'''<li class="recommended-collection-item">
  {thumb_html}
  <div class="collection-item-body">
    <div class="collection-item-main">
      {item_main}
      <div class="collection-item-meta">{meta_html}</div>
    </div>
    {share_html}
  </div>
</li>'''


def _render_recommended_collections(collections: list[dict]) -> str:
    collection_cards: list[str] = []
    for collection in collections or []:
        if not isinstance(collection, dict):
            continue
        items = [item for item in collection.get("items", []) if isinstance(item, dict)]
        if not items:
            continue
        collection_id = str(collection.get("id") or "collection")
        title = str(collection.get("title") or collection.get("label") or "Colección")
        description = str(
            collection.get("description") or "Juegos agrupados con señales ya calculadas."
        )
        items_html = "".join(_render_collection_item(item) for item in items)
        collection_id_html = html_escape(collection_id)
        collection_cards.append(f'''<article class="recommended-collection-card" data-recommended-collection="{collection_id_html}">
  <h3>{html_escape(title)}</h3>
  <p>{html_escape(description)}</p>
  <ol>{items_html}</ol>
</article>''')
    if not collection_cards:
        return ""
    return f'''<section class="recommended-collections" data-recommended-collections-section>
  <h2 style="margin:1rem 0 .35rem">Colecciones recomendadas</h2>
  <p>Secciones curadas con datos ya calculados del reporte: score, descuento, compatibilidad, reviews y géneros/etiquetas disponibles.</p>
  <div class="recommended-collections-grid">{"".join(collection_cards)}</div>
</section>'''


def _render_personalized_profile(profile: dict) -> str:
    if not isinstance(profile, dict):
        return ""
    chips: list[str] = []
    activity_terms = [
        str(term.get("term") or "").strip()
        for term in profile.get("activity_terms", [])
        if isinstance(term, dict) and term.get("term")
    ][:3]
    if activity_terms:
        chips.append(f"Actividad: {', '.join(activity_terms)}")
    chips.extend(_activity_summary_chips(profile.get("activity_summary") or {}))
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
    return f'''<div class="personalized-profile">{"".join(f'<span>{html_escape(chip)}</span>' for chip in chips)}</div>'''


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
        chips.append(f"Actividad local: {' · '.join(hours_parts)}")
    for item in summary.get("top_played", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        total = _profile_positive_number(item.get("total_hours"))
        if name and total:
            chips.append(f"Más jugado: {name} ({total:.1f}h)")
            break
    return chips


def _render_personalized_meta(item: dict) -> str:
    meta: list[str] = []
    personalized_score = item.get("personalized_score")
    if not isinstance(personalized_score, bool) and isinstance(
        personalized_score, (int, float)
    ):
        meta.append(f"Personal {personalized_score}")
    affinity_score = item.get("affinity_score")
    if not isinstance(affinity_score, bool) and isinstance(affinity_score, (int, float)):
        meta.append(f"Afinidad +{affinity_score}")
    discount = _safe_int(item.get("discount"))
    if discount:
        meta.append(f"-{discount}%")
    price_final = str(item.get("price_final") or item.get("price") or "")
    if price_final:
        meta.append(price_final)
    if not meta:
        return ""
    return f'''<div class="personalized-meta">{"".join(f'<span>{html_escape(part)}</span>' for part in meta)}</div>'''


def _behavioral_explanation_appid(item: dict | None) -> str:
    if not isinstance(item, dict):
        return ""
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    return appid if appid.isdigit() else ""


def _behavioral_explanations_by_appid(payload: dict | None) -> dict[str, dict]:
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != "behavioral_explanations_v1"
    ):
        return {}
    raw_items = payload.get("items")
    items = raw_items if isinstance(raw_items, list) else []
    explanations: dict[str, dict] = {}
    for item in (entry for entry in items if isinstance(entry, dict)):
        appid = _behavioral_explanation_appid(item)
        if appid and appid not in explanations:
            explanations[appid] = item
    return explanations


def _render_personalized_behavioral_explanation(explanation: dict | None) -> str:
    if not isinstance(explanation, dict):
        return ""
    confidence = str(explanation.get("confidence") or "").strip().lower()
    title = (
        "Por qué podría gustarte"
        if confidence in {"medium", "high"}
        else "Señales de estilo del juego"
    )
    headline = str(explanation.get("headline") or "").strip()
    raw_reasons = (
        explanation.get("reasons")
        if isinstance(explanation.get("reasons"), list)
        else []
    )
    raw_cues = (
        explanation.get("supporting_cues")
        if isinstance(explanation.get("supporting_cues"), list)
        else []
    )
    reasons = [str(reason).strip() for reason in raw_reasons if str(reason).strip()][:2]
    cue_labels = [
        str(cue.get("label") or "").strip()
        for cue in raw_cues
        if isinstance(cue, dict) and str(cue.get("label") or "").strip()
    ][:3]
    if not headline and not reasons and not cue_labels:
        return ""
    headline_html = f"<p>{html_escape(headline)}</p>" if headline else ""
    reasons_html = "".join(f"<li>{html_escape(reason)}</li>" for reason in reasons)
    reasons_block = f"<ul>{reasons_html}</ul>" if reasons_html else ""
    cues_html = "".join(f"<span>{html_escape(label)}</span>" for label in cue_labels)
    cues_block = (
        f'<div class="personalized-behavioral-cues">{cues_html}</div>'
        if cues_html
        else ""
    )
    return f'''<div class="personalized-behavioral-note">
    <strong>{html_escape(title)}</strong>
    {headline_html}
    {reasons_block}
    {cues_block}
    <small>Señal advisory: no cambia score ni ranking.</small>
  </div>'''


def _render_personalized_item(
    item: dict,
    index: int,
    behavioral_explanation: dict | None = None,
) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    safe_appid = appid if appid.isdigit() else ""
    name = str(item.get("name") or item.get("steam_name") or "Juego desconocido")
    name_html = (
        f'<a href="{STORE_URL.format(appid=safe_appid)}" target="_blank" rel="noopener noreferrer">'
        f"{html_escape(name)}</a>"
        if safe_appid
        else html_escape(name)
    )
    reasons = [str(reason) for reason in item.get("reasons", []) if str(reason).strip()]
    reasons_html = "".join(
        f"<li>{html_escape(reason)}</li>"
        for reason in (reasons[:3] or ["score base del reporte"])
    )
    share_html = ""
    if safe_appid:
        price_final = str(item.get("price_final") or item.get("price") or "")
        share_payload = _build_share_payload(
            name=name,
            appid=safe_appid,
            price=price_final,
            original_price=str(item.get("price_original") or price_final),
            discount=_safe_int(item.get("discount")),
            min_hist=str(item.get("min_hist") or item.get("historical_low") or ""),
        )
        share_html = f'<div class="personalized-share">{_render_share_button(share_payload)}</div>'
    data_attr = (
        f' data-personalized-recommendation="{html_escape(safe_appid)}"'
        if safe_appid
        else ""
    )
    thumb_html = _render_steam_capsule_thumb(safe_appid, name, "personalized-item-thumb")
    behavioral_html = _render_personalized_behavioral_explanation(behavioral_explanation)
    return f'''<article class="personalized-recommendation-card"{data_attr}>
  <div class="personalized-rank">#{index}</div>
  {thumb_html}
  <h3>{name_html}</h3>
  {_render_personalized_meta(item)}
  <ul class="personalized-reasons">{reasons_html}</ul>
  {behavioral_html}
  {share_html}
</article>'''


def _render_personalized_recommendations(
    payload: dict | None,
    behavioral_explanations: dict | None = None,
) -> str:
    if not isinstance(payload, dict):
        return ""
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    if not items:
        return ""
    explanations_by_appid = _behavioral_explanations_by_appid(behavioral_explanations)
    cards = "".join(
        _render_personalized_item(
            item,
            index,
            explanations_by_appid.get(_behavioral_explanation_appid(item)),
        )
        for index, item in enumerate(items, 1)
    )
    return f'''<section class="personalized-recommendations" data-personalized-recommendations-section>
  <h2 style="margin:1rem 0 .35rem">Recomendaciones personalizadas</h2>
  <p>Ranking explicable con score del reporte y señales opcionales de actividad, biblioteca y preferencias. No cambia el score global.</p>
  {_render_personalized_profile(payload.get("profile") or {})}
  <div class="personalized-recommendations-grid">{cards}</div>
</section>'''


def _gift_social_reasons(item: dict, *, limit: int = 2) -> list[str]:
    reasons = item.get("social_reasons") if isinstance(item, dict) else None
    if not isinstance(reasons, list):
        reasons = item.get("reasons") if isinstance(item, dict) else None
    if not isinstance(reasons, list):
        reason = str(item.get("reason") or "").strip() if isinstance(item, dict) else ""
        return [reason] if reason else []
    compact: list[str] = []
    for reason in reasons:
        text = str(reason or "").strip()
        if text and text not in compact:
            compact.append(text)
        if len(compact) >= limit:
            break
    return compact


def _render_gift_meta(item: dict) -> str:
    meta: list[str] = []
    discount = _safe_int(item.get("discount"))
    if discount:
        meta.append(f"-{discount}%")
    price_final = str(item.get("price_final") or item.get("price") or "")
    if price_final:
        meta.append(price_final)
    if not meta:
        return ""
    return f'''<div class="gift-meta">{"".join(f'<span>{html_escape(part)}</span>' for part in meta)}</div>'''


def _render_gift_idea_item(item: dict, index: int) -> str:
    appid = str(item.get("appid") or item.get("steam_appid") or "").strip()
    safe_appid = appid if appid.isdigit() else ""
    name = str(item.get("name") or item.get("steam_name") or "Juego desconocido")
    name_html = (
        f'<a href="{STORE_URL.format(appid=safe_appid)}" target="_blank" rel="noopener noreferrer">'
        f"{html_escape(name)}</a>"
        if safe_appid
        else html_escape(name)
    )
    reasons = _gift_social_reasons(item)
    reasons_html = "".join(
        f"<li>{html_escape(reason)}</li>"
        for reason in (reasons or ["lo tiene en wishlist y está en oferta"])
    )
    share_html = ""
    if safe_appid:
        price_final = str(item.get("price_final") or item.get("price") or "")
        share_payload = _build_share_payload(
            name=name,
            appid=safe_appid,
            price=price_final,
            original_price=str(item.get("price_original") or price_final),
            discount=_safe_int(item.get("discount")),
            min_hist=str(item.get("min_hist") or item.get("historical_low") or ""),
        )
        share_html = f'<div class="gift-share">{_render_share_button(share_payload)}</div>'
    data_attr = f' data-gift-idea="{html_escape(safe_appid)}"' if safe_appid else ""
    return f'''<article class="gift-idea-card"{data_attr}>
  <div class="gift-rank">#{index}</div>
  <h3>{name_html}</h3>
  {_render_gift_meta(item)}
  <ul class="gift-reasons">{reasons_html}</ul>
  {share_html}
</article>'''


def _render_gift_ideas(gift_ideas: list[dict] | None, compare_data: dict | None) -> str:
    items = [item for item in gift_ideas or [] if isinstance(item, dict)]
    if not items:
        return ""
    friend = ""
    if isinstance(compare_data, dict):
        friend = str(
            compare_data.get("friend_name") or compare_data.get("friend_vanity") or ""
        ).strip()
    friend_copy = f" para {friend}" if friend else ""
    cards = "".join(
        _render_gift_idea_item(item, index) for index, item in enumerate(items[:6], 1)
    )
    hidden_count = max(0, len(items) - 6)
    hidden_html = (
        f'<p>{hidden_count} idea(s) más en el reporte completo.</p>'
        if hidden_count
        else ""
    )
    return f'''<section class="gift-ideas" data-gift-ideas-section>
  <h2 style="margin:1rem 0 .35rem">Gift Ideas{html_escape(friend_copy)}</h2>
  <p>Regalos desde la wishlist comparada, con razones sociales compactas. No abre carrito ni compra nada.</p>
  <div class="gift-ideas-grid">{cards}</div>
  {hidden_html}
</section>'''


def _render_shared_gift_idea_item(item: dict, index: int) -> str:
    friend_labels = item.get("friend_labels") or []
    wanted_by_count = _safe_int(item.get("wanted_by_count"))
    if friend_labels:
        friend_copy = ", ".join(str(label) for label in friend_labels)
    else:
        friend_copy = f"{wanted_by_count or 'Varios'} amigos"
    return _render_gift_idea_item(
        {**item, "social_reasons": _gift_social_reasons(item)}, index
    ).replace(
        '<ul class="gift-reasons">',
        f'<div class="gift-friends">{html_escape(friend_copy)}</div><ul class="gift-reasons">',
        1,
    )


def _render_multi_profile_summary(compare_profiles: list[dict] | None) -> str:
    counts = compare_profile_counts(compare_profiles)
    if not counts["total"]:
        return ""
    summary = f"{counts['available']} perfiles disponibles"
    if counts["unavailable"]:
        summary += f" · {counts['unavailable']} no disponibles"
    return f'<p class="gift-group-summary">{html_escape(summary)}</p>'


def _render_gift_group(
    *,
    title: str,
    description: str,
    rows: list[dict],
    empty_message: str,
    shared: bool = False,
) -> str:
    if rows:
        renderer = _render_shared_gift_idea_item if shared else _render_gift_idea_item
        cards = "".join(renderer(row, index) for index, row in enumerate(rows[:6], 1))
        hidden_count = max(0, len(rows) - 6)
        hidden_html = (
            f'<p class="gift-group-more">{hidden_count} idea(s) más en el reporte completo.</p>'
            if hidden_count
            else ""
        )
        body = f'<div class="gift-ideas-grid">{cards}</div>{hidden_html}'
    else:
        body = f'<p class="gift-empty">{html_escape(empty_message)}</p>'
    return f'''<div class="gift-group">
  <h3>{html_escape(title)}</h3>
  <p>{html_escape(description)}</p>
  {body}
</div>'''


def _render_multi_profile_gifts(
    compare_profiles: list[dict] | None,
    gift_ideas_by_friend: list[dict] | None,
    shared_gift_ideas: list[dict] | None,
) -> str:
    sections: list[str] = []
    shared_rows = normalize_shared_gift_idea_rows(shared_gift_ideas)
    if shared_rows or shared_gift_ideas:
        sections.append(
            _render_gift_group(
                title="Ideas compartidas",
                description="Juegos en oferta que quieren 2+ amigos.",
                rows=shared_rows,
                empty_message="Hay datos de regalos compartidos, pero no hay items concretos para mostrar.",
                shared=True,
            )
        )

    friend_groups = normalize_gift_idea_groups(gift_ideas_by_friend)
    for group in friend_groups:
        friend_label = str(group["friend_label"])
        sections.append(
            _render_gift_group(
                title=f"Ideas para {friend_label}",
                description=f"Juegos que {friend_label} quiere, están en oferta, y tú no los tienes.",
                rows=group.get("rows") or [],
                empty_message=f"Hay datos de regalos para {friend_label}, pero no hay items concretos para mostrar.",
            )
        )
    if gift_ideas_by_friend and not friend_groups:
        sections.append(
            _render_gift_group(
                title="Ideas por amigo",
                description="Datos multi-perfil recibidos.",
                rows=[],
                empty_message="Hay datos multi-perfil, pero no hay grupos renderizables para mostrar.",
            )
        )
    if not sections:
        return ""
    return f'''<section class="gift-ideas multi-profile-gifts" data-multi-profile-gift-section>
  <h2 style="margin:1rem 0 .35rem">Regalos grupales</h2>
  <p>Sugerencias locales y advisory-only para comparar múltiples amigos. No abre carrito ni compra nada.</p>
  {_render_multi_profile_summary(compare_profiles)}
  {"".join(sections)}
</section>'''


def generate_share_html(
    deals,
    vanity,
    min_discount,
    sale_name="",
    top_picks=None,
    reviews=None,
    deck_compat=None,
    historical_lows=None,
    profile_display_name: str | None = None,
    recommended_collections: list[dict] | None = None,
    personalized_recommendations: dict | None = None,
    gift_ideas: list[dict] | None = None,
    compare_data: dict | None = None,
    compare_profiles: list[dict] | None = None,
    gift_ideas_by_friend: list[dict] | None = None,
    shared_gift_ideas: list[dict] | None = None,
    external_offers: dict | None = None,
    behavioral_explanations: dict | None = None,
):
    """Generate a lightweight shareable HTML page with the deals list."""
    reviews = reviews or {}
    deck_compat = deck_compat or {}
    historical_lows = historical_lows or {}
    top_picks = top_picks or []
    recommended_collections = recommended_collections or []
    personalized_recommendations = personalized_recommendations or {"items": []}
    gift_ideas = gift_ideas or []
    external_offers = external_offers if isinstance(external_offers, dict) else None
    behavioral_explanations = (
        behavioral_explanations if isinstance(behavioral_explanations, dict) else None
    )
    today = date.today().strftime("%Y-%m-%d")
    title = f"Steam Deals — {profile_display_name or vanity}"
    deals_by_appid = {deal["appid"]: deal for deal in deals}
    rows = "".join(
        _render_deal_row(deal, reviews, deck_compat, historical_lows)
        for deal in deals
    )

    picks_html = ""
    if top_picks:
        pick_cards = "".join(
            _render_top_pick_card(
                top_pick,
                source_deal=deals_by_appid.get(top_pick["appid"]),
                historical_lows=historical_lows,
            )
            for top_pick in top_picks[:5]
        )
        picks_html = (
            '<h2 style="margin:1rem 0 .5rem">Juegos destacados</h2>'
            f'<p style="color:#8f98a0;font-size:.78rem;margin:0 0 .55rem">{html_escape(_SCORE_EXPLANATION)}</p>'
            '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.5rem">'
            f"{pick_cards}</div>"
        )

    collections_html = _render_recommended_collections(recommended_collections)
    personalized_html = _render_personalized_recommendations(
        personalized_recommendations,
        behavioral_explanations,
    )
    gift_html = _render_gift_ideas(gift_ideas, compare_data)
    multi_profile_gifts_html = _render_multi_profile_gifts(
        compare_profiles,
        gift_ideas_by_friend,
        shared_gift_ideas,
    )
    external_offers_html = _render_external_offers(external_offers)

    sale_line = f" — {html_escape(sale_name)}" if sale_name else ""
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{html_escape(title)}</title>
<style>{_STYLE}</style>
</head><body>
<h1>&#127918; {html_escape(title)}{sale_line}</h1>
<div class="meta">{today} | {len(deals)} deals (&ge;{min_discount}%) | Precios en MXN</div>
{picks_html}
{personalized_html}
{gift_html}
{multi_profile_gifts_html}
{external_offers_html}
{collections_html}
<h2 style="margin:1rem 0 .5rem">Todos los Deals</h2>
<table><thead><tr><th>%</th><th>Precio</th><th>Reseñas</th><th>Compatibilidad</th><th>Juego</th></tr></thead><tbody>{rows}</tbody></table>
<div style="margin-top:1.5rem;text-align:center;color:#8f98a0;font-size:.75rem">Generado con Steam Deals Generator</div>

<!-- Share Modal -->
<div class="share-modal" id="share-modal">
  <div class="share-modal-content">
    <h3>Compartir oferta</h3>
    <div class="share-game-info">
      <div class="share-game-name" id="share-name"></div>
      <div class="share-game-price" id="share-price"></div>
      <div class="share-game-minhist" id="share-minhist"></div>
    </div>
    <div class="share-actions">
      <button class="share-btn share-btn-copy-app" id="btn-copy-app" onclick="copyShareLink()">Copiar link steamtools://</button>
      <button class="share-btn share-btn-copy-steam" onclick="copySteamLink()">Copiar link de Steam</button>
      <button class="share-btn share-btn-open" onclick="openInSteam()">Abrir en Steam</button>
    </div>
    <button type="button" class="share-btn share-btn-close" onclick="closeShareModal()">Cerrar</button>
  </div>
</div>
<script>{_SCRIPT}</script>
</body></html>"""
