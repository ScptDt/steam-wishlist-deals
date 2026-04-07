#!/usr/bin/env python3
"""
PAYDAY 2 DLC Tracker — Plan de compra con precios en tiempo real.

Uso:
    python3 payday2_dlc_tracker.py --vanity BG00G
    python3 payday2_dlc_tracker.py --key TU_KEY --vanity BG00G
    python3 payday2_dlc_tracker.py --itad-key TU_KEY --budget 500
    python3 payday2_dlc_tracker.py --mark-owned 12345
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
from difflib import SequenceMatcher
from pathlib import Path


# ─────────────────────────────────────────────
# ANSI + HELPERS
# ─────────────────────────────────────────────

class C:
    RST  = "\033[0m"
    BOLD = "\033[1m"
    DIM  = "\033[2m"
    GRN  = "\033[32m"
    YLW  = "\033[33m"
    RED  = "\033[31m"
    CYN  = "\033[36m"

def _ok(msg):   return f"{C.GRN}✓{C.RST}  {msg}"
def _warn(msg): return f"{C.YLW}⚠{C.RST}  {msg}"
def _err(msg):  return f"{C.RED}✗{C.RST}  {msg}"
def _dim(msg):  return f"{C.DIM}{msg}{C.RST}"
def _bold(msg): return f"{C.BOLD}{msg}{C.RST}"

def _get_json(url: str, headers: dict = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def _post_json(url: str, body) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

STORE_URL = "https://store.steampowered.com/app/{appid}/"

def _md_esc(text: str) -> str:
    return text.replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")

def _link(name: str, appid: str) -> str:
    return f"[{_md_esc(name)}]({STORE_URL.format(appid=appid)})"

MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

CONFIG_FILE = Path.home() / ".config" / "steam_deals.json"

def load_user_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def get_config():
    parser = argparse.ArgumentParser(description="PAYDAY 2 DLC Tracker")
    parser.add_argument("--key", help="Steam API Key")
    parser.add_argument("--vanity", help="Steam vanity URL, ID, o perfil")
    parser.add_argument("--itad-key", help="IsThereAnyDeal API Key")
    parser.add_argument("--output", help="Directorio de salida")
    parser.add_argument("--no-cache", action="store_true", help="Ignorar caché")
    parser.add_argument("--mark-owned", nargs="*", metavar="APPID", help="Marcar DLCs como poseídos")
    parser.add_argument("--mark-unowned", nargs="*", metavar="APPID", help="Marcar DLCs como no poseídos")
    parser.add_argument("--budget", type=float, help="Presupuesto en MXN")
    parser.add_argument("--alert-price", type=float, help="Alertar si DLC baja de N MXN")
    parser.add_argument("--csv", action="store_true", help="Generar CSV")
    args = parser.parse_args()

    cfg = load_user_config()
    key = args.key or cfg.get("key")
    vanity = args.vanity or cfg.get("vanity") or "BG00G"
    itad_key = args.itad_key or cfg.get("itad_key")
    output_dir = Path(args.output).expanduser() if args.output else (
        Path(cfg["output_dir"]).expanduser() if cfg.get("output_dir") else Path(__file__).resolve().parent
    )
    budget = args.budget or cfg.get("payday2_budget")
    alert_price = args.alert_price or cfg.get("payday2_alert_price")

    return {
        "key": key, "vanity": vanity, "itad_key": itad_key,
        "output_dir": output_dir, "no_cache": args.no_cache, "csv": args.csv,
        "mark_owned": args.mark_owned or [],
        "mark_unowned": args.mark_unowned or [],
        "budget": budget, "alert_price": alert_price,
    }


# ─────────────────────────────────────────────
# PAYDAY 2 APPID
# ─────────────────────────────────────────────

PD2_APPID = "218620"


# ─────────────────────────────────────────────
# DLC DATABASE (curada del plan de compra)
# ─────────────────────────────────────────────
# tier: S > A > B > C
# type: heist, armas, cosmético, música
# bundle: nombre del bundle que lo contiene
# phase: 1-4
# priority: 1-38 (orden de compra recomendado)

DLC_DB = {
    # ── TIER S ──
    "McShay Weapon Pack 2": {
        "tier": "S", "type": "armas", "priority": 1, "phase": 3,
        "bundle": "Lost in Transit Bundle",
        "notes": "Hailstorm Mk 5 (2000 RPM, penetra Shields). VD-12 shotgun, Kahn .357.",
    },
    "McShay Weapon Pack 4": {
        "tier": "S", "type": "armas", "priority": 2, "phase": 3,
        "bundle": "Crude Awakening Bundle",
        "notes": "Campbell 74 LMG (100 acc/stab + lanzallamas), Deimos shotgun, Amaroq sniper.",
    },
    "Black Cat Heist": {
        "tier": "S", "type": "heist", "priority": 3, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Casino en yate, stealth/loud, 2 rutas loud. Mecánica airlift.",
    },
    "McShay Weapon Pack 3": {
        "tier": "S", "type": "armas", "priority": 4, "phase": 3,
        "bundle": "Hostile Takeover Bundle",
        "notes": "Akron HC LMG→DMR convertible, Aran G2 sniper secundaria, Rodion 3B triple cañón.",
    },
    # ── TIER A ──
    "Dragon Heist": {
        "tier": "A", "type": "heist", "priority": 5, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Stealth/loud + preplanning. Atmosférico, abre City of Gold.",
    },
    "Buluc's Mansion Heist": {
        "tier": "A", "type": "heist", "priority": 6, "phase": 2,
        "bundle": "Buluc's Mansion Bundle",
        "notes": "Stealth retador en mansión mexicana. Scavenger hunt.",
    },
    "Hostile Takeover Heist": {
        "tier": "A", "type": "heist", "priority": 7, "phase": 3,
        "bundle": "Hostile Takeover Bundle",
        "notes": "Oficina/lab, crew se divide en pares. ECM rushable <2 min.",
    },
    "Fugitive Weapon Pack": {
        "tier": "A", "type": "armas", "priority": 8, "phase": 2,
        "bundle": "Breakfast in Tijuana Bundle",
        "notes": "M60 LMG (mejor precisión de LMGs), R700 sniper, Holt 9mm.",
    },
    "Jiu Feng Smuggler Pack": {
        "tier": "A", "type": "armas", "priority": 9, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Mosconi 12G Tactical (borderline OP), AK Gen 21, Crosskill Chunky.",
    },
    "Lost in Transit Heist": {
        "tier": "A", "type": "heist", "priority": 10, "phase": 3,
        "bundle": "Lost in Transit Bundle",
        "notes": "Robar un tren. Experiencia única y memorable.",
    },
    "McShay Weapon Pack": {
        "tier": "A", "type": "armas", "priority": 11, "phase": 3,
        "bundle": "Midland Bundle",
        "notes": "SG Versteckt 51D (LMG oculta), Pronghorn sniper, Basilisk lanzagranadas.",
    },
    # ── TIER B ──
    "Ukrainian Prisoner Heist": {
        "tier": "B", "type": "heist", "priority": 12, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Rescate en muelles de SF. Tipo Heat Street.",
    },
    "Breakfast in Tijuana Heist": {
        "tier": "B", "type": "heist", "priority": 13, "phase": 2,
        "bundle": "Breakfast in Tijuana Bundle",
        "notes": "Asalto a estación de policía. Stealth→loud si suena alarma.",
    },
    "Border Crossing Heist": {
        "tier": "B", "type": "heist", "priority": 14, "phase": 2,
        "bundle": "Border Crossing Bundle",
        "notes": "2 heists en 1 (principal + cooking). Divisivo.",
    },
    "Mountain Master Heist": {
        "tier": "B", "type": "heist", "priority": 15, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Final de City of Gold. Sólido pero menos memorable.",
    },
    "Crude Awakening Heist": {
        "tier": "B", "type": "heist", "priority": 16, "phase": 3,
        "bundle": "Crude Awakening Bundle",
        "notes": "Misión de asesinato. Divertido pero tuvo bugs.",
    },
    "McShay Mod Pack": {
        "tier": "B", "type": "armas", "priority": 17, "phase": 3,
        "bundle": "Hostile Takeover Bundle",
        "notes": "15 mods + miras + Ordnance Bag + granada adhesiva.",
    },
    "Gunslinger Weapon Pack": {
        "tier": "B", "type": "armas", "priority": 18, "phase": 2,
        "bundle": "Buluc's Mansion Bundle",
        "notes": "Bernetti Rangehitter sniper, Reinfeld 88 shotgun.",
    },
    "Jiu Feng Smuggler Pack 2": {
        "tier": "B", "type": "armas", "priority": 19, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Sniper, AR con granada integrada, SMG akimbo.",
    },
    "Jiu Feng Smuggler Pack 4": {
        "tier": "B", "type": "armas", "priority": 20, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Argos III shotgun futurista, pistola, SMG.",
    },
    "Jiu Feng Smuggler Pack 3": {
        "tier": "B", "type": "armas", "priority": 21, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Armas adecuadas que se solapan con existentes.",
    },
    "Cartel Optics Mod Pack": {
        "tier": "B", "type": "armas", "priority": 22, "phase": 2,
        "bundle": "Border Crossing Bundle",
        "notes": "Miras reflex 0 penalización ocultación. Reskins.",
    },
    "Midland Ranch Heist": {
        "tier": "B", "type": "heist", "priority": 23, "phase": 3,
        "bundle": "Midland Bundle",
        "notes": "Divisivo. Stealth fun, loud miserable. Torreta + carrito golf.",
    },
    # ── TIER C ──
    "h3h3 Character Pack": {
        "tier": "C", "type": "armas", "priority": 24, "phase": 4,
        "bundle": None,
        "notes": "Airbow nerfeada. Tag Team mediocre. Solo para fans h3h3.",
    },
    "Guardians Tailor Pack": {
        "tier": "C", "type": "cosmético", "priority": 25, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Solo outfits cosméticos.",
    },
    "Mega City Tailor Pack": {
        "tier": "C", "type": "cosmético", "priority": 26, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Solo outfits cosméticos.",
    },
    "Winter Ghosts Tailor Pack": {
        "tier": "C", "type": "cosmético", "priority": 27, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Solo outfits cosméticos.",
    },
    "Golden Dagger Tailor Pack": {
        "tier": "C", "type": "cosmético", "priority": 28, "phase": 1,
        "bundle": "City of Gold Collection",
        "notes": "Solo outfits cosméticos.",
    },
    "Tailor Pack 1": {
        "tier": "C", "type": "cosmético", "priority": 29, "phase": 2,
        "bundle": "Border Crossing Bundle",
        "notes": "Solo outfits cosméticos.",
    },
    "Tailor Pack 3": {
        "tier": "C", "type": "cosmético", "priority": 30, "phase": 2,
        "bundle": "Buluc's Mansion Bundle",
        "notes": "Solo outfits cosméticos.",
    },
    "Southbound Tailor Pack": {
        "tier": "C", "type": "cosmético", "priority": 31, "phase": 3,
        "bundle": "Midland Bundle",
        "notes": "Solo outfits cosméticos.",
    },
    "Street Smart Tailor Pack": {
        "tier": "C", "type": "cosmético", "priority": 32, "phase": 3,
        "bundle": "Hostile Takeover Bundle",
        "notes": "Solo outfits cosméticos.",
    },
    "Lawless Tailor Pack": {
        "tier": "C", "type": "cosmético", "priority": 33, "phase": 3,
        "bundle": "Crude Awakening Bundle",
        "notes": "Solo outfits cosméticos.",
    },
    "High Octane Tailor Pack": {
        "tier": "C", "type": "cosmético", "priority": 34, "phase": 3,
        "bundle": "Lost in Transit Bundle",
        "notes": "Solo outfits cosméticos.",
    },
    "Weapon Color Pack 2": {
        "tier": "C", "type": "cosmético", "priority": 35, "phase": 2,
        "bundle": "Breakfast in Tijuana Bundle",
        "notes": "Solo 20 camos de armas.",
    },
    "Weapon Color Pack 3": {
        "tier": "C", "type": "cosmético", "priority": 36, "phase": 2,
        "bundle": "Buluc's Mansion Bundle",
        "notes": "Solo 20 colores perlados.",
    },
    "Chinatown Music Pack": {
        "tier": "C", "type": "música", "priority": 37, "phase": 3,
        "bundle": "Crude Awakening Bundle",
        "notes": "Solo música + cosmético.",
    },
    "Tijuana Music Pack": {
        "tier": "C", "type": "música", "priority": 38, "phase": 3,
        "bundle": "Lost in Transit Bundle",
        "notes": "Solo música + cosmético.",
    },
}

BUNDLES = {
    "City of Gold Collection": {
        "phase": 1,
        "dlcs": [
            "Dragon Heist", "Ukrainian Prisoner Heist", "Black Cat Heist",
            "Mountain Master Heist", "Jiu Feng Smuggler Pack",
            "Jiu Feng Smuggler Pack 2", "Jiu Feng Smuggler Pack 3",
            "Jiu Feng Smuggler Pack 4", "Guardians Tailor Pack",
            "Mega City Tailor Pack", "Winter Ghosts Tailor Pack",
            "Golden Dagger Tailor Pack",
        ],
    },
    "Breakfast in Tijuana Bundle": {
        "phase": 2,
        "dlcs": ["Breakfast in Tijuana Heist", "Fugitive Weapon Pack", "Weapon Color Pack 2"],
    },
    "Border Crossing Bundle": {
        "phase": 2,
        "dlcs": ["Border Crossing Heist", "Cartel Optics Mod Pack", "Tailor Pack 1"],
    },
    "Buluc's Mansion Bundle": {
        "phase": 2,
        "dlcs": ["Buluc's Mansion Heist", "Gunslinger Weapon Pack", "Tailor Pack 3", "Weapon Color Pack 3"],
    },
    "Hostile Takeover Bundle": {
        "phase": 3,
        "dlcs": ["Hostile Takeover Heist", "McShay Weapon Pack 3", "McShay Mod Pack", "Street Smart Tailor Pack"],
    },
    "Midland Bundle": {
        "phase": 3,
        "dlcs": ["Midland Ranch Heist", "McShay Weapon Pack", "Southbound Tailor Pack"],
    },
    "Crude Awakening Bundle": {
        "phase": 3,
        "dlcs": ["Crude Awakening Heist", "McShay Weapon Pack 4", "Lawless Tailor Pack", "Chinatown Music Pack"],
    },
    "Lost in Transit Bundle": {
        "phase": 3,
        "dlcs": ["Lost in Transit Heist", "McShay Weapon Pack 2", "High Octane Tailor Pack", "Tijuana Music Pack"],
    },
}

TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3}
TIER_LABELS = {
    "S": "COMPRAR PRIMERO (Impacto alto en gameplay)",
    "A": "COMPRAR SEGUNDO (Buen contenido)",
    "B": "COMPRAR SI ESTÁ BARATO (Decente, no esencial)",
    "C": "DESCARTABLE (Cosméticos / completionismo)",
}
TYPE_ICONS = {"heist": "🏦", "armas": "🔫", "cosmético": "👔", "música": "🎵"}

UPCOMING_SALES = [
    {"event": "Steam Summer Sale", "date": "25 jun - 9 jul 2026", "discount": 75},
    {"event": "Steam Autumn Sale", "date": "~1 oct 2026", "discount": 50},
    {"event": "Steam Winter Sale", "date": "~18 dic 2026 - 2 ene 2027", "discount": 75},
]


# ─────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────

PD2_CACHE_DIR = Path.home() / ".cache" / "steam_deals" / "payday2"
DLC_LIST_CACHE = PD2_CACHE_DIR / "dlc_list.json"
DLC_MAPPING_CACHE = PD2_CACHE_DIR / "dlc_mapping.json"
PRICES_CACHE = PD2_CACHE_DIR / "prices.json"
OWNED_CACHE = PD2_CACHE_DIR / "owned.json"
HISTORY_FILE = PD2_CACHE_DIR / "price_history.json"

DLC_LIST_TTL = 168  # 7 days
PRICES_TTL = 24     # 1 day


def _load_cache(path: Path, ttl_hours: float = 0) -> tuple[dict, float]:
    if not path.exists():
        return {}, float("inf")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, float("inf")
    age = float("inf")
    if data.get("saved_at"):
        age = (datetime.now() - datetime.fromisoformat(data["saved_at"])).total_seconds() / 3600
    return data, age


def _save_cache(path: Path, data: dict):
    PD2_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data["saved_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────
# STEAM API
# ─────────────────────────────────────────────

def resolve_steam_id(api_key: str | None, vanity: str) -> str:
    m = re.match(r'https?://steamcommunity\.com/profiles/(\d+)', vanity)
    if m:
        return m.group(1)
    m = re.match(r'https?://steamcommunity\.com/id/([^/]+)', vanity)
    if m:
        vanity = m.group(1)
    if vanity.isdigit() and len(vanity) == 17:
        return vanity
    if api_key:
        url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={api_key}&vanityurl={vanity}"
        data = _get_json(url)
        if data["response"]["success"] != 1:
            raise ValueError(f"No se pudo resolver: {vanity}")
        return data["response"]["steamid"]
    url = f"https://steamcommunity.com/id/{vanity}/?xml=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        text = r.read().decode("utf-8")
    m = re.search(r'<steamID64>(\d+)</steamID64>', text)
    if not m:
        raise ValueError(f"No se pudo resolver: {vanity}")
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


def fetch_dlc_names(appids: list[str], cached_mapping: dict, rate_limit: float = 0.3) -> dict[str, str]:
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
            print(f"  {_dim(f'  {idx+1}/{total} nombres...')}", flush=True)

    return result


def match_dlc_names_to_db(names: dict[str, str]) -> dict[str, dict]:
    """Match Steam DLC names to curated database. Returns {appid: db_entry_with_appid}."""
    mapping = {}
    used_db_keys = set()

    # Normalize: strip "PAYDAY 2: " prefix
    def norm(s):
        s = re.sub(r'^PAYDAY\s*2\s*[:：\-–]\s*', '', s, flags=re.IGNORECASE)
        return s.strip().lower()

    # Pass 1: exact match
    for appid, steam_name in names.items():
        n = norm(steam_name)
        for db_key, db_entry in DLC_DB.items():
            if db_key in used_db_keys:
                continue
            if norm(db_key) == n:
                mapping[appid] = {**db_entry, "appid": appid, "db_name": db_key, "steam_name": steam_name}
                used_db_keys.add(db_key)
                break

    # Pass 2: fuzzy match remaining
    for appid, steam_name in names.items():
        if appid in mapping:
            continue
        n = norm(steam_name)
        best_score, best_key = 0, None
        for db_key in DLC_DB:
            if db_key in used_db_keys:
                continue
            score = SequenceMatcher(None, n, norm(db_key)).ratio()
            if score > best_score:
                best_score, best_key = score, db_key
        if best_key and best_score >= 0.6:
            db_entry = DLC_DB[best_key]
            mapping[appid] = {**db_entry, "appid": appid, "db_name": best_key, "steam_name": steam_name}
            used_db_keys.add(best_key)

    return mapping


def get_owned_games(api_key: str, steam_id: str) -> set[str]:
    """Get all owned appids (games + DLCs)."""
    url = (
        f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        f"?key={api_key}&steamid={steam_id}&include_appinfo=1&include_played_free_games=1"
    )
    data = _get_json(url)
    return {str(g["appid"]) for g in data.get("response", {}).get("games", [])}


def load_owned(steam_id: str) -> set[str]:
    cache, _ = _load_cache(OWNED_CACHE)
    if cache.get("steam_id") == steam_id:
        return set(cache.get("appids", []))
    return set()


def save_owned(steam_id: str, owned: set[str]):
    _save_cache(OWNED_CACHE, {"steam_id": steam_id, "appids": sorted(owned)})


def fetch_dlc_prices(appids: list[str], no_cache: bool = False, rate_limit: float = 0.3) -> dict[str, dict]:
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
                    "price_raw": 0, "price_fmt": "Gratis",
                    "orig_raw": 0, "orig_fmt": "Gratis",
                    "discount": 0, "delisted": not info.get("name"),
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
            print(f"  {_dim(f'  {idx+1}/{total} precios...')}", flush=True)

    _save_cache(PRICES_CACHE, {"prices": result})
    return result


# ─────────────────────────────────────────────
# ITAD (mínimo histórico + multi-tienda)
# ─────────────────────────────────────────────

ITAD_BATCH = 50

def itad_lookup(appids: list[str], itad_key: str) -> dict[str, str]:
    result = {}
    for i in range(0, len(appids), ITAD_BATCH):
        batch = appids[i:i + ITAD_BATCH]
        body = [{"type": "steam", "id": f"app/{a}"} for a in batch]
        try:
            data = _post_json(f"https://api.isthereanydeal.com/games/lookup/v1?key={itad_key}", body)
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
        batch = all_ids[i:i + ITAD_BATCH]
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
        batch = all_ids[i:i + ITAD_BATCH]
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
                            best_other = {"store": pd.get("shop", {}).get("name", "?"), "price": amt, "url": pd.get("url", "")}
                    if best_other and steam_price is not None and best_other["price"] < steam_price:
                        result[appid] = best_other
        except Exception as exc:
            print(f"  {_warn(f'ITAD prices: {exc}')}", flush=True)
        time.sleep(0.5)
    return result


# ─────────────────────────────────────────────
# PRICE HISTORY
# ─────────────────────────────────────────────

def load_price_history() -> dict:
    if not HISTORY_FILE.exists():
        return {"snapshots": []}
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"snapshots": []}


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
    PD2_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


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
            result[appid] = {"times_seen": 1, "lowest": curr, "avg": curr, "is_at_lowest": False, "direction": "new"}
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


# ─────────────────────────────────────────────
# RECOMMENDATIONS
# ─────────────────────────────────────────────

def compute_recommendations(missing: list[dict], budget: float | None, alert_price: float | None) -> dict:
    on_sale = sorted(
        [d for d in missing if d.get("discount", 0) > 0],
        key=lambda d: (-TIER_ORDER.get(d.get("tier", "C"), 9), d.get("priority", 99)),
    )

    buy_now = []
    for d in on_sale:
        if d.get("tier") in ("S", "A"):
            buy_now.append(d)

    alerts = []
    if alert_price:
        alerts = [d for d in missing if d.get("price_raw", 0) > 0 and d["price_raw"] / 100 <= alert_price]

    budget_fit = []
    if budget:
        remaining = budget
        for d in sorted(missing, key=lambda d: d.get("priority", 99)):
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
        "on_sale_savings": sum(((d.get("orig_raw", 0) - d.get("price_raw", 0)) / 100) for d in on_sale),
    }


def compute_phase_costs(missing: list[dict]) -> dict[int, dict]:
    phases = {}
    for d in missing:
        ph = d.get("phase", 0)
        if ph not in phases:
            phases[ph] = {"total": 0, "discounted": 0, "count": 0, "dlcs": []}
        phases[ph]["total"] += d.get("orig_raw", 0) / 100
        phases[ph]["discounted"] += d.get("price_raw", 0) / 100
        phases[ph]["count"] += 1
        phases[ph]["dlcs"].append(d)
    return phases


# ─────────────────────────────────────────────
# GENERATE MARKDOWN
# ─────────────────────────────────────────────

def generate_md(
    all_dlcs: dict[str, dict],  # appid → merged info
    owned_appids: set[str],
    pd2_dlc_appids: list[str],
    prices: dict[str, dict],
    sale_name: str,
    recommendations: dict,
    phase_costs: dict[int, dict],
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

    # Compute totals
    missing_total_orig = sum(d.get("orig_raw", 0) for a, d in all_dlcs.items() if a not in owned_appids) / 100
    missing_total_curr = sum(d.get("price_raw", 0) for a, d in all_dlcs.items() if a not in owned_appids) / 100
    on_sale = sum(1 for a, d in all_dlcs.items() if a not in owned_appids and d.get("discount", 0) > 0)
    avg_discount = 0
    if on_sale:
        avg_discount = sum(d.get("discount", 0) for a, d in all_dlcs.items() if a not in owned_appids and d.get("discount", 0) > 0) / on_sale

    lines = [
        f"# PAYDAY 2 — Plan de Compra (Actualizado)",
        f"> Generado: {today} | Precios en MXN | Perfil: {vanity}",
        f"> Posees: {owned_count}/{total_dlcs} items | Faltan: {missing_count} DLCs",
        "",
        "---",
        "",
        "## Resumen",
        "",
        "| Métrica | Valor |",
        "|---------|-------|",
        f"| DLCs poseídos | {owned_count}/{total_dlcs} ({owned_count*100//total_dlcs}%) |",
        f"| Costo restante (precio normal) | Mex$ {missing_total_orig:,.0f} |",
    ]
    if missing_total_curr != missing_total_orig:
        savings = missing_total_orig - missing_total_curr
        lines.append(f"| **Con descuento actual** | **Mex$ {missing_total_curr:,.0f}** (ahorras Mex$ {savings:,.0f}) |")
    lines += [
        f"| DLCs en oferta ahora | {on_sale} |",
    ]
    if budget:
        lines.append(f"| Tu presupuesto | Mex$ {budget:,.0f} |")
    lines += ["", "---", ""]

    # Sale / Recommendation
    if sale_name:
        lines += [f"## 🏷️ {sale_name}", ""]
    else:
        lines += ["## Estado de ofertas", ""]

    rec = recommendations
    if rec["on_sale_count"] > 0:
        lines.append(f"> **{rec['on_sale_count']} DLCs en oferta** | Ahorro potencial: Mex$ {rec['on_sale_savings']:,.0f}")
        lines.append("")
        if rec["buy_now"]:
            lines += ["### Recomendación: COMPRAR AHORA", ""]
            lines.append("| DLC | Tier | Precio | Descuento | Bundle |")
            lines.append("|-----|------|--------|-----------|--------|")
            for d in rec["buy_now"]:
                lines.append(f"| {_link(d['steam_name'], d['appid'])} | {d['tier']} | {d.get('price_fmt', '?')} | -{d.get('discount', 0)}% | {d.get('bundle') or '—'} |")
            lines.append("")
        if rec["optimal_next"]:
            opt = rec["optimal_next"]
            lines.append(f"> **Mejor compra ahora:** {opt['steam_name']} (-{opt.get('discount', 0)}%, {opt.get('price_fmt', '?')})")
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
            lines.append(f"| {sale['event']} | {sale['date']} | -{sale['discount']}% | ~Mex$ {est_savings:,.0f} |")
        lines += [
            "",
            f"> **Recomendación:** Espera al Summer Sale (75% off). Costo estimado: ~Mex$ {missing_total_orig * 0.25:,.0f}",
        ]
    lines += ["", "---", ""]

    # Budget
    if budget and rec["budget_fit"]:
        total_budget_cost = sum(d.get("price_raw", 0) / 100 for d in rec["budget_fit"])
        lines += [
            f"## 💰 Con tu presupuesto (Mex$ {budget:,.0f})",
            "",
            f"> Puedes comprar {len(rec['budget_fit'])} DLCs por ~Mex$ {total_budget_cost:,.0f} (ordenados por prioridad)",
            "",
            "| # | DLC | Tier | Precio |",
            "|---|-----|------|--------|",
        ]
        for i, d in enumerate(rec["budget_fit"], 1):
            lines.append(f"| {i} | {_link(d['steam_name'], d['appid'])} | {d['tier']} | {d.get('price_fmt', '?')} |")
        lines += ["", "---", ""]

    # DLCs by tier
    missing_dlcs = sorted(
        [d for a, d in all_dlcs.items() if a not in owned_appids],
        key=lambda d: (TIER_ORDER.get(d.get("tier", "C"), 9), d.get("priority", 99)),
    )

    lines += ["## DLCs Faltantes por Tier", ""]
    current_tier = None
    for d in missing_dlcs:
        tier = d.get("tier", "?")
        if tier != current_tier:
            current_tier = tier
            tier_dlcs = [x for x in missing_dlcs if x.get("tier") == tier]
            tier_cost = sum(x.get("price_raw", 0) / 100 for x in tier_dlcs)
            lines += [
                f"### TIER {tier} — {TIER_LABELS.get(tier, '')} ({len(tier_dlcs)} DLCs, ~Mex$ {tier_cost:,.0f})",
                "",
            ]
            header = "| # | DLC | Tipo | Precio | Oferta"
            sep = "|---|-----|------|--------|-------"
            if itad_lows:
                header += " | Mín. histórico"
                sep += "|----------------"
            if itad_current:
                header += " | Mejor precio"
                sep += "|--------------"
            header += " | Bundle |"
            sep += "|--------|"
            lines += [header, sep]

        appid = d.get("appid", "")
        icon = TYPE_ICONS.get(d.get("type", ""), "")
        price = d.get("price_fmt", "?")
        disc = f"-{d['discount']}%" if d.get("discount", 0) > 0 else "—"
        if d.get("discount", 0) >= 50:
            disc = f"**{disc}**"
        bundle = d.get("bundle") or "—"

        row = f"| {d.get('priority', '?')} | {_link(d.get('steam_name', d.get('db_name', '?')), appid)} | {icon} {d.get('type', '')} | {price} | {disc}"

        if itad_lows:
            low = itad_lows.get(appid)
            row += f" | Mex$ {low['price']:.0f} ({low['date']})" if low else " | —"
        if itad_current:
            cp = itad_current.get(appid)
            row += f" | ${cp['price']:.0f} en [{cp['store']}]({cp['url']})" if cp else " | —"
        row += f" | {bundle} |"
        lines.append(row)

    lines += ["", "---", ""]

    # Phase costs
    lines += ["## Plan por Fases (Costos Reales)", ""]
    phase_names = {1: "City of Gold Collection", 2: "Silk Road (Mini Bundles)", 3: "Texas Heat (Mini Bundles)", 4: "DLCs Sueltos"}
    for ph in sorted(phase_costs):
        pc = phase_costs[ph]
        name = phase_names.get(ph, f"Fase {ph}")
        lines += [
            f"### FASE {ph}: {name} — Mex$ {pc['discounted']:,.0f}" + (f" ~~Mex$ {pc['total']:,.0f}~~" if pc['total'] != pc['discounted'] else ""),
            "",
            "| DLC | Precio | Desc. | Tipo |",
            "|-----|--------|-------|------|",
        ]
        for d in sorted(pc["dlcs"], key=lambda x: x.get("priority", 99)):
            disc = f"-{d['discount']}%" if d.get("discount", 0) > 0 else "—"
            icon = TYPE_ICONS.get(d.get("type", ""), "")
            lines.append(f"| {_link(d.get('steam_name', d.get('db_name', '?')), d.get('appid', ''))} | {d.get('price_fmt', '?')} | {disc} | {icon} {d.get('type', '')} |")
        lines += [f"| **Total Fase {ph}** | **Mex$ {pc['discounted']:,.0f}** | | {pc['count']} DLCs |", "", "---", ""]

    # Bundles summary
    lines += ["## Resumen por Bundle", ""]
    lines += ["| Bundle | Fase | DLCs faltantes | Costo actual |", "|--------|------|----------------|--------------|"]
    for bname, binfo in BUNDLES.items():
        bdlcs = []
        for db_key in binfo["dlcs"]:
            for a, d in all_dlcs.items():
                if d.get("db_name") == db_key and a not in owned_appids:
                    bdlcs.append(d)
                    break
        if bdlcs:
            cost = sum(d.get("price_raw", 0) / 100 for d in bdlcs)
            lines.append(f"| {bname} | {binfo['phase']} | {len(bdlcs)} | Mex$ {cost:,.0f} |")
    lines += ["", "---", ""]

    # Price history / trends
    if any(t.get("times_seen", 0) > 1 for t in trends.values()):
        lines += ["## Historial de Precios", ""]
        lines += ["| DLC | Hoy | Promedio | Mín. registrado | Tendencia |", "|-----|-----|---------|-----------------|-----------|"]
        for d in missing_dlcs:
            appid = d.get("appid", "")
            t = trends.get(appid, {})
            if t.get("times_seen", 0) <= 1:
                continue
            curr = d.get("price_raw", 0) / 100
            arrows = {"down": "⬇️", "up": "⬆️", "stable": "➡️", "new": "🆕"}
            arrow = arrows.get(t.get("direction", ""), "")
            low_marker = " 🔥" if t.get("is_at_lowest") else ""
            lines.append(f"| {_md_esc(d.get('steam_name', '?'))} | Mex$ {curr:.0f} | Mex$ {t['avg']/100:.0f} | Mex$ {t['lowest']/100:.0f}{low_marker} | {arrow} |")
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
        lines.append(f"| {sale['event']} | {sale['date']} | -{sale['discount']}% | ~Mex$ {est:,.0f} |")
    lines += [""]

    # Scarface note (preserved)
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


# ─────────────────────────────────────────────
# RUN COMPARISON
# ─────────────────────────────────────────────

RUN_HISTORY_FILE = PD2_CACHE_DIR / "run_history.json"

def load_previous_run() -> dict | None:
    if not RUN_HISTORY_FILE.exists():
        return None
    try:
        data = json.loads(RUN_HISTORY_FILE.read_text(encoding="utf-8"))
        return data.get("last_run")
    except (json.JSONDecodeError, OSError):
        return None


def save_run(owned_count: int, missing_count: int, prices: dict, on_sale: int):
    PD2_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    run = {
        "date": date.today().isoformat(),
        "owned": owned_count,
        "missing": missing_count,
        "on_sale": on_sale,
        "prices": {a: {"price": p.get("price_raw", 0), "discount": p.get("discount", 0)} for a, p in prices.items()},
    }
    RUN_HISTORY_FILE.write_text(json.dumps({"last_run": run}, ensure_ascii=False, indent=2), encoding="utf-8")


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


# ─────────────────────────────────────────────
# GENERATE HTML
# ─────────────────────────────────────────────

def _html_esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


CAPSULE_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_231x87.jpg"
HEADER_IMG_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"


def generate_html(
    all_dlcs: dict[str, dict],
    owned_appids: set[str],
    pd2_dlc_appids: list[str],
    prices: dict[str, dict],
    sale_name: str,
    recommendations: dict,
    phase_costs: dict[int, dict],
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
    cost_orig = sum(d.get("orig_raw", 0) for a, d in all_dlcs.items() if a not in owned_appids) / 100
    cost_curr = sum(d.get("price_raw", 0) for a, d in all_dlcs.items() if a not in owned_appids) / 100
    on_sale = sum(1 for a, d in all_dlcs.items() if a not in owned_appids and d.get("discount", 0) > 0)
    pct_owned = owned * 100 // total if total else 0

    # Build JSON data for JS
    dlc_json_list = []
    for d in sorted(
        [d for a, d in all_dlcs.items() if a not in owned_appids and d.get("tier")],
        key=lambda d: (TIER_ORDER.get(d.get("tier", "C"), 9), d.get("priority", 99)),
    ):
        appid = d.get("appid", "")
        low = itad_lows.get(appid)
        dlc_json_list.append({
            "id": appid, "name": d.get("steam_name", d.get("db_name", "?")),
            "tier": d.get("tier", "C"), "type": d.get("type", "?"),
            "price": d.get("price_raw", 0), "orig": d.get("orig_raw", 0),
            "priceFmt": d.get("price_fmt", "?"), "origFmt": d.get("orig_fmt", "?"),
            "discount": d.get("discount", 0), "bundle": d.get("bundle") or "",
            "phase": d.get("phase", 0), "priority": d.get("priority", 99),
            "notes": d.get("notes", ""),
            "low": low["price"] if low else None,
            "lowDate": low["date"] if low else None,
        })

    # Bundle data for cards
    bundle_json = {}
    for bname, binfo in BUNDLES.items():
        bdlcs = []
        for db_key in binfo["dlcs"]:
            for a, d in all_dlcs.items():
                if d.get("db_name") == db_key and a not in owned_appids:
                    bdlcs.append({"id": a, "name": d.get("steam_name", db_key), "price": d.get("price_raw", 0)})
                    break
        if bdlcs:
            bundle_json[bname] = {"phase": binfo["phase"], "dlcs": bdlcs, "cost": sum(x["price"] for x in bdlcs)}

    # History sparkline data
    history_data = {}
    if history:
        for snap in history.get("snapshots", [])[-30:]:
            for appid, sp in snap.get("prices", {}).items():
                if appid not in history_data:
                    history_data[appid] = []
                history_data[appid].append(sp.get("price", 0))

    data_json = json.dumps({
        "dlcs": dlc_json_list,
        "bundles": bundle_json,
        "history": history_data,
        "totalAll": total,
        "ownedCount": owned,
        "costOrig": round(cost_orig),
        "costCurr": round(cost_curr),
    }, ensure_ascii=False)

    # Comparison badges
    comp_html = ""
    if comparison:
        parts = []
        if comparison.get("new_sales"):
            parts.append(f'<span class="badge bg-green">{len(comparison["new_sales"])} nuevas ofertas</span>')
        if comparison.get("ended_sales"):
            parts.append(f'<span class="badge bg-red">{len(comparison["ended_sales"])} terminaron</span>')
        if comparison.get("price_drops"):
            parts.append(f'<span class="badge bg-blue">{len(comparison["price_drops"])} bajaron</span>')
        if parts:
            comp_html = f'<div class="comp-row">vs {comparison.get("prev_date", "?")}: {" ".join(parts)}</div>'

    sale_badge = f'<div class="sale-banner">🏷️ {_html_esc(sale_name)}</div>' if sale_name else ""

    rec = recommendations
    rec_html = ""
    if rec["buy_now"]:
        items = " ".join(
            f'<a href="{STORE_URL.format(appid=d["appid"])}" class="rec-item" target="_blank">{_html_esc(d["steam_name"])} <small>-{d.get("discount",0)}%</small></a>'
            for d in rec["buy_now"][:4]
        )
        rec_html = f'<div class="rec-buy">🛒 <strong>Comprar ahora:</strong> {items}</div>'
    elif not rec["on_sale_count"]:
        rec_html = '<div class="rec-wait">⏳ Sin ofertas — espera al <strong>Summer Sale</strong> (25 jun, ~75% off)</div>'

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
/* Header */
.hdr{{background:linear-gradient(135deg,#0e1a26,#1b2838);border-bottom:2px solid var(--border);padding:1.5rem 1rem;text-align:center}}
.hdr h1{{font-size:1.6rem;color:var(--accent);letter-spacing:.02em}}
.hdr .sub{{color:var(--text2);font-size:.85rem;margin-top:.3rem}}
/* Cards */
.card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:1.2rem;margin-bottom:1rem}}
.card h2{{font-size:1rem;color:var(--accent);margin-bottom:.8rem;font-weight:600}}
/* Stat grid */
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin-bottom:1rem}}
.st{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:.8rem;text-align:center}}
.st .v{{font-size:1.5rem;font-weight:700;color:var(--accent)}}
.st .l{{font-size:.72rem;color:var(--text2);margin-top:.15rem}}
.st.g .v{{color:var(--green)}} .st.y .v{{color:var(--yellow)}} .st.r .v{{color:var(--red)}}
/* Donut */
.donut-wrap{{display:flex;align-items:center;justify-content:center;gap:2rem;margin-bottom:1rem;flex-wrap:wrap}}
.donut-svg{{width:160px;height:160px}}
.donut-center{{font-size:1.4rem;font-weight:700;fill:var(--text)}}
.donut-label{{font-size:.7rem;fill:var(--text2)}}
.donut-ring{{fill:none;stroke:var(--bg2);stroke-width:18}}
.donut-fill{{fill:none;stroke:var(--accent);stroke-width:18;stroke-linecap:round;transition:stroke-dashoffset .8s ease}}
.donut-legend{{font-size:.85rem;color:var(--text2)}}
.donut-legend div{{margin-bottom:.4rem}}
.donut-legend .dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:.4rem;vertical-align:middle}}
/* Banners */
.sale-banner{{background:var(--gold);color:#1b2838;padding:.5rem 1rem;border-radius:6px;font-weight:600;text-align:center;margin-bottom:.75rem}}
.rec-buy{{background:rgba(108,198,68,.12);border:1px solid var(--green);padding:.7rem 1rem;border-radius:6px;margin-bottom:.75rem}}
.rec-buy .rec-item{{background:rgba(108,198,68,.15);padding:.2rem .6rem;border-radius:4px;margin:0 .3rem;white-space:nowrap}}
.rec-wait{{background:rgba(240,178,50,.08);border:1px solid var(--yellow);color:var(--yellow);padding:.7rem 1rem;border-radius:6px;margin-bottom:.75rem}}
.comp-row{{font-size:.82rem;color:var(--text2);margin-bottom:.6rem}}
.badge{{display:inline-block;padding:.1rem .4rem;border-radius:3px;font-size:.72rem;font-weight:600}}
.bg-green{{background:rgba(108,198,68,.2);color:var(--green)}}
.bg-red{{background:rgba(199,50,46,.2);color:var(--red)}}
.bg-blue{{background:rgba(102,192,244,.2);color:var(--accent)}}
/* Simulator */
.sim{{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}}
.sim input[type=range]{{flex:1;min-width:200px;accent-color:var(--accent)}}
.sim .sim-val{{font-size:1.2rem;font-weight:700;color:var(--accent);min-width:3.5rem;text-align:center}}
.sim-result{{display:flex;gap:1.5rem;margin-top:.5rem;font-size:.9rem;flex-wrap:wrap}}
.sim-result .sr{{color:var(--green);font-weight:600}}
/* Bundle cards */
.bundles-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:.75rem}}
.bcard{{background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden;transition:border-color .2s}}
.bcard:hover{{border-color:var(--accent)}}
.bcard-head{{padding:.7rem .9rem;display:flex;justify-content:space-between;align-items:center;background:rgba(102,192,244,.05)}}
.bcard-name{{font-weight:600;font-size:.9rem}}
.bcard-cost{{color:var(--accent);font-weight:700;font-size:.95rem}}
.bcard-phase{{font-size:.7rem;color:var(--text2)}}
.bcard-dlcs{{padding:.5rem .9rem .7rem}}
.bcard-dlc{{display:flex;align-items:center;gap:.5rem;padding:.25rem 0;font-size:.8rem;border-bottom:1px solid rgba(42,71,94,.3)}}
.bcard-dlc:last-child{{border:none}}
.bcard-dlc img{{width:80px;height:30px;border-radius:3px;object-fit:cover;flex-shrink:0}}
.bcard-dlc .bdprice{{margin-left:auto;color:var(--text2);font-size:.75rem;white-space:nowrap}}
/* Filters */
.filters{{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.75rem;align-items:center}}
.filters select,.filters input[type=text]{{background:var(--card);border:1px solid var(--border);color:var(--text);padding:.4rem .6rem;border-radius:4px;font-size:.8rem}}
.filters select:focus,.filters input:focus{{border-color:var(--accent);outline:none}}
.filters .count{{font-size:.75rem;color:var(--text2);margin-left:auto}}
/* Table */
.tbl-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:.82rem}}
th{{background:var(--bg2);color:var(--text2);text-align:left;padding:.55rem .5rem;font-weight:600;position:sticky;top:0;cursor:pointer;white-space:nowrap;user-select:none}}
th:hover{{color:var(--accent)}}
td{{padding:.45rem .5rem;border-bottom:1px solid rgba(42,71,94,.4);vertical-align:middle}}
tr:hover{{background:rgba(102,192,244,.04)}}
tr.checked-row{{opacity:.4}}
tr.checked-row td{{text-decoration:line-through}}
.tier{{font-weight:700;text-align:center;width:28px}}
.tier-S{{color:var(--gold)}} .tier-A{{color:var(--green)}} .tier-B{{color:var(--accent)}} .tier-C{{color:var(--text2)}}
.dlc-cell{{display:flex;align-items:center;gap:.5rem}}
.dlc-cell img{{width:92px;height:34px;border-radius:3px;object-fit:cover;flex-shrink:0;transition:transform .2s}}
.dlc-cell img:hover{{transform:scale(2.5);position:relative;z-index:10;box-shadow:0 4px 20px rgba(0,0,0,.6)}}
.dlc-info .dlc-name{{font-weight:500}}
.dlc-info .dlc-notes{{font-size:.68rem;color:var(--text2);max-width:250px}}
.sale-tag{{color:var(--green);font-weight:700}}
.low-tag{{color:var(--yellow)}}
.chk{{width:16px;height:16px;accent-color:var(--green);cursor:pointer}}
.sparkline{{width:80px;height:24px}}
.sparkline polyline{{fill:none;stroke:var(--accent);stroke-width:1.5}}
/* Footer */
.footer{{text-align:center;color:var(--text2);font-size:.72rem;padding:2rem 0 1rem}}
@media(max-width:600px){{
  .stats{{grid-template-columns:repeat(3,1fr)}}
  .bundles-grid{{grid-template-columns:1fr}}
  .donut-wrap{{flex-direction:column}}
  .dlc-cell img{{width:60px;height:22px}}
}}
</style>
</head>
<body>
<div class="hdr">
  <h1>&#127918; PAYDAY 2 DLC Tracker</h1>
  <div class="sub">{today} &middot; {_html_esc(vanity)} &middot; MXN</div>
</div>
<div class="container">
  {sale_badge}
  {comp_html}
  {rec_html}

  <!-- Donut + Stats -->
  <div class="donut-wrap">
    <svg class="donut-svg" viewBox="0 0 180 180">
      <circle class="donut-ring" cx="90" cy="90" r="70"/>
      <circle class="donut-fill" cx="90" cy="90" r="70" stroke-dasharray="440" stroke-dashoffset="{440 - 440*pct_owned/100}" transform="rotate(-90 90 90)"/>
      <text class="donut-center" x="90" y="86" text-anchor="middle">{pct_owned}%</text>
      <text class="donut-label" x="90" y="105" text-anchor="middle">{owned}/{total} DLCs</text>
    </svg>
    <div class="donut-legend">
      <div><span class="dot" style="background:var(--accent)"></span>Poseidos: {owned}</div>
      <div><span class="dot" style="background:var(--gold)"></span>Tier S faltantes: {sum(1 for d in dlc_json_list if d['tier']=='S')}</div>
      <div><span class="dot" style="background:var(--green)"></span>Tier A faltantes: {sum(1 for d in dlc_json_list if d['tier']=='A')}</div>
      <div><span class="dot" style="background:var(--yellow)"></span>Tier B faltantes: {sum(1 for d in dlc_json_list if d['tier']=='B')}</div>
      <div><span class="dot" style="background:var(--text2)"></span>Tier C faltantes: {sum(1 for d in dlc_json_list if d['tier']=='C')}</div>
    </div>
  </div>

  <div class="stats" id="stats-bar">
    <div class="st y"><div class="v" id="s-cost">Mex$ {cost_curr:,.0f}</div><div class="l">Costo actual</div></div>
    <div class="st"><div class="v">Mex$ {cost_orig:,.0f}</div><div class="l">Precio normal</div></div>
    <div class="st g"><div class="v" id="s-sale">{on_sale}</div><div class="l">En oferta</div></div>
    <div class="st"><div class="v" id="s-missing">{missing}</div><div class="l">Faltan</div></div>
    <div class="st g"><div class="v">Mex$ {cost_orig*0.25:,.0f}</div><div class="l">Est. Summer 75%</div></div>
    <div class="st"><div class="v" id="s-checked">0</div><div class="l">Marcados</div></div>
  </div>

  <!-- Discount Simulator -->
  <div class="card">
    <h2>&#128270; Simulador de Descuento</h2>
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

  <!-- Bundle Cards -->
  <div class="card">
    <h2>&#128230; Bundles</h2>
    <div class="bundles-grid" id="bundles"></div>
  </div>

  <!-- DLC Table -->
  <div class="card">
    <h2>&#128203; DLCs Faltantes</h2>
    <div class="filters">
      <select id="f-tier" onchange="render()"><option value="">Tier</option><option value="S">S</option><option value="A">A</option><option value="B">B</option><option value="C">C</option></select>
      <select id="f-phase" onchange="render()"><option value="">Fase</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select>
      <select id="f-type" onchange="render()"><option value="">Tipo</option><option value="heist">Heist</option><option value="armas">Armas</option><option value="cosmético">Cosm.</option><option value="música">Música</option></select>
      <select id="f-sale" onchange="render()"><option value="">Oferta</option><option value="y">En oferta</option><option value="n">Normal</option></select>
      <input type="text" id="f-q" placeholder="Buscar..." oninput="render()">
      <span class="count" id="f-count"></span>
    </div>
    <div class="tbl-wrap">
      <table><thead><tr>
        <th style="width:30px">&#9745;</th>
        <th onclick="doSort('tier')">Tier</th>
        <th onclick="doSort('name')">DLC</th>
        <th onclick="doSort('type')">Tipo</th>
        <th onclick="doSort('price')">Precio</th>
        <th onclick="doSort('discount')">Oferta</th>
        <th>Hist.</th>
        <th onclick="doSort('bundle')">Bundle</th>
        <th onclick="doSort('phase')">Fase</th>
      </tr></thead><tbody id="tbody"></tbody></table>
    </div>
  </div>
</div>
<div class="footer">PAYDAY 2 DLC Tracker &middot; {today}</div>

<script>
const DATA = {data_json};
const STORE = "https://store.steampowered.com/app/";
const CAP = "https://cdn.akamai.steamstatic.com/steam/apps/";
const ICONS = {{heist:"🏦",armas:"🔫","cosmético":"👔","música":"🎵"}};
const TIER_CLS = {{S:"tier-S",A:"tier-A",B:"tier-B",C:"tier-C"}};
let checked = JSON.parse(localStorage.getItem('pd2_checked')||'[]');
let sortKey = 'priority', sortAsc = true;

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
  const tier=document.getElementById('f-tier').value;
  const phase=document.getElementById('f-phase').value;
  const type=document.getElementById('f-type').value;
  const sale=document.getElementById('f-sale').value;
  const q=document.getElementById('f-q').value.toLowerCase();
  let dlcs=DATA.dlcs.filter(d=>{{
    if(tier&&d.tier!==tier) return false;
    if(phase&&d.phase!=phase) return false;
    if(type&&d.type!==type) return false;
    if(sale==='y'&&d.discount===0) return false;
    if(sale==='n'&&d.discount>0) return false;
    if(q&&!d.name.toLowerCase().includes(q)&&!(d.notes||'').toLowerCase().includes(q)) return false;
    return true;
  }});
  // Sort
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
    const low=d.low?('$'+d.low.toFixed(0)):'—';
    return '<tr class="'+cls+'" data-id="'+d.id+'">'+
      '<td><input type="checkbox" class="chk" '+(ck?'checked':'')+' onchange="toggleCheck(\\\''+d.id+'\\\')"></td>'+
      '<td class="tier '+TIER_CLS[d.tier]+'">'+d.tier+'</td>'+
      '<td><div class="dlc-cell"><img src="'+CAP+d.id+'/capsule_231x87.jpg" loading="lazy" onerror="this.style.display=\\\'none\\\'"><div class="dlc-info"><div class="dlc-name"><a href="'+STORE+d.id+'/" target="_blank">'+d.name+'</a></div><div class="dlc-notes">'+(d.notes||'')+'</div></div></div></td>'+
      '<td>'+(ICONS[d.type]||'')+' '+d.type+'</td>'+
      '<td>'+d.priceFmt+'</td>'+
      '<td>'+disc+'</td>'+
      '<td>'+sparkSvg(d.id)+'</td>'+
      '<td>'+d.bundle+'</td>'+
      '<td>'+d.phase+'</td></tr>';
  }}).join('');
  document.getElementById('f-count').textContent=dlcs.length+'/'+DATA.dlcs.length;
}}

function doSort(key){{ if(sortKey===key) sortAsc=!sortAsc; else{{ sortKey=key; sortAsc=true; }} render(); }}

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
    if(d.discount>0) total+=d.price; // already discounted
    else total+=d.orig*(1-pct/100);
  }});
  total/=100;
  const orig=unchecked.reduce((s,d)=>s+d.orig,0)/100;
  document.getElementById('sim-cost').textContent='Mex$ '+Math.round(total).toLocaleString('en');
  document.getElementById('sim-save').textContent='Mex$ '+Math.round(orig-total).toLocaleString('en');
}}

function renderBundles(){{
  const el=document.getElementById('bundles');
  el.innerHTML=Object.entries(DATA.bundles).map(([name,b])=>{{
    const dlcs=b.dlcs.map(d=>
      '<div class="bcard-dlc"><img src="'+CAP+d.id+'/capsule_231x87.jpg" loading="lazy" onerror="this.style.display=\\\'none\\\'"><span>'+d.name.replace('PAYDAY 2: ','')+'</span><span class="bdprice">$'+(d.price/100).toFixed(0)+'</span></div>'
    ).join('');
    return '<div class="bcard"><div class="bcard-head"><div><div class="bcard-name">'+name+'</div><div class="bcard-phase">Fase '+b.phase+' &middot; '+b.dlcs.length+' DLCs</div></div><div class="bcard-cost">Mex$ '+(b.cost/100).toLocaleString('en',{{maximumFractionDigits:0}})+'</div></div><div class="bcard-dlcs">'+dlcs+'</div></div>';
  }}).join('');
}}

// Init
render(); updateStats(); renderBundles(); simulate();
</script>
</body>
</html>'''


# ─────────────────────────────────────────────
# GENERATE CSV
# ─────────────────────────────────────────────

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
    writer.writerow(["AppID", "Name", "Tier", "Type", "Priority", "Phase", "Bundle",
                     "Price (MXN)", "Original Price", "Discount%", "ITAD Low", "Status", "Notes", "URL"])

    missing = sorted(
        [(a, all_dlcs[a]) for a in pd2_dlc_appids if a not in owned_appids and a in all_dlcs and all_dlcs[a].get("tier")],
        key=lambda x: (TIER_ORDER.get(x[1].get("tier", "C"), 9), x[1].get("priority", 99)),
    )
    for appid, d in missing:
        low = itad_lows.get(appid)
        writer.writerow([
            appid,
            d.get("steam_name", d.get("db_name", "")),
            d.get("tier", ""),
            d.get("type", ""),
            d.get("priority", ""),
            d.get("phase", ""),
            d.get("bundle", ""),
            d.get("price_fmt", ""),
            d.get("orig_fmt", ""),
            f"-{d['discount']}%" if d.get("discount", 0) > 0 else "",
            f"${low['price']:.0f}" if low else "",
            "Missing",
            d.get("notes", ""),
            STORE_URL.format(appid=appid),
        ])
    return buf.getvalue()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(line_buffering=True)
    print(f"{C.BOLD}=== PAYDAY 2 DLC Tracker ==={C.RST}\n")

    cfg = get_config()
    KEY = cfg["key"]
    VANITY = cfg["vanity"]
    ITAD_KEY = cfg["itad_key"]
    OUTPUT_DIR = cfg["output_dir"]
    NO_CACHE = cfg["no_cache"]
    t0 = time.monotonic()

    TOTAL = 9 + (1 if KEY else 0) + (1 if ITAD_KEY else 0) + (1 if cfg["csv"] else 0)
    _n = [0]
    def step(msg):
        _n[0] += 1
        print(f"\n{C.CYN}[{_n[0]}/{TOTAL}]{C.RST} {_bold(msg)}", flush=True)

    if not KEY:
        print(f"  {_dim('Sin API Key — ownership desde caché/base curada')}")

    # [1] Steam ID
    step("Resolviendo Steam ID...")
    steam_id = resolve_steam_id(KEY, VANITY)
    print(f"  {_ok(steam_id)}")

    # [2] DLC list
    step("Obteniendo lista de DLCs de PAYDAY 2...")
    pd2_dlc_appids = fetch_pd2_dlc_list(NO_CACHE)
    print(f"  {_ok(f'{len(pd2_dlc_appids)} DLCs encontrados')}")

    # Fetch/load DLC names + match to database
    mapping_cache, _ = _load_cache(DLC_MAPPING_CACHE)
    cached_names = mapping_cache.get("names", {})
    if NO_CACHE:
        cached_names = {}
    dlc_names = fetch_dlc_names(pd2_dlc_appids, cached_names)
    _save_cache(DLC_MAPPING_CACHE, {"names": dlc_names})
    db_mapping = match_dlc_names_to_db(dlc_names)
    matched = len(db_mapping)
    print(f"  {_ok(f'{matched}/{len(DLC_DB)} DLCs de la base curada identificados')}")
    if matched < len(DLC_DB):
        unmatched = set(DLC_DB.keys()) - {d["db_name"] for d in db_mapping.values()}
        for name in sorted(unmatched):
            print(f"  {_warn(f'No encontrado: {name}')}")

    # [3] Ownership
    if KEY:
        step("Verificando DLCs poseídos...")
        all_owned = get_owned_games(KEY, steam_id)
        pd2_owned = {a for a in pd2_dlc_appids if a in all_owned}
        # Merge with manual overrides
        prev_owned = load_owned(steam_id)
        pd2_owned |= prev_owned
    else:
        pd2_owned = load_owned(steam_id)

    # Apply CLI overrides
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
    total_cost = sum(prices.get(a, {}).get("price_raw", 0) for a in missing_appids) / 100
    print(f"  {_ok(f'{len(prices)} precios · {on_sale} en oferta · Total: Mex$ {total_cost:,.0f}')}")

    # [5] Active sale
    step("Detectando oferta activa de Steam...")
    sale_name = get_active_sale()
    if sale_name:
        print(f"  {_ok(f'🏷️  {sale_name}')}")
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

    # [8] Recommendations + phase costs
    step("Calculando recomendaciones...")
    # Merge all DLC data
    all_dlcs = {}
    for appid in pd2_dlc_appids:
        d = {}
        if appid in db_mapping:
            d = dict(db_mapping[appid])
        if appid in prices:
            d.update(prices[appid])
        if appid in dlc_names:
            d.setdefault("steam_name", dlc_names[appid])
        d.setdefault("appid", appid)
        all_dlcs[appid] = d

    missing_list = [all_dlcs[a] for a in missing_appids if a in all_dlcs]
    recommendations = compute_recommendations(missing_list, cfg["budget"], cfg["alert_price"])
    phase_costs = compute_phase_costs(missing_list)

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
            print(f"  {_ok('vs ' + comparison.get('prev_date', '?') + ': ' + ' · '.join(parts))}")

    save_run(owned_count, missing_count, prices, on_sale)

    # [9] Generate MD
    step("Generando Markdown...")
    md = generate_md(
        all_dlcs=all_dlcs,
        owned_appids=pd2_owned,
        pd2_dlc_appids=pd2_dlc_appids,
        prices=prices,
        sale_name=sale_name,
        recommendations=recommendations,
        phase_costs=phase_costs,
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

    # [10] Generate HTML
    step("Generando HTML interactivo...")
    html = generate_html(
        all_dlcs=all_dlcs,
        owned_appids=pd2_owned,
        pd2_dlc_appids=pd2_dlc_appids,
        prices=prices,
        sale_name=sale_name,
        recommendations=recommendations,
        phase_costs=phase_costs,
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
        csv_content = generate_csv(all_dlcs, pd2_owned, pd2_dlc_appids, prices, itad_lows)
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
