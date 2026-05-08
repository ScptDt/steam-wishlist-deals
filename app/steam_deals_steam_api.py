from __future__ import annotations

import json
import re
import urllib.error
from pathlib import Path


PROFILE_ID_RE = re.compile(r"https?://steamcommunity\.com/profiles/(\d+)")
PROFILE_VANITY_RE = re.compile(r"https?://steamcommunity\.com/id/([^/]+)")
STEAM_ID64_RE = re.compile(r"<steamID64>(\d+)</steamID64>")
STEAM_ID_RE = re.compile(r"<steamID><!\[CDATA\[(.*?)\]\]></steamID>")
PROMO_PRIMARY_TYPES = (1, 11)
MAJOR_SALE_KEYWORDS = ("summer sale", "winter sale", "autumn sale", "spring sale")
PUBLISHER_FRANCHISE_KEYWORDS = ("publisher", "franchise")


def _normalized_vanity(vanity: str) -> str:
    profile_match = PROFILE_VANITY_RE.match(vanity)
    if profile_match:
        return profile_match.group(1)
    return vanity


def _public_profile_error(vanity: str) -> ValueError:
    return ValueError(
        f"No se pudo resolver el perfil: {vanity}. "
        "Usa tu SteamID de 17 dígitos o una URL pública válida."
    )


def resolve_steam_id(
    api_key: str | None,
    vanity: str,
    *,
    get_json,
    fetch_public_profile_xml,
) -> str:
    """Convierte vanity URL, link de perfil, o Steam ID numérico a Steam ID."""
    profile_match = PROFILE_ID_RE.match(vanity)
    if profile_match:
        return profile_match.group(1)

    vanity = _normalized_vanity(vanity)
    if vanity.isdigit() and len(vanity) == 17:
        return vanity

    if api_key:
        url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={api_key}&vanityurl={vanity}"
        try:
            data = get_json(url)
            if data["response"]["success"] != 1:
                raise ValueError(f"No se pudo resolver el vanity URL: {vanity}")
            return data["response"]["steamid"]
        except urllib.error.HTTPError as exc:
            if exc.code not in (401, 403):
                raise

    try:
        text = fetch_public_profile_xml(vanity)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError(
                f"Steam rechazó el perfil público (HTTP {exc.code}). "
                "Revisa que el perfil sea público, usa tu SteamID de 17 dígitos o regenera/borra la API key."
            ) from exc
        raise
    steam_id_match = STEAM_ID64_RE.search(text)
    if not steam_id_match:
        raise _public_profile_error(vanity)
    return steam_id_match.group(1)


def resolve_profile_display_name(
    steam_id: str,
    vanity_input: str,
    *,
    api_key: str | None,
    get_json,
    fetch_public_profile_xml,
) -> str:
    """Resuelve nombre visible del perfil Steam con fallback seguro."""

    if api_key:
        try:
            url = (
                "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
                f"?key={api_key}&steamids={steam_id}"
            )
            data = get_json(url)
            players = data.get("response", {}).get("players", [])
            if players:
                name = str(players[0].get("personaname", "")).strip()
                if name:
                    return name
        except Exception:
            pass

    fallback_source = vanity_input
    profile_match = PROFILE_ID_RE.match(vanity_input)
    if profile_match:
        fallback_source = profile_match.group(1)
    else:
        fallback_source = _normalized_vanity(vanity_input)

    try:
        text = fetch_public_profile_xml(fallback_source)
        steam_id_match = STEAM_ID_RE.search(text)
        if steam_id_match:
            name = steam_id_match.group(1).strip()
            if name:
                return name
    except Exception:
        pass

    return fallback_source


def get_wishlist(
    api_key: str | None, steam_id: str, *, get_json
) -> tuple[list[str], dict[str, int]]:
    """Devuelve (lista de appids, dict appid→priority). Funciona con o sin API key."""
    url = f"https://api.steampowered.com/IWishlistService/GetWishlist/v1/?steamid={steam_id}"
    if api_key:
        url += f"&key={api_key}"
    try:
        data = get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError(
                f"No se pudo acceder a la wishlist (HTTP {exc.code}). ¿Es privada?"
            ) from exc
        raise
    items = data.get("response", {}).get("items", [])
    appids = [str(item["appid"]) for item in items]
    priorities = {str(item["appid"]): item.get("priority", 0) for item in items}
    return appids, priorities


def _owned_games_url(api_key: str, steam_id: str) -> str:
    return (
        f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        f"?key={api_key}&steamid={steam_id}&include_appinfo=1&include_played_free_games=1"
    )


