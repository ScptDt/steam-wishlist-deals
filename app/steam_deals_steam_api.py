from __future__ import annotations

import json
import re
import urllib.error
from pathlib import Path


PROFILE_ID_RE = re.compile(r"https?://steamcommunity\.com/profiles/(\d+)")
PROFILE_VANITY_RE = re.compile(r"https?://steamcommunity\.com/id/([^/]+)")
STEAM_ID64_RE = re.compile(r"<steamID64>(\d+)</steamID64>")


def _normalized_vanity(vanity: str) -> str:
    profile_match = PROFILE_VANITY_RE.match(vanity)
    if profile_match:
        return profile_match.group(1)
    return vanity


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
        data = get_json(url)
        if data["response"]["success"] != 1:
            raise ValueError(f"No se pudo resolver el vanity URL: {vanity}")
        return data["response"]["steamid"]

    text = fetch_public_profile_xml(vanity)
    steam_id_match = STEAM_ID64_RE.search(text)
    if not steam_id_match:
        raise ValueError(f"No se pudo resolver el perfil: {vanity}")
    return steam_id_match.group(1)


def get_wishlist(api_key: str | None, steam_id: str, *, get_json) -> tuple[list[str], dict[str, int]]:
    """Devuelve (lista de appids, dict appid→priority). Funciona con o sin API key."""
    url = f"https://api.steampowered.com/IWishlistService/GetWishlist/v1/?steamid={steam_id}"
    if api_key:
        url += f"&key={api_key}"
    try:
        data = get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError(f"No se pudo acceder a la wishlist (HTTP {exc.code}). ¿Es privada?") from exc
        raise
    items = data.get("response", {}).get("items", [])
    appids = [str(item["appid"]) for item in items]
    priorities = {str(item["appid"]): item.get("priority", 0) for item in items}
    return appids, priorities


def get_owned_games(api_key: str, steam_id: str, *, get_json) -> dict[str, str]:
    """Devuelve dict appid → nombre de juegos propios en Steam."""
    url = (
        f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        f"?key={api_key}&steamid={steam_id}&include_appinfo=1&include_played_free_games=1"
    )
    data = get_json(url)
    return {str(game["appid"]): game["name"] for game in data.get("response", {}).get("games", [])}


def compare_wishlists(
    api_key,
    steam_id_1,
    vanity_2,
    *,
    resolve_steam_id_fn,
    get_wishlist_fn,
):
    """Compare two wishlists. Returns overlap, unique to each, friend info."""
    _ = steam_id_1
    friend_id = resolve_steam_id_fn(api_key, vanity_2)
    friend_appids, friend_priorities = get_wishlist_fn(api_key, friend_id)
    friend_set = set(friend_appids)
    return {
        "friend_id": friend_id,
        "friend_vanity": vanity_2,
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


def get_active_sale(*, get_json) -> str:
    """Detecta la oferta/evento activo en Steam via marketing messages API."""
    try:
        data = get_json("https://api.steampowered.com/IMarketingMessagesService/GetActiveMarketingMessages/v1/")
        messages = data.get("response", {}).get("messages", [])
        for preferred_type in (1, 11):
            for message in messages:
                if message.get("type") != preferred_type:
                    continue
                title = message.get("title", "").strip()
                if title:
                    return title
        for message in messages:
            title = message.get("title", "").strip()
            if title:
                return title
    except Exception:
        pass
    return ""
