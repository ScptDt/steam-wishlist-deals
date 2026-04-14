from __future__ import annotations

import json
from pathlib import Path


WATCHLIST_FILE = Path.home() / ".config" / "steam_deals_watchlist.json"


def load_watchlist(watchlist_file: Path = WATCHLIST_FILE) -> list[dict]:
    if not watchlist_file.exists():
        return []
    try:
        return json.loads(watchlist_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_watchlist(items: list[dict], watchlist_file: Path = WATCHLIST_FILE) -> None:
    watchlist_file.parent.mkdir(parents=True, exist_ok=True)
    watchlist_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add_watchlist_item(items: list[dict], appid: str, target_price: float, name: str) -> list[dict]:
    updated = [item for item in items if item["appid"] != appid]
    updated.append({"appid": appid, "name": name, "target_price": target_price})
    return updated


def remove_watchlist_item(items: list[dict], appid: str) -> tuple[list[dict], bool]:
    updated = [item for item in items if item["appid"] != appid]
    return updated, len(updated) < len(items)


def check_watchlist_alerts(deals: list[dict], watchlist: list[dict]) -> list[dict]:
    """Check which watchlist games have hit their target price."""
    deal_map = {deal["appid"]: deal for deal in deals}
    alerts = []
    for item in watchlist:
        deal = deal_map.get(item["appid"])
        if deal and deal.get("price_raw", 0) / 100 <= item["target_price"]:
            alerts.append({**deal, "target_price": item["target_price"]})
    return alerts


def handle_watchlist_command(
    args: list[str],
    *,
    watchlist_file: Path = WATCHLIST_FILE,
    resolve_name=None,
    emit=print,
    ok=None,
    warn=None,
    err=None,
    dim=None,
    bold=None,
) -> bool:
    """Handle --watchlist subcommands. Returns True if handled (should exit)."""
    ok = ok or (lambda text: text)
    warn = warn or (lambda text: text)
    err = err or (lambda text: text)
    dim = dim or (lambda text: text)
    bold = bold or (lambda text: text)
    resolve_name = resolve_name or (lambda appid: appid)

    if not args:
        args = ["list"]
    cmd = args[0].lower()
    items = load_watchlist(watchlist_file)

    if cmd == "list":
        if not items:
            emit(f"  {dim('Watchlist vacía. Usa --watchlist add APPID PRECIO para agregar.')}")
        else:
            emit(f"\n  {bold('Watchlist Personal')} ({len(items)} juegos)\n")
            emit(f"  {'AppID':<10} {'Precio objetivo':>16}  Nombre")
            emit(f"  {'─' * 10} {'─' * 16}  {'─' * 30}")
            for item in items:
                emit(f"  {item['appid']:<10} ${item['target_price']:>14,.0f}  {item.get('name', '?')}")
        return True

    if cmd == "add":
        if len(args) < 3:
            emit(f"  {err('Uso: --watchlist add APPID PRECIO')}")
            return True
        appid = args[1]
        try:
            target = float(args[2])
        except ValueError:
            emit(f"  {err(f'Precio inválido: {args[2]}')}")
            return True
        items = add_watchlist_item(items, appid, target, resolve_name(appid))
        save_watchlist(items, watchlist_file)
        game_name = items[-1]["name"]
        emit(f"  {ok(f'Agregado: {game_name} (AppID {appid}) — objetivo ${target:.0f} MXN')}")
        return True

    if cmd == "remove":
        if len(args) < 2:
            emit(f"  {err('Uso: --watchlist remove APPID')}")
            return True
        appid = args[1]
        updated, removed = remove_watchlist_item(items, appid)
        if removed:
            save_watchlist(updated, watchlist_file)
            emit(f"  {ok(f'Removido AppID {appid} de la watchlist')}")
        else:
            emit(f"  {warn(f'AppID {appid} no está en la watchlist')}")
        return True

    emit(f"  {err(f'Subcomando desconocido: {cmd}. Usa: add, remove, list')}")
    return True