def owned_game_records_from_payload(data: dict) -> list[dict]:
    records: list[dict] = []
    for game in data.get("response", {}).get("games", []):
        appid = str(game.get("appid") or "").strip()
        if not appid:
            continue
        record = {
            "appid": appid,
            "name": str(game.get("name") or "").strip(),
        }
        for key in ("playtime_forever", "playtime_2weeks"):
            if game.get(key) is not None:
                record[key] = game.get(key)
        records.append(record)
    return records


def owned_games_from_records(records: list[dict]) -> dict[str, str]:
    return {
        str(record["appid"]): str(record.get("name") or "")
        for record in records
        if str(record.get("appid") or "").strip()
    }


def get_owned_game_records(api_key: str, steam_id: str, *, get_json) -> list[dict]:
    """Devuelve registros propios preservando metadata local de actividad."""
    url = _owned_games_url(api_key, steam_id)
    try:
        data = get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError(
                f"Steam rechazó la API key al obtener tu biblioteca (HTTP {exc.code}). "
                "El reporte puede continuar sin marcar juegos ya comprados; revisa/regenera la API key si quieres esa señal."
            ) from exc
        raise
    return owned_game_records_from_payload(data)


def get_owned_games_with_records(api_key: str, steam_id: str, *, get_json) -> tuple[dict[str, str], list[dict]]:
    """Devuelve mapa compatible y registros ricos desde una sola respuesta."""
    records = get_owned_game_records(api_key, steam_id, get_json=get_json)
    return owned_games_from_records(records), records


def get_owned_games(api_key: str, steam_id: str, *, get_json) -> dict[str, str]:
    """Devuelve dict appid → nombre de juegos propios en Steam."""
    owned, _records = get_owned_games_with_records(api_key, steam_id, get_json=get_json)
    return owned


def compare_wishlists(
    api_key,
    steam_id_1,
    vanity_2,
    *,
    resolve_steam_id_fn,
    get_wishlist_fn,
    resolve_profile_display_name_fn=None,
):
    """Compare two wishlists. Returns overlap, unique to each, friend info."""
    _ = steam_id_1
    friend_id = resolve_steam_id_fn(api_key, vanity_2)
    friend_appids, friend_priorities = get_wishlist_fn(api_key, friend_id)
    friend_set = set(friend_appids)
    friend_name = vanity_2
    if resolve_profile_display_name_fn is not None:
        try:
            resolved_name = resolve_profile_display_name_fn(friend_id, vanity_2, api_key)
            if resolved_name:
                friend_name = str(resolved_name)
        except Exception:
            pass
    return {
        "friend_id": friend_id,
        "friend_vanity": vanity_2,
        "friend_name": friend_name,
        "friend_appids": friend_appids,
        "friend_priorities": friend_priorities,
        "friend_set": friend_set,
    }


def load_family_games(json_path: Path) -> set[str]:
    """Carga un JSON de biblioteca familiar → set de appids."""
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return {str(key) for key in raw}
    if isinstance(raw, list):
        return {str(appid) for appid in raw}
    raise ValueError(f"Formato de family JSON no reconocido: {type(raw)}")


def _promo_title(message: dict) -> str:
    return str(message.get("title", "") or "").strip()


def classify_steam_promo_message(message: dict) -> dict:
    """Classify one Steam marketing message into a stable promo category."""
    title = _promo_title(message)
    lower_title = title.lower()
    category = "unknown"
    if "weeklong" in lower_title:
        category = "weeklong"
    elif "midweek" in lower_title or "mid-week" in lower_title:
        category = "midweek"
    elif "weekend" in lower_title:
        category = "weekend"
    elif any(keyword in lower_title for keyword in MAJOR_SALE_KEYWORDS):
        category = "major_sale"
    elif "fest" in lower_title or "festival" in lower_title:
        category = "fest"
    elif any(keyword in lower_title for keyword in PUBLISHER_FRANCHISE_KEYWORDS):
        category = "publisher_sale"
    elif "now available" in lower_title or "launch" in lower_title:
        category = "launch"
    elif any(
        keyword in lower_title
        for keyword in ("sale", "deals", "deal", "specials", "discount")
    ):
        category = "themed"

    message_type = message.get("type")
    return {
        "title": title,
        "type": message_type,
        "category": category,
        "is_primary_type": message_type in PROMO_PRIMARY_TYPES,
    }


