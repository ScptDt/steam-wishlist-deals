#!/usr/bin/env python3
"""
Steam Wishlist Deals Generator
Genera un MD con los deals de tu wishlist cruzados con tu HLTB.

Uso:
    python3 steam_deals_generator.py --vanity BG00G
    python3 steam_deals_generator.py --vanity https://steamcommunity.com/id/BG00G/
    python3 steam_deals_generator.py --key TU_KEY --vanity BG00G --discount 60
    python3 steam_deals_generator.py --genre roguelike --genre indie
    python3 steam_deals_generator.py --no-cache        # re-fetch aunque haya caché
    python3 steam_deals_generator.py --family-json ~/familia.json
    python3 steam_deals_generator.py --itad-key TU_ITAD_KEY  # precio mínimo histórico

La Steam API Key es opcional. Sin key: funciona con endpoints públicos (wishlist
debe ser pública). Con key: además muestra juegos propios para limpiar la wishlist.

Config guardada en ~/.config/steam_deals.json tras el primer run interactivo.
"""

import argparse
import csv
import io
import json
import re
import sys
import time
import threading
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path


# ─────────────────────────────────────────────
# COLORES ANSI
# ─────────────────────────────────────────────

class C:
    RST  = "\033[0m"
    BOLD = "\033[1m"
    DIM  = "\033[2m"
    GRN  = "\033[32m"
    YLW  = "\033[33m"
    RED  = "\033[31m"
    CYN  = "\033[36m"

def _safe_symbol(unicode_symbol: str, fallback: str) -> str:
    enc = (sys.stdout.encoding or "utf-8")
    try:
        unicode_symbol.encode(enc)
        return unicode_symbol
    except Exception:
        return fallback

SYM_OK = _safe_symbol("✓", "OK")
SYM_WARN = _safe_symbol("⚠", "!")
SYM_ERR = _safe_symbol("✗", "X")
SYM_TAG = _safe_symbol("🏷️", "[SALE]")
SYM_TARGET = _safe_symbol("🎯", "[ALERT]")
SYM_BUDGET = _safe_symbol("💰", "[BUDGET]")
SYM_GIFT = _safe_symbol("🎁", "[GIFT]")
BAR_FILL = _safe_symbol("█", "#")
BAR_EMPTY = _safe_symbol("░", "-")
EVENT_PREFIX = "__STEAM_EVENT__"
WEB_EVENT_MODE = False

def _ok(msg):   return f"{C.GRN}{SYM_OK}{C.RST}  {msg}"
def _warn(msg): return f"{C.YLW}{SYM_WARN}{C.RST}  {msg}"
def _err(msg):  return f"{C.RED}{SYM_ERR}{C.RST}  {msg}"
def _dim(msg):  return f"{C.DIM}{msg}{C.RST}"
def _bold(msg): return f"{C.BOLD}{msg}{C.RST}"


def emit_event(event_type: str, **payload) -> None:
    if not WEB_EVENT_MODE:
        return
    try:
        msg = {"type": event_type, **payload}
        print(f"{EVENT_PREFIX}{json.dumps(msg, ensure_ascii=False)}", flush=True)
    except Exception:
        # Los eventos son opcionales; nunca deben romper el flujo principal.
        return


# ─────────────────────────────────────────────
# CONFIG FILE (~/.config/steam_deals.json)
# ─────────────────────────────────────────────

CONFIG_FILE = Path.home() / ".config" / "steam_deals.json"


def load_user_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_user_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {_ok(f'Config guardada en {CONFIG_FILE}')}")


# ─────────────────────────────────────────────
# WATCHLIST (PRICE ALERTS)
# ─────────────────────────────────────────────

WATCHLIST_FILE = Path.home() / ".config" / "steam_deals_watchlist.json"


def load_watchlist() -> list[dict]:
    if not WATCHLIST_FILE.exists():
        return []
    try:
        return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_watchlist(items: list[dict]) -> None:
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def handle_watchlist_command(args: list[str]) -> bool:
    """Handle --watchlist subcommands. Returns True if handled (should exit)."""
    if not args:
        # --watchlist with no args = list
        args = ["list"]
    cmd = args[0].lower()
    items = load_watchlist()

    if cmd == "list":
        if not items:
            print(f"  {_dim('Watchlist vacía. Usa --watchlist add APPID PRECIO para agregar.')}")
        else:
            print(f"\n  {_bold('Watchlist Personal')} ({len(items)} juegos)\n")
            print(f"  {'AppID':<10} {'Precio objetivo':>16}  Nombre")
            print(f"  {'─' * 10} {'─' * 16}  {'─' * 30}")
            for w in items:
                print(f"  {w['appid']:<10} ${w['target_price']:>14,.0f}  {w.get('name', '?')}")
        return True

    elif cmd == "add":
        if len(args) < 3:
            print(f"  {_err('Uso: --watchlist add APPID PRECIO')}")
            return True
        appid = args[1]
        try:
            target = float(args[2])
        except ValueError:
            print(f"  {_err(f'Precio inválido: {args[2]}')}")
            return True
        # Fetch game name
        name = appid
        try:
            url = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=basic"
            data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
            info = data.get(appid, {}).get("data", {})
            name = info.get("name", appid)
        except Exception:
            pass
        # Remove existing entry for same appid
        items = [w for w in items if w["appid"] != appid]
        items.append({"appid": appid, "name": name, "target_price": target})
        save_watchlist(items)
        print(f"  {_ok(f'Agregado: {name} (AppID {appid}) — objetivo ${target:.0f} MXN')}")
        return True

    elif cmd == "remove":
        if len(args) < 2:
            print(f"  {_err('Uso: --watchlist remove APPID')}")
            return True
        appid = args[1]
        before = len(items)
        items = [w for w in items if w["appid"] != appid]
        if len(items) < before:
            save_watchlist(items)
            print(f"  {_ok(f'Removido AppID {appid} de la watchlist')}")
        else:
            print(f"  {_warn(f'AppID {appid} no está en la watchlist')}")
        return True

    else:
        print(f"  {_err(f'Subcomando desconocido: {cmd}. Usa: add, remove, list')}")
        return True


def check_watchlist_alerts(deals: list[dict], watchlist: list[dict]) -> list[dict]:
    """Check which watchlist games have hit their target price."""
    deal_map = {d["appid"]: d for d in deals}
    alerts = []
    for w in watchlist:
        deal = deal_map.get(w["appid"])
        if deal and deal.get("price_raw", 0) / 100 <= w["target_price"]:
            alerts.append({
                **deal,
                "target_price": w["target_price"],
            })
    return alerts


# ─────────────────────────────────────────────
# ARGUMENTOS + CONFIG FILE + FALLBACK INTERACTIVO
# ─────────────────────────────────────────────

def get_config():
    parser = argparse.ArgumentParser(description="Steam Wishlist Deals Generator")
    parser.add_argument("--web-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--interactive", action="store_true",
                        help="Habilita prompts en terminal para configurar valores faltantes")
    parser.add_argument("--key",         help="Steam API Key (opcional, habilita sección de juegos propios)")
    parser.add_argument("--vanity",      help="Vanity URL, Steam ID, o link de perfil de Steam")
    parser.add_argument("--hltb",        help="Ruta al CSV de HLTB")
    parser.add_argument("--output",      help="Directorio de salida para los MD")
    parser.add_argument("--discount",    type=int, help="Descuento mínimo %%")
    parser.add_argument("--genre",       nargs="*", metavar="GENRE",
                        help="Géneros de interés (ej. --genre roguelike --genre indie)")
    parser.add_argument("--no-cache",    action="store_true",
                        help="Re-fetch aunque haya caché válida")
    parser.add_argument("--family-json", nargs="?", const="", default=None,
                        help="Ruta al JSON de biblioteca familiar. Sin valor = omitir")
    parser.add_argument("--itad-key",    help="IsThereAnyDeal API Key (para mínimo histórico)")
    # Filtros avanzados
    parser.add_argument("--max-price",       type=float, metavar="N", help="Solo deals bajo N MXN")
    parser.add_argument("--deck-only",       action="store_true", help="Solo Deck Verified o Playable")
    parser.add_argument("--deck-verified",   action="store_true", help="Solo Deck Verified")
    parser.add_argument("--min-reviews",     type=int, metavar="N", help="Solo juegos con >= N%% reviews positivas")
    parser.add_argument("--min-review-count",type=int, metavar="N", help="Solo juegos con >= N reviews totales")
    parser.add_argument("--max-hours",       type=float, metavar="N", help="Solo juegos con HLTB <= N horas")
    parser.add_argument("--top",             type=int, metavar="N", default=10, help="Top N picks (default: 10)")
    parser.add_argument("--sort",            choices=["discount","price","reviews","priority","score"], default="discount", help="Ordenar tiers por campo")
    parser.add_argument("--new-only",        action="store_true", help="Solo deals nuevos vs run anterior")
    parser.add_argument("--csv",             action="store_true", help="Generar CSV para Excel/Sheets")
    parser.add_argument("--watchlist",       nargs="*", metavar="CMD",
                        help="Watchlist: add APPID PRECIO / remove APPID / list")
    parser.add_argument("--budget",          type=float, metavar="MXN",
                        help="Presupuesto en MXN — recomendación óptima de compras")
    parser.add_argument("--compare",         metavar="VANITY2",
                        help="Comparar tu wishlist con otro perfil de Steam")
    parser.add_argument("--telegram-token",  help="Telegram Bot API token para notificaciones")
    parser.add_argument("--telegram-chat",   help="Telegram chat ID para notificaciones")
    parser.add_argument("--discord-webhook", help="Discord webhook URL para notificaciones")
    parser.add_argument("--schedule",        type=float, metavar="HOURS",
                        help="Ejecutar automáticamente cada N horas (ej: --schedule 6)")
    args = parser.parse_args()

    # Handle watchlist subcommand (standalone, exits early)
    if args.watchlist is not None:
        handle_watchlist_command(args.watchlist)
        sys.exit(0)

    cfg = load_user_config()
    local_cache_dir = Path(__file__).resolve().parent / ".cache" / "steam_deals"
    has_local_cache = local_cache_dir.exists() and any(local_cache_dir.iterdir())
    can_prompt = bool(
        not args.web_run
        and sys.stdin
        and sys.stdin.isatty()
        and (args.interactive or not has_local_cache)
    )
    interactive_keys: list[str] = []

    def ask(prompt, default=None):
        if not can_prompt:
            return default or ""
        suffix = f" [{default}]" if default else ""
        try:
            return input(f"  {prompt}{suffix}: ").strip()
        except EOFError:
            return default or ""

    def from_arg_cfg_or_ask(arg_val, cfg_key, prompt, default=None):
        if arg_val is not None:
            return arg_val
        if cfg.get(cfg_key) is not None:
            return cfg[cfg_key]
        if can_prompt:
            interactive_keys.append(cfg_key)
        raw = ask(prompt, default)
        return raw or default or ""

    # Key es opcional — sin key funciona con endpoints públicos
    key    = args.key or cfg.get("key") or None
    vanity = from_arg_cfg_or_ask(args.vanity, "vanity", "Vanity URL, Steam ID, o link de perfil", "BG00G") or "BG00G"

    # HLTB
    if args.hltb:
        hltb = Path(args.hltb).expanduser()
    elif cfg.get("hltb"):
        hltb = Path(cfg["hltb"]).expanduser()
    else:
        if can_prompt:
            interactive_keys.append("hltb")
        raw = ask("Ruta al CSV de HLTB (Enter para omitir)")
        hltb = Path(raw).expanduser() if raw else None

    # Output dir (el nombre del archivo se genera dinámicamente en main)
    script_dir = str(Path(__file__).resolve().parent)
    if args.output:
        output_dir = Path(args.output).expanduser()
    elif cfg.get("output_dir"):
        output_dir = Path(cfg["output_dir"]).expanduser()
    else:
        if can_prompt:
            interactive_keys.append("output_dir")
        raw = ask("Directorio de salida para los MD", script_dir)
        output_dir = Path(raw or script_dir).expanduser()

    # Discount
    if args.discount is not None:
        discount = args.discount
    elif cfg.get("discount") is not None:
        discount = cfg["discount"]
    else:
        if can_prompt:
            interactive_keys.append("discount")
        raw = ask("Descuento mínimo %", "50")
        discount = int(raw) if raw else 50

    # Genres
    if args.genre is not None:
        genres = [g.strip().lower() for g in args.genre if g.strip()]
    elif cfg.get("genres") is not None:
        genres = cfg["genres"]
    else:
        if can_prompt:
            interactive_keys.append("genres")
        raw = ask("Géneros de interés (coma-separados, Enter para omitir)")
        genres = [g.strip().lower() for g in raw.split(",") if g.strip()]

    # Family JSON — avanzado, sin prompt interactivo
    if args.family_json is not None:
        family_json = Path(args.family_json).expanduser() if args.family_json else None
    elif cfg.get("family_json"):
        family_json = Path(cfg["family_json"]).expanduser()
    else:
        family_json = None

    # ITAD Key — sin prompt interactivo
    itad_key = args.itad_key or cfg.get("itad_key") or None

    no_cache = args.no_cache

    # Ofrecer guardar config si se usó algún prompt
    if can_prompt and interactive_keys:
        raw = input("\n  ¿Guardar como configuración por defecto? [s/N]: ").strip().lower()
        if raw == "s":
            save_user_config({
                **cfg,
                "key":         key,
                "vanity":      vanity,
                "hltb":        str(hltb) if hltb else None,
                "output_dir":  str(output_dir),
                "discount":    discount,
                "genres":      genres,
                "family_json": str(family_json) if family_json else None,
                "itad_key":    itad_key,
            })

    filters = {
        "max_price": args.max_price,
        "deck_only": args.deck_only,
        "deck_verified": args.deck_verified,
        "min_reviews": args.min_reviews,
        "min_review_count": args.min_review_count,
        "max_hours": args.max_hours,
        "top": args.top,
        "sort": args.sort,
        "new_only": args.new_only,
        "csv": args.csv,
        "budget": args.budget,
        "compare": args.compare,
        "telegram_token": args.telegram_token or cfg.get("telegram_token"),
        "telegram_chat": args.telegram_chat or cfg.get("telegram_chat"),
        "discord_webhook": args.discord_webhook or cfg.get("discord_webhook"),
        "schedule": args.schedule,
    }

    return args.web_run, args.interactive, key, vanity, hltb, output_dir, discount, genres, no_cache, family_json, itad_key, filters


# ─────────────────────────────────────────────
# STEAM API
# ─────────────────────────────────────────────

def resolve_steam_id(api_key: str | None, vanity: str) -> str:
    """Convierte vanity URL, link de perfil, o Steam ID numérico a Steam ID."""
    # Extraer vanity/ID de URLs de perfil
    m = re.match(r'https?://steamcommunity\.com/profiles/(\d+)', vanity)
    if m:
        return m.group(1)
    m = re.match(r'https?://steamcommunity\.com/id/([^/]+)', vanity)
    if m:
        vanity = m.group(1)

    if vanity.isdigit() and len(vanity) == 17:
        return vanity

    # Con API key: usar endpoint oficial
    if api_key:
        url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={api_key}&vanityurl={vanity}"
        data = _get_json(url)
        if data["response"]["success"] != 1:
            raise ValueError(f"No se pudo resolver el vanity URL: {vanity}")
        return data["response"]["steamid"]

    # Sin key: endpoint público XML
    url = f"https://steamcommunity.com/id/{vanity}/?xml=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        text = r.read().decode("utf-8")
    m = re.search(r'<steamID64>(\d+)</steamID64>', text)
    if not m:
        raise ValueError(f"No se pudo resolver el perfil: {vanity}")
    return m.group(1)


def get_wishlist(api_key: str | None, steam_id: str) -> tuple[list[str], dict[str, int]]:
    """Devuelve (lista de appids, dict appid→priority). Funciona con o sin API key."""
    url = f"https://api.steampowered.com/IWishlistService/GetWishlist/v1/?steamid={steam_id}"
    if api_key:
        url += f"&key={api_key}"
    try:
        data = _get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError(f"No se pudo acceder a la wishlist (HTTP {exc.code}). ¿Es privada?") from exc
        raise
    items = data.get("response", {}).get("items", [])
    appids = [str(item["appid"]) for item in items]
    priorities = {str(item["appid"]): item.get("priority", 0) for item in items}
    return appids, priorities


def get_owned_games(api_key: str, steam_id: str) -> dict[str, str]:
    """Devuelve dict appid → nombre de juegos propios en Steam."""
    url = (
        f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        f"?key={api_key}&steamid={steam_id}&include_appinfo=1&include_played_free_games=1"
    )
    data = _get_json(url)
    return {str(g["appid"]): g["name"] for g in data.get("response", {}).get("games", [])}


def compare_wishlists(api_key, steam_id_1, vanity_2):
    """Compare two wishlists. Returns overlap, unique to each, friend info."""
    friend_id = resolve_steam_id(api_key, vanity_2)
    friend_appids, friend_priorities = get_wishlist(api_key, friend_id)
    my_appids_set = set()  # will be filled by caller
    friend_set = set(friend_appids)
    return {
        "friend_id": friend_id,
        "friend_vanity": vanity_2,
        "friend_appids": friend_appids,
        "friend_priorities": friend_priorities,
        "friend_set": friend_set,
    }


def build_gift_ideas(friend_set, deals, owned):
    """Find deals that the friend wants but you don't own."""
    owned_set = set(owned.keys())
    ideas = []
    for d in deals:
        if d["appid"] in friend_set and d["appid"] not in owned_set:
            ideas.append(d)
    ideas.sort(key=lambda x: -x["discount"])
    return ideas


def load_family_games(json_path: Path) -> set[str]:
    """Carga un JSON de biblioteca familiar → set de appids."""
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return {str(k) for k in raw}
    if isinstance(raw, list):
        return {str(a) for a in raw}
    raise ValueError(f"Formato de family JSON no reconocido: {type(raw)}")


def get_active_sale() -> str:
    """Detecta la oferta/evento activo en Steam via marketing messages API."""
    try:
        url = "https://api.steampowered.com/IMarketingMessagesService/GetActiveMarketingMessages/v1/"
        data = _get_json(url)
        messages = data.get("response", {}).get("messages", [])
        for msg in messages:
            if msg.get("type") == 1:
                title = msg.get("title", "").strip()
                if title:
                    return title
        for msg in messages:
            if msg.get("type") == 11:
                title = msg.get("title", "").strip()
                if title:
                    return title
        for msg in messages:
            title = msg.get("title", "").strip()
            if title:
                return title
    except Exception:
        pass
    return ""


