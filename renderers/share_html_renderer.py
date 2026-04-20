from __future__ import annotations

from datetime import date

from .common import html_escape


STORE_URL = "https://store.steampowered.com/app/{appid}/"
CAPSULE_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_231x87.jpg"
HEADER_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"


def _render_deal_row(
    deal: dict, reviews: dict[str, dict], deck_compat: dict[str, int]
) -> str:
    appid = deal["appid"]
    review = reviews.get(appid)
    review_text = f"{review['desc']} ({review['pct']}%)" if review else ""
    deck_text = {3: "Verified", 2: "Playable"}.get(deck_compat.get(appid, 0), "")
    capsule = CAPSULE_URL.format(appid=appid)
    store = STORE_URL.format(appid=appid)
    return (
        f"<tr><td>-{deal['discount']}%</td><td>{html_escape(deal['price_final'])}</td>"
        f"<td>{review_text}</td><td>{deck_text}</td>"
        f'<td><div style="display:flex;align-items:center;gap:.4rem">'
        f'<img src="{capsule}" style="width:80px;height:30px;object-fit:cover;border-radius:3px" '
        f'loading="lazy" onerror="this.style.display=\'none\'">'
        f'<a href="{store}" target="_blank">{html_escape(deal["name"])}</a>'
        f"</div></td></tr>\n"
    )


def _render_top_pick_card(top_pick: dict) -> str:
    header = HEADER_URL.format(appid=top_pick["appid"])
    store = STORE_URL.format(appid=top_pick["appid"])
    metacritic_score = top_pick.get("metacritic_score")
    metacritic_html = (
        f'<div style="font-size:.75rem;color:#8f98a0;margin-top:.15rem">Metacritic {metacritic_score}</div>'
        if metacritic_score is not None
        else ""
    )
    return (
        f'<a href="{store}" target="_blank" '
        f'style="text-decoration:none;color:inherit;background:#16202d;border:1px solid #2a475e;'
        f'border-radius:6px;overflow:hidden;display:flex;flex-direction:column">'
        f'<img src="{header}" style="width:100%;aspect-ratio:460/215;object-fit:cover" loading="lazy">'
        f'<div style="padding:.4rem .6rem"><div style="font-size:1.2rem;font-weight:bold;color:#66c0f4">'
        f'Score {top_pick["score"]}</div><div style="font-size:.8rem;margin:.2rem 0">{html_escape(top_pick["name"])}</div>'
        f'<div style="font-size:.8rem"><span style="color:#6cc644">-{top_pick["discount"]}%</span> '
        f"{html_escape(top_pick['price_final'])}</div>{metacritic_html}</div></a>"
    )


