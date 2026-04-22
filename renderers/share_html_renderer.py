from __future__ import annotations

from datetime import date
import json

from .common import html_escape


STORE_URL = "https://store.steampowered.com/app/{appid}/"
CAPSULE_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_231x87.jpg"
HEADER_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"

_SCORE_EXPLANATION = (
    "Score = recomendación compuesta para priorizar qué revisar primero."
)


def _build_share_payload(
    *,
    name: str,
    appid: str,
    price: str,
    original_price: str,
    discount: int,
    min_hist: str,
) -> dict[str, object]:
    return {
        "name": name,
        "steam_name": name,
        "appid": appid,
        "price": price,
        "price_final": price,
        "price_original": original_price,
        "original_price": original_price,
        "discount": discount,
        "min_hist": min_hist,
        "min_historical": min_hist,
        "url": STORE_URL.format(appid=appid),
    }


def _share_payload_attr(payload: dict[str, object]) -> str:
    return html_escape(json.dumps(payload, ensure_ascii=False))


def _render_share_button(payload: dict[str, object]) -> str:
    return (
        '<button type="button" class="share-btn-inline" '
        f'data-share-game="{_share_payload_attr(payload)}" '
        'onclick="openShareModal(JSON.parse(this.dataset.shareGame))">'
        '&#128279; Compartir</button>'
    )

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
  const appid = String(source.appid || '').trim();
  if (!appid) return null;
  const name = source.name || source.steam_name || 'Juego desconocido';
  const currentPrice = parseShareMoney(source.price ?? source.price_final);
  const originalPrice = parseShareMoney(source.price_original ?? source.original_price) ?? currentPrice;
  const discount = Number(source.discount || 0) || 0;
  const minHist = parseShareMoney(source.min_hist ?? source.min_historical);
  const steamUrl = source.url || ('https://store.steampowered.com/app/' + appid + '/');
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
      name,
      steam_name: name,
      appid,
      price: priceLabel || '',
      price_final: priceLabel || '',
      price_original: originalLabel || priceLabel || '',
      original_price: originalLabel || priceLabel || '',
      discount,
      min_hist: minHistLabel || '',
      min_historical: minHistLabel || '',
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
    flashShareButton(btn, 'Copiado!', 'Copiar link steamtools://');
  }).catch(() => {
    window.prompt('Copia este link:', shareUrl);
  });
}

function copySteamLink() {
  if (!currentSteamUrl) return;
  copyTextWithFallback(currentSteamUrl).then(() => {
    const btn = document.querySelector('.share-btn-copy-steam');
    flashShareButton(btn, 'Copiado!', 'Copiar link de Steam');
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
        f'<a href="{store}" target="_blank">{html_escape(deal["name"])}</a>'
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
        f'<a href="{store}" target="_blank" '
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
):
    """Generate a lightweight shareable HTML page with the deals list."""
    reviews = reviews or {}
    deck_compat = deck_compat or {}
    historical_lows = historical_lows or {}
    top_picks = top_picks or []
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

    sale_line = f" — {html_escape(sale_name)}" if sale_name else ""
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{html_escape(title)}</title>
<style>{_STYLE}</style>
</head><body>
<h1>&#127918; {html_escape(title)}{sale_line}</h1>
<div class="meta">{today} | {len(deals)} deals (&ge;{min_discount}%) | Precios en MXN</div>
{picks_html}
<h2 style="margin:1rem 0 .5rem">Todos los Deals</h2>
<table><thead><tr><th>%</th><th>Precio</th><th>Reseñas</th><th>Compatibilidad</th><th>Juego</th></tr></thead><tbody>{rows}</tbody></table>
<div style="margin-top:1.5rem;text-align:center;color:#8f98a0;font-size:.75rem">Generado con Steam Deals Generator</div>

<!-- Share Modal -->
<div class="share-modal" id="share-modal">
  <div class="share-modal-content">
    <h3>Compartir Deal</h3>
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