PROMO_CATEGORY_LABELS = {
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


PROMO_CATEGORY_PRIORITY = {
    "major_sale": 10,
    "fest": 20,
    "publisher_sale": 30,
    "themed": 35,
    "weekend": 40,
    "midweek": 45,
    "launch": 50,
    "weeklong": 60,
    "unknown": 80,
}

PROMO_DECISION_HINTS = {
    "major_sale": (
        "Mega sale oficial: suele ser una de las mejores ventanas para revisar "
        "compras si el precio ya convence."
    ),
    "fest": (
        "Fest temático: oportunidad fuerte para juegos del tema; compara contra "
        "tu interés y mínimo histórico."
    ),
    "publisher_sale": (
        "Publisher/franquicia: más fuerte que promos rutinarias; revisar si el "
        "descuento supera tu referencia histórica."
    ),
    "themed": (
        "Promo temática: útil si coincide con tu wishlist, pero no necesariamente "
        "supera una mega sale."
    ),
    "weekend": (
        "Weekend deal: ventana corta; comprar solo si ya estaba en radar y el "
        "precio es bueno."
    ),
    "midweek": (
        "Midweek deal: promo puntual; revisar precio, pero no tratarla como "
        "evento grande."
    ),
    "launch": (
        "Lanzamiento/Now Available: contexto de un juego concreto; no debería "
        "pesar más que Fests o mega sales."
    ),
    "weeklong": (
        "Weeklong: promo rutinaria; mejor usarla como contexto, no como urgencia "
        "fuerte."
    ),
    "unknown": "Promo detectada sin categoría clara; usar solo como contexto local.",
}


def promo_category_label(category: str) -> str:
    key = str(category or "").strip()
    return PROMO_CATEGORY_LABELS.get(key, key or "Otra promo")


def _promo_priority(promo: dict) -> int:
    category = str(promo.get("category", "") or "").strip()
    return PROMO_CATEGORY_PRIORITY.get(category, PROMO_CATEGORY_PRIORITY["unknown"])


def _select_primary_promo(promos: list[dict]) -> dict | None:
    ranked = [promo for promo in promos if promo.get("title")]
    if not ranked:
        return None
    return min(
        enumerate(ranked),
        key=lambda item: (
            _promo_priority(item[1]),
            0 if item[1].get("is_primary_type") else 1,
            item[0],
        ),
    )[1]


def _extra_promo_titles(promos: list[dict], primary_title: str) -> list[str]:
    titles: list[str] = []
    for promo in promos:
        title = str(promo.get("title", "") or "").strip()
        if title and title != primary_title and title not in titles:
            titles.append(title)
    return titles


def _promo_display_label(primary_title: str, extra_titles: list[str]) -> str:
    if not primary_title:
        return ""
    if not extra_titles:
        return primary_title
    return f"{primary_title} + {len(extra_titles)} promos adicionales"


def _promo_decision_hint(primary: dict | None) -> str:
    if not isinstance(primary, dict):
        return ""
    category = str(primary.get("category", "") or "").strip() or "unknown"
    return PROMO_DECISION_HINTS.get(category, PROMO_DECISION_HINTS["unknown"])


def _promo_simultaneous_hint(primary_title: str, extra_titles: list[str]) -> str:
    if not primary_title or not extra_titles:
        return ""
    return (
        f"Se destaca {primary_title} por jerarquía de promo; "
        f"también hay {len(extra_titles)} promo(s) activa(s) de menor peso."
    )


def build_active_promo_context(messages: list[dict]) -> dict:
    promos = [
        classify_steam_promo_message(message)
        for message in messages
        if _promo_title(message)
    ]
    primary = _select_primary_promo(promos)
    categories = sorted(
        {promo["category"] for promo in promos if promo.get("category")},
        key=lambda category: PROMO_CATEGORY_PRIORITY.get(
            category, PROMO_CATEGORY_PRIORITY["unknown"]
        ),
    )
    primary_title = primary.get("title", "") if primary else ""
    extra_titles = _extra_promo_titles(promos, primary_title)
    return {
        "sale_name": primary_title,
        "primary": primary,
        "promos": promos,
        "categories": categories,
        "category_label": " · ".join(promo_category_label(category) for category in categories),
        "display_label": _promo_display_label(primary_title, extra_titles),
        "decision_hint": _promo_decision_hint(primary),
        "simultaneous_hint": _promo_simultaneous_hint(primary_title, extra_titles),
        "additional_promos_count": len(extra_titles),
    }


def get_active_promo_context(*, get_json) -> dict:
    """Return structured active Steam promo context from marketing messages."""
    try:
        data = get_json(
            "https://api.steampowered.com/IMarketingMessagesService/GetActiveMarketingMessages/v1/"
        )
        messages = data.get("response", {}).get("messages", [])
        return build_active_promo_context(messages if isinstance(messages, list) else [])
    except Exception:
        return build_active_promo_context([])


def get_active_sale(*, get_json) -> str:
    """Detecta la oferta/evento activo en Steam via marketing messages API."""
    return get_active_promo_context(get_json=get_json).get("sale_name", "")