def generate_share_html(
    deals,
    vanity,
    min_discount,
    sale_name="",
    top_picks=None,
    reviews=None,
    deck_compat=None,
    profile_display_name: str | None = None,
):
    """Generate a lightweight shareable HTML page with the deals list."""
    reviews = reviews or {}
    deck_compat = deck_compat or {}
    top_picks = top_picks or []
    today = date.today().strftime("%Y-%m-%d")
    title = f"Steam Deals — {profile_display_name or vanity}"
    rows = "".join(_render_deal_row(deal, reviews, deck_compat) for deal in deals)

    picks_html = ""
    if top_picks:
        pick_cards = "".join(
            _render_top_pick_card(top_pick) for top_pick in top_picks[:5]
        )
        picks_html = (
            '<h2 style="margin:1rem 0 .5rem">Top Picks</h2>'
            '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.5rem">'
            f"{pick_cards}</div>"
        )

    sale_line = f" — {html_escape(sale_name)}" if sale_name else ""
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{html_escape(title)}</title>
<style>{{*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:system-ui,sans-serif;background:#1b2838;color:#c7d5e0;padding:1rem;max-width:1000px;margin:0 auto}}a{{color:#66c0f4;text-decoration:none}}a:hover{{text-decoration:underline}}h1{{font-size:1.3rem;margin-bottom:.3rem}}table{{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:.5rem}}th{{background:#2a475e;padding:.4rem .5rem;text-align:left;border-bottom:2px solid #2a475e}}td{{padding:.35rem .5rem;border-bottom:1px solid #2a475e}}tr:hover{{background:#1a3a5c}}.meta{{color:#8f98a0;font-size:.85rem;margin-bottom:1rem}}.share-modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;align-items:center;justify-content:center}}.share-modal.active{{display:flex}}.share-modal-content{{background:#16202d;border:1px solid #2a475e;border-radius:12px;padding:1.5rem;max-width:420px;width:90%}}.share-modal h3{{color:#66c0f4;margin-bottom:1rem;font-size:1.1rem}}.share-game-info{{background:#1b2838;border-radius:8px;padding:1rem;margin-bottom:1rem}}.share-game-name{{font-weight:600;font-size:1rem;margin-bottom:.5rem}}.share-game-price{{color:#6cc644;font-size:1.2rem;font-weight:700}}.share-game-price span{{text-decoration:line-through;color:#8f98a0;font-weight:400;font-size:.9rem}}.share-game-minhist{{font-size:.8rem;color:#8f98a0;margin-top:.3rem}}.share-game-minhist span{{color:#f0b232}}.share-actions{{display:flex;flex-direction:column;gap:.6rem}}.share-btn{{padding:.6rem 1rem;border-radius:6px;font-size:.85rem;font-weight:600;cursor:pointer;text-align:center}}.share-btn-copy-app{{background:#66c0f4;color:#000;border:none}}.share-btn-copy-app:hover{{background:#4db8e8}}.share-btn-copy-steam{{background:#2a475e;color:#c7d5e0;border:1px solid #2a475e}}.share-btn-copy-steam:hover{{border-color:#66c0f4}}.share-btn-open{{background:#1b2838;color:#8f98a0;border:1px solid #2a475e}}.share-close{{margin-top:.8rem;text-align:center;color:#8f98a0;font-size:.85rem;cursor:pointer}}.share-close:hover{{color:#c7d5e0}}</style>
</head><body>
<h1>&#127918; {html_escape(title)}{sale_line}</h1>
<div class="meta">{today} | {len(deals)} deals (&ge;{min_discount}%) | Precios en MXN</div>
{picks_html}
<h2 style="margin:1rem 0 .5rem">Todos los Deals</h2>
<table><thead><tr><th>%</th><th>Precio</th><th>Reviews</th><th>Deck</th><th>Juego</th></tr></thead><tbody>{rows}</tbody></table>
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
    <div class="share-close" onclick="closeShareModal()">Cerrar</div>
  </div>
</div>
<script>let currentShareData=null,currentSteamUrl='';function encodeSharePayload(data){{const json=JSON.stringify(data||{{}});try{{return btoa(unescape(encodeURIComponent(json)))}}catch(e){{try{{return btoa(json)}}catch(e2){{return ''}}}}}}function copyTextWithFallback(text){{if(!text)return Promise.reject(new Error('empty-text'));if(navigator.clipboard&&typeof navigator.clipboard.writeText==='function'){{return navigator.clipboard.writeText(text)}}return new Promise((resolve,reject)=>{{const textarea=document.createElement('textarea');textarea.value=text;textarea.setAttribute('readonly','');textarea.style.position='fixed';textarea.style.opacity='0';document.body.appendChild(textarea);textarea.select();try{{const ok=document.execCommand('copy');textarea.remove();if(ok)resolve();else reject(new Error('copy-failed'))}}catch(err){{textarea.remove();reject(err)}}}})}}function flashShareButton(button,successLabel,defaultLabel){{if(!button)return;button.textContent=successLabel;setTimeout(()=>{{button.textContent=defaultLabel}},2000)}}function openShareModal(game){{currentShareData=game;currentSteamUrl='https://store.steampowered.com/app/'+game.appid+'/';document.getElementById('share-name').textContent=game.name||'';document.getElementById('share-price').innerHTML=(game.price_original&&game.price?'<span>$'+game.price_original+' </span>':'')+(game.price||'')+(game.discount?' ('+game.discount+'% OFF)':'');document.getElementById('share-minhist').innerHTML=game.min_hist?'Minimo historico: <span>$'+game.min_hist+'</span>':'';document.getElementById('share-modal').classList.add('active')}}function closeShareModal(){{document.getElementById('share-modal').classList.remove('active');currentShareData=null}}function copyShareLink(){{if(!currentShareData)return;const encoded=encodeSharePayload(currentShareData);if(!encoded)return;const shareUrl='steamtools://share?data='+encoded;copyTextWithFallback(shareUrl).then(()=>{{const btn=document.getElementById('btn-copy-app');flashShareButton(btn,'Copiado!','Copiar link steamtools://')}}).catch(()=>{{window.prompt('Copia este link:',shareUrl)}})}}function copySteamLink(){{if(!currentSteamUrl)return;copyTextWithFallback(currentSteamUrl).then(()=>{{const btn=document.querySelector('.share-btn-copy-steam');flashShareButton(btn,'Copiado!','Copiar link de Steam')}}).catch(()=>{{window.prompt('Copia este link de Steam:',currentSteamUrl)}})}}function openInSteam(){{if(currentSteamUrl)window.open(currentSteamUrl,'_blank')}}</script>
</body></html>"""