# ─────────────────────────────────────────────
# IsThereAnyDeal API (mínimo histórico)
# ─────────────────────────────────────────────

ITAD_BATCH = 50


def itad_lookup_games(appids: list[str], itad_key: str) -> dict[str, str]:
    """Resuelve Steam appids → ITAD game IDs. Devuelve {appid: itad_id}."""
    result = {}
    for i in range(0, len(appids), ITAD_BATCH):
        batch = appids[i:i + ITAD_BATCH]
        body = [{"type": "steam", "id": f"app/{a}"} for a in batch]
        try:
            data = _post_json(
                f"https://api.isthereanydeal.com/games/lookup/v1?key={itad_key}",
                body,
            )
            if isinstance(data, list):
                for item, appid in zip(data, batch):
                    if item and isinstance(item, dict) and item.get("found"):
                        result[appid] = item["game"]["id"]
        except Exception as exc:
            print(f"\n  {_warn(f'ITAD lookup error: {exc}')}", flush=True)
        time.sleep(0.5)
    return result


def itad_get_store_lows(itad_ids: dict[str, str], itad_key: str, country: str = "MX") -> dict[str, dict]:
    """Obtiene mínimo histórico en Steam. Devuelve {appid: {price, cut, date}}."""
    # Invertir: itad_id → appid
    id_to_appid = {v: k for k, v in itad_ids.items()}
    all_ids = list(itad_ids.values())
    result = {}

    for i in range(0, len(all_ids), ITAD_BATCH):
        batch = all_ids[i:i + ITAD_BATCH]
        try:
            data = _post_json(
                f"https://api.isthereanydeal.com/games/storelow/v2?key={itad_key}&country={country}&shops=61",
                batch,
            )
            if isinstance(data, list):
                for item in data:
                    itad_id = item.get("id", "")
                    appid = id_to_appid.get(itad_id)
                    lows = item.get("lows", [])
                    if appid and lows:
                        low = lows[0]
                        price_obj = low.get("price", {})
                        result[appid] = {
                            "price":    price_obj.get("amount", 0),
                            "currency": price_obj.get("currency", ""),
                            "cut":      low.get("cut", 0),
                            "date":     (low.get("timestamp") or "")[:10],
                        }
        except Exception as exc:
            print(f"\n  {_warn(f'ITAD storelow error: {exc}')}", flush=True)
        time.sleep(0.5)

    return result


def itad_get_current_prices(itad_ids: dict[str, str], itad_key: str, country: str = "MX") -> dict[str, dict]:
    """Current best prices across stores. Returns {appid: {store, price, url}} only when another store beats Steam."""
    id_to_appid = {v: k for k, v in itad_ids.items()}
    all_ids = list(itad_ids.values())
    result = {}

    for i in range(0, len(all_ids), ITAD_BATCH):
        batch = all_ids[i:i + ITAD_BATCH]
        try:
            data = _post_json(
                f"https://api.isthereanydeal.com/games/prices/v3?key={itad_key}&country={country}",
                batch,
            )
            if isinstance(data, list):
                for item in data:
                    itad_id = item.get("id", "")
                    appid = id_to_appid.get(itad_id)
                    if not appid:
                        continue
                    price_deals = item.get("deals", [])
                    steam_price = None
                    best_other = None
                    for pd in price_deals:
                        shop = pd.get("shop", {})
                        shop_id = shop.get("id", 0)
                        price_obj = pd.get("price", {})
                        price_amt = price_obj.get("amount", 0)
                        if shop_id == 61:  # Steam
                            steam_price = price_amt
                        elif best_other is None or price_amt < best_other["price"]:
                            best_other = {
                                "store": shop.get("name", "?"),
                                "price": price_amt,
                                "url": pd.get("url", ""),
                            }
                    if best_other and steam_price is not None and best_other["price"] < steam_price:
                        result[appid] = best_other
        except Exception as exc:
            print(f"\n  {_warn(f'ITAD prices error: {exc}')}", flush=True)
        time.sleep(0.5)

    return result


def itad_get_active_bundles(itad_ids: dict[str, str], itad_key: str, country: str = "US") -> dict[str, list[dict]]:
    """Active bundles containing deal games. Returns {appid: [{title, store, price, currency, url}]}."""
    id_to_appid = {v: k for k, v in itad_ids.items()}
    all_ids = list(itad_ids.values())
    result: dict[str, list[dict]] = {}

    for i in range(0, len(all_ids), ITAD_BATCH):
        batch = all_ids[i:i + ITAD_BATCH]
        try:
            data = _post_json(
                f"https://api.isthereanydeal.com/games/overview/v2?key={itad_key}&country={country}",
                batch,
            )
            bundles = data.get("bundles", []) if isinstance(data, dict) else []
            for bundle in bundles:
                title = bundle.get("title", "")
                page = bundle.get("page", {})
                store = page.get("name", "")
                url = bundle.get("url", "")
                for tier in bundle.get("tiers", []):
                    price_obj = tier.get("price") or {}
                    tier_price = price_obj.get("amount", 0)
                    tier_currency = price_obj.get("currency", "USD")
                    for game in tier.get("games", []):
                        game_id = game.get("id", "")
                        appid = id_to_appid.get(game_id)
                        if not appid:
                            continue
                        entry = {"title": title, "store": store, "price": tier_price,
                                 "currency": tier_currency, "url": url}
                        if appid not in result:
                            result[appid] = []
                        if not any(b["title"] == title for b in result[appid]):
                            result[appid].append(entry)
        except Exception as exc:
            print(f"\n  {_warn(f'ITAD bundles error: {exc}')}", flush=True)
        time.sleep(0.5)

    return result


# ─────────────────────────────────────────────
# COMPARAR CON MD ANTERIOR
# ─────────────────────────────────────────────

