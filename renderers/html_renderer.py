from __future__ import annotations

from datetime import date
import json
import re

from .common import html_escape


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


def _html_esc(text: str) -> str:
    return html_escape(text)


def _html_link(name: str, appid: str) -> str:
    return f'<a href="{STORE_URL.format(appid=appid)}" target="_blank">{_html_esc(name)}</a>'


def _html_deck_badge(category: int) -> str:
    labels = {
        3: ("Verified", "verified"),
        2: ("Playable", "playable"),
        1: ("Unsupported", "unsupported"),
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


def _build_sparkline_svg(
    snapshots: list[dict], width: int = 80, height: int = 24
) -> str:
    if len(snapshots) < 2:
        return ""
    prices = [s["price_raw"] / 100 for s in snapshots]
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


def _html_budget_pick_context(pick: dict) -> str:
    recommendation = _html_esc(pick.get("recommendation", ""))
    reasons = _html_esc(" · ".join(pick.get("score_reasons", [])))
    if not recommendation and not reasons:
        return ""
    return (
        f'<div class="pick-recommendation" style="margin-top:.25rem">{recommendation}</div>'
        f'<div class="pick-why">{reasons}</div>'
    )


def _html_budget_variant_cards(variants: list[dict], *, selected_variant: str | None) -> str:
    if not variants:
        return ""
    cards = []
    for variant in variants:
        label = _html_esc(variant.get("label") or variant.get("id") or "Variante")
        description = _html_esc(variant.get("description", ""))
        selected_names = [
            _html_esc(item.get("name", ""))
            for item in variant.get("selected", [])[:4]
        ]
        names_text = ", ".join(name for name in selected_names if name)
        extra_count = max(0, len(variant.get("selected", [])) - len(selected_names))
        if extra_count:
            names_text += f" +{extra_count} más"
        selected_badge = (
            '<span style="font-size:.7rem;padding:.12rem .45rem;border-radius:999px;background:var(--accent-blue);color:#000;font-weight:700">Actual</span>'
            if variant.get("id") == selected_variant
            else ""
        )
        border_color = (
            "var(--accent-blue)"
            if variant.get("id") == selected_variant
            else "var(--border)"
        )
        cards.append(
            f'''<div style="background:var(--bg-card);border:1px solid {border_color};border-radius:8px;padding:.75rem .85rem">
  <div style="display:flex;justify-content:space-between;gap:.6rem;align-items:flex-start;margin-bottom:.35rem">
    <strong style="color:var(--text-primary)">{label}</strong>
    {selected_badge}
  </div>
  <div style="font-size:.76rem;color:var(--text-secondary);line-height:1.4;margin-bottom:.45rem">{description}</div>
  <div style="font-size:.76rem;color:var(--text-primary)">{variant.get('games_count', 0)} juegos &middot; ${variant.get('total_spent', 0):.0f} gastados &middot; ${variant.get('remaining', 0):.0f} restante</div>
  <div style="font-size:.74rem;color:var(--text-secondary);margin-top:.35rem">Incluye: {names_text or 'Sin selección disponible'}</div>
</div>'''
        )
    return f'''<div style="margin-top:.95rem">
  <h3 style="font-size:.95rem;margin:0 0 .35rem">&#128257; Probar otra lista</h3>
  <p class="section-desc">El modo presupuesto ahora prepara tres variantes para el mismo tope: lista chica, media y grande.</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.65rem">{"".join(cards)}</div>
</div>'''


def _html_budget_replacements(selected: list[dict]) -> str:
    replacement_groups = []
    for pick in selected:
        replacements = pick.get("replacement_candidates") or []
        if not replacements:
            continue
        options = []
        for replacement in replacements:
            options.append(
                f'<li style="margin:.2rem 0"><strong>{_html_link(replacement["name"], replacement["appid"])}</strong> '
                f'&middot; {_html_esc(replacement.get("price_final", "—"))} '
                f'&middot; Score {_html_esc(str(replacement.get("score", "—")))} '
                f'&middot; Nuevo total: ${replacement.get("swap_total_spent", 0):.0f} '
                f'&middot; Restante: ${replacement.get("swap_remaining", 0):.0f}</li>'
            )
        replacement_groups.append(
            f'''<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:.7rem .8rem">
  <div style="font-size:.82rem;color:var(--text-primary);margin-bottom:.35rem"><strong>{_html_esc(pick.get("name", ""))}</strong></div>
  <div style="font-size:.75rem;color:var(--text-secondary);margin-bottom:.3rem">Opciones para cambiar este juego sin romper el presupuesto:</div>
  <ul style="margin:0;padding-left:1.1rem;font-size:.75rem;color:var(--text-secondary)">{"".join(options)}</ul>
</div>'''
        )
    if not replacement_groups:
        return ""
    return f'''<div style="margin-top:.95rem">
  <h3 style="font-size:.95rem;margin:0 0 .35rem">&#128260; Cambiar este juego</h3>
  <p class="section-desc">Cada bloque propone reemplazos que siguen respetando el mismo presupuesto total.</p>
  <div style="display:grid;gap:.6rem">{"".join(replacement_groups)}</div>
</div>'''


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
.share-close { margin-top: 0.8rem; text-align: center; color: var(--text-secondary); font-size: 0.85rem; cursor: pointer; }
.share-close:hover { color: var(--text-primary); }
"""

_HTML_JS = """
const sortState = {};
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
  const discMin = parseInt(document.getElementById('f-discount').value);
  const priceMax = parseInt(document.getElementById('f-price-max').value);
  const deck = document.getElementById('f-deck').value;
  const revMin = parseInt(document.getElementById('f-reviews').value);
  const search = document.getElementById('f-search').value.toLowerCase();
  const newOnly = document.getElementById('f-new-only').checked;
  let totalV = 0, totalD = 0, totalP = 0;
  document.querySelectorAll('.deals-table tbody tr').forEach(row => {
    const d = row.dataset;
    let show = true;
    if (parseInt(d.discount) < discMin) show = false;
    if (priceMax < 2000 && parseFloat(d.price) > priceMax) show = false;
    if (deck !== 'all' && d.deck !== deck) show = false;
    const rv = parseInt(d.review);
    if (rv >= 0 && rv < revMin) show = false;
    if (search && !d.name.includes(search)) show = false;
    if (newOnly && d.new !== '1') show = false;
    row.style.display = show ? '' : 'none';
    if (show) { totalV++; totalD += parseInt(d.discount); totalP += parseFloat(d.price); }
  });
  const sd = document.getElementById('stat-deals'); if (sd) sd.textContent = totalV.toLocaleString() + ' deals visibles';
  if (totalV > 0) {
    const sa = document.getElementById('stat-avg-disc'); if (sa) sa.textContent = 'Promedio: -' + Math.round(totalD / totalV) + '%';
    const sp = document.getElementById('stat-avg-price'); if (sp) sp.textContent = 'Precio medio: $' + Math.round(totalP / totalV);
  }
  document.querySelectorAll('.tier-section').forEach(s => {
    const t = s.querySelector('.deals-table');
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
document.addEventListener('DOMContentLoaded', () => {
  applyFilters();
  bindShareModalInteractions();
});
function copyForSheets() {
  const rows = [];
  document.querySelectorAll('.deals-table').forEach(table => {
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
    btn.innerHTML = '&#9989; Copiado!';
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
        3: ("#6cc644", "Verified"),
        2: ("#f0b232", "Playable"),
        1: ("#c7322e", "Unsupported"),
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

    compat_html = f"""<div class="dash-card"><h3>&#127918; Deck / ProtonDB</h3>
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
    local_trends: dict[str, dict] | None = None,
    price_history: dict | None = None,
    profile_display_name: str | None = None,
    *,
    group_by_tier,
    group_deals_by_tag,
) -> str:
    del (
        backlog_on_sale,
        have_on_sale,
        owned,
        genres,
        hltb_used,
        family_appids,
        local_trends,
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
    achievements_data = achievements_data or {}
    watchlist_alerts = watchlist_alerts or []
    price_history_games = (price_history or {}).get("games", {})
    has_itad = bool(historical_lows)
    has_best = bool(current_prices)
    has_ach = bool(achievements_data)
    has_sparklines = bool(price_history_games)
    deals_by_appid = {deal["appid"]: deal for deal in deals}

    total_deals = len(deals)
    avg_disc = sum(d["discount"] for d in deals) / total_deals if total_deals else 0
    avg_price = (
        sum(_html_price_raw(d["price_final"]) for d in deals) / total_deals
        if total_deals
        else 0
    )
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
        f'<span class="pill" id="stat-avg-disc">Promedio: -{avg_disc:.0f}%</span>',
        f'<span class="pill" id="stat-avg-price">Precio medio: ${avg_price:.0f}</span>',
        f'<span class="pill">{verified} Deck Verified</span>',
    ]
    if new_count:
        pills.append(f'<span class="pill pill-new">{new_count} nuevos</span>')
    parts.append(f"""<header class="stats-bar">
  <h1>Steam Deals &mdash; {_html_esc(vanity)}</h1>
  <div class="stats-meta">{sale_html}{today} | Precios en MXN</div>
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
            original_price = _html_esc(
                str(tp.get("price_original") or source_deal.get("price_original") or tp.get("price_final") or "")
            )
            recommendation = _html_esc(tp.get("recommendation", ""))
            why_text = _html_esc(" · ".join(tp.get("score_reasons", [])))
            why_html = (
                f'<div class="pick-recommendation">{recommendation}</div><div class="pick-why">{why_text}</div>'
                if recommendation or why_text
                else ""
            )
            share_payload = _build_share_payload(
                name=tp["name"],
                appid=tp["appid"],
                price=str(tp.get("price_final") or ""),
                original_price=original_price,
                discount=int(tp.get("discount") or 0),
                min_hist=min_hist_str,
            )
            cards.append(f'''<div class="pick-card {rank_cls}">
  <a href="{store_url}" target="_blank" style="display:block">
    <img class="pick-img" src="{header_img}" alt="" loading="lazy" onerror="this.style.display='none'">
    <div class="pick-body">
      <div class="pick-rank">#{idx}</div>
      <div class="pick-score" title="Score = recomendación compuesta para priorizar qué revisar primero.">Score {_html_esc(str(tp["score"]))}</div>
      <div class="pick-name">{_html_esc(tp["name"])}{prio_html}</div>
      <div class="pick-details"><span class="pick-discount">-{tp["discount"]}%</span><span class="pick-price">{_html_esc(tp["price_final"])}</span></div>
      <div class="pick-meta">{rev_html} &middot; {mc_html} &middot; {dk_html} &middot; {mp_html}</div>
      {why_html}
    </div>
  </a>
  {_html_share_button(share_payload)}
</div>''')
        parts.append(f"""<section class="top-picks">
  <h2>&#127942; Top {len(top_picks)} Picks</h2>
  <p class="section-desc">Score = recomendación compuesta para priorizar qué revisar primero. Combina reviews (26%) + descuento (22%) + prioridad (18%) + $/hora HLTB (14%) + Deck (10%) + Metacritic (5%) + antigüedad (5%).</p>
  <div class="picks-grid">{"".join(cards)}</div>
</section>""")

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
        selected_variant = budget_data.get("selected_variant")
        variants = budget_data.get("variants") or []
        pct_used = (
            budget_data["total_spent"] / budget_data["budget"] * 100
            if budget_data["budget"] > 0
            else 0
        )
        budget_rows = ""
        for idx, pick in enumerate(budget_data["selected"], 1):
            capsule = CAPSULE_URL.format(appid=pick["appid"])
            pick_context = _html_budget_pick_context(pick)
            budget_rows += f'''<tr>
  <td>{idx}</td><td>{pick.get("score", "—")}</td><td>-{pick["discount"]}%</td>
  <td>{_html_esc(pick["price_final"])}</td>
  <td><div class="game-cell"><img class="game-thumb" src="{capsule}" alt="" loading="lazy" onerror="this.style.display='none'"><span>{_html_link(pick["name"], pick["appid"])}{pick_context}</span></div></td>
</tr>'''
        variant_cards_html = _html_budget_variant_cards(
            variants, selected_variant=selected_variant
        )
        replacements_html = _html_budget_replacements(budget_data.get("selected", []))
        parts.append(f"""<section style="margin-bottom:1.5rem">
  <h2>&#128176; Tu Presupuesto Ideal &mdash; ${budget_data["budget"]:.0f} MXN</h2>
  <p class="section-desc">Con ${budget_data["budget"]:.0f} MXN puedes comprar {budget_data["games_count"]} juegos &middot; Ahorro: ${budget_data["total_savings"]:.0f} &middot; Restante: ${budget_data["remaining"]:.0f}</p>
  <div style="background:var(--bg-secondary);border-radius:6px;height:24px;margin-bottom:.8rem;overflow:hidden;position:relative">
    <div style="height:100%;width:{pct_used:.0f}%;background:linear-gradient(90deg,var(--accent-blue),#4b9cd3);border-radius:6px"></div>
    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:600;color:var(--text-primary)">${budget_data["total_spent"]:.0f} / ${budget_data["budget"]:.0f} ({pct_used:.0f}%)</div>
  </div>
  <div class="table-wrap"><table class="deals-table"><thead><tr><th>#</th><th>Score</th><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>{budget_rows}</tbody></table></div>
  {variant_cards_html}
  {replacements_html}
</section>""")

    if compare_data:
        friend = compare_data.get("friend_vanity", "?")
        overlap = compare_data.get("overlap", set())
        overlap_deals = [d for d in deals if d["appid"] in overlap]
        comp_html = f"""<section style="margin-bottom:1.5rem">
  <h2>&#128101; Wishlist Comparison &mdash; {_html_esc(friend)}</h2>
  <p class="section-desc">{len(overlap)} juegos en com&uacute;n"""
        if overlap_deals:
            comp_html += f" &middot; {len(overlap_deals)} en oferta"
        comp_html += "</p>"
        if overlap_deals:
            ol_rows = ""
            for d in sorted(overlap_deals, key=lambda x: -x["discount"])[:20]:
                capsule = CAPSULE_URL.format(appid=d["appid"])
                ol_rows += f'<tr><td>-{d["discount"]}%</td><td>{_html_esc(d["price_final"])}</td><td><div class="game-cell"><img class="game-thumb" src="{capsule}" alt="" loading="lazy" onerror="this.style.display=\'none\'"><span>{_html_link(d["name"], d["appid"])}</span></div></td></tr>'
            comp_html += f'<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">En com&uacute;n y en oferta</h3><div class="table-wrap"><table class="deals-table"><thead><tr><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>{ol_rows}</tbody></table></div>'
        gift_ideas_list = gift_ideas or []
        if gift_ideas_list:
            gi_rows = ""
            for game in gift_ideas_list[:20]:
                capsule = CAPSULE_URL.format(appid=game["appid"])
                gi_rows += f'<tr><td>-{game["discount"]}%</td><td>{_html_esc(game["price_final"])}</td><td><div class="game-cell"><img class="game-thumb" src="{capsule}" alt="" loading="lazy" onerror="this.style.display=\'none\'"><span>{_html_link(game["name"], game["appid"])}</span></div></td></tr>'
            comp_html += f'<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">&#127873; Gift Ideas para {_html_esc(friend)}</h3><div class="table-wrap"><table class="deals-table"><thead><tr><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>{gi_rows}</tbody></table></div>'
        comp_html += "</section>"
        parts.append(comp_html)

    parts.append(f'''<details open class="filter-panel">
  <summary>&#128269; Filtros</summary>
  <div class="filter-grid">
    <div class="filter-group"><label>Buscar juego</label><input type="text" id="f-search" placeholder="Nombre..." oninput="applyFilters()"></div>
    <div class="filter-group"><label>Descuento min: <output id="f-disc-val">{min_discount}%</output></label><input type="range" id="f-discount" min="50" max="100" value="{min_discount}" oninput="document.getElementById('f-disc-val').textContent=this.value+'%';applyFilters()"></div>
    <div class="filter-group"><label>Precio max: <output id="f-price-val">Sin limite</output></label><input type="range" id="f-price-max" min="0" max="2000" value="2000" step="10" oninput="document.getElementById('f-price-val').textContent=this.value>=2000?'Sin limite':'$'+this.value;applyFilters()"></div>
    <div class="filter-group"><label>Steam Deck</label><select id="f-deck" onchange="applyFilters()"><option value="all">Todos</option><option value="3">Verified</option><option value="2">Playable</option><option value="1">Unsupported</option></select></div>
    <div class="filter-group"><label>Reviews min: <output id="f-rev-val">0%</output></label><input type="range" id="f-reviews" min="0" max="100" value="0" oninput="document.getElementById('f-rev-val').textContent=this.value+'%';applyFilters()"></div>
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
            ("Era", "price"),
            ("Reviews", "num"),
            ("MC", "num"),
            ("Deck", "text"),
            ("Modo", "text"),
        ]
        if has_ach:
            cols.append(("Logros", "num"))
        if has_sparklines:
            cols.append(("Tendencia local", "text"))
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
                game_hist = price_history_games.get(appid, {})
                snaps = game_hist.get("snapshots", [])
                spark = _build_sparkline_svg(snaps) if len(snaps) >= 2 else "—"
                cells.append(f"<td>{spark}</td>")
            if has_itad:
                low = historical_lows.get(appid)
                if low:
                    low_txt = f"${low['price']:.0f} ({low['date']})"
                    cells.append(f"<td>{_html_esc(low_txt)}</td>")
                else:
                    cells.append("<td>—</td>")
            if has_best:
                bp = current_prices.get(appid)
                if bp:
                    bp_html = f'${bp["price"]:.0f} en <a href="{bp["url"]}" target="_blank">{_html_esc(bp["store"])} </a>'
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
                f"<span{desc_attr}>{_html_link(d['name'], appid)}{_html_prio_badge(prio)}</span>"
                f'{_html_share_button(share_payload, style="margin-left:.4rem;position:relative;top:-1px")}'
                f"</div>"
            )
            cells.append(f"<td>{name_html}</td>")

            data_attrs = f'data-discount="{d["discount"]}" data-price="{price_num}" data-deck="{dk}" data-review="{rev_pct}" data-name="{_html_esc(d["name"].lower())}" data-new="{"1" if is_new else "0"}"'
            rows.append(f"<tr {data_attrs}>{''.join(cells)}</tr>")

        note_parts = []
        if has_sparklines:
            note_parts.append(
                "Tendencia local = cómo se movió el precio de cada juego en tus corridas previas."
            )
        if has_itad:
            note_parts.append(
                "Mín. histórico = mejor precio detectado antes en Steam."
            )
        note_html = (
            f'<p class="section-desc">{" · ".join(note_parts)}</p>'
            if note_parts
            else ""
        )

        parts.append(f"""<details open class="tier-section">
  <summary class="tier-header">{_html_esc(tier_name)} de Descuento <span class="tier-count">(<span class="visible-count">{len(tier_deals)}</span> juegos)</span></summary>
  {note_html}
  <div class="table-wrap"><table class="deals-table" id="t-{tid}"><thead><tr>{ths}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
</details>""")

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Steam Deals &mdash; {_html_esc(profile_display_name or vanity)}</title><style>{_HTML_CSS}</style></head>
<body>
{"".join(parts)}
<div class="share-modal" id="share-modal">
  <div class="share-modal-content">
    <h3>Compartir Deal</h3>
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
    <button type="button" class="share-close" onclick="closeShareModal()">Cerrar</button>
  </div>
</div>
<script>{_HTML_JS}</script>
</body>
</html>"""
