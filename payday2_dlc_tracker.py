#!/usr/bin/env python3
"""
PAYDAY 2 DLC Tracker — Precios y ofertas de DLCs en tiempo real.

Uso:
    python3 payday2_dlc_tracker.py --vanity gaben
    python3 payday2_dlc_tracker.py --key TU_KEY --vanity gaben
    python3 payday2_dlc_tracker.py --itad-key TU_KEY --budget 500
    python3 payday2_dlc_tracker.py --mark-owned 12345
    python3 payday2_dlc_tracker.py --min-deal 50
    python3 payday2_dlc_tracker.py --no-cache

Reutiliza la config de Steam Deals (~/.config/steam_deals.json).
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

from shared_web_infra import resolve_config_secret
from shared.io_utils import http_get_json, http_post_json, load_json_file, write_json_file

from shared.io_utils import http_get_json, http_post_json, load_json_file


# ============================================
# ANSI + HELPERS
# ============================================


class C:
    RST = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GRN = "\033[32m"
    YLW = "\033[33m"
    RED = "\033[31m"
    CYN = "\033[36m"


def _ok(msg):
    return f"{C.GRN}[+]{C.RST}  {msg}"


def _warn(msg):
    return f"{C.YLW}[!]{C.RST}  {msg}"


def _err(msg):
    return f"{C.RED}[x]{C.RST}  {msg}"


def _dim(msg):
    return f"{C.DIM}{msg}{C.RST}"


def _bold(msg):
    return f"{C.BOLD}{msg}{C.RST}"


def _get_json(url: str, headers: dict = None) -> dict:
    return http_get_json(url, headers=headers, timeout=15)


def _post_json(url: str, body) -> dict:
    return http_post_json(url, body, timeout=30)


STORE_URL = "https://store.steampowered.com/app/{appid}/"


def _md_esc(text: str) -> str:
    return text.replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def _link(name: str, appid: str) -> str:
    return f"[{_md_esc(name)}]({STORE_URL.format(appid=appid)})"


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


# ============================================─
# CONFIG
# ============================================─

CONFIG_FILE = Path.home() / ".config" / "steam_deals.json"


def load_user_config() -> dict:
    return load_json_file(CONFIG_FILE, {})


def get_config(*, argv=None, environ=None, load_user_config_fn=load_user_config):
    parser = argparse.ArgumentParser(description="PAYDAY 2 DLC Tracker")
    parser.add_argument("--key", help="Steam API Key")
    parser.add_argument("--vanity", help="Steam vanity URL, ID, o perfil")
    parser.add_argument("--itad-key", help="IsThereAnyDeal API Key")
    parser.add_argument("--output", help="Directorio de salida")
    parser.add_argument("--no-cache", action="store_true", help="Ignorar caché")
    parser.add_argument(
        "--mark-owned", nargs="*", metavar="APPID", help="Marcar DLCs como poseídos"
    )
    parser.add_argument(
        "--mark-unowned",
        nargs="*",
        metavar="APPID",
        help="Marcar DLCs como no poseídos",
    )
    parser.add_argument("--budget", type=float, help="Presupuesto en MXN")
    parser.add_argument(
        "--alert-price", type=float, help="Alertar si DLC baja de N MXN"
    )
    parser.add_argument(
        "--min-deal",
        type=int,
        default=None,
        help="Descuento mínimo %% para recomendar compra (default: 50)",
    )
    parser.add_argument("--csv", action="store_true", help="Generar CSV")
    args = parser.parse_args(argv)

    cfg = load_user_config_fn()
    key = resolve_config_secret(args.key, cfg, "key", environ=environ)
    vanity = args.vanity or cfg.get("vanity") or "gaben"
    itad_key = resolve_config_secret(args.itad_key, cfg, "itad_key", environ=environ)
    output_dir = (
        Path(args.output).expanduser()
        if args.output
        else (
            Path(cfg["output_dir"]).expanduser()
            if cfg.get("output_dir")
            else Path(__file__).resolve().parent
        )
    )
    budget = args.budget or cfg.get("payday2_budget")
    alert_price = args.alert_price or cfg.get("payday2_alert_price")
    min_deal = (
        args.min_deal if args.min_deal is not None else cfg.get("payday2_min_deal", 50)
    )

    return {
        "key": key,
        "vanity": vanity,
        "itad_key": itad_key,
        "output_dir": output_dir,
        "no_cache": args.no_cache,
        "csv": args.csv,
        "mark_owned": args.mark_owned or [],
        "mark_unowned": args.mark_unowned or [],
        "budget": budget,
        "alert_price": alert_price,
        "min_deal": min_deal,
    }


# ============================================─
# PAYDAY 2 APPID
# ============================================─

PD2_APPID = "218620"


UPCOMING_SALES = [
    {"event": "Steam Summer Sale", "date": "25 jun - 9 jul 2026", "discount": 75},
    {"event": "Steam Autumn Sale", "date": "~1 oct 2026", "discount": 50},
    {"event": "Steam Winter Sale", "date": "~18 dic 2026 - 2 ene 2027", "discount": 75},
]


# ============================================─
# CACHE
# ============================================─

PROJECT_DIR = Path(__file__).resolve().parent
PD2_CACHE_DIR = PROJECT_DIR / ".cache" / "steam_deals" / "payday2"
DLC_LIST_CACHE = PD2_CACHE_DIR / "dlc_list.json"
DLC_MAPPING_CACHE = PD2_CACHE_DIR / "dlc_mapping.json"
PRICES_CACHE = PD2_CACHE_DIR / "prices.json"
OWNED_CACHE = PD2_CACHE_DIR / "owned.json"
HISTORY_FILE = PD2_CACHE_DIR / "price_history.json"
BUNDLES_CACHE = PD2_CACHE_DIR / "bundles.json"

DLC_LIST_TTL = 168  # 7 days
PRICES_TTL = 24  # 1 day
BUNDLES_TTL = 168  # 7 days


def _load_cache(path: Path, ttl_hours: float = 0) -> tuple[dict, float]:
    if not path.exists():
        return {}, float("inf")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, float("inf")
    age = float("inf")
    if data.get("saved_at"):
        age = (
            datetime.now() - datetime.fromisoformat(data["saved_at"])
        ).total_seconds() / 3600
    return data, age


def _save_cache(path: Path, data: dict):
    PD2_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data["saved_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================─
# STEAM API
# ============================================─


def resolve_steam_id(api_key: str | None, vanity: str) -> str:
    m = re.match(r"https?://steamcommunity\.com/profiles/(\d+)", vanity)
    if m:
        return m.group(1)
    m = re.match(r"https?://steamcommunity\.com/id/([^/]+)", vanity)
    if m:
        vanity = m.group(1)
    if vanity.isdigit() and len(vanity) == 17:
        return vanity
    if api_key:
        url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={api_key}&vanityurl={vanity}"
        try:
            data = _get_json(url)
            if data["response"]["success"] != 1:
                raise ValueError(f"No se pudo resolver: {vanity}")
            return data["response"]["steamid"]
        except urllib.error.HTTPError as exc:
            if exc.code not in (401, 403):
                raise
            print(
                _warn(
                    f"Steam rechazó la API key al resolver el perfil (HTTP {exc.code}). "
                    "Intentando fallback público sin key..."
                ),
                flush=True,
            )
        except ValueError:
            raise
    url = f"https://steamcommunity.com/id/{vanity}/?xml=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError(
                f"Steam rechazó el perfil público (HTTP {exc.code}). "
                "Revisa que el perfil sea público, usa tu SteamID de 17 dígitos o regenera/borra la API key."
            ) from exc
        raise
    m = re.search(r"<steamID64>(\d+)</steamID64>", text)
    if not m:
        raise ValueError(
            f"No se pudo resolver el perfil: {vanity}. Usa tu SteamID de 17 dígitos o una URL pública válida."
        )
    return m.group(1)


def get_active_sale() -> str:
    try:
        url = "https://api.steampowered.com/IMarketingMessagesService/GetActiveMarketingMessages/v1/"
        data = _get_json(url)
        msgs = data.get("response", {}).get("messages", [])
        for msg in msgs:
            if msg.get("type") in (1, 11):
                title = msg.get("title", "").strip()
                if title:
                    return title
    except Exception:
        pass
    return ""


def fetch_pd2_dlc_list(no_cache: bool = False) -> list[str]:
    """Get all PAYDAY 2 DLC appids from Steam."""
    cache, age = _load_cache(DLC_LIST_CACHE)
    if not no_cache and age <= DLC_LIST_TTL and cache.get("appids"):
        return [str(a) for a in cache["appids"]]

    url = f"https://store.steampowered.com/api/appdetails?appids={PD2_APPID}&cc=mx"
    data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
    entry = data.get(PD2_APPID, {})
    if not entry.get("success"):
        raise ValueError("No se pudo obtener datos de PAYDAY 2")
    dlc_ids = entry.get("data", {}).get("dlc", [])
    _save_cache(DLC_LIST_CACHE, {"appids": dlc_ids})
    return [str(a) for a in dlc_ids]


def fetch_dlc_names(
    appids: list[str], cached_mapping: dict, rate_limit: float = 0.3
) -> dict[str, str]:
    """Fetch names for DLC appids individually. Returns {appid: name}."""
    result = dict(cached_mapping)
    to_fetch = [a for a in appids if a not in result]
    if not to_fetch:
        return result

    total = len(to_fetch)
    for idx, appid in enumerate(to_fetch):
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=mx&filters=basic"
        try:
            data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
            entry = data.get(appid, {})
            if entry.get("success"):
                name = entry.get("data", {}).get("name", "")
                if name:
                    result[appid] = name
        except Exception:
            pass
        if idx < total - 1:
            time.sleep(rate_limit)
        # Progress indicator every 20
        if (idx + 1) % 20 == 0:
            print(f"  {_dim(f'  {idx + 1}/{total} nombres...')}", flush=True)

    return result


def _strip_prefix(name: str) -> str:
    """Strip 'PAYDAY 2: ' prefix for cleaner display."""
    return re.sub(r"^PAYDAY\s*2\s*[:：\-–]\s*", "", name, flags=re.IGNORECASE).strip()


def fetch_bundles(pd2_dlc_appids: list[str], no_cache: bool = False) -> list[dict]:
    """Fetch PD2 bundles from Steam store. Returns [{name, bundle_id, dlc_appids: [str]}]."""
    cache, age = _load_cache(BUNDLES_CACHE)
    if not no_cache and age <= BUNDLES_TTL and cache.get("bundles"):
        return cache["bundles"]

    # Step 1: get bundle IDs from PD2 store page
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cookie": "birthtime=568022401; mature_content=1; wants_mature_content=1",
    }
    try:
        url = f"https://store.steampowered.com/app/{PD2_APPID}/PAYDAY_2/"
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        bundle_ids = sorted(set(re.findall(r"/bundle/(\d+)", html)))
    except Exception:
        return cache.get("bundles", [])

    if not bundle_ids:
        return cache.get("bundles", [])

    # Step 2: fetch contents of each bundle
    dlc_set = set(pd2_dlc_appids)
    bundles = []
    for bid in bundle_ids:
        try:
            burl = f"https://store.steampowered.com/bundle/{bid}/"
            req = urllib.request.Request(burl, headers=headers)
            bhtml = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")

            # Extract name
            m = re.search(r'<h2 class="pageheader">(.*?)</h2>', bhtml)
            if not m:
                m = re.search(r"<title>(.*?)(?:\s+on\s+Steam)?</title>", bhtml)
            name = _strip_prefix(m.group(1).strip()) if m else f"Bundle {bid}"

            # Extract appids
            appids = sorted(set(re.findall(r'data-ds-appid="(\d+)"', bhtml)))
            # Filter to only PD2 DLCs (not base game, not other games)
            dlc_appids = [a for a in appids if a in dlc_set]

            if dlc_appids:
                bundles.append(
                    {"name": name, "bundle_id": bid, "dlc_appids": dlc_appids}
                )

            time.sleep(0.3)
        except Exception:
            continue

    if bundles:
        _save_cache(BUNDLES_CACHE, {"bundles": bundles})

    return bundles


def get_owned_games(api_key: str, steam_id: str) -> set[str]:
    """Get all owned appids (games + DLCs)."""
    url = (
        f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        f"?key={api_key}&steamid={steam_id}&include_appinfo=1&include_played_free_games=1"
    )
    try:
        data = _get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError(
                f"Steam rechazó la API key al verificar juegos poseídos (HTTP {exc.code}). "
                "Continuando con DLCs marcados manualmente en el dashboard."
            ) from exc
        raise
    return {str(g["appid"]) for g in data.get("response", {}).get("games", [])}


def resolve_owned_dlc_appids(
    api_key: str | None,
    steam_id: str,
    pd2_dlc_appids: list[str],
    *,
    get_owned_games_fn=get_owned_games,
    load_owned_fn=None,
    emit=print,
) -> set[str]:
    """Resolve owned PAYDAY 2 DLCs, preserving manual cache on API auth errors."""
    if load_owned_fn is None:
        load_owned_fn = load_owned
    manual_owned = set(load_owned_fn(steam_id))
    if not api_key:
        return manual_owned
    try:
        all_owned = get_owned_games_fn(api_key, steam_id)
    except ValueError as exc:
        emit(f"  {_warn(str(exc))}")
        return manual_owned
    return {appid for appid in pd2_dlc_appids if appid in all_owned} | manual_owned


def load_owned(steam_id: str) -> set[str]:
    cache, _ = _load_cache(OWNED_CACHE)
    if cache.get("steam_id") == steam_id:
        return set(cache.get("appids", []))
    return set()


def save_owned(steam_id: str, owned: set[str]):
    _save_cache(OWNED_CACHE, {"steam_id": steam_id, "appids": sorted(owned)})


def fetch_dlc_prices(
    appids: list[str], no_cache: bool = False, rate_limit: float = 0.3
) -> dict[str, dict]:
    """Fetch prices for DLC appids individually. Returns {appid: {name, price_raw, price_fmt, orig_raw, orig_fmt, discount}}."""
    cache, age = _load_cache(PRICES_CACHE)
    cached_prices = cache.get("prices", {})
    if no_cache:
        cached_prices = {}
    elif age <= PRICES_TTL:
        missing = [a for a in appids if a not in cached_prices]
        if not missing:
            return cached_prices

    result = dict(cached_prices)
    to_fetch = [a for a in appids if a not in result]
    if not to_fetch:
        return result

    total = len(to_fetch)
    for idx, appid in enumerate(to_fetch):
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=mx&filters=price_overview,basic"
        try:
            data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
            entry = data.get(appid, {})
            if not entry.get("success"):
                continue
            info = entry.get("data", {})
            po = info.get("price_overview")
            if not po:
                result[appid] = {
                    "name": info.get("name", ""),
                    "price_raw": 0,
                    "price_fmt": "Gratis",
                    "orig_raw": 0,
                    "orig_fmt": "Gratis",
                    "discount": 0,
                    "delisted": not info.get("name"),
                }
                continue
            result[appid] = {
                "name": info.get("name", ""),
                "price_raw": po.get("final", 0),
                "price_fmt": po.get("final_formatted", "?"),
                "orig_raw": po.get("initial", 0),
                "orig_fmt": po.get("initial_formatted", "?"),
                "discount": po.get("discount_percent", 0),
            }
        except Exception as exc:
            print(f"  {_warn(f'Error: {appid}: {exc}')}", flush=True)
        if idx < total - 1:
            time.sleep(rate_limit)
        if (idx + 1) % 20 == 0:
            print(f"  {_dim(f'  {idx + 1}/{total} precios...')}", flush=True)

    _save_cache(PRICES_CACHE, {"prices": result})
    return result


# ============================================─
# ITAD (mínimo histórico + multi-tienda)
# ============================================─

ITAD_BATCH = 50


def itad_lookup(appids: list[str], itad_key: str) -> dict[str, str]:
    result = {}
    for i in range(0, len(appids), ITAD_BATCH):
        batch = appids[i : i + ITAD_BATCH]
        body = [{"type": "steam", "id": f"app/{a}"} for a in batch]
        try:
            data = _post_json(
                f"https://api.isthereanydeal.com/games/lookup/v1?key={itad_key}", body
            )
            if isinstance(data, list):
                for item, appid in zip(data, batch):
                    if item and isinstance(item, dict) and item.get("found"):
                        result[appid] = item["game"]["id"]
        except Exception as exc:
            print(f"  {_warn(f'ITAD lookup: {exc}')}", flush=True)
        time.sleep(0.5)
    return result


def itad_store_lows(itad_ids: dict[str, str], itad_key: str) -> dict[str, dict]:
    id_to_appid = {v: k for k, v in itad_ids.items()}
    all_ids = list(itad_ids.values())
    result = {}
    for i in range(0, len(all_ids), ITAD_BATCH):
        batch = all_ids[i : i + ITAD_BATCH]
        try:
            data = _post_json(
                f"https://api.isthereanydeal.com/games/storelow/v2?key={itad_key}&country=MX&shops=61",
                batch,
            )
            if isinstance(data, list):
                for item in data:
                    appid = id_to_appid.get(item.get("id", ""))
                    lows = item.get("lows", [])
                    if appid and lows:
                        p = lows[0].get("price", {})
                        result[appid] = {
                            "price": p.get("amount", 0),
                            "cut": lows[0].get("cut", 0),
                            "date": (lows[0].get("timestamp") or "")[:10],
                        }
        except Exception as exc:
            print(f"  {_warn(f'ITAD storelow: {exc}')}", flush=True)
        time.sleep(0.5)
    return result


def itad_current_prices(itad_ids: dict[str, str], itad_key: str) -> dict[str, dict]:
    id_to_appid = {v: k for k, v in itad_ids.items()}
    all_ids = list(itad_ids.values())
    result = {}
    for i in range(0, len(all_ids), ITAD_BATCH):
        batch = all_ids[i : i + ITAD_BATCH]
        try:
            data = _post_json(
                f"https://api.isthereanydeal.com/games/prices/v3?key={itad_key}&country=MX",
                batch,
            )
            if isinstance(data, list):
                for item in data:
                    appid = id_to_appid.get(item.get("id", ""))
                    if not appid:
                        continue
                    steam_price, best_other = None, None
                    for pd in item.get("deals", []):
                        shop_id = pd.get("shop", {}).get("id", 0)
                        amt = pd.get("price", {}).get("amount", 0)
                        if shop_id == 61:
                            steam_price = amt
                        elif best_other is None or amt < best_other["price"]:
                            best_other = {
                                "store": pd.get("shop", {}).get("name", "?"),
                                "price": amt,
                                "url": pd.get("url", ""),
                            }
                    if (
                        best_other
                        and steam_price is not None
                        and best_other["price"] < steam_price
                    ):
                        result[appid] = best_other
        except Exception as exc:
            print(f"  {_warn(f'ITAD prices: {exc}')}", flush=True)
        time.sleep(0.5)
    return result


# ============================================─
# PRICE HISTORY
# ============================================─


def load_price_history() -> dict:
    return load_json_file(HISTORY_FILE, {"snapshots": []})


def save_price_snapshot(history: dict, prices: dict):
    today = date.today().isoformat()
    entry = {}
    for appid, p in prices.items():
        if p.get("price_raw"):
            entry[appid] = {"price": p["price_raw"], "discount": p.get("discount", 0)}
    # Replace same-day or append
    snaps = history.get("snapshots", [])
    if snaps and snaps[-1].get("date") == today:
        snaps[-1]["prices"] = entry
    else:
        snaps.append({"date": today, "prices": entry})
    # Keep last 365 days
    history["snapshots"] = snaps[-365:]
    write_json_file(HISTORY_FILE, history, ensure_ascii=False, indent=2)


def analyze_trends(history: dict, prices: dict) -> dict[str, dict]:
    """Return {appid: {times_seen, lowest, avg, is_at_lowest, direction}}."""
    snaps = history.get("snapshots", [])
    result = {}
    for appid in prices:
        past_prices = []
        for snap in snaps[:-1]:  # exclude current
            sp = snap.get("prices", {}).get(appid)
            if sp:
                past_prices.append(sp["price"])
        curr = prices[appid].get("price_raw", 0)
        if not past_prices:
            result[appid] = {
                "times_seen": 1,
                "lowest": curr,
                "avg": curr,
                "is_at_lowest": False,
                "direction": "new",
            }
            continue
        lowest = min(past_prices)
        avg = sum(past_prices) / len(past_prices)
        result[appid] = {
            "times_seen": len(past_prices) + 1,
            "lowest": min(lowest, curr),
            "avg": round(avg),
            "is_at_lowest": curr <= lowest and curr > 0,
            "direction": "down" if curr < avg else ("up" if curr > avg else "stable"),
        }
    return result


# ============================================─
# RECOMMENDATIONS
# ============================================─


def _dlc_search_name(dlc: dict) -> str:
    return str(dlc.get("steam_name") or dlc.get("name") or "").lower()


def classify_payday2_dlc_importance(dlc: dict) -> dict:
    """Classify a PAYDAY 2 DLC by likely gameplay impact using its Steam name."""
    name = _dlc_search_name(dlc)

    if any(
        term in name
        for term in ("tailor", "music", "soundtrack", "weapon color", "b-sides", " vr")
    ):
        return {
            "tier": "C",
            "label": "Cosmético/audio",
            "importance_score": 24,
        }
    if "subscription" in name:
        return {
            "tier": "C",
            "label": "Suscripción/servicio",
            "importance_score": 35,
        }
    if any(
        term in name
        for term in (
            "heist",
            "bank",
            "casino",
            "armored transport",
            "hotline miami",
            "goat simulator",
        )
    ):
        return {
            "tier": "S",
            "label": "Heist/contenido jugable",
            "importance_score": 95,
        }
    if any(
        term in name
        for term in (
            "weapon pack",
            "mod pack",
            "gage ",
            "smuggler",
            "shotgun",
            "sniper",
            "assault",
            "spec ops",
            "ninja",
            "chivalry",
            "historical",
            "bbq",
            "western",
            "ak/car",
            "overkill pack",
            "fugitive weapon",
            "federales weapon",
            "mcshay weapon",
        )
    ):
        return {
            "tier": "A",
            "label": "Armas/mods jugables",
            "importance_score": 72,
        }
    if any(
        term in name
        for term in (
            "character pack",
            "jacket",
            "sokol",
            "clover",
            "dragan",
            "sydney",
            "biker character",
            "yakuza",
            "h3h3",
        )
    ):
        return {
            "tier": "B",
            "label": "Personaje/perk deck",
            "importance_score": 58,
        }
    if "pack" in name:
        return {
            "tier": "B",
            "label": "Contenido jugable",
            "importance_score": 56,
        }
    return {
        "tier": "B",
        "label": "DLC general",
        "importance_score": 45,
    }


def compute_payday2_dlc_value(dlc: dict) -> dict:
    """Return explainable value metadata for PAYDAY 2 budget ranking."""
    category = classify_payday2_dlc_importance(dlc)
    discount = max(0, int(dlc.get("discount") or 0))
    price_mxn = max(0, int(dlc.get("price_raw") or 0)) / 100

    discount_bonus = min(discount, 90) * 0.45
    price_bonus = 0
    if 0 < price_mxn <= 40:
        price_bonus = 8
    elif price_mxn <= 70:
        price_bonus = 5
    elif price_mxn <= 120:
        price_bonus = 2

    reasons = [category["label"]]
    if discount >= 50:
        reasons.append("Buen descuento")
    elif discount > 0:
        reasons.append("Oferta activa")
    if 0 < price_mxn <= 50:
        reasons.append("Precio bajo")

    return {
        "importance_score": category["importance_score"],
        "importance_tier": category["tier"],
        "importance_label": category["label"],
        "value_score": round(category["importance_score"] + discount_bonus + price_bonus),
        "value_reasons": reasons[:3],
    }


def enrich_payday2_dlc_value(dlc: dict) -> dict:
    return {**dlc, **compute_payday2_dlc_value(dlc)}


def payday2_budget_sort_key(dlc: dict) -> tuple:
    enriched = enrich_payday2_dlc_value(dlc)
    return (
        -enriched["value_score"],
        -enriched["importance_score"],
        -int(enriched.get("discount") or 0),
        int(enriched.get("price_raw") or 0),
        str(enriched.get("steam_name") or ""),
    )


def compute_recommendations(
    missing: list[dict],
    budget: float | None,
    alert_price: float | None,
    min_deal: int = 50,
) -> dict:
    enriched_missing = [enrich_payday2_dlc_value(d) for d in missing]
    on_sale = sorted(
        [d for d in enriched_missing if d.get("discount", 0) > 0],
        key=payday2_budget_sort_key,
    )

    buy_now = [d for d in on_sale if d.get("discount", 0) >= min_deal]

    alerts = []
    if alert_price:
        alerts = [
            d
            for d in enriched_missing
            if d.get("price_raw", 0) > 0 and d["price_raw"] / 100 <= alert_price
        ]

    budget_fit = []
    if budget:
        remaining = budget
        for d in sorted(enriched_missing, key=payday2_budget_sort_key):
            price = d.get("price_raw", 0) / 100
            if price > 0 and price <= remaining:
                budget_fit.append(d)
                remaining -= price

    optimal = on_sale[0] if on_sale else None

    return {
        "buy_now": buy_now,
        "alerts": alerts,
        "budget_fit": budget_fit,
        "optimal_next": optimal,
        "on_sale_count": len(on_sale),
        "on_sale_savings": sum(
            ((d.get("orig_raw", 0) - d.get("price_raw", 0)) / 100) for d in on_sale
        ),
        "min_deal": min_deal,
    }


# ============================================─
# GENERATE MARKDOWN
# ============================================─


def generate_md(
    all_dlcs: dict[str, dict],
    owned_appids: set[str],
    pd2_dlc_appids: list[str],
    prices: dict[str, dict],
    sale_name: str,
    recommendations: dict,
    trends: dict[str, dict],
    itad_lows: dict[str, dict],
    itad_current: dict[str, dict],
    budget: float | None,
    vanity: str,
) -> str:
    today_obj = date.today()
    today = f"{today_obj.day} de {MESES[today_obj.month]} de {today_obj.year}"
    total_dlcs = len(pd2_dlc_appids)
    owned_count = sum(1 for a in pd2_dlc_appids if a in owned_appids)
    missing_count = total_dlcs - owned_count

    missing_total_orig = (
        sum(d.get("orig_raw", 0) for a, d in all_dlcs.items() if a not in owned_appids)
        / 100
    )
    missing_total_curr = (
        sum(d.get("price_raw", 0) for a, d in all_dlcs.items() if a not in owned_appids)
        / 100
    )
    on_sale = sum(
        1
        for a, d in all_dlcs.items()
        if a not in owned_appids and d.get("discount", 0) > 0
    )

    lines = [
        f"# PAYDAY 2 — DLC Tracker",
        f"> Generado: {today} | Precios en MXN | Perfil: {vanity}",
        f"> Posees: {owned_count}/{total_dlcs} items | Faltan: {missing_count} DLCs",
        "",
        "---",
        "",
        "## Resumen",
        "",
        "| Métrica | Valor |",
        "|---------|-------|",
        f"| DLCs poseídos | {owned_count}/{total_dlcs} ({owned_count * 100 // total_dlcs if total_dlcs else 0}%) |",
        f"| Costo restante (precio normal) | Mex$ {missing_total_orig:,.0f} |",
    ]
    if missing_total_curr != missing_total_orig:
        savings = missing_total_orig - missing_total_curr
        lines.append(
            f"| **Con descuento actual** | **Mex$ {missing_total_curr:,.0f}** (ahorras Mex$ {savings:,.0f}) |"
        )
    lines.append(f"| DLCs en oferta ahora | {on_sale} |")
    if budget:
        lines.append(f"| Tu presupuesto | Mex$ {budget:,.0f} |")
    lines += ["", "---", ""]

    # Sale / Recommendation
    if sale_name:
        lines += [f"## {sale_name}", ""]
    else:
        lines += ["## Estado de ofertas", ""]

    rec = recommendations
    min_deal = rec.get("min_deal", 50)
    if rec["on_sale_count"] > 0:
        lines.append(
            f"> **{rec['on_sale_count']} DLCs en oferta** | Ahorro potencial: Mex$ {rec['on_sale_savings']:,.0f}"
        )
        lines.append("")
        if rec["buy_now"]:
            lines += [f"### Recomendación: COMPRAR AHORA (>= {min_deal}% off)", ""]
            lines.append("| DLC | Precio | Descuento |")
            lines.append("|-----|--------|-----------|")
            for d in rec["buy_now"]:
                lines.append(
                    f"| {_link(d['steam_name'], d['appid'])} | {d.get('price_fmt', '?')} | -{d.get('discount', 0)}% |"
                )
            lines.append("")
        if rec["optimal_next"]:
            opt = rec["optimal_next"]
            lines.append(
                f"> **Mejor compra ahora:** {opt['steam_name']} (-{opt.get('discount', 0)}%, {opt.get('price_fmt', '?')})"
            )
            lines.append("")
    else:
        lines += [
            "> Sin ofertas activas en DLCs de PAYDAY 2.",
            "",
            "### Próximas ofertas estimadas",
            "",
            "| Evento | Fecha | Descuento esperado | Ahorro estimado |",
            "|--------|-------|--------------------|--------------------|",
        ]
        for sale in UPCOMING_SALES:
            est_savings = missing_total_orig * sale["discount"] / 100
            lines.append(
                f"| {sale['event']} | {sale['date']} | -{sale['discount']}% | ~Mex$ {est_savings:,.0f} |"
            )
        lines += [
            "",
            f"> **Recomendación:** Espera al Summer Sale (75% off). Costo estimado: ~Mex$ {missing_total_orig * 0.25:,.0f}",
        ]
    lines += ["", "---", ""]

    # Budget
    if budget and rec["budget_fit"]:
        total_budget_cost = sum(d.get("price_raw", 0) / 100 for d in rec["budget_fit"])
        lines += [
            f"## Con tu presupuesto (Mex$ {budget:,.0f})",
            "",
            f"> Puedes comprar {len(rec['budget_fit'])} DLCs por ~Mex$ {total_budget_cost:,.0f} (priorizando importancia y valor, no solo precio)",
            "",
            "| # | DLC | Prioridad | Precio | Descuento | Por qué |",
            "|---|-----|-----------|--------|-----------|--------|",
        ]
        for i, d in enumerate(rec["budget_fit"], 1):
            disc = f"-{d['discount']}%" if d.get("discount", 0) > 0 else "—"
            tier = d.get("importance_tier", "B")
            reason = " · ".join(d.get("value_reasons", [])[:2]) or d.get(
                "importance_label", "Valor estimado"
            )
            lines.append(
                f"| {i} | {_link(d['steam_name'], d['appid'])} | {tier} | {d.get('price_fmt', '?')} | {disc} | {_md_esc(reason)} |"
            )
        lines += ["", "---", ""]

    # All missing DLCs — sorted by discount desc
    missing_dlcs = sorted(
        [d for a, d in all_dlcs.items() if a not in owned_appids],
        key=lambda d: (-d.get("discount", 0), d.get("price_raw", 0)),
    )

    lines += ["## DLCs Faltantes", ""]
    header = "| DLC | Precio | Original | Descuento"
    sep = "|-----|--------|----------|----------"
    if itad_lows:
        header += " | Mín. histórico"
        sep += "|----------------"
    if itad_current:
        header += " | Mejor precio"
        sep += "|--------------"
    header += " |"
    sep += "|"
    lines += [header, sep]

    for d in missing_dlcs:
        appid = d.get("appid", "")
        name = d.get("steam_name", "?")
        price = d.get("price_fmt", "?")
        orig = d.get("orig_fmt", "?")
        disc = f"-{d['discount']}%" if d.get("discount", 0) > 0 else "—"
        if d.get("discount", 0) >= 50:
            disc = f"**{disc}**"

        row = f"| {_link(name, appid)} | {price} | {orig} | {disc}"

        if itad_lows:
            low = itad_lows.get(appid)
            row += f" | Mex$ {low['price']:.0f} ({low['date']})" if low else " | —"
        if itad_current:
            cp = itad_current.get(appid)
            row += (
                f" | ${cp['price']:.0f} en [{cp['store']}]({cp['url']})"
                if cp
                else " | —"
            )
        row += " |"
        lines.append(row)

    lines += ["", "---", ""]

    # Price history / trends
    if any(t.get("times_seen", 0) > 1 for t in trends.values()):
        lines += ["## Historial de Precios", ""]
        lines += [
            "| DLC | Hoy | Promedio | Mín. registrado | Tendencia |",
            "|-----|-----|---------|-----------------|-----------|",
        ]
        for d in missing_dlcs:
            appid = d.get("appid", "")
            t = trends.get(appid, {})
            if t.get("times_seen", 0) <= 1:
                continue
            curr = d.get("price_raw", 0) / 100
            arrows = {"down": "v", "up": "^", "stable": "=", "new": "*"}
            arrow = arrows.get(t.get("direction", ""), "")
            low_marker = " BEST" if t.get("is_at_lowest") else ""
            lines.append(
                f"| {_md_esc(d.get('steam_name', '?'))} | Mex$ {curr:.0f} | Mex$ {t['avg'] / 100:.0f} | Mex$ {t['lowest'] / 100:.0f}{low_marker} | {arrow} |"
            )
        lines += ["", "---", ""]

    # Upcoming sales
    lines += [
        "## Próximas Ofertas Estimadas",
        "",
        "| Evento | Fecha | Desc. esperado | Costo estimado (tus DLCs) |",
        "|--------|-------|----------------|---------------------------|",
    ]
    for sale in UPCOMING_SALES:
        est = missing_total_orig * (1 - sale["discount"] / 100)
        lines.append(
            f"| {sale['event']} | {sale['date']} | -{sale['discount']}% | ~Mex$ {est:,.0f} |"
        )
    lines += [""]

    lines += [
        "---",
        "",
        "## Nota: Scarface Character Pack (DESCONTINUADO)",
        "",
        "> Este DLC fue retirado de Steam el 1 de octubre de 2020. No se puede comprar en Steam.",
        "> Monitorea Instant Gaming y Humble Bundle para keys de Legacy Collection baratas.",
        "",
        "---",
        "",
        f"*Generado automáticamente por payday2_dlc_tracker.py — {today}*",
    ]

    return "\n".join(lines)


# ============================================─
# RUN COMPARISON
# ============================================─

RUN_HISTORY_FILE = PD2_CACHE_DIR / "run_history.json"


def load_previous_run() -> dict | None:
    data = load_json_file(RUN_HISTORY_FILE, None)
    if not isinstance(data, dict):
        return None
    return data.get("last_run")


def save_run(owned_count: int, missing_count: int, prices: dict, on_sale: int):
    run = {
        "date": date.today().isoformat(),
        "owned": owned_count,
        "missing": missing_count,
        "on_sale": on_sale,
        "prices": {
            a: {"price": p.get("price_raw", 0), "discount": p.get("discount", 0)}
            for a, p in prices.items()
        },
    }
    write_json_file(RUN_HISTORY_FILE, {"last_run": run}, ensure_ascii=False, indent=2)


def compute_run_comparison(prices: dict, prev_run: dict | None) -> dict:
    if not prev_run:
        return {}
    prev_prices = prev_run.get("prices", {})
    new_sales, ended_sales, price_drops = [], [], []
    for appid, p in prices.items():
        curr_disc = p.get("discount", 0)
        prev = prev_prices.get(appid, {})
        prev_disc = prev.get("discount", 0)
        curr_price = p.get("price_raw", 0)
        prev_price = prev.get("price", 0)
        if curr_disc > 0 and prev_disc == 0:
            new_sales.append(appid)
        elif curr_disc == 0 and prev_disc > 0:
            ended_sales.append(appid)
        if curr_price < prev_price and prev_price > 0:
            price_drops.append((appid, prev_price, curr_price))
    return {
        "new_sales": new_sales,
        "ended_sales": ended_sales,
        "price_drops": price_drops,
        "prev_date": prev_run.get("date", "?"),
        "prev_owned": prev_run.get("owned", 0),
    }


# ============================================─
# GENERATE HTML
# ============================================─


def _html_esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


CAPSULE_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_231x87.jpg"
HEADER_IMG_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"


def generate_html(
    all_dlcs: dict[str, dict],
    owned_appids: set[str],
    pd2_dlc_appids: list[str],
    prices: dict[str, dict],
    sale_name: str,
    recommendations: dict,
    itad_lows: dict[str, dict],
    vanity: str,
    comparison: dict,
    history: dict | None = None,
) -> str:
    today_obj = date.today()
    today = f"{today_obj.day} de {MESES[today_obj.month]} de {today_obj.year}"
    total = len(pd2_dlc_appids)
    owned = sum(1 for a in pd2_dlc_appids if a in owned_appids)
    missing = total - owned
    cost_orig = (
        sum(d.get("orig_raw", 0) for a, d in all_dlcs.items() if a not in owned_appids)
        / 100
    )
    cost_curr = (
        sum(d.get("price_raw", 0) for a, d in all_dlcs.items() if a not in owned_appids)
        / 100
    )
    on_sale = sum(
        1
        for a, d in all_dlcs.items()
        if a not in owned_appids and d.get("discount", 0) > 0
    )
    pct_owned = owned * 100 // total if total else 0

    # Build JSON data for JS — sorted by discount desc
    dlc_json_list = []
    for d in sorted(
        [
            d
            for a, d in all_dlcs.items()
            if a not in owned_appids and d.get("steam_name")
        ],
        key=lambda d: (-d.get("discount", 0), d.get("price_raw", 0)),
    ):
        value = compute_payday2_dlc_value(d)
        appid = d.get("appid", "")
        low = itad_lows.get(appid)
        dlc_json_list.append(
            {
                "id": appid,
                "name": d.get("steam_name", "?"),
                "price": d.get("price_raw", 0),
                "orig": d.get("orig_raw", 0),
                "priceFmt": d.get("price_fmt", "?"),
                "origFmt": d.get("orig_fmt", "?"),
                "discount": d.get("discount", 0),
                "low": low["price"] if low else None,
                "lowDate": low["date"] if low else None,
                "importanceScore": value["importance_score"],
                "importanceTier": value["importance_tier"],
                "importanceLabel": value["importance_label"],
                "valueScore": value["value_score"],
                "valueReasons": value["value_reasons"],
            }
        )

    # History sparkline data
    history_data = {}
    if history:
        for snap in history.get("snapshots", [])[-30:]:
            for appid, sp in snap.get("prices", {}).items():
                if appid not in history_data:
                    history_data[appid] = []
                history_data[appid].append(sp.get("price", 0))

    data_json = json.dumps(
        {
            "dlcs": dlc_json_list,
            "history": history_data,
            "totalAll": total,
            "ownedCount": owned,
            "costOrig": round(cost_orig),
            "costCurr": round(cost_curr),
        },
        ensure_ascii=False,
    )

    # Comparison badges
    comp_html = ""
    if comparison:
        parts = []
        if comparison.get("new_sales"):
            parts.append(
                f'<span class="badge bg-green">{len(comparison["new_sales"])} nuevas ofertas</span>'
            )
        if comparison.get("ended_sales"):
            parts.append(
                f'<span class="badge bg-red">{len(comparison["ended_sales"])} terminaron</span>'
            )
        if comparison.get("price_drops"):
            parts.append(
                f'<span class="badge bg-blue">{len(comparison["price_drops"])} bajaron</span>'
            )
        if parts:
            comp_html = f'<div class="comp-row">vs {comparison.get("prev_date", "?")}: {" ".join(parts)}</div>'

    sale_badge = (
        f'<div class="sale-banner">{_html_esc(sale_name)}</div>' if sale_name else ""
    )

    rec = recommendations
    rec_html = ""
    if rec["buy_now"]:
        items = " ".join(
            f'<a href="{STORE_URL.format(appid=d["appid"])}" class="rec-item" target="_blank">{_html_esc(d["steam_name"])} <small>-{d.get("discount", 0)}%</small></a>'
            for d in rec["buy_now"][:6]
        )
        rec_html = f'<div class="rec-buy"><strong>Comprar ahora (>= {rec.get("min_deal", 50)}% off):</strong> {items}</div>'
    elif not rec["on_sale_count"]:
        rec_html = '<div class="rec-wait">Sin ofertas — espera al <strong>Summer Sale</strong> (25 jun, ~75% off)</div>'

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PAYDAY 2 DLC Tracker — {_html_esc(vanity)}</title>
<style>
:root{{--bg:#1b2838;--bg2:#2a475e;--card:#16202d;--border:#2a475e;--text:#c7d5e0;--text2:#8f98a0;--accent:#66c0f4;--green:#6cc644;--yellow:#f0b232;--red:#c7322e;--gold:#d4a84b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.5}}
a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
.container{{max-width:1200px;margin:0 auto;padding:1rem}}
.hdr{{background:linear-gradient(135deg,#0e1a26,#1b2838);border-bottom:2px solid var(--border);padding:1.5rem 1rem;text-align:center}}
.hdr h1{{font-size:1.6rem;color:var(--accent);letter-spacing:.02em}}
.hdr .sub{{color:var(--text2);font-size:.85rem;margin-top:.3rem}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:1.2rem;margin-bottom:1rem}}
.card h2{{font-size:1rem;color:var(--accent);margin-bottom:.8rem;font-weight:600}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin-bottom:1rem}}
.st{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:.8rem;text-align:center}}
.st .v{{font-size:1.5rem;font-weight:700;color:var(--accent)}}
.st .l{{font-size:.72rem;color:var(--text2);margin-top:.15rem}}
.st.g .v{{color:var(--green)}} .st.y .v{{color:var(--yellow)}} .st.r .v{{color:var(--red)}}
.donut-wrap{{display:flex;align-items:center;justify-content:center;gap:2rem;margin-bottom:1rem;flex-wrap:wrap}}
.donut-svg{{width:160px;height:160px}}
.donut-center{{font-size:1.4rem;font-weight:700;fill:var(--text)}}
.donut-label{{font-size:.7rem;fill:var(--text2)}}
.donut-ring{{fill:none;stroke:var(--bg2);stroke-width:18}}
.donut-fill{{fill:none;stroke:var(--accent);stroke-width:18;stroke-linecap:round;transition:stroke-dashoffset .8s ease}}
.donut-legend{{font-size:.85rem;color:var(--text2)}}
.donut-legend div{{margin-bottom:.4rem}}
.donut-legend .dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:.4rem;vertical-align:middle}}
.sale-banner{{background:var(--gold);color:#1b2838;padding:.5rem 1rem;border-radius:6px;font-weight:600;text-align:center;margin-bottom:.75rem}}
.rec-buy{{background:rgba(108,198,68,.12);border:1px solid var(--green);padding:.7rem 1rem;border-radius:6px;margin-bottom:.75rem}}
.rec-buy .rec-item{{background:rgba(108,198,68,.15);padding:.2rem .6rem;border-radius:4px;margin:0 .3rem;white-space:nowrap}}
.rec-wait{{background:rgba(240,178,50,.08);border:1px solid var(--yellow);color:var(--yellow);padding:.7rem 1rem;border-radius:6px;margin-bottom:.75rem}}
.comp-row{{font-size:.82rem;color:var(--text2);margin-bottom:.6rem}}
.badge{{display:inline-block;padding:.1rem .4rem;border-radius:3px;font-size:.72rem;font-weight:600}}
.bg-green{{background:rgba(108,198,68,.2);color:var(--green)}}
.bg-red{{background:rgba(199,50,46,.2);color:var(--red)}}
.bg-blue{{background:rgba(102,192,244,.2);color:var(--accent)}}
.sim{{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}}
.sim input[type=range]{{flex:1;min-width:200px;accent-color:var(--accent)}}
.sim .sim-val{{font-size:1.2rem;font-weight:700;color:var(--accent);min-width:3.5rem;text-align:center}}
.sim-result{{display:flex;gap:1.5rem;margin-top:.5rem;font-size:.9rem;flex-wrap:wrap}}
.sim-result .sr{{color:var(--green);font-weight:600}}
.filters{{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.75rem;align-items:center}}
.filters select,.filters input[type=text]{{background:var(--card);border:1px solid var(--border);color:var(--text);padding:.4rem .6rem;border-radius:4px;font-size:.8rem}}
.filters select:focus,.filters input:focus{{border-color:var(--accent);outline:none}}
.filters .count{{font-size:.75rem;color:var(--text2);margin-left:auto}}
.tbl-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:.82rem}}
th{{background:var(--bg2);color:var(--text2);text-align:left;padding:.55rem .5rem;font-weight:600;position:sticky;top:0;cursor:pointer;white-space:nowrap;user-select:none}}
th:hover{{color:var(--accent)}}
td{{padding:.45rem .5rem;border-bottom:1px solid rgba(42,71,94,.4);vertical-align:middle}}
tr:hover{{background:rgba(102,192,244,.04)}}
tr.checked-row{{opacity:.4}}
tr.checked-row td{{text-decoration:line-through}}
.dlc-cell{{display:flex;align-items:center;gap:.5rem}}
.dlc-cell img{{width:92px;height:34px;border-radius:3px;object-fit:cover;flex-shrink:0;transition:transform .2s}}
.dlc-cell img:hover{{transform:scale(2.5);position:relative;z-index:10;box-shadow:0 4px 20px rgba(0,0,0,.6)}}
.dlc-info .dlc-name{{font-weight:500}}
.sale-tag{{color:var(--green);font-weight:700}}
.low-tag{{color:var(--yellow)}}
.chk{{width:16px;height:16px;accent-color:var(--green);cursor:pointer}}
.sparkline{{width:80px;height:24px}}
.sparkline polyline{{fill:none;stroke:var(--accent);stroke-width:1.5}}
.footer{{text-align:center;color:var(--text2);font-size:.72rem;padding:2rem 0 1rem}}
@media(max-width:600px){{
  .stats{{grid-template-columns:repeat(3,1fr)}}
  .donut-wrap{{flex-direction:column}}
  .dlc-cell img{{width:60px;height:22px}}
}}
</style>
</head>
<body>
<div class="hdr">
  <h1>PAYDAY 2 DLC Tracker</h1>
  <div class="sub">{today} &middot; {_html_esc(vanity)} &middot; MXN</div>
</div>
<div class="container">
  {sale_badge}
  {comp_html}
  {rec_html}

  <div class="donut-wrap">
    <svg class="donut-svg" viewBox="0 0 180 180">
      <circle class="donut-ring" cx="90" cy="90" r="70"/>
      <circle class="donut-fill" cx="90" cy="90" r="70" stroke-dasharray="440" stroke-dashoffset="{440 - 440 * pct_owned / 100}" transform="rotate(-90 90 90)"/>
      <text class="donut-center" x="90" y="86" text-anchor="middle">{pct_owned}%</text>
      <text class="donut-label" x="90" y="105" text-anchor="middle">{owned}/{total} DLCs</text>
    </svg>
    <div class="donut-legend">
      <div><span class="dot" style="background:var(--accent)"></span>Poseidos: {owned}</div>
      <div><span class="dot" style="background:var(--green)"></span>En oferta: {on_sale}</div>
      <div><span class="dot" style="background:var(--text2)"></span>Precio normal: {missing - on_sale}</div>
    </div>
  </div>

  <div class="stats" id="stats-bar">
    <div class="st y"><div class="v" id="s-cost">Mex$ {cost_curr:,.0f}</div><div class="l">Costo actual</div></div>
    <div class="st"><div class="v">Mex$ {cost_orig:,.0f}</div><div class="l">Precio normal</div></div>
    <div class="st g"><div class="v" id="s-sale">{on_sale}</div><div class="l">En oferta</div></div>
    <div class="st"><div class="v" id="s-missing">{missing}</div><div class="l">Faltan</div></div>
    <div class="st g"><div class="v">Mex$ {cost_orig * 0.25:,.0f}</div><div class="l">Est. Summer 75%</div></div>
    <div class="st"><div class="v" id="s-checked">0</div><div class="l">Marcados</div></div>
  </div>

  <div class="card">
    <h2>Simulador de Descuento</h2>
    <div class="sim">
      <span style="color:var(--text2)">0%</span>
      <input type="range" id="sim-slider" min="0" max="90" step="5" value="0" oninput="simulate()">
      <span class="sim-val" id="sim-pct">0%</span>
      <span style="color:var(--text2)">90%</span>
    </div>
    <div class="sim-result">
      <div>Costo simulado: <span class="sr" id="sim-cost">—</span></div>
      <div>Ahorro: <span class="sr" id="sim-save">—</span></div>
    </div>
  </div>

  <div class="card">
    <h2>DLCs Faltantes</h2>
    <div class="filters">
      <select id="f-sale" onchange="render()"><option value="">Oferta</option><option value="y">En oferta</option><option value="n">Normal</option></select>
      <input type="text" id="f-q" placeholder="Buscar..." oninput="render()">
      <span class="count" id="f-count"></span>
    </div>
    <div class="tbl-wrap">
      <table><thead><tr>
        <th style="width:30px">&#9745;</th>
        <th onclick="doSort('name')">DLC</th>
        <th onclick="doSort('price')">Precio</th>
        <th onclick="doSort('discount')">Oferta</th>
        <th>Hist.</th>
      </tr></thead><tbody id="tbody"></tbody></table>
    </div>
  </div>
</div>
<div class="footer">PAYDAY 2 DLC Tracker &middot; {today}</div>

<script>
const DATA = {data_json};
const STORE = "https://store.steampowered.com/app/";
const CAP = "https://cdn.akamai.steamstatic.com/steam/apps/";
let checked = JSON.parse(localStorage.getItem('pd2_checked')||'[]');
let sortKey = 'discount', sortAsc = false;

function saveChecked(){{ localStorage.setItem('pd2_checked',JSON.stringify(checked)); }}
function isChecked(id){{ return checked.includes(id); }}
function toggleCheck(id){{
  if(isChecked(id)) checked=checked.filter(x=>x!==id); else checked.push(id);
  saveChecked(); render(); updateStats();
}}

function sparkSvg(id){{
  const pts = DATA.history[id];
  if(!pts||pts.length<2) return '';
  const max=Math.max(...pts), min=Math.min(...pts), range=max-min||1;
  const w=80, h=24, step=w/(pts.length-1);
  const coords=pts.map((p,i)=>Math.round(i*step)+','+Math.round(h-2-(p-min)/range*(h-4))).join(' ');
  return '<svg class="sparkline" viewBox="0 0 '+w+' '+h+'"><polyline points="'+coords+'"/></svg>';
}}

function render(){{
  const sale=document.getElementById('f-sale').value;
  const q=document.getElementById('f-q').value.toLowerCase();
  let dlcs=DATA.dlcs.filter(d=>{{
    if(sale==='y'&&d.discount===0) return false;
    if(sale==='n'&&d.discount>0) return false;
    if(q&&!d.name.toLowerCase().includes(q)) return false;
    return true;
  }});
  dlcs.sort((a,b)=>{{
    let va=a[sortKey], vb=b[sortKey];
    if(typeof va==='string') return sortAsc?va.localeCompare(vb):vb.localeCompare(va);
    return sortAsc?(va-vb):(vb-va);
  }});
  const tbody=document.getElementById('tbody');
  tbody.innerHTML=dlcs.map(d=>{{
    const ck=isChecked(d.id);
    const cls=ck?'checked-row':'';
    const disc=d.discount>0?('<span class="'+(d.discount>=50?'sale-tag':'low-tag')+'">-'+d.discount+'%</span>'):'—';
    return '<tr class="'+cls+'" data-id="'+d.id+'">'+
      '<td><input type="checkbox" class="chk" '+(ck?'checked':'')+' onchange="toggleCheck(\\\''+d.id+'\\\')"></td>'+
      '<td><div class="dlc-cell"><img src="'+CAP+d.id+'/capsule_231x87.jpg" loading="lazy" onerror="this.style.display=\\\'none\\\'"><div class="dlc-info"><div class="dlc-name"><a href="'+STORE+d.id+'/" target="_blank">'+d.name+'</a></div></div></div></td>'+
      '<td>'+d.priceFmt+'</td>'+
      '<td>'+disc+'</td>'+
      '<td>'+sparkSvg(d.id)+'</td></tr>';
  }}).join('');
  document.getElementById('f-count').textContent=dlcs.length+'/'+DATA.dlcs.length;
}}

function doSort(key){{ if(sortKey===key) sortAsc=!sortAsc; else{{ sortKey=key; sortAsc=key==='name'; }} render(); }}

function updateStats(){{
  const unchecked=DATA.dlcs.filter(d=>!isChecked(d.id));
  const cost=unchecked.reduce((s,d)=>s+d.price,0)/100;
  document.getElementById('s-cost').textContent='Mex$ '+cost.toLocaleString('en',{{maximumFractionDigits:0}});
  document.getElementById('s-missing').textContent=unchecked.length;
  document.getElementById('s-checked').textContent=checked.length;
}}

function simulate(){{
  const pct=parseInt(document.getElementById('sim-slider').value);
  document.getElementById('sim-pct').textContent=pct+'%';
  const unchecked=DATA.dlcs.filter(d=>!isChecked(d.id));
  let total=0;
  unchecked.forEach(d=>{{
    if(d.discount>0) total+=d.price;
    else total+=d.orig*(1-pct/100);
  }});
  total/=100;
  const orig=unchecked.reduce((s,d)=>s+d.orig,0)/100;
  document.getElementById('sim-cost').textContent='Mex$ '+Math.round(total).toLocaleString('en');
  document.getElementById('sim-save').textContent='Mex$ '+Math.round(orig-total).toLocaleString('en');
}}

render(); updateStats(); simulate();
</script>
</body>
</html>'''


# ============================================─
# GENERATE CSV
# ============================================─


def generate_csv(
    all_dlcs: dict[str, dict],
    owned_appids: set[str],
    pd2_dlc_appids: list[str],
    prices: dict[str, dict],
    itad_lows: dict[str, dict],
) -> str:
    import csv
    import io

    buf = io.StringIO()
    buf.write("\ufeff")  # BOM for Excel
    writer = csv.writer(buf)
    writer.writerow(
        [
            "AppID",
            "Name",
            "Price (MXN)",
            "Original Price",
            "Discount%",
            "ITAD Low",
            "Status",
            "URL",
        ]
    )

    missing = sorted(
        [
            (a, all_dlcs[a])
            for a in pd2_dlc_appids
            if a not in owned_appids and a in all_dlcs
        ],
        key=lambda x: (-x[1].get("discount", 0), x[1].get("price_raw", 0)),
    )
    for appid, d in missing:
        low = itad_lows.get(appid)
        writer.writerow(
            [
                appid,
                d.get("steam_name", ""),
                d.get("price_fmt", ""),
                d.get("orig_fmt", ""),
                f"-{d['discount']}%" if d.get("discount", 0) > 0 else "",
                f"${low['price']:.0f}" if low else "",
                "Missing",
                STORE_URL.format(appid=appid),
            ]
        )
    return buf.getvalue()


# ============================================─
# MAIN
# ============================================─


def main():
    sys.stdout.reconfigure(line_buffering=True)
    print(f"{C.BOLD}=== PAYDAY 2 DLC Tracker ==={C.RST}\n")

    cfg = get_config()
    KEY = cfg["key"]
    VANITY = cfg["vanity"]
    ITAD_KEY = cfg["itad_key"]
    OUTPUT_DIR = cfg["output_dir"]
    NO_CACHE = cfg["no_cache"]
    MIN_DEAL = cfg["min_deal"]
    t0 = time.monotonic()

    TOTAL = 9 + (1 if KEY else 0) + (1 if ITAD_KEY else 0) + (1 if cfg["csv"] else 0)
    _n = [0]

    def step(msg):
        _n[0] += 1
        print(f"\n{C.CYN}[{_n[0]}/{TOTAL}]{C.RST} {_bold(msg)}", flush=True)

    if not KEY:
        print(f"  {_dim('Sin API Key — ownership desde cache')}")
    print(f"  {_dim(f'Min deal: {MIN_DEAL}%')}")

    # [1] Steam ID
    step("Resolviendo Steam ID...")
    steam_id = resolve_steam_id(KEY, VANITY)
    print(f"  {_ok(steam_id)}")

    # [2] DLC list + names
    step("Obteniendo lista de DLCs de PAYDAY 2...")
    pd2_dlc_appids = fetch_pd2_dlc_list(NO_CACHE)
    print(f"  {_ok(f'{len(pd2_dlc_appids)} DLCs encontrados')}")

    mapping_cache, _ = _load_cache(DLC_MAPPING_CACHE)
    cached_names = mapping_cache.get("names", {})
    if NO_CACHE:
        cached_names = {}
    dlc_names = fetch_dlc_names(pd2_dlc_appids, cached_names)
    _save_cache(DLC_MAPPING_CACHE, {"names": dlc_names})
    print(f"  {_ok(f'{len(dlc_names)} nombres obtenidos')}")

    # [3] Ownership
    if KEY:
        step("Verificando DLCs poseídos...")
        pd2_owned = resolve_owned_dlc_appids(KEY, steam_id, pd2_dlc_appids)
    else:
        pd2_owned = resolve_owned_dlc_appids(None, steam_id, pd2_dlc_appids)

    for appid in cfg["mark_owned"]:
        pd2_owned.add(appid)
        print(f"  {_ok(f'Marcado como poseído: {appid}')}")
    for appid in cfg["mark_unowned"]:
        pd2_owned.discard(appid)
        print(f"  {_ok(f'Marcado como no poseído: {appid}')}")

    save_owned(steam_id, pd2_owned)
    owned_count = sum(1 for a in pd2_dlc_appids if a in pd2_owned)
    missing_count = len(pd2_dlc_appids) - owned_count
    print(f"  {_ok(f'{owned_count} poseídos · {missing_count} faltan')}")

    # [4] Prices
    step("Obteniendo precios de DLCs...")
    missing_appids = [a for a in pd2_dlc_appids if a not in pd2_owned]
    prices = fetch_dlc_prices(missing_appids, NO_CACHE)
    on_sale = sum(1 for a in missing_appids if prices.get(a, {}).get("discount", 0) > 0)
    total_cost = (
        sum(prices.get(a, {}).get("price_raw", 0) for a in missing_appids) / 100
    )
    print(
        f"  {_ok(f'{len(prices)} precios · {on_sale} en oferta · Total: Mex$ {total_cost:,.0f}')}"
    )

    # [5] Bundles
    step("Obteniendo bundles de Steam...")
    bundles = fetch_bundles(pd2_dlc_appids, NO_CACHE)
    if bundles:
        for b in bundles:
            bname = b["name"]
            bcount = len(b["dlc_appids"])
            print(f"  {_ok(f'{bname} ({bcount} DLCs)')}")
    else:
        print(f"  {_dim('No se encontraron bundles')}")

    step("Detectando oferta activa de Steam...")
    sale_name = get_active_sale()
    if sale_name:
        print(f"  {_ok(sale_name)}")
    else:
        print(f"  {_dim('Sin oferta especial detectada')}")

    # [6] ITAD (optional)
    itad_lows, itad_current = {}, {}
    if ITAD_KEY:
        step("Obteniendo datos de IsThereAnyDeal...")
        itad_ids = itad_lookup(missing_appids, ITAD_KEY)
        print(f"  {_ok(f'{len(itad_ids)}/{len(missing_appids)} encontrados en ITAD')}")
        if itad_ids:
            itad_lows = itad_store_lows(itad_ids, ITAD_KEY)
            print(f"  {_ok(f'{len(itad_lows)} mínimos históricos')}")
            itad_current = itad_current_prices(itad_ids, ITAD_KEY)
            if itad_current:
                print(f"  {_ok(f'{len(itad_current)} más baratos en otra tienda')}")

    # [7] Price history
    step("Analizando historial de precios...")
    history = load_price_history()
    save_price_snapshot(history, prices)
    trends = analyze_trends(history, prices)
    tracked = sum(1 for t in trends.values() if t.get("times_seen", 0) > 1)
    at_lowest = sum(1 for t in trends.values() if t.get("is_at_lowest"))
    if tracked:
        print(f"  {_ok(f'{tracked} con historial · {at_lowest} en mejor precio')}")
    else:
        print(f"  {_dim('Primera ejecución — snapshot guardado')}")

    # [8] Recommendations
    step("Calculando recomendaciones...")
    all_dlcs = {}
    for appid in pd2_dlc_appids:
        d = {}
        if appid in prices:
            d.update(prices[appid])
        if appid in dlc_names:
            d["steam_name"] = _strip_prefix(dlc_names[appid])
        d.setdefault("appid", appid)
        all_dlcs[appid] = d

    missing_list = [all_dlcs[a] for a in missing_appids if a in all_dlcs]
    recommendations = compute_recommendations(
        missing_list, cfg["budget"], cfg["alert_price"], MIN_DEAL
    )

    if recommendations["on_sale_count"] > 0:
        n_sale = recommendations["on_sale_count"]
        savings = recommendations["on_sale_savings"]
        print(f"  {_ok(f'{n_sale} DLCs en oferta · ahorro: Mex$ {savings:,.0f}')}")
    else:
        print(f"  {_dim('Sin ofertas — espera al Summer/Winter Sale')}")

    if cfg["budget"] and recommendations["budget_fit"]:
        b = cfg["budget"]
        n_fit = len(recommendations["budget_fit"])
        print(f"  {_ok(f'Presupuesto Mex$ {b:,.0f}: alcanza para {n_fit} DLCs')}")

    if recommendations.get("alerts"):
        for d in recommendations["alerts"]:
            aname = d.get("steam_name", "?")
            aprice = d.get("price_fmt", "?")
            print(f"  {_warn(f'ALERTA: {aname} a {aprice}')}")

    # Run comparison
    prev_run = load_previous_run()
    comparison = compute_run_comparison(prices, prev_run)
    if comparison:
        parts = []
        if comparison.get("new_sales"):
            parts.append(f"{len(comparison['new_sales'])} nuevas ofertas")
        if comparison.get("ended_sales"):
            parts.append(f"{len(comparison['ended_sales'])} terminaron")
        if comparison.get("price_drops"):
            parts.append(f"{len(comparison['price_drops'])} bajaron")
        if parts:
            print(
                f"  {_ok('vs ' + comparison.get('prev_date', '?') + ': ' + ' · '.join(parts))}"
            )

    save_run(owned_count, missing_count, prices, on_sale)

    # Generate MD
    step("Generando Markdown...")
    md = generate_md(
        all_dlcs=all_dlcs,
        owned_appids=pd2_owned,
        pd2_dlc_appids=pd2_dlc_appids,
        prices=prices,
        sale_name=sale_name,
        recommendations=recommendations,
        trends=trends,
        itad_lows=itad_lows,
        itad_current=itad_current,
        budget=cfg["budget"],
        vanity=VANITY,
    )
    output_file = Path(OUTPUT_DIR) / "PAYDAY2_Plan_de_Compra.md"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(md, encoding="utf-8")
    print(f"  {_ok(str(output_file))}")

    # Generate HTML
    step("Generando HTML interactivo...")
    html = generate_html(
        all_dlcs=all_dlcs,
        owned_appids=pd2_owned,
        pd2_dlc_appids=pd2_dlc_appids,
        prices=prices,
        sale_name=sale_name,
        recommendations=recommendations,
        itad_lows=itad_lows,
        vanity=VANITY,
        comparison=comparison,
        history=history,
    )
    html_file = output_file.with_suffix(".html")
    html_file.write_text(html, encoding="utf-8")
    print(f"  {_ok(str(html_file))}")

    # CSV (optional)
    if cfg["csv"]:
        step("Generando CSV...")
        csv_content = generate_csv(
            all_dlcs, pd2_owned, pd2_dlc_appids, prices, itad_lows
        )
        csv_file = output_file.with_suffix(".csv")
        csv_file.write_text(csv_content, encoding="utf-8")
        print(f"  {_ok(str(csv_file))}")

    # Summary
    elapsed = time.monotonic() - t0
    print(f"\n{C.GRN}{'─' * 42}{C.RST}")
    print(f"  {_bold('Listo')} en {elapsed:.1f}s")
    summary = f"  {owned_count}/{len(pd2_dlc_appids)} poseídos · {missing_count} faltan · Mex$ {total_cost:,.0f}"
    if on_sale:
        summary += f" · {on_sale} en oferta"
    print(summary)
    print(f"  {output_file.name} + .html")
    print(f"{C.GRN}{'─' * 42}{C.RST}\n")


if __name__ == "__main__":
    main()