def load_previous_deal_appids(output_dir: Path, current_filename: str) -> set[str]:
    """Busca el MD anterior más reciente y extrae los appids de deals."""
    md_files = sorted(output_dir.glob("Steam Deals*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in md_files:
        if f.name == current_filename:
            continue
        try:
            text = f.read_text(encoding="utf-8")
            appids = set(re.findall(r"store\.steampowered\.com/app/(\d+)/", text))
            if appids:
                return appids
        except OSError:
            continue
    return set()


# ─────────────────────────────────────────────
# HISTORIAL DE RUNS
# ─────────────────────────────────────────────


def save_run_history(steam_id: str, vanity: str, sale_name: str,
                     min_discount: int, deals: list[dict]) -> Path:
    """Guarda snapshot del run actual en historial JSON."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now()
    filename = f"run_{ts.strftime('%Y-%m-%d_%H%M%S')}.json"
    entry = {
        "steam_id": steam_id,
        "vanity": vanity,
        "date": date.today().isoformat(),
        "timestamp": ts.isoformat(),
        "sale_name": sale_name,
        "min_discount": min_discount,
        "deals": {
            d["appid"]: {
                "name": d["name"],
                "discount": d["discount"],
                "price_final": d["price_final"],
                "price_raw": d.get("price_raw", 0),
            }
            for d in deals
        },
    }
    path = HISTORY_DIR / filename
    path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
    _prune_history()
    return path


def load_previous_run(steam_id: str) -> dict | None:
    """Carga el run anterior más reciente del historial."""
    if not HISTORY_DIR.exists():
        return None
    files = sorted(HISTORY_DIR.glob("run_*.json"), reverse=True)
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("steam_id") == steam_id:
                return data
        except (json.JSONDecodeError, OSError):
            continue
    return None


def load_run_history(steam_id: str, max_runs: int = 30) -> list[dict]:
    """Carga los últimos N runs para deal streak tracking."""
    if not HISTORY_DIR.exists():
        return []
    files = sorted(HISTORY_DIR.glob("run_*.json"), reverse=True)
    runs = []
    for f in files:
        if len(runs) >= max_runs:
            break
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("steam_id") == steam_id:
                runs.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return runs


def _prune_history():
    """Elimina archivos de historial más allá del máximo."""
    files = sorted(HISTORY_DIR.glob("run_*.json"))
    excess = len(files) - HISTORY_MAX_FILES
    if excess > 0:
        for f in files[:excess]:
            f.unlink(missing_ok=True)


def compute_deal_comparison(
    current_deals: list[dict],
    previous_run: dict | None,
    run_history: list[dict],
) -> dict:
    """Compara deals actuales con run anterior y historial."""
    result = {"price_changes": {}, "new_deals": set(), "disappeared": [], "deal_streak": {}}
    if not previous_run:
        return result

    prev_deals = previous_run.get("deals", {})
    current_appids = {d["appid"] for d in current_deals}
    prev_appids = set(prev_deals.keys())

    result["new_deals"] = current_appids - prev_appids

    # Price changes
    for deal in current_deals:
        appid = deal["appid"]
        if appid not in prev_deals:
            continue
        prev = prev_deals[appid]
        curr_raw = deal.get("price_raw", 0)
        prev_raw = prev.get("price_raw", 0)
        if curr_raw and prev_raw and curr_raw != prev_raw:
            delta = curr_raw - prev_raw
            delta_pesos = abs(delta) / 100
            result["price_changes"][appid] = {
                "delta_raw": delta,
                "delta_str": f"${delta_pesos:.0f}" if delta_pesos >= 1 else f"${delta_pesos:.2f}",
                "prev_price": prev.get("price_final", "?"),
                "direction": "down" if delta < 0 else "up",
            }

    # Disappeared deals
    prev_date = previous_run.get("date", "?")
    for appid in sorted(prev_appids - current_appids):
        info = prev_deals[appid]
        result["disappeared"].append({
            "appid": appid, "name": info.get("name", "?"),
            "discount": info.get("discount", 0), "price_final": info.get("price_final", "?"),
            "last_seen": prev_date,
        })

    # Deal streak
    for deal in current_deals:
        appid = deal["appid"]
        streak = 1
        for past_run in run_history:
            if appid in past_run.get("deals", {}):
                streak += 1
            else:
                break
        result["deal_streak"][appid] = streak

    return result


# ─────────────────────────────────────────────
# HISTORIAL LOCAL DE PRECIOS
# ─────────────────────────────────────────────


def _fmt_mxn(centavos: int) -> str:
    pesos = centavos / 100
    return f"${int(pesos)}" if pesos == int(pesos) else f"${pesos:.2f}"


def load_price_history(steam_id: str) -> dict:
    if not PRICE_HISTORY_FILE.exists():
        return {"version": 1, "steam_id": steam_id, "games": {}}
    try:
        data = json.loads(PRICE_HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "steam_id": steam_id, "games": {}}
    if data.get("steam_id") != steam_id:
        return {"version": 1, "steam_id": steam_id, "games": {}}
    return data


def save_price_history(history: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PRICE_HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")


def log_price_snapshot(history: dict, deals: list[dict]) -> None:
    """Register current run's prices into the history."""
    today_str = date.today().isoformat()
    games = history.setdefault("games", {})
    for deal in deals:
        appid = deal["appid"]
        price_raw = deal.get("price_raw", 0)
        if not price_raw:
            continue
        game_entry = games.setdefault(appid, {"name": deal["name"], "snapshots": []})
        game_entry["name"] = deal["name"]
        # Replace same-day snapshot
        snaps = game_entry["snapshots"]
        snaps[:] = [s for s in snaps if s["date"] != today_str]
        snaps.append({"date": today_str, "discount": deal["discount"], "price_raw": price_raw})
        # Keep max 60 snapshots per game
        if len(snaps) > 60:
            snaps[:] = snaps[-60:]


def analyze_trends(history: dict, deals: list[dict]) -> dict[str, dict]:
    """Analyze price trends for current deals. Returns {appid: trend_info}."""
    games = history.get("games", {})
    result = {}
    today_str = date.today().isoformat()

    for deal in deals:
        appid = deal["appid"]
        price_raw = deal.get("price_raw", 0)
        game_entry = games.get(appid)
        if not game_entry or not price_raw:
            result[appid] = {"times_on_sale": 1, "is_first_time": True}
            continue

        snaps = game_entry.get("snapshots", [])
        prev_snaps = [s for s in snaps if s["date"] != today_str]

        if not prev_snaps:
            result[appid] = {"times_on_sale": 1, "is_first_time": True}
            continue

        times = len(prev_snaps) + 1
        prices = [s["price_raw"] for s in prev_snaps]
        lowest = min(prices)
        avg = round(sum(prices) / len(prices))

        result[appid] = {
            "times_on_sale": times,
            "is_first_time": False,
            "is_best_local": price_raw <= lowest,
            "is_first_at_price": price_raw not in prices,
            "lowest_fmt": _fmt_mxn(lowest),
            "avg_fmt": _fmt_mxn(avg),
            "avg_raw": avg,
        }
    return result


def format_trend(trend: dict) -> str:
    if trend.get("is_first_time"):
        return "🆕 1ra vez"
    if trend.get("is_best_local") and trend.get("times_on_sale", 0) > 1:
        return "🔥 Mín. local"
    if trend.get("is_first_at_price"):
        return f"💰 1ra vez a este precio"
    times = trend.get("times_on_sale", 0)
    avg = trend.get("avg_fmt", "?")
    return f"📊 {times}x · prom {avg}"


# ─────────────────────────────────────────────
# CACHÉ DE PRECIOS (smart partial refresh)
# ─────────────────────────────────────────────

PROJECT_DIR     = Path(__file__).resolve().parent
CACHE_DIR       = PROJECT_DIR / ".cache" / "steam_deals"
CACHE_FILE      = CACHE_DIR / "prices_cache.json"
CACHE_MAX_HOURS = 24
REVIEWS_CACHE_FILE = CACHE_DIR / "reviews_cache.json"
DECK_CACHE_FILE    = CACHE_DIR / "deck_cache.json"
EXTRA_CACHE_TTL    = 168  # 7 days in hours
HISTORY_DIR        = CACHE_DIR / "history"
HISTORY_MAX_FILES  = 100
TAGS_CACHE_FILE    = CACHE_DIR / "tags_cache.json"
TAGS_CACHE_TTL     = 720  # 30 days in hours
PRICE_HISTORY_FILE = CACHE_DIR / "price_history.json"
PROTONDB_CACHE_FILE = CACHE_DIR / "protondb_cache.json"
ANTICHEAT_CACHE_FILE = CACHE_DIR / "anticheat_cache.json"
ACHIEVEMENTS_CACHE_FILE = CACHE_DIR / "achievements_cache.json"
ACHIEVEMENTS_CACHE_TTL  = 720  # 30 days in hours


def load_price_cache(steam_id: str) -> tuple[dict, float]:
    if not CACHE_FILE.exists():
        return {}, float("inf")
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, float("inf")
    if data.get("steam_id") != steam_id:
        return {}, float("inf")
    age_hours = (datetime.now() - datetime.fromisoformat(data["saved_at"])).total_seconds() / 3600
    return data.get("fetched", {}), age_hours


def save_price_cache(steam_id: str, fetched: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps({"steam_id": steam_id, "saved_at": datetime.now().isoformat(), "fetched": fetched},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────
# FETCH DE PRECIOS (batched con fallback)
# ─────────────────────────────────────────────

BATCH_SIZE = 20


def _fetch_single(appid: str, country: str, delay: float) -> dict | None:
    """Fallback: fetch individual de un appid."""
    url = (
        f"https://store.steampowered.com/api/appdetails"
        f"?appids={appid}&cc={country}&filters=price_overview,basic,genres,platforms,release_date,metacritic,categories"
    )
    try:
        data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        time.sleep(delay)
        return data
    except Exception:
        time.sleep(delay)
        return None


def _parse_release_year(date_str: str) -> int | None:
    """Extrae el año de una fecha de Steam (ej. 'Mar 25, 2019' → 2019)."""
    if not date_str:
        return None
    m = re.search(r'((?:19|20)\d{2})', date_str)
    return int(m.group(1)) if m else None


def _process_app_entry(appid: str, data: dict) -> dict | None:
    """Extrae info de precio de la respuesta de appdetails para un appid."""
    app_entry = data.get(appid)
    if not app_entry or not isinstance(app_entry, dict) or not app_entry.get("success"):
        return None
    info = app_entry.get("data", {})
    price_info = info.get("price_overview")
    if not price_info:
        return None
    rd = info.get("release_date", {})
    release_str = rd.get("date", "") if not rd.get("coming_soon") else ""
    # Strip HTML from short_description
    raw_desc = info.get("short_description", "")
    clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()[:120] if raw_desc else ""
    return {
        "name":             info.get("name", ""),
        "type":             info.get("type", "game"),
        "discount_percent": price_info.get("discount_percent", 0),
        "price_final":      price_info.get("final_formatted", ""),
        "price_original":   price_info.get("initial_formatted", ""),
        "price_final_raw":  price_info.get("final", 0),
        "genres":           [g["description"].lower() for g in info.get("genres", [])],
        "release_year":     _parse_release_year(release_str),
        "description":      clean_desc,
        "linux_native":     info.get("platforms", {}).get("linux", False),
        "metacritic_score": info.get("metacritic", {}).get("score"),
        "metacritic_url":   info.get("metacritic", {}).get("url", ""),
        "categories":       [c["id"] for c in info.get("categories", [])],
    }


def get_deals_from_wishlist(
    appids: list[str],
    fetched_cache: dict,
    steam_id: str,
    country: str = "mx",
    min_discount: int = 50,
    rate_limit: float = 1.5,
) -> tuple[list[dict], int]:
    to_fetch = [a for a in appids if a not in fetched_cache]
    total    = len(to_fetch)
    BAR_W    = 25
    delay    = rate_limit

    if total > 0:
        batches = [to_fetch[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
        n_batches = len(batches)
        start = time.monotonic()
        eta_str = f"~{n_batches * delay / 60:.1f} min"
        print(f"  Fetching {total:,} juegos en {n_batches} batches ({eta_str})...", flush=True)

        fetched_count = 0
        for bi, batch in enumerate(batches):
            pct    = fetched_count / total
            filled = int(pct * BAR_W)
            bar    = f"{C.GRN}{BAR_FILL * filled}{C.DIM}{BAR_EMPTY * (BAR_W - filled)}{C.RST}"
            if fetched_count > 0:
                eta_sec = (time.monotonic() - start) / fetched_count * (total - fetched_count)
                eta_str = f"{eta_sec / 60:.1f}m"
            print(f"\r  {bar} {fetched_count:,}/{total:,} ETA {eta_str}  ", end="", flush=True)

            ids_str = ",".join(batch)
            url = (
                f"https://store.steampowered.com/api/appdetails"
                f"?appids={ids_str}&cc={country}&filters=price_overview,basic,genres,platforms,release_date,metacritic,categories"
            )

            backoff = 30
            data    = None
            for attempt in range(4):
                try:
                    data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        print(f"\n  {_warn(f'Rate limit — esperando {backoff}s (intento {attempt+1}/4)')}", flush=True)
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 120)
                        delay = min(delay * 1.5, 5.0)
                        print(f"  {_dim(f'Delay ajustado a {delay:.1f}s entre batches')}", flush=True)
                    else:
                        print(f"\n  {_warn(f'HTTP {e.code} en batch {bi+1}, saltando')}", flush=True)
                        time.sleep(delay)
                        break
                except Exception as exc:
                    print(f"\n  {_warn(f'Error en batch {bi+1}: {exc}')}", flush=True)
                    time.sleep(delay * 3)
                    break

            if data is None:
                # Fallback: intentar individualmente
                print(f"\n  {_dim('Batch falló, intentando individualmente...')}", flush=True)
                for appid in batch:
                    single = _fetch_single(appid, country, delay)
                    if single:
                        result = _process_app_entry(appid, single)
                        fetched_cache[appid] = result
                    else:
                        fetched_cache[appid] = None
                fetched_count += len(batch)
                continue

            # Verificar si el batch devolvió todo null (Steam a veces rechaza batches)
            null_count = sum(1 for a in batch if not data.get(a) or not isinstance(data.get(a), dict))
            if null_count == len(batch) and len(batch) > 1:
                print(f"\n  {_dim('Batch devolvió todo null, reintentando individualmente...')}", flush=True)
                for appid in batch:
                    single = _fetch_single(appid, country, delay)
                    if single:
                        result = _process_app_entry(appid, single)
                        fetched_cache[appid] = result
                    else:
                        fetched_cache[appid] = None
                fetched_count += len(batch)
                continue

            for appid in batch:
                result = _process_app_entry(appid, data)
                fetched_cache[appid] = result

            fetched_count += len(batch)

            if bi > 0 and bi % 10 == 0:
                save_price_cache(steam_id, fetched_cache)

            time.sleep(delay)

        print(f"\r  {'':70}\r", end="", flush=True)

    deals = [
        {
            "appid":          appid,
            "name":           info["name"],
            "type":           info.get("type", "game"),
            "discount":       info["discount_percent"],
            "price_final":    info["price_final"],
            "price_original": info["price_original"],
            "price_raw":      info.get("price_final_raw", 0),
            "genres":         info["genres"],
            "release_year":   info.get("release_year"),
            "description":    info.get("description", ""),
            "linux_native":   info.get("linux_native", False),
            "metacritic_score": info.get("metacritic_score"),
            "metacritic_url":   info.get("metacritic_url", ""),
            "categories":     info.get("categories", []),
        }
        for appid in appids
        if (info := fetched_cache.get(appid)) and info and info.get("discount_percent", 0) >= min_discount
    ]
    deals.sort(key=lambda x: -x["discount"])
    return deals, total


# ─────────────────────────────────────────────
# PARSEAR HLTB CSV
# ─────────────────────────────────────────────

def _parse_hltb_hours(val: str) -> float | None:
    """Convierte 'HH:MM:SS' o '--' a horas decimales."""
    if not val or val.strip() == "--":
        return None
    parts = val.strip().split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return h + m / 60 + s / 3600
    except (ValueError, IndexError):
        return None


def parse_hltb(csv_path: Path) -> dict[str, list[dict]]:
    result = {"backlog": [], "completed": [], "playing": [], "retired": []}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = row["Title"].strip()
            # Tomar Main + Extras si existe, sino Main Story
            hours = _parse_hltb_hours(row.get("Main + Extras", ""))
            if hours is None:
                hours = _parse_hltb_hours(row.get("Main Story", ""))
            entry = {
                "title": title,
                "storefront": row.get("Storefront", "").strip(),
                "hours": hours,
            }
            if   row.get("Backlog",    "").strip() == "X": result["backlog"].append(entry)
            elif row.get("Completed",  "").strip() == "X": result["completed"].append(entry)
            elif row.get("Playing",    "").strip() == "X": result["playing"].append(entry)
            elif row.get("Retired",    "").strip() == "X": result["retired"].append(entry)
    return result


# ─────────────────────────────────────────────
# FUZZY MATCHING HLTB × DEALS
# ─────────────────────────────────────────────

EDITION_WORDS = {
    "definitive", "remastered", "complete", "deluxe", "hd", "edition",
    "goty", "collection", "director", "cut", "enhanced", "anniversary",
    "intergrade", "gold", "platinum", "ultimate",
}
ROMAN = {
    "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5",
    "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10",
    "xi": "11", "xii": "12", "xiii": "13", "xiv": "14", "xv": "15",
}


def normalize(s: str) -> str:
    s = re.sub(r"[®™©]", "", s.lower())
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(ROMAN.get(w, w) for w in re.sub(r"\s+", " ", s).strip().split())


def extract_numbers(s: str) -> set[str]:
    return set(re.findall(r"\b\d+\b", normalize(s)))


def significant_words(s: str) -> set[str]:
    stop = {"the", "a", "an", "of", "in", "and", "or", "to", "is", "it", "at", "on", "for"}
    return set(normalize(s).split()) - stop


def is_same_game(a: str, b: str) -> bool:
    na, nb = extract_numbers(a), extract_numbers(b)
    if na and nb and na != nb:          return False
    if bool(na) != bool(nb):            return False
    wa, wb   = significant_words(a), significant_words(b)
    only_a   = (wa - wb) - EDITION_WORDS
    only_b   = (wb - wa) - EDITION_WORDS
    if only_a and only_b:               return False
    shared   = wa & wb
    if not shared:                      return False
    shorter  = wa if len(wa) <= len(wb) else wb
    return len(shared) / len(shorter) >= 0.7


def find_best_match(hltb_title: str, deals: list[dict], threshold: float = 0.75):
    hn = normalize(hltb_title)
    best_score, best_deal = 0.0, None
    for deal in deals:
        if deal.get("type", "game") != "game":
            continue
        score = SequenceMatcher(None, hn, normalize(deal["name"])).ratio()
        if score > best_score:
            best_score, best_deal = score, deal
    if best_score >= threshold and best_deal and is_same_game(hltb_title, best_deal["name"]):
        return best_score, best_deal
    return 0.0, None


def cross_hltb_with_deals(
    hltb: dict[str, list[dict]],
    deals: list[dict],
    threshold: float = 0.75,
    family_appids: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    used_names     = set()
    backlog_on_sale = []
    have_on_sale   = []
    family_appids  = family_appids or set()

    for status, games in [
        ("backlog",   hltb["backlog"]),
        ("completed", hltb["completed"]),
        ("playing",   hltb["playing"]),
        ("retired",   hltb["retired"]),
    ]:
        for game in games:
            score, deal = find_best_match(game["title"], deals, threshold)
            if deal and deal["name"] not in used_names:
                # Precio/hora
                hours = game.get("hours")
                price_raw = deal.get("price_raw", 0)
                price_per_hour = None
                if hours and hours > 0 and price_raw > 0:
                    price_per_hour = (price_raw / 100) / hours

                entry = {
                    "appid":          deal["appid"],
                    "hltb_title":     game["title"],
                    "steam_name":     deal["name"],
                    "storefront":     game["storefront"],
                    "discount":       deal["discount"],
                    "price":          deal["price_final"],
                    "price_original": deal["price_original"],
                    "score":          round(score, 2),
                    "status":         status,
                    "in_family":      deal["appid"] in family_appids,
                    "hours":          hours,
                    "price_per_hour": price_per_hour,
                }
                (backlog_on_sale if status == "backlog" else have_on_sale).append(entry)
                used_names.add(deal["name"])

    backlog_on_sale.sort(key=lambda x: -x["discount"])
    have_on_sale.sort(key=lambda x: -x["discount"])
    return backlog_on_sale, have_on_sale


# ─────────────────────────────────────────────
# FILTRO POR GÉNERO
# ─────────────────────────────────────────────

def filter_by_genres(deals: list[dict], genres: list[str]) -> list[dict]:
    if not genres:
        return []
    matched = [d for d in deals if any(g in dg for g in genres for dg in d.get("genres", []))]
    matched.sort(key=lambda x: -x["discount"])
    return matched


def apply_filters(
    deals: list[dict],
    filters: dict,
    reviews: dict[str, dict],
    deck_compat: dict[str, int],
    hltb_hours: dict[str, float],
    previous_appids: set[str],
    comparison: dict | None = None,
) -> list[dict]:
    """Aplica filtros CLI avanzados sobre la lista de deals."""
    filtered = list(deals)
    comp = comparison or {}

    if filters.get("max_price") is not None:
        limit = filters["max_price"] * 100
        filtered = [d for d in filtered if d.get("price_raw", 0) <= limit]

    if filters.get("deck_verified"):
        filtered = [d for d in filtered if deck_compat.get(d["appid"], 0) == 3]
    elif filters.get("deck_only"):
        filtered = [d for d in filtered if deck_compat.get(d["appid"], 0) >= 2]

    if filters.get("min_reviews") is not None:
        filtered = [d for d in filtered
                    if (r := reviews.get(d["appid"])) and r.get("pct", 0) >= filters["min_reviews"]]

    if filters.get("min_review_count") is not None:
        filtered = [d for d in filtered
                    if (r := reviews.get(d["appid"])) and r.get("total", 0) >= filters["min_review_count"]]

    if filters.get("max_hours") is not None:
        filtered = [d for d in filtered
                    if (h := hltb_hours.get(d["appid"])) is not None and h <= filters["max_hours"]]

    if filters.get("new_only"):
        new_set = comp.get("new_deals", set())
        if new_set:
            filtered = [d for d in filtered if d["appid"] in new_set]
        elif previous_appids:
            filtered = [d for d in filtered if d["appid"] not in previous_appids]

    return filtered


# ─────────────────────────────────────────────
# FETCH PARALELO (ThreadPoolExecutor)
# ─────────────────────────────────────────────

MAX_WORKERS = 8
RATE_LIMIT_INTERVAL = 0.15


def _fetch_parallel(items: list[str], fetch_fn, label: str,
                    rate_limit: float = RATE_LIMIT_INTERVAL, max_workers: int = MAX_WORKERS) -> dict:
    """Execute fetch_fn(appid) in parallel with global rate limiting."""
    total = len(items)
    if total == 0:
        return {}
    results = {}
    BAR_W = 25
    start = time.monotonic()
    completed = [0]
    lock = threading.Lock()
    last_req = [0.0]
    throttle = threading.Lock()

    def throttled(appid):
        with throttle:
            now = time.monotonic()
            wait = rate_limit - (now - last_req[0])
            if wait > 0:
                time.sleep(wait)
            last_req[0] = time.monotonic()
        return appid, fetch_fn(appid)

    eta_str = f"~{total * rate_limit / max_workers / 60:.1f} min"
    print(f"  Fetching {label} de {total} juegos ({eta_str})...", flush=True)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(throttled, aid): aid for aid in items}
        for future in as_completed(futures):
            completed[0] += 1
            pct = completed[0] / total
            filled = int(pct * BAR_W)
            bar = f"{C.GRN}{BAR_FILL * filled}{C.DIM}{BAR_EMPTY * (BAR_W - filled)}{C.RST}"
            elapsed = time.monotonic() - start
            if completed[0] > 1:
                eta_sec = elapsed / completed[0] * (total - completed[0])
                eta_str = f"{eta_sec / 60:.1f}m"
            print(f"\r  {bar} {completed[0]}/{total} ETA {eta_str}  ", end="", flush=True)
            try:
                appid, result = future.result()
                if result is not None:
                    with lock:
                        results[appid] = result
            except Exception:
                pass

    print(f"\r  {'':70}\r", end="", flush=True)
    return results


def _fetch_single_review(appid: str) -> dict | None:
    url = f"https://store.steampowered.com/appreviews/{appid}?json=1&num_per_page=0&language=all"
    try:
        data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        qs = data.get("query_summary", {})
        total_reviews = qs.get("total_reviews", 0)
        if total_reviews > 0:
            pos = qs.get("total_positive", 0)
            return {"desc": qs.get("review_score_desc", ""), "pct": round(pos / total_reviews * 100), "total": total_reviews}
    except Exception:
        pass
    return None


def _fetch_single_deck(appid: str) -> int | None:
    url = f"https://store.steampowered.com/saleaction/ajaxgetdeckappcompatibilityreport?nAppID={appid}"
    try:
        data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        return data.get("results", {}).get("resolved_category", 0)
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: REVIEWS DE STEAM
# ─────────────────────────────────────────────


def load_reviews_cache(steam_id: str) -> tuple[dict, float]:
    if not REVIEWS_CACHE_FILE.exists():
        return {}, float("inf")
    try:
        data = json.loads(REVIEWS_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, float("inf")
    if data.get("steam_id") != steam_id:
        return {}, float("inf")
    age_hours = (datetime.now() - datetime.fromisoformat(data["saved_at"])).total_seconds() / 3600
    return data.get("reviews", {}), age_hours


def save_reviews_cache(steam_id: str, reviews: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWS_CACHE_FILE.write_text(
        json.dumps({"steam_id": steam_id, "saved_at": datetime.now().isoformat(), "reviews": reviews},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_reviews(appids: list[str], cached: dict, rate_limit: float = 0.15) -> dict[str, dict]:
    """Fetch Steam reviews in parallel. Returns merged {appid: {desc, pct, total}}."""
    to_fetch = [a for a in appids if a not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    fetched = _fetch_parallel(to_fetch, _fetch_single_review, "reviews", rate_limit=rate_limit)
    result.update(fetched)
    return result


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: COMPATIBILIDAD STEAM DECK
# ─────────────────────────────────────────────

DECK_LABELS = {3: "✅ Verified", 2: "🟡 Playable", 1: "❌ Unsupported"}


def deck_badge(category: int) -> str:
    return DECK_LABELS.get(category, "")


def load_deck_cache(steam_id: str) -> tuple[dict, float]:
    if not DECK_CACHE_FILE.exists():
        return {}, float("inf")
    try:
        data = json.loads(DECK_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, float("inf")
    if data.get("steam_id") != steam_id:
        return {}, float("inf")
    age_hours = (datetime.now() - datetime.fromisoformat(data["saved_at"])).total_seconds() / 3600
    return data.get("deck", {}), age_hours


def save_deck_cache(steam_id: str, deck: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DECK_CACHE_FILE.write_text(
        json.dumps({"steam_id": steam_id, "saved_at": datetime.now().isoformat(), "deck": deck},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_deck_compat(appids: list[str], cached: dict, rate_limit: float = 0.15) -> dict[str, int]:
    """Fetch Steam Deck compatibility in parallel. Returns merged {appid: category}."""
    to_fetch = [a for a in appids if a not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    fetched = _fetch_parallel(to_fetch, _fetch_single_deck, "Deck compat", rate_limit=rate_limit)
    result.update(fetched)
    return result


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: PROTONDB
# ─────────────────────────────────────────────

PROTONDB_TIERS = {
    "native": "🐧 Native",
    "platinum": "💎 Platinum",
    "gold": "🥇 Gold",
    "silver": "🥈 Silver",
    "bronze": "🥉 Bronze",
    "borked": "💔 Borked",
}


def protondb_badge(tier: str) -> str:
    return PROTONDB_TIERS.get(tier, "")


def load_protondb_cache() -> tuple[dict, float]:
    if not PROTONDB_CACHE_FILE.exists():
        return {}, float("inf")
    try:
        data = json.loads(PROTONDB_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, float("inf")
    age_hours = (datetime.now() - datetime.fromisoformat(data["saved_at"])).total_seconds() / 3600
    return data.get("protondb", {}), age_hours


def save_protondb_cache(protondb: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PROTONDB_CACHE_FILE.write_text(
        json.dumps({"saved_at": datetime.now().isoformat(), "protondb": protondb}, ensure_ascii=False),
        encoding="utf-8",
    )


def _fetch_single_protondb(appid: str) -> dict | None:
    url = f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
    try:
        data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        tier = data.get("tier", "")
        if tier:
            return {"tier": tier, "score": data.get("score", 0), "total": data.get("total", 0)}
    except Exception:
        pass
    return None


def fetch_protondb(appids: list[str], cached: dict, rate_limit: float = 0.15) -> dict[str, dict]:
    """Fetch ProtonDB tiers in parallel. Returns merged {appid: {tier, score, total}}."""
    to_fetch = [a for a in appids if a not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    fetched = _fetch_parallel(to_fetch, _fetch_single_protondb, "ProtonDB", rate_limit=rate_limit)
    result.update(fetched)
    return result


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: ARE WE ANTI-CHEAT YET
# ─────────────────────────────────────────────

ANTICHEAT_WARN = {"Denied", "Broken"}  # statuses worth warning about


def load_anticheat_cache() -> tuple[dict, float]:
    if not ANTICHEAT_CACHE_FILE.exists():
        return {}, float("inf")
    try:
        data = json.loads(ANTICHEAT_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, float("inf")
    age_hours = (datetime.now() - datetime.fromisoformat(data["saved_at"])).total_seconds() / 3600
    return data.get("games", {}), age_hours


def save_anticheat_cache(games: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ANTICHEAT_CACHE_FILE.write_text(
        json.dumps({"saved_at": datetime.now().isoformat(), "games": games}, ensure_ascii=False),
        encoding="utf-8",
    )


def fetch_anticheat_db() -> dict[str, dict]:
    """Download Are We Anti-Cheat Yet database. Returns {appid: {status, anticheats, native}}."""
    url = "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/master/games.json"
    try:
        data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        result = {}
        if isinstance(data, list):
            for game in data:
                store_ids = game.get("storeIds", {})
                steam_id = store_ids.get("steam")
                if steam_id:
                    result[str(steam_id)] = {
                        "status": game.get("status", ""),
                        "anticheats": game.get("anticheats", []),
                        "native": game.get("native", False),
                    }
        return result
    except Exception as exc:
        print(f"\n  {_warn(f'Anti-cheat DB error: {exc}')}", flush=True)
        return {}


def linux_badge(deck_cat: int, protondb: dict | None, anticheat: dict | None, linux_native: bool = False) -> str:
    """Build combined Deck/Linux badge string."""
    parts = []
    # Linux native (from Steam platforms data)
    if linux_native:
        parts.append("🐧 Native")
    # Deck compat
    dk = deck_badge(deck_cat)
    if dk:
        parts.append(dk)
    # ProtonDB
    if protondb:
        pb = protondb_badge(protondb.get("tier", ""))
        if pb:
            parts.append(pb)
    # Anti-cheat warning
    if anticheat:
        status = anticheat.get("status", "")
        ac_names = ", ".join(anticheat.get("anticheats", []))
        if status in ANTICHEAT_WARN:
            parts.append(f"⛔ {ac_names} ({status})")
        elif status == "Supported" and ac_names:
            parts.append(f"✅ {ac_names}")
    return " · ".join(parts) if parts else "—"


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: STEAM TAGS (STEAMSPY)
# ─────────────────────────────────────────────

GENERIC_TAGS = {
    "singleplayer", "multiplayer", "action", "indie", "adventure",
    "free to play", "early access", "2d", "3d", "casual", "simulation",
    "strategy", "rpg", "fps", "puzzle", "platformer",
}


def load_tags_cache() -> tuple[dict, float]:
    if not TAGS_CACHE_FILE.exists():
        return {}, float("inf")
    try:
        data = json.loads(TAGS_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, float("inf")
    age_hours = (datetime.now() - datetime.fromisoformat(data["saved_at"])).total_seconds() / 3600
    tags = data.get("tags", {})
    # Migrate old format: {appid: {tag: votes}} → {appid: {tags: {...}, players: {}}}
    for appid, val in tags.items():
        if isinstance(val, dict) and "tags" not in val:
            tags[appid] = {"tags": val, "players": {}}
    return tags, age_hours


def save_tags_cache(tags: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TAGS_CACHE_FILE.write_text(
        json.dumps({"saved_at": datetime.now().isoformat(), "tags": tags}, ensure_ascii=False),
        encoding="utf-8",
    )


def fetch_tags(appids: list[str], cached: dict, rate_limit: float = 1.1) -> dict[str, dict]:
    """Fetch tags from SteamSpy for appids not in cache."""
    to_fetch = [a for a in appids if a not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    total = len(to_fetch)
    BAR_W = 25
    start = time.monotonic()
    eta_str = f"~{total * rate_limit / 60:.1f} min"
    print(f"  Fetching tags de {total} juegos via SteamSpy ({eta_str})...", flush=True)

    for i, appid in enumerate(to_fetch):
        pct = i / total
        filled = int(pct * BAR_W)
        bar = f"{C.GRN}{BAR_FILL * filled}{C.DIM}{BAR_EMPTY * (BAR_W - filled)}{C.RST}"
        if i > 0:
            eta_sec = (time.monotonic() - start) / i * (total - i)
            eta_str = f"{eta_sec / 60:.1f}m"
        print(f"\r  {bar} {i}/{total} ETA {eta_str}  ", end="", flush=True)

        url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
        try:
            data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
            tags = data.get("tags", {})
            if tags and isinstance(tags, dict):
                result[appid] = {
                    "tags": tags,
                    "players": {
                        "owners": data.get("owners", ""),
                        "ccu": data.get("ccu", 0),
                        "players_2weeks": data.get("players_2weeks", 0),
                    },
                }
        except Exception:
            pass
        time.sleep(rate_limit)

    print(f"\r  {'':70}\r", end="", flush=True)
    return result


def get_top_tags(tags_data: dict, appid: str, n: int = 3) -> list[str]:
    """Get top N non-generic tags for an appid."""
    entry = tags_data.get(appid, {})
    app_tags = entry.get("tags", entry) if isinstance(entry, dict) else {}
    if not app_tags or not isinstance(app_tags, dict):
        return []
    sorted_tags = sorted(app_tags.items(), key=lambda x: -x[1])
    return [t for t, _ in sorted_tags if t.lower() not in GENERIC_TAGS][:n]


def group_deals_by_tag(deals: list[dict], tags_data: dict, min_count: int = 3) -> list[tuple[str, list[dict]]]:
    """Group deals by their most popular tags."""
    tag_to_deals: dict[str, list[dict]] = {}
    for d in deals:
        for tag in get_top_tags(tags_data, d["appid"], n=5):
            tag_to_deals.setdefault(tag, []).append(d)
    # Filter and sort
    result = [(tag, ds) for tag, ds in tag_to_deals.items() if len(ds) >= min_count]
    result.sort(key=lambda x: -len(x[1]))
    return result[:10]


def _parse_owners(owners_str: str) -> tuple[int, int]:
    """Parse '200,000 .. 500,000' into (200000, 500000)."""
    if not owners_str or ".." not in owners_str:
        return (0, 0)
    parts = owners_str.split("..")
    try:
        lo = int(parts[0].strip().replace(",", ""))
        hi = int(parts[1].strip().replace(",", ""))
        return (lo, hi)
    except (ValueError, IndexError):
        return (0, 0)


def players_badge(tags_entry: dict) -> str:
    """Generate compact player badge from tags_data entry."""
    players = tags_entry.get("players", {})
    owners = players.get("owners", "")
    _, hi = _parse_owners(owners)
    if hi == 0:
        return ""
    def _fmt(n: int) -> str:
        if n >= 1_000_000: return f"{n / 1_000_000:.0f}M"
        if n >= 1_000: return f"{n // 1_000}K"
        return str(n)
    lo, _ = _parse_owners(owners)
    return f"👥 {_fmt(lo)}-{_fmt(hi)}" if lo else f"👥 <{_fmt(hi)}"


# ─────────────────────────────────────────────
# ACHIEVEMENTS (GLOBAL COMPLETION DATA)
# ─────────────────────────────────────────────


def load_achievements_cache(steam_id: str) -> tuple[dict, float]:
    if not ACHIEVEMENTS_CACHE_FILE.exists():
        return {}, float("inf")
    try:
        data = json.loads(ACHIEVEMENTS_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, float("inf")
    if data.get("steam_id") != steam_id:
        return {}, float("inf")
    age_hours = (datetime.now() - datetime.fromisoformat(data["saved_at"])).total_seconds() / 3600
    return data.get("achievements", {}), age_hours


def save_achievements_cache(steam_id: str, achievements: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ACHIEVEMENTS_CACHE_FILE.write_text(
        json.dumps({"steam_id": steam_id, "saved_at": datetime.now().isoformat(),
                     "achievements": achievements}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _fetch_single_achievement(appid: str) -> dict | None:
    url = f"https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={appid}"
    try:
        data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        achs = data.get("achievementpercentages", {}).get("achievements", [])
        if not achs:
            return None
        count = len(achs)
        avg_completion = sum(a.get("percent", 0) for a in achs) / count
        return {"count": count, "avg_completion": round(avg_completion, 1)}
    except Exception:
        return None


def fetch_achievements(appids: list[str], cached: dict, rate_limit: float = 0.15) -> dict[str, dict]:
    """Fetch achievement data in parallel. Returns merged {appid: {count, avg_completion}}."""
    to_fetch = [a for a in appids if a not in cached]
    if not to_fetch:
        return cached
    result = dict(cached)
    fetched = _fetch_parallel(to_fetch, _fetch_single_achievement, "achievements", rate_limit=rate_limit)
    result.update(fetched)
    return result


def achievements_badge(ach: dict | None) -> str:
    """MD badge for achievements."""
    if not ach:
        return "—"
    return f"\U0001f3c6 {ach['count']} ({ach['avg_completion']:.0f}%)"


def _html_achievements_badge(ach: dict | None) -> str:
    if not ach:
        return '<span class="review-na">\u2014</span>'
    return f'<span class="badge ach-badge" title="Avg global completion: {ach["avg_completion"]:.1f}%">\U0001f3c6 {ach["count"]}</span>'


# ─────────────────────────────────────────────
# TOP PICKS (BEST VALUE SCORE)
# ─────────────────────────────────────────────


def compute_value_score(discount: int, review_pct: int | None, priority: int,
                        price_per_hour: float | None, deck_cat: int,
                        release_year: int | None = None,
                        metacritic_score: int | None = None) -> float:
    """Compute a 0-100 value score combining multiple signals."""
    s_discount = min(discount, 100)
    s_reviews = review_pct if review_pct is not None else 50
    if priority == 0:
        s_priority = 30
    elif priority <= 10:
        s_priority = 100
    elif priority <= 50:
        s_priority = 80
    elif priority <= 200:
        s_priority = 60
    elif priority <= 500:
        s_priority = 40
    else:
        s_priority = 20
    if price_per_hour is not None and price_per_hour > 0:
        s_pph = max(0, min(100, 100 - price_per_hour * 2))
    else:
        s_pph = 50
    deck_scores = {3: 100, 2: 70, 1: 0, 0: 50}
    s_deck = deck_scores.get(deck_cat, 50)
    # Age factor: newer games with good discounts score higher
    if release_year is None:
        s_age = 50
    else:
        age = max(0, date.today().year - release_year)
        if age <= 1: s_age = 100
        elif age <= 3: s_age = 80
        elif age <= 5: s_age = 60
        elif age <= 8: s_age = 50
        else: s_age = 35
    # Metacritic bonus
    if metacritic_score is None:
        s_mc = 50
    elif metacritic_score >= 85:
        s_mc = 100
    elif metacritic_score >= 75:
        s_mc = 80
    elif metacritic_score >= 60:
        s_mc = 60
    else:
        s_mc = 30
    return s_discount * 0.22 + s_reviews * 0.26 + s_priority * 0.18 + s_pph * 0.14 + s_deck * 0.10 + s_age * 0.05 + s_mc * 0.05


def rank_top_picks(
    deals: list[dict],
    priorities: dict[str, int],
    reviews: dict[str, dict],
    hltb_hours: dict[str, float],
    deck_compat: dict[str, int],
    n: int = 10,
) -> list[dict]:
    """Rank deals by composite value score, return top N."""
    scored = []
    for deal in deals:
        appid = deal["appid"]
        review = reviews.get(appid)
        review_pct = review["pct"] if review else None
        priority = priorities.get(appid, 0)
        hours = hltb_hours.get(appid)
        price_raw = deal.get("price_raw", 0)
        pph = (price_raw / 100) / hours if hours and hours > 0 and price_raw > 0 else None
        deck_cat = deck_compat.get(appid, 0)
        mc_score = deal.get("metacritic_score")
        score = compute_value_score(deal["discount"], review_pct, priority, pph, deck_cat,
                                    release_year=deal.get("release_year"),
                                    metacritic_score=mc_score)
        scored.append({
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
            "metacritic_score": mc_score,
            "categories": deal.get("categories", []),
        })
    scored.sort(key=lambda x: -x["score"])
    return scored[:n]


def compute_budget_picks(deals, budget_mxn, top_picks, watchlist_alerts=None):
    """Greedy budget optimizer: pick best deals that fit within budget."""
    pick_scores = {tp["appid"]: tp["score"] for tp in (top_picks or [])}
    # Build efficiency list
    candidates = []
    for d in deals:
        price = d.get("price_raw", 0) / 100
        if price <= 0:
            continue
        score = pick_scores.get(d["appid"], 50.0)
        candidates.append({**d, "score": score, "efficiency": score / price})

    # Phase 1: watchlist hits first
    selected = []
    remaining = budget_mxn
    wl_appids = set()
    if watchlist_alerts:
        for wa in sorted(watchlist_alerts, key=lambda x: x.get("price_raw", 0)):
            cost = wa.get("price_raw", 0) / 100
            if cost <= remaining and cost > 0:
                score = pick_scores.get(wa["appid"], 50.0)
                selected.append({**wa, "score": score})
                remaining -= cost
                wl_appids.add(wa["appid"])

    # Phase 2: greedy by efficiency
    for c in sorted(candidates, key=lambda x: -x["efficiency"]):
        if c["appid"] in wl_appids:
            continue
        cost = c.get("price_raw", 0) / 100
        if cost <= remaining and cost > 0:
            selected.append(c)
            remaining -= cost
            if remaining <= 0:
                break

    total_spent = budget_mxn - remaining
    # Estimate savings: original = price / (1 - discount/100)
    total_savings = 0
    for s in selected:
        price = s.get("price_raw", 0) / 100
        disc = s.get("discount", 0)
        if disc > 0 and disc < 100:
            original = price * 100 / (100 - disc)
            total_savings += original - price

    return {
        "budget": budget_mxn,
        "selected": selected,
        "total_spent": round(total_spent, 2),
        "total_savings": round(total_savings, 2),
        "remaining": round(remaining, 2),
        "games_count": len(selected),
    }


# ─────────────────────────────────────────────
# GENERAR MARKDOWN
# ─────────────────────────────────────────────

STORE_URL    = "https://store.steampowered.com/app/{appid}/"
CAPSULE_URL  = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_231x87.jpg"
HEADER_URL   = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"

MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _md_esc(text: str) -> str:
    """Escape characters that break markdown tables and links."""
    return text.replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def _link(name: str, appid: str) -> str:
    return f"[{_md_esc(name)}]({STORE_URL.format(appid=appid)})"


def _prio_badge(priority: int) -> str:
    if priority == 0:
        return ""
    if priority <= 10:
        return f" **#{priority}**"
    if priority <= 50:
        return f" #{priority}"
    return ""


def format_deal_row(game: dict, show_storefront: bool = False) -> str:
    pct  = f"-{game['discount']}%"
    name = _link(game["steam_name"], game["appid"])
    if game["score"] < 0.95 and game["hltb_title"].lower() != game["steam_name"].lower():
        name += f" _(HLTB: {_md_esc(game['hltb_title'])})_"
    # Precio/hora
    pph = game.get("price_per_hour")
    pph_str = f" · ${pph:.1f}/h" if pph is not None else ""
    hours = game.get("hours")
    hours_str = f" · {hours:.0f}h" if hours else ""
    extra = f"{hours_str}{pph_str}" if (hours_str or pph_str) else ""

    if show_storefront:
        return f"| {pct} | {game['price']}{extra} | {game['storefront'] or '?'} | {name} |"
    return f"| {pct} | {game['price']}{extra} | {game['price_original']} | {name} |"


def group_by_tier(games: list[dict]) -> list[tuple[str, list[dict]]]:
    tiers = [
        ("90%+",   lambda d: d >= 90),
        ("80–89%", lambda d: 80 <= d < 90),
        ("70–79%", lambda d: 70 <= d < 80),
        ("60–69%", lambda d: 60 <= d < 70),
        ("50–59%", lambda d: 50 <= d < 60),
    ]
    return [(name, [g for g in games if fn(g["discount"])]) for name, fn in tiers]


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
    watchlist_alerts = watchlist_alerts or []
    comp = comparison or {}
    owned_and_wishlisted = sorted(
        [(a, owned[a]) for a in set(owned) & set(wishlist_appids)],
        key=lambda x: x[1].lower(),
    )

    # Clasificar grupos HLTB si aplica
    otras = familia = steam_sf = sin_sf = []
    if hltb_used:
        family_appids = family_appids or set()
        otras    = [g for g in backlog_on_sale if g["storefront"] and g["storefront"].lower() not in ("steam", "") and not g["in_family"]]
        familia  = [g for g in backlog_on_sale if g["in_family"]]
        steam_sf = [g for g in backlog_on_sale if g["storefront"].lower() == "steam" and not g["in_family"]]
        sin_sf   = [g for g in backlog_on_sale if not g["storefront"] and not g["in_family"]]

    # Header
    sale_line = f"Evento: 🏷️ **{sale_name}** | " if sale_name else ""
    lines = [
        f"# Steam Wishlist Deals — {vanity}",
        f"> {sale_line}{today} | Precios en MXN | Perfil: {vanity.lower()}",
        f"> Wishlist: {len(wishlist_appids):,} juegos | Deals (≥{min_discount}%): {len(deals):,}"
        + (f" | Backlog en oferta: {len(backlog_on_sale)}" if hltb_used else ""),
    ]
    # Comparison summary in header
    delta_parts = []
    new_deal_count = len(comp.get("new_deals", set()))
    disappeared_count = len(comp.get("disappeared", []))
    price_drops = sum(1 for v in comp.get("price_changes", {}).values() if v["direction"] == "down")
    if new_deal_count:
        delta_parts.append(f"🆕 {new_deal_count} nuevos")
    if disappeared_count:
        delta_parts.append(f"❌ {disappeared_count} terminaron")
    if price_drops:
        delta_parts.append(f"⬇️ {price_drops} bajaron de precio")
    if delta_parts:
        lines.append(f"> {' · '.join(delta_parts)}")
    lines += ["", "---", ""]

    # Top Picks
    if top_picks:
        lines += [
            "## 🏆 Top 10 Picks",
            "",
            "> Ranking: reviews (26%) + descuento (22%) + prioridad (18%) + $/hora HLTB (14%) + Deck (10%) + Metacritic (5%) + edad (5%).",
            "",
            "| # | Score | % | Precio | Año | Reviews | MC | Deck/Linux | Modo | Juego |",
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
            mp_str = multiplayer_badges(tp.get("categories", []))  or "—"
            prio = _prio_badge(tp.get("priority", 0))
            name_col = f"{_link(tp['name'], tp['appid'])}{prio}"
            yr = tp.get("release_year") or "—"
            lines.append(f"| {idx} | {tp['score']} | -{tp['discount']}% | {tp['price_final']} | {yr} | {rev_str} | {mc_str} | {dk_str} | {mp_str} | {name_col} |")
        lines += ["", "---", ""]

    # Watchlist Alerts
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
            lines.append(f"| {_link(wa['name'], wa['appid'])} | {wa['price_final']} | ${wa['target_price']:.0f} | -{wa['discount']}% | {savings_str} |")
        lines += ["", "---", ""]

    # Budget Mode
    if budget_result:
        b = budget_result
        lines += [
            f"## 💰 Budget Mode — ${b['budget']:.0f} MXN",
            "",
            f"> Con **${b['budget']:.0f} MXN** puedes comprar **{b['games_count']} juegos**.",
            f"> Total: ${b['total_spent']:.0f} | Ahorro vs original: ${b['total_savings']:.0f} | Restante: ${b['remaining']:.0f}",
            "",
            "| # | Score | % | Precio | Juego |",
            "|---|-------|---|--------|-------|",
        ]
        for idx, pick in enumerate(b["selected"], 1):
            lines.append(f"| {idx} | {pick.get('score', '—')} | -{pick['discount']}% | {pick['price_final']} | {_link(pick['name'], pick['appid'])} |")
        lines += ["", "---", ""]

    # Wishlist Comparison
    if compare_data:
        friend = compare_data.get("friend_vanity", "?")
        overlap = compare_data.get("overlap", set())
        lines += [
            f"## 👥 Wishlist Comparison — {friend}",
            "",
            f"> **{len(overlap)} juegos en común** entre tu wishlist y la de {friend}.",
            "",
        ]
        overlap_deals = [d for d in deals if d["appid"] in overlap]
        if overlap_deals:
            lines += [
                f"### En común y en oferta ({len(overlap_deals)} juegos)",
                "", "| % | Precio | Juego |", "|---|--------|-------|",
            ]
            for d in sorted(overlap_deals, key=lambda x: -x["discount"])[:20]:
                lines.append(f"| -{d['discount']}% | {d['price_final']} | {_link(d['name'], d['appid'])} |")
            lines.append("")
        if gift_ideas:
            lines += [
                f"### 🎁 Gift Ideas para {friend} ({len(gift_ideas)} juegos)",
                "", f"> Juegos que {friend} quiere, están en oferta, y tú no los tienes.", "",
                "| % | Precio | Juego |", "|---|--------|-------|",
            ]
            for g in gift_ideas[:20]:
                lines.append(f"| -{g['discount']}% | {g['price_final']} | {_link(g['name'], g['appid'])} |")
        lines += ["", "---", ""]

    # Bundles activos
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
            price_str = f"${binfo['price']:.0f} {binfo['currency']}" if binfo['price'] else "Gratis"
            link = f"[{binfo['store']}]({binfo['url']})" if binfo.get("url") else binfo["store"]
            lines += [f"### 📦 {bname}", f"> {price_str} en {link}", "", "| Juego | Precio Steam |", "|-------|-------------|"]
            for aid in binfo["appids"]:
                deal = next((d for d in deals if d["appid"] == aid), None)
                if deal:
                    lines.append(f"| {_link(deal['name'], aid)} | {deal['price_final']} |")
            lines.append("")
        lines += ["---", ""]

    # Backlog en Oferta (solo familia + sin storefront = deals útiles)
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
                ("🟡", "Confirmado en Familia de Steam",       familia),
                ("🟢", "Sin plataforma registrada en HLTB",   sin_sf),
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

    # Genre Deals
    if genres:
        genre_deals = filter_by_genres(deals, genres)
        genre_label = ", ".join(genres)
        lines += [
            "---", "",
            f"## Genre Deals — {genre_label}",
            "",
            f"> **{len(genre_deals)} juegos** en oferta que coinciden con: _{genre_label}_.",
            "",
        ]
        if genre_deals:
            lines += ["| % | Precio | Era | Juego |", "|---|--------|-----|-------|"]
            for d in genre_deals:
                lines.append(f"| -{d['discount']}% | {d['price_final']} | {d['price_original']} | {_link(d['name'], d['appid'])} |")
        else:
            lines.append("_Ningún juego de tu wishlist en oferta coincide con esos géneros._")
        lines.append("")

    # Deals por Tag
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
                    lines.append(f"| -{d['discount']}% | {d['price_final']} | {_link(d['name'], d['appid'])} |")
                lines.append("")

    # ── Quitar de la Wishlist ──
    lines += [
        "---", "",
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

        lines += ["", "### Completados / Retirados en HLTB en oferta en la Wishlist", ""]
        if have_on_sale:
            lines += ["| % | Precio | Estado | Juego |", "|---|--------|--------|-------|"]
            for g in have_on_sale:
                lines.append(f"| -{g['discount']}% | {g['price']} | {g['status']} | {_link(g['steam_name'], g['appid'])} |")
        else:
            lines.append("_Ninguno encontrado._")

    # ── Sugerencias inteligentes de limpieza ──
    current_year = date.today().year
    cleanup_neg = [(d, reviews.get(d["appid"])) for d in deals
                   if (r := reviews.get(d["appid"])) and r.get("pct", 100) < 50]
    cleanup_always = [(d, local_trends.get(d["appid"])) for d in deals
                      if (t := local_trends.get(d["appid"])) and t.get("times_on_sale", 0) >= 5]
    cleanup_nolinux = [d for d in deals
                       if deck_compat_data.get(d["appid"], 0) == 1
                       and (p := protondb_data.get(d["appid"])) and p.get("tier") == "borked"]
    cleanup_ac = [(d, anticheat_data.get(d["appid"])) for d in deals
                  if (a := anticheat_data.get(d["appid"])) and a.get("status") in ("Denied", "Broken")]
    cleanup_old = [(d, d.get("release_year")) for d in deals
                   if d.get("release_year") and (current_year - d["release_year"]) > 8 and d["discount"] < 70]

    if cleanup_neg:
        cleanup_neg.sort(key=lambda x: x[1]["pct"])
        lines += ["", f"### 👎 Reviews muy negativas ({len(cleanup_neg)} juegos)", "",
                   "> Estos juegos tienen reviews negativas, ¿seguro que los quieres?", "",
                   "| % | Precio | Reviews | Juego |", "|---|--------|---------|-------|"]
        for d, rev in cleanup_neg:
            lines.append(f"| -{d['discount']}% | {d['price_final']} | {rev['desc']} ({rev['pct']}%) | {_link(d['name'], d['appid'])} |")

    if cleanup_always:
        cleanup_always.sort(key=lambda x: -x[1]["times_on_sale"])
        lines += ["", f"### 🔄 Siempre en oferta ({len(cleanup_always)} juegos)", "",
                   "> Estos juegos están siempre en oferta, no hay prisa.", "",
                   "| % | Precio | Veces | Prom. | Juego |", "|---|--------|-------|-------|-------|"]
        for d, trend in cleanup_always:
            lines.append(f"| -{d['discount']}% | {d['price_final']} | {trend['times_on_sale']}x | {trend.get('avg_fmt', '?')} | {_link(d['name'], d['appid'])} |")

    if cleanup_nolinux:
        lines += ["", f"### 🐧 Sin soporte Linux/Deck ({len(cleanup_nolinux)} juegos)", "",
                   "> ProtonDB Borked + Deck Unsupported.", "",
                   "| % | Precio | Juego |", "|---|--------|-------|"]
        for d in sorted(cleanup_nolinux, key=lambda x: -x["discount"]):
            lines.append(f"| -{d['discount']}% | {d['price_final']} | {_link(d['name'], d['appid'])} |")

    if cleanup_ac:
        lines += ["", f"### ⛔ Anti-cheat no funciona en Linux ({len(cleanup_ac)} juegos)", "",
                   "> Anti-cheat status Denied o Broken en Linux.", "",
                   "| % | Precio | Anti-Cheat | Status | Juego |", "|---|--------|------------|--------|-------|"]
        for d, ac in cleanup_ac:
            ac_names = ", ".join(ac.get("anticheats", []))
            lines.append(f"| -{d['discount']}% | {d['price_final']} | {ac_names} | {ac['status']} | {_link(d['name'], d['appid'])} |")

    if cleanup_old:
        cleanup_old.sort(key=lambda x: (x[1], -x[0]["discount"]))
        lines += ["", f"### 🕰️ Juego viejo, descuento bajo ({len(cleanup_old)} juegos)", "",
                   "> Juegos de más de 8 años con menos de 70% de descuento. Suelen bajar más.", "",
                   "| % | Precio | Año | Juego |", "|---|--------|-----|-------|"]
        for d, year in cleanup_old:
            lines.append(f"| -{d['discount']}% | {d['price_final']} | {year} | {_link(d['name'], d['appid'])} |")

    lines += ["", "---", ""]

    # Ofertas terminadas
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
            lines.append(f"| -{dd['discount']}% | {dd['price_final']} | {_link(dd['name'], dd['appid'])} |")
        lines += ["", "---", ""]

    # Deals por tier (con prioridad, mínimo histórico, reviews, deck, mejor precio)
    has_itad = bool(historical_lows)
    has_best_prices = bool(current_prices)
    for tier_name, tier_deals in group_by_tier(deals):
        # Ordenar tiers según --sort
        _sort_keys = {
            "discount": lambda d: -d["discount"],
            "price":    lambda d: d.get("price_raw", 0),
            "reviews":  lambda d: -(reviews.get(d["appid"], {}).get("pct", 0)),
            "priority": lambda d: (priorities.get(d["appid"], 0) == 0, priorities.get(d["appid"], 9999)),
            "score":    lambda d: -(compute_value_score(d["discount"], reviews.get(d["appid"], {}).get("pct"), priorities.get(d["appid"], 0), None, deck_compat_data.get(d["appid"], 0), release_year=d.get("release_year"), metacritic_score=d.get("metacritic_score"))),
        }
        tier_deals.sort(key=_sort_keys.get(sort_field, _sort_keys["discount"]))

        lines += [
            f"## {tier_name} de Descuento ({len(tier_deals)} juegos)",
            "",
        ]

        # Build dynamic header
        has_tags = bool(tags_data)
        has_ach = bool(achievements_data)
        header = "| | % | Precio | Era | Año | Reviews | MC | Deck/Linux | Modo"
        sep    = "|-|---|--------|-----|-----|---------|----|-----------|----|"
        if has_ach:
            header += " | Logros"
            sep    += "|-------"
        if has_tags:
            header += " | Tags"
            sep    += "|------"
        if has_itad:
            header += " | Min. hist."
            sep    += "|------------"
        if has_best_prices:
            header += " | Mejor precio"
            sep    += "|--------------"
        has_trends = bool(local_trends)
        if has_trends:
            header += " | Tendencia"
            sep    += "|-----------"
        header += " | Juego |"
        sep    += "|-------|"
        lines += [header, sep]

        for d in tier_deals:
            # Rich markers from comparison
            markers = []
            appid = d["appid"]
            if appid in comp.get("new_deals", set()):
                markers.append("🆕")
            pc = comp.get("price_changes", {}).get(appid)
            if pc:
                markers.append(f"⬇️ -{pc['delta_str']}" if pc["direction"] == "down" else f"⬆️ +{pc['delta_str']}")
            streak = comp.get("deal_streak", {}).get(appid, 0)
            if streak >= 3:
                markers.append(f"🔥 {streak}º run")
            # Fallback to previous_appids if no comparison data
            if not markers and not comp and previous_appids and appid not in previous_appids:
                markers.append("🆕")
            new_marker = " ".join(markers)
            prio = _prio_badge(priorities.get(d["appid"], 0))
            name_col = f"{_link(d['name'], d['appid'])}{prio}"

            # Reviews
            rev = reviews.get(d["appid"])
            rev_str = f"{rev['desc']} ({rev['pct']}%)" if rev else "—"

            # Deck/Linux (combined)
            dk = deck_compat_data.get(d["appid"], 0)
            pdb = protondb_data.get(d["appid"])
            ac = anticheat_data.get(d["appid"])
            dk_str = linux_badge(dk, pdb, ac, d.get("linux_native", False))

            # Metacritic
            mc = d.get("metacritic_score")
            mc_str = str(mc) if mc else "—"
            # Multiplayer/Co-op
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
                bp_str = f"${bp['price']:.0f} en [{bp['store']}]({bp['url']})" if bp else "—"
                row += f" | {bp_str}"

            if has_trends:
                trend = local_trends.get(d["appid"])
                row += f" | {format_trend(trend)}" if trend else " | —"

            row += f" | {name_col} |"
            lines.append(row)
        lines += ["", "---", ""]

    return "\n".join(lines)


# ─────────────────────────────────────────────
# GENERAR HTML INTERACTIVO
# ─────────────────────────────────────────────

def _html_esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _html_link(name: str, appid: str) -> str:
    return f'<a href="{STORE_URL.format(appid=appid)}" target="_blank">{_html_esc(name)}</a>'


def _html_deck_badge(category: int) -> str:
    labels = {3: ("Verified", "verified"), 2: ("Playable", "playable"), 1: ("Unsupported", "unsupported")}
    if category not in labels:
        return '<span class="badge deck-unknown">\u2014</span>'
    text, cls = labels[category]
    return f'<span class="badge deck-{cls}">{text}</span>'


def _html_review_badge(review: dict | None) -> str:
    if not review:
        return '<span class="review-na">\u2014</span>'
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


def _html_metacritic_badge(score: int | None) -> str:
    if score is None:
        return '<span class="review-na">\u2014</span>'
    cls = "mc-good" if score >= 75 else "mc-mixed" if score >= 50 else "mc-bad"
    return f'<span class="badge {cls}">{score}</span>'


def multiplayer_badges(categories: list[int]) -> str:
    """Emoji badges for multiplayer/co-op categories (for MD)."""
    cats = set(categories)
    badges = []
    if cats & {9, 38, 39}:
        badges.append("Co-op")
    if cats & {36, 37}:
        badges.append("PvP")
    if not badges and 1 in cats:
        badges.append("Multi")
    if not badges and 2 in cats:
        badges.append("Single")
    return " · ".join(badges) if badges else ""


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
    return " ".join(parts) if parts else '<span class="review-na">\u2014</span>'


def _build_sparkline_svg(snapshots: list[dict], width: int = 80, height: int = 24) -> str:
    """Build an inline SVG sparkline from price snapshots."""
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
    color = "#6cc644" if last_price <= mn else "#f0b232" if last_price <= mn + rng * 0.3 else "#c7d5e0"
    # Dot on current price
    lx, ly = points[-1].split(",")
    return (f'<svg width="{width}" height="{height}" style="vertical-align:middle" title="Historial: ${mn:.0f}-${mx:.0f}">'
            f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5"/>'
            f'<circle cx="{lx}" cy="{ly}" r="2" fill="{color}"/></svg>')


def _html_price_raw(price_str: str) -> float:
    m = re.search(r'[\d,.]+', price_str.replace(',', ''))
    return float(m.group()) if m else 0.0


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
document.addEventListener('DOMContentLoaded', applyFilters);
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
// Share Modal
let currentShareData = null;
let currentSteamUrl = '';
function openShareModal(game) {
  currentShareData = game;
  currentSteamUrl = 'https://store.steampowered.com/app/' + game.appid + '/';
  document.getElementById('share-name').textContent = game.name || '';
  document.getElementById('share-price').innerHTML = (game.price_original && game.price ? '<span>$' + game.price_original + ' </span>' : '') + (game.price || '') + (game.discount ? ' (' + game.discount + '% OFF)' : '');
  document.getElementById('share-minhist').innerHTML = game.min_hist ? 'Minimo historico: <span>$' + game.min_hist + '</span>' : '';
  document.getElementById('share-modal').classList.add('active');
}
function closeShareModal() {
  document.getElementById('share-modal').classList.remove('active');
  currentShareData = null;
}
function copyShareLink() {
  if (!currentShareData) return;
  const encoded = btoa(JSON.stringify(currentShareData));
  const shareUrl = 'steamtools://share?data=' + encoded;
  navigator.clipboard.writeText(shareUrl).then(() => {
    const btn = document.getElementById('btn-copy-app');
    btn.textContent = 'Copiado!';
    setTimeout(() => btn.textContent = 'Copiar link steamtools://', 2000);
  });
}
function copySteamLink() {
  if (!currentSteamUrl) return;
  navigator.clipboard.writeText(currentSteamUrl).then(() => {
    const btn = document.querySelector('.share-btn-copy-steam');
    btn.textContent = 'Copiado!';
    setTimeout(() => btn.textContent = 'Copiar link de Steam', 2000);
  });
}
function openInSteam() {
  if (currentSteamUrl) window.open(currentSteamUrl, '_blank');
}
"""


def _build_dashboard_html(deals, reviews, deck_compat_data, tags_data, protondb_data):
    """Build statistics dashboard HTML section."""
    if not deals:
        return ""
    total = len(deals)

    # Financial summary
    total_orig = sum(_html_price_raw(d.get("price_original", "")) for d in deals)
    total_final = sum(_html_price_raw(d["price_final"]) for d in deals)
    total_savings = total_orig - total_final
    avg_disc = sum(d["discount"] for d in deals) / total
    prices = sorted(_html_price_raw(d["price_final"]) for d in deals)
    median_price = prices[len(prices) // 2] if prices else 0

    fin_html = f'''<div class="dash-card" style="grid-column:1/-1">
  <h3>&#128176; Resumen Financiero</h3>
  <div class="fin-grid">
    <div class="fin-item"><div class="fin-value">${total_orig:,.0f}</div><div class="fin-label">Precio original</div></div>
    <div class="fin-item"><div class="fin-value">${total_final:,.0f}</div><div class="fin-label">En oferta</div></div>
    <div class="fin-item"><div class="fin-value fin-savings">${total_savings:,.0f}</div><div class="fin-label">Ahorro total</div></div>
    <div class="fin-item"><div class="fin-value">-{avg_disc:.0f}%</div><div class="fin-label">Descuento promedio</div></div>
    <div class="fin-item"><div class="fin-value">${median_price:.0f}</div><div class="fin-label">Precio mediana</div></div>
  </div>
</div>'''

    # Discount distribution bars
    tier_colors = {"90%+": "#6cc644", "80–89%": "#4eaa5a", "70–79%": "#f0b232", "60–69%": "#e89030", "50–59%": "#c7322e"}
    tiers = group_by_tier(deals)
    max_t = max((len(ds) for _, ds in tiers), default=1) or 1
    bars_html = ""
    for name, ds in tiers:
        pct = len(ds) / max_t * 100
        color = tier_colors.get(name, "#66c0f4")
        bars_html += f'<div class="hbar-row"><span class="hbar-label">{name}</span><div class="hbar-track"><div class="hbar-fill" style="width:{pct}%;background:{color}">{len(ds)}</div></div><span class="hbar-value">{len(ds)}</span></div>\n'
    disc_html = f'<div class="dash-card"><h3>&#128200; Descuentos</h3>{bars_html}</div>'

    # Deck + ProtonDB stacked bars
    dk_counts = {3: 0, 2: 0, 1: 0, 0: 0}
    for d in deals:
        dk_counts[deck_compat_data.get(d["appid"], 0)] = dk_counts.get(deck_compat_data.get(d["appid"], 0), 0) + 1
    dk_colors = {3: ("#6cc644", "Verified"), 2: ("#f0b232", "Playable"), 1: ("#c7322e", "Unsupported"), 0: ("#555", "Unknown")}
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
            t = pdb.get("tier", "")
            pdb_counts[t] = pdb_counts.get(t, 0) + 1
    pdb_colors = {"native": "#6cc644", "platinum": "#b4c7dc", "gold": "#d4a84b", "silver": "#a8a8a8", "bronze": "#cd7f32", "borked": "#c7322e"}
    pdb_segs = ""
    pdb_legend = ""
    for t in ("native", "platinum", "gold", "silver", "bronze", "borked"):
        c = pdb_counts.get(t, 0)
        if c > 0:
            pct = c / total * 100
            pdb_segs += f'<div class="stacked-seg" style="width:{pct}%;background:{pdb_colors[t]}">{c if pct > 5 else ""}</div>'
            pdb_legend += f'<span class="legend-item"><span class="legend-dot" style="background:{pdb_colors[t]}"></span>{t.title()} ({c})</span>'

    compat_html = f'''<div class="dash-card"><h3>&#127918; Deck / ProtonDB</h3>
  <div style="margin-bottom:.6rem"><div style="font-size:.75rem;color:var(--text-secondary);margin-bottom:.2rem">Steam Deck</div><div class="stacked-bar">{dk_segs}</div><div class="stacked-legend">{dk_legend}</div></div>
  <div><div style="font-size:.75rem;color:var(--text-secondary);margin-bottom:.2rem">ProtonDB</div><div class="stacked-bar">{pdb_segs}</div><div class="stacked-legend">{pdb_legend}</div></div>
</div>'''

    # Top tags bars
    tags_html = ""
    if tags_data:
        tag_groups = group_deals_by_tag(deals, tags_data)
        if tag_groups:
            max_tg = len(tag_groups[0][1]) if tag_groups else 1
            tg_bars = ""
            for tname, tdeals in tag_groups[:8]:
                pct = len(tdeals) / max_tg * 100
                tg_bars += f'<div class="hbar-row"><span class="hbar-label">{_html_esc(tname)}</span><div class="hbar-track"><div class="hbar-fill" style="width:{pct}%;background:var(--accent-blue)">{len(tdeals)}</div></div><span class="hbar-value">{len(tdeals)}</span></div>\n'
            tags_html = f'<div class="dash-card"><h3>&#127991; Top Tags</h3>{tg_bars}</div>'

    return f'''<details open class="dashboard">
  <summary>&#128202; Dashboard</summary>
  <div class="dash-grid">
    {fin_html}
    {disc_html}
    {compat_html}
    {tags_html}
  </div>
</details>'''


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
) -> str:
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
    local_trends = local_trends or {}
    price_history_games = (price_history or {}).get("games", {})
    has_itad = bool(historical_lows)
    has_best = bool(current_prices)
    has_ach = bool(achievements_data)
    has_sparklines = bool(price_history_games)

    # Stats
    total_deals = len(deals)
    avg_disc = sum(d["discount"] for d in deals) / total_deals if total_deals else 0
    avg_price = sum(_html_price_raw(d["price_final"]) for d in deals) / total_deals if total_deals else 0
    verified = sum(1 for d in deals if deck_compat_data.get(d["appid"]) == 3)
    new_count = sum(1 for d in deals if previous_appids and d["appid"] not in previous_appids) if previous_appids else 0

    parts = []

    # ── Stats bar ──
    sale_html = f'Evento: <span class="sale-badge">&#127991; {_html_esc(sale_name)}</span> | ' if sale_name else ""
    pills = [
        f'<span class="pill">{len(wishlist_appids):,} en wishlist</span>',
        f'<span class="pill pill-accent" id="stat-deals">{total_deals:,} deals (&ge;{min_discount}%)</span>',
        f'<span class="pill" id="stat-avg-disc">Promedio: -{avg_disc:.0f}%</span>',
        f'<span class="pill" id="stat-avg-price">Precio medio: ${avg_price:.0f}</span>',
        f'<span class="pill">{verified} Deck Verified</span>',
    ]
    if new_count:
        pills.append(f'<span class="pill pill-new">{new_count} nuevos</span>')
    parts.append(f'''<header class="stats-bar">
  <h1>Steam Deals &mdash; {_html_esc(vanity)}</h1>
  <div class="stats-meta">{sale_html}{today} | Precios en MXN</div>
  <div class="stats-pills">{"".join(pills)}</div>
</header>''')

    # ── Dashboard ──
    parts.append(_build_dashboard_html(deals, reviews, deck_compat_data, tags_data or {}, protondb_data or {}))

    # ── Top Picks ──
    if top_picks:
        cards = []
        for idx, tp in enumerate(top_picks, 1):
            rank_cls = "rank-gold" if idx == 1 else "rank-silver" if idx == 2 else "rank-bronze" if idx == 3 else ""
            rev_html = _html_review_badge(tp.get("review"))
            dk_html = _html_deck_badge(tp.get("deck", 0))
            mc_html = _html_metacritic_badge(tp.get("metacritic_score"))
            mp_html = _html_multiplayer_badges(tp.get("categories", []))
            prio_html = _html_prio_badge(tp.get("priority", 0))
            header_img = HEADER_URL.format(appid=tp['appid'])
            store_url = STORE_URL.format(appid=tp['appid'])
            min_hist = historical_lows.get(tp['appid'])
            min_hist_str = f"${min_hist['price']:.0f}" if min_hist else ""
            tp_data = f'{{"name":"{_html_esc(tp["name"])}","appid":"{tp["appid"]}","price":"{_html_esc(tp["price_final"])}","price_original":"{_html_esc(tp.get("price_original",""))}","discount":{tp["discount"]},"min_hist":"{min_hist_str}"}}'
            cards.append(f'''<div class="pick-card {rank_cls}">
  <a href="{store_url}" target="_blank" style="display:block">
    <img class="pick-img" src="{header_img}" alt="" loading="lazy" onerror="this.style.display='none'">
    <div class="pick-body">
      <div class="pick-rank">#{idx}</div>
      <div class="pick-score">{tp['score']}</div>
      <div class="pick-name">{_html_esc(tp['name'])}{prio_html}</div>
      <div class="pick-details"><span class="pick-discount">-{tp['discount']}%</span><span class="pick-price">{_html_esc(tp['price_final'])}</span></div>
      <div class="pick-meta">{rev_html} &middot; {mc_html} &middot; {dk_html} &middot; {mp_html}</div>
    </div>
  </a>
  <button class="share-btn-mini" onclick="openShareModal({tp_data})" title="Compartir">&#128279;</button>
</div>''')
        parts.append(f'''<section class="top-picks">
  <h2>&#127942; Top {len(top_picks)} Picks</h2>
  <p class="section-desc">Ranking: reviews (26%) + descuento (22%) + prioridad (18%) + $/hora HLTB (14%) + Deck (10%) + Metacritic (5%) + edad (5%).</p>
  <div class="picks-grid">{"".join(cards)}</div>
</section>''')

    # ── Watchlist Alerts ──
    if watchlist_alerts:
        wl_rows = []
        for wa in watchlist_alerts:
            savings = wa["target_price"] - (wa.get("price_raw", 0) / 100)
            savings_html = f'<span style="color:var(--accent-green)">+${savings:.0f}</span>' if savings > 0 else ""
            capsule = CAPSULE_URL.format(appid=wa["appid"])
            wl_rows.append(f'''<div class="wl-card">
  <img src="{capsule}" alt="" loading="lazy" style="width:120px;height:45px;border-radius:4px;object-fit:cover" onerror="this.style.display='none'">
  <div class="wl-info">
    <div><strong>{_html_link(wa["name"], wa["appid"])}</strong></div>
    <div style="font-size:.85rem">{_html_esc(wa["price_final"])} <span style="color:var(--text-secondary)">(objetivo: ${wa["target_price"]:.0f})</span> {savings_html}</div>
    <div style="font-size:.8rem"><span class="pick-discount">-{wa["discount"]}%</span></div>
  </div>
</div>''')
        parts.append(f'''<section class="top-picks" style="margin-bottom:1.5rem">
  <h2>&#127919; Watchlist Alerts</h2>
  <p class="section-desc">{len(watchlist_alerts)} juegos alcanzaron tu precio objetivo</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.6rem">{"".join(wl_rows)}</div>
</section>''')

    # ── Budget Mode ──
    if budget_result:
        b = budget_result
        pct_used = b["total_spent"] / b["budget"] * 100 if b["budget"] > 0 else 0
        budget_rows = ""
        for idx, pick in enumerate(b["selected"], 1):
            capsule = CAPSULE_URL.format(appid=pick["appid"])
            budget_rows += f'''<tr>
  <td>{idx}</td><td>{pick.get("score", "—")}</td><td>-{pick["discount"]}%</td>
  <td>{_html_esc(pick["price_final"])}</td>
  <td><div class="game-cell"><img class="game-thumb" src="{capsule}" alt="" loading="lazy" onerror="this.style.display='none'"><span>{_html_link(pick["name"], pick["appid"])}</span></div></td>
</tr>'''
        parts.append(f'''<section style="margin-bottom:1.5rem">
  <h2>&#128176; Budget Mode &mdash; ${b["budget"]:.0f} MXN</h2>
  <p class="section-desc">Con ${b["budget"]:.0f} MXN puedes comprar {b["games_count"]} juegos &middot; Ahorro: ${b["total_savings"]:.0f} &middot; Restante: ${b["remaining"]:.0f}</p>
  <div style="background:var(--bg-secondary);border-radius:6px;height:24px;margin-bottom:.8rem;overflow:hidden;position:relative">
    <div style="height:100%;width:{pct_used:.0f}%;background:linear-gradient(90deg,var(--accent-blue),#4b9cd3);border-radius:6px"></div>
    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:600;color:var(--text-primary)">${b["total_spent"]:.0f} / ${b["budget"]:.0f} ({pct_used:.0f}%)</div>
  </div>
  <div class="table-wrap"><table class="deals-table"><thead><tr><th>#</th><th>Score</th><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>{budget_rows}</tbody></table></div>
</section>''')

    # ── Wishlist Comparison ──
    if compare_data:
        friend = compare_data.get("friend_vanity", "?")
        overlap = compare_data.get("overlap", set())
        overlap_deals = [d for d in deals if d["appid"] in overlap]
        comp_html = f'''<section style="margin-bottom:1.5rem">
  <h2>&#128101; Wishlist Comparison &mdash; {_html_esc(friend)}</h2>
  <p class="section-desc">{len(overlap)} juegos en com&uacute;n'''
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
            for g in gift_ideas_list[:20]:
                capsule = CAPSULE_URL.format(appid=g["appid"])
                gi_rows += f'<tr><td>-{g["discount"]}%</td><td>{_html_esc(g["price_final"])}</td><td><div class="game-cell"><img class="game-thumb" src="{capsule}" alt="" loading="lazy" onerror="this.style.display=\'none\'"><span>{_html_link(g["name"], g["appid"])}</span></div></td></tr>'
            comp_html += f'<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">&#127873; Gift Ideas para {_html_esc(friend)}</h3><div class="table-wrap"><table class="deals-table"><thead><tr><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>{gi_rows}</tbody></table></div>'
        comp_html += "</section>"
        parts.append(comp_html)

    # ── Filters ──
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

    # ── Tier tables ──
    for tier_name, tier_deals in group_by_tier(deals):
        tier_deals.sort(key=lambda d: (priorities.get(d["appid"], 0) == 0, priorities.get(d["appid"], 9999)))
        tid = re.sub(r'[^a-z0-9]', '', tier_name.lower())

        # Headers
        cols = [("", "text"), ("%", "num"), ("Precio", "price"), ("Era", "price"), ("Reviews", "num"), ("MC", "num"), ("Deck", "text"), ("Modo", "text")]
        if has_ach:
            cols.append(("Logros", "num"))
        if has_sparklines:
            cols.append(("Trend", "text"))
        if has_itad:
            cols.append(("Min. hist.", "price"))
        if has_best:
            cols.append(("Mejor precio", "price"))
        cols.append(("Juego", "text"))

        ths = "".join(
            f'<th onclick="sortTable(\'t-{tid}\',{i},\'{ct}\')">{_html_esc(h)} <span class="sort-arrow">&#9650;&#9660;</span></th>'
            for i, (h, ct) in enumerate(cols)
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
                spark = _build_sparkline_svg(snaps) if len(snaps) >= 2 else "\u2014"
                cells.append(f"<td>{spark}</td>")
            if has_itad:
                low = historical_lows.get(appid)
                if low:
                    low_txt = f"${low['price']:.0f} ({low['date']})"
                    cells.append(f"<td>{_html_esc(low_txt)}</td>")
                else:
                    cells.append("<td>\u2014</td>")
            if has_best:
                bp = current_prices.get(appid)
                if bp:
                    bp_html = f'${bp["price"]:.0f} en <a href="{bp["url"]}" target="_blank">{_html_esc(bp["store"])}</a>'
                    cells.append(f"<td>{bp_html}</td>")
                else:
                    cells.append("<td>\u2014</td>")
            capsule_img = CAPSULE_URL.format(appid=appid)
            desc_attr = f' title="{_html_esc(d.get("description", ""))}"' if d.get("description") else ""
            min_hist = historical_lows.get(appid)
            min_hist_str = f"${min_hist['price']:.0f}" if min_hist else ""
            game_data = f'{{"name":"{_html_esc(d["name"])}","appid":"{appid}","price":"{_html_esc(d["price_final"])}","price_original":"{_html_esc(d["price_original"])}","discount":{d["discount"]},"min_hist":"{min_hist_str}"}}'
            name_html = (
                f'<div class="game-cell">'
                f'<img class="game-thumb" src="{capsule_img}" alt="" loading="lazy" onerror="this.style.display=\'none\'">'
                f'<span{desc_attr}>{_html_link(d["name"], appid)}{_html_prio_badge(prio)}</span>'
                f'<button class="share-btn-mini" onclick="openShareModal({game_data})" title="Compartir" style="margin-left:.4rem;position:relative;top:-1px">&#128279;</button>'
                f'</div>'
            )
            cells.append(f"<td>{name_html}</td>")

            data_attrs = f'data-discount="{d["discount"]}" data-price="{price_num}" data-deck="{dk}" data-review="{rev_pct}" data-name="{_html_esc(d["name"].lower())}" data-new="{"1" if is_new else "0"}"'
            rows.append(f"<tr {data_attrs}>{''.join(cells)}</tr>")

        parts.append(f'''<details open class="tier-section">
  <summary class="tier-header">{_html_esc(tier_name)} de Descuento <span class="tier-count">(<span class="visible-count">{len(tier_deals)}</span> juegos)</span></summary>
  <div class="table-wrap"><table class="deals-table" id="t-{tid}"><thead><tr>{ths}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
</details>''')

    return f'''<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Steam Deals &mdash; {_html_esc(vanity)}</title><style>{_HTML_CSS}</style></head>
<body>
{"".join(parts)}
<script>{_HTML_JS}</script>
</body>
</html>'''


# ─────────────────────────────────────────────
# GENERAR CSV
# ─────────────────────────────────────────────

CSV_DECK = {3: "Verified", 2: "Playable", 1: "Unsupported", 0: ""}
CSV_PROTON = {"native": "Native", "platinum": "Platinum", "gold": "Gold",
              "silver": "Silver", "bronze": "Bronze", "borked": "Borked"}

def _csv_trend(trend: dict) -> str:
    if trend.get("is_first_time"): return "1ra vez"
    if trend.get("is_best_local") and trend.get("times_on_sale", 0) > 1: return "Min. local"
    if trend.get("is_first_at_price"): return "1ra vez a este precio"
    return f"{trend.get('times_on_sale', 0)}x, prom {trend.get('avg_fmt', '?')}"


def generate_share_html(deals, vanity, min_discount, sale_name="", top_picks=None, reviews=None, deck_compat=None):
    """Generate a lightweight shareable HTML page with the deals list."""
    reviews = reviews or {}
    deck_compat = deck_compat or {}
    top_picks = top_picks or []
    today = date.today().strftime("%Y-%m-%d")
    title = f"Steam Deals — {vanity}"
    rows = ""
    for d in deals:
        appid = d["appid"]
        rev = reviews.get(appid)
        rev_str = f'{rev["desc"]} ({rev["pct"]}%)' if rev else ""
        dk = deck_compat.get(appid, 0)
        dk_str = {3: "Verified", 2: "Playable"}.get(dk, "")
        capsule = CAPSULE_URL.format(appid=appid)
        store = STORE_URL.format(appid=appid)
        rows += f'<tr><td>-{d["discount"]}%</td><td>{_html_esc(d["price_final"])}</td><td>{rev_str}</td><td>{dk_str}</td><td><div style="display:flex;align-items:center;gap:.4rem"><img src="{capsule}" style="width:80px;height:30px;object-fit:cover;border-radius:3px" loading="lazy" onerror="this.style.display=\'none\'"><a href="{store}" target="_blank">{_html_esc(d["name"])}</a></div></td></tr>\n'

    picks_html = ""
    if top_picks:
        pick_cards = ""
        for idx, tp in enumerate(top_picks[:5], 1):
            header = HEADER_URL.format(appid=tp["appid"])
            store = STORE_URL.format(appid=tp["appid"])
            pick_cards += f'<a href="{store}" target="_blank" style="text-decoration:none;color:inherit;background:#16202d;border:1px solid #2a475e;border-radius:6px;overflow:hidden;display:flex;flex-direction:column"><img src="{header}" style="width:100%;aspect-ratio:460/215;object-fit:cover" loading="lazy"><div style="padding:.4rem .6rem"><div style="font-size:1.2rem;font-weight:bold;color:#66c0f4">{tp["score"]}</div><div style="font-size:.8rem;margin:.2rem 0">{_html_esc(tp["name"])}</div><div style="font-size:.8rem"><span style="color:#6cc644">-{tp["discount"]}%</span> {_html_esc(tp["price_final"])}</div></div></a>'
        picks_html = f'<h2 style="margin:1rem 0 .5rem">Top Picks</h2><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.5rem">{pick_cards}</div>'

    sale_line = f' — {_html_esc(sale_name)}' if sale_name else ""
    return f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{_html_esc(title)}</title>
<style>{{*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:system-ui,sans-serif;background:#1b2838;color:#c7d5e0;padding:1rem;max-width:1000px;margin:0 auto}}a{{color:#66c0f4;text-decoration:none}}a:hover{{text-decoration:underline}}h1{{font-size:1.3rem;margin-bottom:.3rem}}table{{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:.5rem}}th{{background:#2a475e;padding:.4rem .5rem;text-align:left;border-bottom:2px solid #2a475e}}td{{padding:.35rem .5rem;border-bottom:1px solid #2a475e}}tr:hover{{background:#1a3a5c}}.meta{{color:#8f98a0;font-size:.85rem;margin-bottom:1rem}}.share-modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;align-items:center;justify-content:center}}.share-modal.active{{display:flex}}.share-modal-content{{background:#16202d;border:1px solid #2a475e;border-radius:12px;padding:1.5rem;max-width:420px;width:90%}}.share-modal h3{{color:#66c0f4;margin-bottom:1rem;font-size:1.1rem}}.share-game-info{{background:#1b2838;border-radius:8px;padding:1rem;margin-bottom:1rem}}.share-game-name{{font-weight:600;font-size:1rem;margin-bottom:.5rem}}.share-game-price{{color:#6cc644;font-size:1.2rem;font-weight:700}}.share-game-price span{{text-decoration:line-through;color:#8f98a0;font-weight:400;font-size:.9rem}}.share-game-minhist{{font-size:.8rem;color:#8f98a0;margin-top:.3rem}}.share-game-minhist span{{color:#f0b232}}.share-actions{{display:flex;flex-direction:column;gap:.6rem}}.share-btn{{padding:.6rem 1rem;border-radius:6px;font-size:.85rem;font-weight:600;cursor:pointer;text-align:center}}.share-btn-copy-app{{background:#66c0f4;color:#000;border:none}}.share-btn-copy-app:hover{{background:#4db8e8}}.share-btn-copy-steam{{background:#2a475e;color:#c7d5e0;border:1px solid #2a475e}}.share-btn-copy-steam:hover{{border-color:#66c0f4}}.share-btn-open{{background:#1b2838;color:#8f98a0;border:1px solid #2a475e}}.share-close{{margin-top:.8rem;text-align:center;color:#8f98a0;font-size:.85rem;cursor:pointer}}.share-close:hover{{color:#c7d5e0}}</style>
</head><body>
<h1>&#127918; {_html_esc(title)}{sale_line}</h1>
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
<script>let currentShareData=null,currentSteamUrl='';function openShareModal(game){{currentShareData=game;currentSteamUrl='https://store.steampowered.com/app/'+game.appid+'/';document.getElementById('share-name').textContent=game.name||'';document.getElementById('share-price').innerHTML=(game.price_original&&game.price?'<span>$'+game.price_original+' </span>':'')+(game.price||'')+(game.discount?' ('+game.discount+'% OFF)':'');document.getElementById('share-minhist').innerHTML=game.min_hist?'Minimo historico: <span>$'+game.min_hist+'</span>':'';document.getElementById('share-modal').classList.add('active')}}function closeShareModal(){{document.getElementById('share-modal').classList.remove('active');currentShareData=null}}function copyShareLink(){{if(!currentShareData)return;const encoded=btoa(JSON.stringify(currentShareData));const shareUrl='steamtools://share?data='+encoded;navigator.clipboard.writeText(shareUrl).then(()=>{{const btn=document.getElementById('btn-copy-app');btn.textContent='Copiado!';setTimeout(()=>btn.textContent='Copiar link steamtools://',2000)}})}}function copySteamLink(){{if(!currentSteamUrl)return;navigator.clipboard.writeText(currentSteamUrl).then(()=>{{const btn=document.querySelector('.share-btn-copy-steam');btn.textContent='Copiado!';setTimeout(()=>btn.textContent='Copiar link de Steam',2000)}})}}function openInSteam(){{if(currentSteamUrl)window.open(currentSteamUrl,'_blank')}}</script>
</body></html>'''


def generate_csv(
    deals, priorities=None, reviews=None, deck_compat=None,
    protondb_data=None, anticheat_data=None, tags_data=None,
    hltb_hours=None, historical_lows=None, current_prices=None,
    top_picks=None, local_trends=None, achievements_data=None,
) -> str:
    priorities = priorities or {}
    reviews = reviews or {}
    deck_compat = deck_compat or {}
    protondb_data = protondb_data or {}
    anticheat_data = anticheat_data or {}
    tags_data = tags_data or {}
    hltb_hours = hltb_hours or {}
    historical_lows = historical_lows or {}
    current_prices = current_prices or {}
    local_trends = local_trends or {}
    achievements_data = achievements_data or {}
    pick_scores = {tp["appid"]: tp["score"] for tp in (top_picks or [])}

    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(["AppID", "Name", "Discount%", "Price (MXN)", "Original Price", "Year",
                      "Reviews", "Reviews%", "ReviewCount", "Metacritic", "Deck", "ProtonDB",
                      "AntiCheat", "Tags", "Mode", "Achievements", "AvgCompletion%",
                      "HLTB Hours", "Price/Hour", "Priority",
                      "Score", "Historical Low", "Best Price", "Trend", "URL"])

    for d in deals:
        appid = d["appid"]
        rev = reviews.get(appid)
        pdb = protondb_data.get(appid)
        ac = anticheat_data.get(appid)
        low = historical_lows.get(appid)
        bp = current_prices.get(appid)
        trend = local_trends.get(appid)
        hours = hltb_hours.get(appid)
        price_raw = d.get("price_raw", 0)
        pph = f"{(price_raw / 100) / hours:.2f}" if hours and hours > 0 and price_raw > 0 else ""
        prio = priorities.get(appid, 0)
        top_tags = get_top_tags(tags_data, appid, n=5)

        mc = d.get("metacritic_score", "")
        mp = multiplayer_badges(d.get("categories", []))
        ach = achievements_data.get(appid)
        writer.writerow([
            appid, d["name"], d["discount"], d["price_final"], d.get("price_original", ""),
            d.get("release_year", ""),
            rev["desc"] if rev else "", rev["pct"] if rev else "", rev["total"] if rev else "",
            mc if mc else "",
            CSV_DECK.get(deck_compat.get(appid, 0), ""),
            CSV_PROTON.get(pdb["tier"], "") if pdb else "",
            f"{', '.join(ac.get('anticheats', []))} ({ac['status']})" if ac else "",
            "; ".join(top_tags),
            mp,
            ach["count"] if ach else "", f"{ach['avg_completion']:.1f}" if ach else "",
            f"{hours:.1f}" if hours else "", pph,
            prio if prio > 0 else "",
            pick_scores.get(appid, ""),
            f"${low['price']:.0f} ({low['date']})" if low else "",
            f"${bp['price']:.0f} en {bp['store']}" if bp else "",
            _csv_trend(trend) if trend else "",
            STORE_URL.format(appid=appid),
        ])

    return buf.getvalue()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _get_json(url: str, headers: dict = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _post_json(url: str, body) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


# ─────────────────────────────────────────────
# NOTIFICATIONS (TELEGRAM / DISCORD)
# ─────────────────────────────────────────────


def build_notification_summary(deals, comparison, top_picks, watchlist_alerts=None):
    """Build a summary dict for notifications. Returns None if nothing notable."""
    comp = comparison or {}
    new_count = len(comp.get("new_deals", set()))
    price_drops = [(appid, v) for appid, v in comp.get("price_changes", {}).items() if v["direction"] == "down"]
    price_drops.sort(key=lambda x: x[1]["delta_raw"])  # biggest drop first

    if new_count == 0 and not price_drops and not watchlist_alerts:
        return None

    deal_map = {d["appid"]: d for d in deals}
    top3 = (top_picks or [])[:3]

    return {
        "total_deals": len(deals),
        "new_count": new_count,
        "top_3": [{"name": tp["name"], "discount": tp["discount"], "price": tp["price_final"], "score": tp["score"]} for tp in top3],
        "price_drops": [{"name": deal_map.get(appid, {}).get("name", appid), "delta": v["delta_str"], "prev": v["prev_price"]} for appid, v in price_drops[:5]],
        "watchlist_hits": [{"name": wa["name"], "price": wa["price_final"], "target": wa["target_price"]} for wa in (watchlist_alerts or [])],
    }


def send_telegram(token: str, chat_id: str, summary: dict) -> bool:
    """Send notification via Telegram Bot API."""
    lines = [f"🎮 *Steam Deals Update*", f"📊 {summary['total_deals']} deals encontrados"]
    if summary["new_count"]:
        lines.append(f"🆕 {summary['new_count']} nuevos")
    if summary["top_3"]:
        lines.append("\n🏆 *Top Picks:*")
        for i, tp in enumerate(summary["top_3"], 1):
            lines.append(f"  {i}\\. {tp['name']} \\-{tp['discount']}% {tp['price']}")
    if summary["price_drops"]:
        lines.append("\n⬇️ *Bajaron de precio:*")
        for pd in summary["price_drops"]:
            lines.append(f"  • {pd['name']} \\-{pd['delta']}")
    if summary["watchlist_hits"]:
        lines.append("\n🎯 *Watchlist Alerts:*")
        for wh in summary["watchlist_hits"]:
            lines.append(f"  • {wh['name']} a {wh['price']} \\(objetivo: ${wh['target']:.0f}\\)")

    text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        body = {"chat_id": chat_id, "text": text, "parse_mode": "MarkdownV2"}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        return resp.get("ok", False)
    except Exception as e:
        print(f"  {_warn(f'Telegram error: {e}')}")
        return False


def send_discord(webhook_url: str, summary: dict) -> bool:
    """Send notification via Discord webhook."""
    fields = [
        {"name": "📊 Deals", "value": f"{summary['total_deals']} encontrados", "inline": True},
    ]
    if summary["new_count"]:
        fields.append({"name": "🆕 Nuevos", "value": str(summary["new_count"]), "inline": True})
    if summary["top_3"]:
        top_text = "\n".join(f"{i}. **{tp['name']}** -{tp['discount']}% {tp['price']}" for i, tp in enumerate(summary["top_3"], 1))
        fields.append({"name": "🏆 Top Picks", "value": top_text})
    if summary["price_drops"]:
        drops_text = "\n".join(f"• {pd['name']} -{pd['delta']}" for pd in summary["price_drops"])
        fields.append({"name": "⬇️ Bajaron", "value": drops_text})
    if summary["watchlist_hits"]:
        wl_text = "\n".join(f"• {wh['name']} a {wh['price']}" for wh in summary["watchlist_hits"])
        fields.append({"name": "🎯 Watchlist", "value": wl_text})

    payload = {"embeds": [{"title": "🎮 Steam Deals Update", "color": 0x66c0f4, "fields": fields}]}
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            pass
        return True
    except Exception as e:
        print(f"  {_warn(f'Discord error: {e}')}")
        return False


def send_notifications(filters: dict, summary: dict) -> None:
    """Send notifications via configured channels."""
    if filters.get("telegram_token") and filters.get("telegram_chat"):
        ok = send_telegram(filters["telegram_token"], filters["telegram_chat"], summary)
        if ok:
            print(f"  {_ok('Notificación Telegram enviada')}")
    if filters.get("discord_webhook"):
        ok = send_discord(filters["discord_webhook"], summary)
        if ok:
            print(f"  {_ok('Notificación Discord enviada')}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    global WEB_EVENT_MODE
    sys.stdout.reconfigure(line_buffering=True)

    print(f"{C.BOLD}=== Steam Wishlist Deals Generator ==={C.RST}\n")

    WEB_RUN, INTERACTIVE, KEY, VANITY, HLTB_CSV, OUTPUT_DIR, MIN_DISCOUNT, genres, no_cache, FAMILY_JSON, ITAD_KEY, FILTERS = get_config()
    WEB_EVENT_MODE = bool(WEB_RUN)
    if not WEB_RUN and not INTERACTIVE:
        print(f"  {_dim('Flujo recomendado: wizard web (python3 steam_deals_web.py).')}" )
        print(f"  {_dim('CLI disponible con flags/config, o modo interactivo con --interactive.')}\n")
    RATE_LIMIT = 1.5
    t0 = time.monotonic()

    # Calcular total de pasos dinámicamente (+2 reviews/deck, +1 protondb/ac, +1 tags, +1 HTML, owned solo con key)
    TOTAL = 11 + (1 if KEY else 0) + (1 if FAMILY_JSON else 0) + (1 if HLTB_CSV else 0) + (1 if ITAD_KEY else 0) + (1 if FILTERS.get("csv") else 0) + (1 if FILTERS.get("telegram_token") or FILTERS.get("discord_webhook") else 0) + (1 if FILTERS.get("compare") else 0)

    if not KEY:
        print(f"  {_dim('Sin API Key — modo público (wishlist debe ser pública)')}")
    _n = [0]

    def step(msg: str):
        _n[0] += 1
        print(f"\n{C.CYN}[{_n[0]}/{TOTAL}]{C.RST} {_bold(msg)}", flush=True)
        emit_event("progress", current=_n[0], total=TOTAL, label=msg)

    # Validar rutas opcionales antes de arrancar
    if HLTB_CSV and not HLTB_CSV.exists():
        print(f"{_err(f'HLTB CSV no encontrado: {HLTB_CSV}')}")
        HLTB_CSV = None
    if FAMILY_JSON and not FAMILY_JSON.exists():
        print(f"{_err(f'Family JSON no encontrado: {FAMILY_JSON}')}")
        FAMILY_JSON = None

    # [1] Steam ID
    step("Resolviendo Steam ID...")
    steam_id = resolve_steam_id(KEY, VANITY)
    print(f"  {_ok(steam_id)}")

    # [2] Wishlist (con prioridad)
    step("Obteniendo wishlist...")
    wishlist_appids, priorities = get_wishlist(KEY, steam_id)
    ranked = sum(1 for p in priorities.values() if p > 0)
    print(f"  {_ok(f'{len(wishlist_appids):,} juegos ({ranked:,} con prioridad)')}")

    # [3] Biblioteca propia (requiere API key)
    owned: dict[str, str] = {}
    if KEY:
        step("Obteniendo biblioteca de Steam...")
        owned = get_owned_games(KEY, steam_id)
        print(f"  {_ok(f'{len(owned):,} juegos comprados')}")

    # Compare wishlists (optional)
    compare_data = None
    gift_ideas = []
    if FILTERS.get("compare"):
        step("Comparando wishlists...")
        try:
            compare_data = compare_wishlists(KEY, steam_id, FILTERS["compare"])
            friend_set = compare_data["friend_set"]
            my_set = set(wishlist_appids)
            overlap = my_set & friend_set
            compare_data["overlap"] = overlap
            print(f"  {_ok(f'Friend: {len(compare_data['friend_appids']):,} juegos en wishlist')}")
            print(f"  {_ok(f'{len(overlap)} en común')}")
        except Exception as e:
            print(f"  {_err(f'No se pudo comparar: {e}')}")
            compare_data = None

    # [4] Detectar oferta activa
    step("Detectando oferta activa de Steam...")
    sale_name = get_active_sale()
    if sale_name:
        print(f"  {_ok(f'{SYM_TAG}  {sale_name}')}")
    else:
        print(f"  {_dim('Sin oferta especial detectada')}")

    # Construir nombre del archivo
    today_obj = date.today()
    date_str = today_obj.strftime("%Y-%m-%d")
    if sale_name:
        safe_sale = re.sub(r'[<>:"/\\|?*]', '', sale_name).strip()
        filename = f"Steam Deals {safe_sale} {date_str}.md"
    else:
        filename = f"Steam Deals {date_str}.md"
    OUTPUT_MD = Path(OUTPUT_DIR) / filename
    print(f"  {_dim(f'Archivo: {OUTPUT_MD.name}')}")

    # Cargar historial de runs
    previous_run = load_previous_run(steam_id)
    run_history = load_run_history(steam_id) if previous_run else []
    if previous_run:
        prev_date = previous_run.get("date", "?")
        prev_count = len(previous_run.get("deals", {}))
        print(f"  {_dim(f'Run anterior: {prev_date} ({prev_count} deals)')}")

    # Fallback: cargar deals del MD anterior si no hay historial
    previous_appids: set[str] = set()
    if not previous_run:
        previous_appids = load_previous_deal_appids(Path(OUTPUT_DIR), filename)
        if previous_appids:
            print(f"  {_dim(f'MD anterior encontrado ({len(previous_appids)} deals) — fallback')}")

    # [5] Precios (con smart cache + batching)
    step("Obteniendo precios de Steam...")
    fetched_cache, cache_age = load_price_cache(steam_id)

    if no_cache:
        fetched_cache = {}
        # Also clear reviews, deck, tags, protondb, anticheat caches
        for cf in (REVIEWS_CACHE_FILE, DECK_CACHE_FILE, TAGS_CACHE_FILE, PROTONDB_CACHE_FILE, ANTICHEAT_CACHE_FILE, ACHIEVEMENTS_CACHE_FILE):
            if cf.exists():
                cf.unlink()
        print(f"  {_warn('--no-cache: ignorando caché existente')}")
    elif fetched_cache:
        new_appids = [a for a in wishlist_appids if a not in fetched_cache]
        if cache_age <= CACHE_MAX_HOURS:
            status_msg = f"{len(new_appids)} nuevos por fetchear" if new_appids else _dim("sin nuevos, skip fetch")
            print(f"  {_ok(f'Caché válida ({cache_age:.1f}h)')} — {status_msg}")
        else:
            print(f"  {_warn(f'Caché expirada ({cache_age:.0f}h) — re-fetching todo')}")
            fetched_cache = {}
    else:
        print(f"  {_dim('Sin caché — fetch completo')}")

    try:
        deals, n_fetched = get_deals_from_wishlist(
            wishlist_appids, fetched_cache, steam_id,
            country="mx", min_discount=MIN_DISCOUNT, rate_limit=RATE_LIMIT,
        )
    except KeyboardInterrupt:
        print(f"\n  {_warn('Interrumpido — guardando caché parcial...')}")
        save_price_cache(steam_id, fetched_cache)
        print(f"  {_ok('Caché guardada. Ejecuta de nuevo para continuar donde quedó.')}")
        sys.exit(1)

    if n_fetched > 0:
        save_price_cache(steam_id, fetched_cache)
        print(f"  {_ok(f'{len(deals):,} deals (≥{MIN_DISCOUNT}%) — caché actualizada')}")
    else:
        print(f"  {_ok(f'{len(deals):,} deals (≥{MIN_DISCOUNT}%) — desde caché')}")

    # Comparar con runs anteriores
    comparison = compute_deal_comparison(deals, previous_run, run_history)
    comp_new = len(comparison.get("new_deals", set()))
    comp_gone = len(comparison.get("disappeared", []))
    comp_drops = sum(1 for v in comparison.get("price_changes", {}).values() if v["direction"] == "down")
    if comp_new or comp_gone or comp_drops:
        parts = []
        if comp_new: parts.append(f"{comp_new} nuevos")
        if comp_gone: parts.append(f"{comp_gone} terminaron")
        if comp_drops: parts.append(f"{comp_drops} bajaron")
        print(f"  {_ok(' · '.join(parts))}")

    # Guardar run actual en historial
    save_run_history(steam_id, VANITY, sale_name, MIN_DISCOUNT, deals)

    # Historial local de precios (tendencias)
    price_history = load_price_history(steam_id)
    log_price_snapshot(price_history, deals)
    local_trends = analyze_trends(price_history, deals)
    save_price_history(price_history)
    trend_count = sum(1 for t in local_trends.values() if not t.get("is_first_time"))
    best_count = sum(1 for t in local_trends.values() if t.get("is_best_local"))
    if trend_count:
        print(f"  {_ok(f'{trend_count} con historial · {best_count} en mejor precio local')}")

    # [6] Reviews de Steam (solo para deals)
    step("Obteniendo reviews de Steam...")
    deal_appids = [d["appid"] for d in deals]
    reviews_cache, reviews_age = load_reviews_cache(steam_id)
    if no_cache:
        reviews_cache = {}
    elif reviews_cache and reviews_age <= EXTRA_CACHE_TTL:
        missing = [a for a in deal_appids if a not in reviews_cache]
        if missing:
            print(f"  {_ok(f'Caché válida ({reviews_age:.0f}h)')} — {len(missing)} nuevos por fetchear")
        else:
            print(f"  {_ok(f'Caché válida ({reviews_age:.0f}h)')} — {_dim('todos en caché')}")
    elif reviews_cache:
        print(f"  {_warn(f'Caché expirada ({reviews_age:.0f}h) — re-fetching')}")
        reviews_cache = {}
    reviews_data = fetch_reviews(deal_appids, reviews_cache)
    save_reviews_cache(steam_id, reviews_data)
    reviewed = sum(1 for a in deal_appids if a in reviews_data)
    print(f"  {_ok(f'{reviewed}/{len(deal_appids)} deals con reviews')}")

    # [7] Compatibilidad Steam Deck (solo para deals)
    step("Obteniendo compatibilidad Steam Deck...")
    deck_cache, deck_age = load_deck_cache(steam_id)
    if no_cache:
        deck_cache = {}
    elif deck_cache and deck_age <= EXTRA_CACHE_TTL:
        missing = [a for a in deal_appids if a not in deck_cache]
        if missing:
            print(f"  {_ok(f'Caché válida ({deck_age:.0f}h)')} — {len(missing)} nuevos por fetchear")
        else:
            print(f"  {_ok(f'Caché válida ({deck_age:.0f}h)')} — {_dim('todos en caché')}")
    elif deck_cache:
        print(f"  {_warn(f'Caché expirada ({deck_age:.0f}h) — re-fetching')}")
        deck_cache = {}
    deck_data = fetch_deck_compat(deal_appids, deck_cache)
    save_deck_cache(steam_id, deck_data)
    verified = sum(1 for a in deal_appids if deck_data.get(a) == 3)
    playable = sum(1 for a in deal_appids if deck_data.get(a) == 2)
    print(f"  {_ok(f'{verified} Verified · {playable} Playable')}")

    # [8] ProtonDB + Are We Anti-Cheat Yet
    step("Obteniendo datos Linux (ProtonDB + Anti-Cheat)...")
    protondb_cache, protondb_age = load_protondb_cache()
    if no_cache:
        protondb_cache = {}
    elif protondb_cache and protondb_age <= EXTRA_CACHE_TTL:
        missing_pdb = [a for a in deal_appids if a not in protondb_cache]
        if missing_pdb:
            print(f"  {_ok(f'ProtonDB caché válida ({protondb_age:.0f}h)')} — {len(missing_pdb)} nuevos")
        else:
            print(f"  {_ok(f'ProtonDB caché válida ({protondb_age:.0f}h)')}")
    elif protondb_cache:
        protondb_cache = {}
    protondb_data = fetch_protondb(deal_appids, protondb_cache)
    save_protondb_cache(protondb_data)
    pdb_count = sum(1 for a in deal_appids if a in protondb_data)
    platinum = sum(1 for a in deal_appids if protondb_data.get(a, {}).get("tier") in ("platinum", "native"))
    print(f"  {_ok(f'ProtonDB: {pdb_count}/{len(deal_appids)} · {platinum} Platinum/Native')}")

    # Anti-cheat DB (single download, cached)
    anticheat_cache, anticheat_age = load_anticheat_cache()
    if no_cache or not anticheat_cache or anticheat_age > EXTRA_CACHE_TTL:
        anticheat_data = fetch_anticheat_db()
        if anticheat_data:
            save_anticheat_cache(anticheat_data)
            print(f"  {_ok(f'Anti-Cheat DB: {len(anticheat_data)} juegos cargados')}")
    else:
        anticheat_data = anticheat_cache
        print(f"  {_ok(f'Anti-Cheat DB desde caché ({anticheat_age:.0f}h)')}")
    ac_issues = sum(1 for a in deal_appids if anticheat_data.get(a, {}).get("status") in ("Denied", "Broken"))
    if ac_issues:
        print(f"  {_warn(f'{ac_issues} deals con problemas de anti-cheat en Linux')}")

    # [9] Tags de Steam (via SteamSpy, solo para deals)
    step("Obteniendo tags de Steam...")
    tags_cache, tags_age = load_tags_cache()
    if no_cache:
        tags_cache = {}
    elif tags_cache and tags_age <= TAGS_CACHE_TTL:
        missing_tags = [a for a in deal_appids if a not in tags_cache]
        if missing_tags:
            print(f"  {_ok(f'Caché válida ({tags_age:.0f}h)')} — {len(missing_tags)} nuevos")
        else:
            print(f"  {_ok(f'Caché válida ({tags_age:.0f}h)')} — {_dim('todos en caché')}")
    elif tags_cache:
        print(f"  {_warn(f'Caché expirada ({tags_age:.0f}h) — re-fetching')}")
        tags_cache = {}
    tags_data = fetch_tags(deal_appids, tags_cache)
    save_tags_cache(tags_data)
    tagged = sum(1 for a in deal_appids if a in tags_data and tags_data[a])
    print(f"  {_ok(f'{tagged}/{len(deal_appids)} deals con tags')}")

    # [10] Achievements
    step("Obteniendo achievements...")
    ach_cache, ach_age = load_achievements_cache(steam_id)
    if no_cache:
        ach_cache = {}
    elif ach_cache and ach_age <= ACHIEVEMENTS_CACHE_TTL:
        missing_ach = [a for a in deal_appids if a not in ach_cache]
        if missing_ach:
            print(f"  {_ok(f'Caché válida ({ach_age:.0f}h)')} — {len(missing_ach)} nuevos por fetchear")
        else:
            print(f"  {_ok(f'Caché válida ({ach_age:.0f}h)')} — {_dim('todos en caché')}")
    elif ach_cache:
        print(f"  {_warn(f'Caché expirada ({ach_age:.0f}h) — re-fetching')}")
        ach_cache = {}
    achievements_data = fetch_achievements(deal_appids, ach_cache)
    save_achievements_cache(steam_id, achievements_data)
    ach_count = sum(1 for a in deal_appids if a in achievements_data)
    print(f"  {_ok(f'{ach_count}/{len(deal_appids)} deals con achievements')}")

    # Biblioteca familiar (opcional)
    family_appids: set[str] = set()
    if FAMILY_JSON:
        step("Cargando biblioteca familiar...")
        family_appids = load_family_games(FAMILY_JSON)
        print(f"  {_ok(f'{len(family_appids):,} juegos en la familia')}")

    # HLTB
    backlog_on_sale, have_on_sale = [], []
    if HLTB_CSV:
        step("Cruzando con HLTB...")
        hltb = parse_hltb(HLTB_CSV)
        bl, cp, pl, rt = len(hltb["backlog"]), len(hltb["completed"]), len(hltb["playing"]), len(hltb["retired"])
        print(f"  {_dim(f'Backlog: {bl:,} | Completados: {cp} | Playing: {pl} | Retired: {rt}')}")
        backlog_on_sale, have_on_sale = cross_hltb_with_deals(hltb, deals, family_appids=family_appids)
        print(f"  {_ok(f'{len(backlog_on_sale)} backlog en oferta | {len(have_on_sale)} completados/retirados')}")

    # IsThereAnyDeal (mínimo histórico + precios multi-tienda + bundles, opcional)
    historical_lows: dict[str, dict] = {}
    current_prices: dict[str, dict] = {}
    active_bundles: dict[str, list[dict]] = {}
    itad_ids: dict[str, str] = {}
    if ITAD_KEY:
        step("Obteniendo datos de IsThereAnyDeal...")
        itad_ids = itad_lookup_games(deal_appids, ITAD_KEY)
        print(f"  {_ok(f'{len(itad_ids):,}/{len(deal_appids):,} juegos encontrados en ITAD')}")
        if itad_ids:
            historical_lows = itad_get_store_lows(itad_ids, ITAD_KEY, country="MX")
            print(f"  {_ok(f'{len(historical_lows):,} mínimos históricos obtenidos')}")
            current_prices = itad_get_current_prices(itad_ids, ITAD_KEY, country="MX")
            if current_prices:
                print(f"  {_ok(f'{len(current_prices):,} juegos más baratos en otra tienda')}")
            else:
                print(f"  {_dim('Steam es el mejor precio en todos los deals')}")
            active_bundles = itad_get_active_bundles(itad_ids, ITAD_KEY)
            if active_bundles:
                bundle_names = {b["title"] for bs in active_bundles.values() for b in bs}
                print(f"  {_ok(f'{len(active_bundles)} juegos en {len(bundle_names)} bundle(s)')}")
            else:
                print(f"  {_dim('Ningún juego en bundles activos')}")

    # Construir mapa HLTB horas para filtros y top picks
    hltb_hours: dict[str, float] = {}
    for entry in backlog_on_sale + have_on_sale:
        if entry.get("hours"):
            hltb_hours[entry["appid"]] = entry["hours"]

    # Aplicar filtros CLI avanzados
    original_count = len(deals)
    deals = apply_filters(deals, FILTERS, reviews_data, deck_data, hltb_hours, previous_appids, comparison)
    if len(deals) < original_count:
        print(f"  {_ok(f'Filtros aplicados: {original_count} → {len(deals)} deals')}")

    # Top Picks
    top_picks = rank_top_picks(deals, priorities, reviews_data, hltb_hours, deck_data, n=FILTERS.get("top", 10))

    # Watchlist alerts
    watchlist = load_watchlist()
    watchlist_alerts = []
    if watchlist:
        watchlist_alerts = check_watchlist_alerts(deals, watchlist)
        if watchlist_alerts:
            print(f"  {_ok(f'{SYM_TARGET} {len(watchlist_alerts)} watchlist alerts!')}")
            for wa in watchlist_alerts:
                print(f"    {wa['name']} — {wa['price_final']} (objetivo: ${wa['target_price']:.0f})")

    # Budget mode
    budget_result = None
    if FILTERS.get("budget"):
        budget_result = compute_budget_picks(deals, FILTERS["budget"], top_picks, watchlist_alerts)
        print(f"  {_ok(f'{SYM_BUDGET} Budget ${FILTERS['budget']:.0f}: {budget_result['games_count']} juegos, ${budget_result['total_spent']:.0f} gastados')}")

    # Gift ideas (compare wishlists)
    if compare_data:
        gift_ideas = build_gift_ideas(compare_data["friend_set"], deals, owned)
        if gift_ideas:
            print(f"  {_ok(f'{SYM_GIFT} {len(gift_ideas)} gift ideas en oferta')}")

    # Generar MD
    step("Generando Markdown...")
    md = generate_md(
        deals, backlog_on_sale, have_on_sale,
        VANITY, owned, wishlist_appids,
        MIN_DISCOUNT, genres,
        hltb_used=HLTB_CSV is not None,
        family_appids=family_appids,
        sale_name=sale_name,
        priorities=priorities,
        historical_lows=historical_lows,
        previous_appids=previous_appids,
        reviews=reviews_data,
        deck_compat=deck_data,
        current_prices=current_prices,
        top_picks=top_picks,
        comparison=comparison,
        sort_field=FILTERS.get("sort", "discount"),
        tags_data=tags_data,
        local_trends=local_trends,
        active_bundles=active_bundles,
        protondb_data=protondb_data,
        anticheat_data=anticheat_data,
        achievements_data=achievements_data,
        watchlist_alerts=watchlist_alerts,
        budget_result=budget_result,
        compare_data=compare_data,
        gift_ideas=gift_ideas,
    )
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(f"  {_ok(str(OUTPUT_MD))}")
    emit_event("file", path=str(OUTPUT_MD))

    # Generar HTML interactivo
    step("Generando HTML interactivo...")
    html = generate_html(
        deals, backlog_on_sale, have_on_sale,
        VANITY, owned, wishlist_appids,
        MIN_DISCOUNT, genres,
        hltb_used=HLTB_CSV is not None,
        family_appids=family_appids,
        sale_name=sale_name,
        priorities=priorities,
        historical_lows=historical_lows,
        previous_appids=previous_appids,
        reviews=reviews_data,
        deck_compat=deck_data,
        current_prices=current_prices,
        top_picks=top_picks,
        tags_data=tags_data,
        protondb_data=protondb_data,
        achievements_data=achievements_data,
        watchlist_alerts=watchlist_alerts,
        budget_result=budget_result,
        compare_data=compare_data,
        gift_ideas=gift_ideas,
        local_trends=local_trends,
        price_history=price_history,
    )
    OUTPUT_HTML = OUTPUT_MD.with_suffix(".html")
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"  {_ok(str(OUTPUT_HTML))}")
    emit_event("file", path=str(OUTPUT_HTML))

    # Generar HTML compartible (lightweight)
    share_html = generate_share_html(deals, VANITY, MIN_DISCOUNT, sale_name=sale_name,
                                      top_picks=top_picks, reviews=reviews_data, deck_compat=deck_data)
    OUTPUT_SHARE = OUTPUT_MD.parent / f"Steam Deals Share {date.today().strftime('%Y-%m-%d')}.html"
    OUTPUT_SHARE.write_text(share_html, encoding="utf-8")
    print(f"  {_ok(str(OUTPUT_SHARE))}")
    emit_event("file", path=str(OUTPUT_SHARE))

    # Generar CSV (opcional)
    if FILTERS.get("csv"):
        step("Generando CSV...")
        csv_content = generate_csv(
            deals, priorities=priorities, reviews=reviews_data, deck_compat=deck_data,
            protondb_data=protondb_data, anticheat_data=anticheat_data, tags_data=tags_data,
            hltb_hours=hltb_hours, historical_lows=historical_lows, current_prices=current_prices,
            top_picks=top_picks, local_trends=local_trends, achievements_data=achievements_data,
        )
        OUTPUT_CSV = OUTPUT_MD.with_suffix(".csv")
        OUTPUT_CSV.write_text(csv_content, encoding="utf-8")
        print(f"  {_ok(str(OUTPUT_CSV))}")
        emit_event("file", path=str(OUTPUT_CSV))

    # Notifications (optional)
    if FILTERS.get("telegram_token") or FILTERS.get("discord_webhook"):
        step("Enviando notificaciones...")
        notif_summary = build_notification_summary(deals, comparison, top_picks, watchlist_alerts)
        if notif_summary:
            send_notifications(FILTERS, notif_summary)
        else:
            print(f"  {_dim('Sin cambios notables — no se envió notificación')}")

    # Resumen final
    elapsed = time.monotonic() - t0
    new_count = sum(1 for d in deals if previous_appids and d["appid"] not in previous_appids) if previous_appids else 0
    print(f"\n{C.GRN}{'─' * 42}{C.RST}")
    print(f"  {_bold('Listo')} en {elapsed:.1f}s")
    summary = f"  {len(deals):,} deals · {len(backlog_on_sale)} backlog"
    if new_count:
        summary += f" · {new_count} nuevos"
    if top_picks:
        summary += f" · Top pick: {top_picks[0]['name']} ({top_picks[0]['score']})"
    summary += f" · {OUTPUT_MD.name}"
    print(summary)
    print(f"{C.GRN}{'─' * 42}{C.RST}\n")


def run_scheduled():
    """Run main() in a loop if --schedule is set."""
    # Peek at --schedule arg without full config parse
    import shlex
    schedule_hours = None
    for i, arg in enumerate(sys.argv):
        if arg == "--schedule" and i + 1 < len(sys.argv):
            try:
                schedule_hours = float(sys.argv[i + 1])
            except ValueError:
                pass
            break

    if not schedule_hours:
        main()
        return

    print(f"{C.BOLD}=== Modo programado: cada {schedule_hours:.1f} horas ==={C.RST}")
    print(f"  {C.DIM}Ctrl+C para detener{C.RST}\n")
    run_count = 0
    while True:
        run_count += 1
        print(f"\n{'═' * 42}")
        print(f"  Run #{run_count} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'═' * 42}\n")
        try:
            main()
        except KeyboardInterrupt:
            print(f"\n  {C.YLW}Scheduler detenido.{C.RST}")
            break
        except Exception as e:
            print(f"\n  {C.RED}Error en run #{run_count}: {e}{C.RST}")
        next_run = datetime.now().strftime('%H:%M')
        wait_secs = schedule_hours * 3600
        next_time = (datetime.now().timestamp() + wait_secs)
        next_str = datetime.fromtimestamp(next_time).strftime('%H:%M')
        print(f"\n  {C.DIM}Próximo run a las {next_str} (en {schedule_hours:.1f}h). Ctrl+C para salir.{C.RST}")
        try:
            time.sleep(wait_secs)
        except KeyboardInterrupt:
            print(f"\n  {C.YLW}Scheduler detenido.{C.RST}")
            break


if __name__ == "__main__":
    run_scheduled()
