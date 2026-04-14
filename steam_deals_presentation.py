from __future__ import annotations


DECK_LABELS = {3: "✅ Verified", 2: "🟡 Playable", 1: "❌ Unsupported"}

PROTONDB_TIERS = {
    "native": "🐧 Native",
    "platinum": "💎 Platinum",
    "gold": "🥇 Gold",
    "silver": "🥈 Silver",
    "bronze": "🥉 Bronze",
    "borked": "💔 Borked",
}

ANTICHEAT_WARN = {"Denied", "Broken"}

GENERIC_TAGS = {
    "singleplayer", "multiplayer", "action", "indie", "adventure",
    "free to play", "early access", "2d", "3d", "casual", "simulation",
    "strategy", "rpg", "fps", "puzzle", "platformer",
}


def deck_badge(category: int) -> str:
    return DECK_LABELS.get(category, "")


def protondb_badge(tier: str) -> str:
    return PROTONDB_TIERS.get(tier, "")


def linux_badge(
    deck_cat: int,
    protondb: dict | None,
    anticheat: dict | None,
    linux_native: bool = False,
    *,
    deck_badge_fn=deck_badge,
    protondb_badge_fn=protondb_badge,
) -> str:
    parts = []
    if linux_native:
        parts.append("🐧 Native")
    deck_text = deck_badge_fn(deck_cat)
    if deck_text:
        parts.append(deck_text)
    if protondb:
        proton_text = protondb_badge_fn(protondb.get("tier", ""))
        if proton_text:
            parts.append(proton_text)
    if anticheat:
        status = anticheat.get("status", "")
        anticheat_names = ", ".join(anticheat.get("anticheats", []))
        if status in ANTICHEAT_WARN:
            parts.append(f"⛔ {anticheat_names} ({status})")
        elif status == "Supported" and anticheat_names:
            parts.append(f"✅ {anticheat_names}")
    return " · ".join(parts) if parts else "—"


def get_top_tags(tags_data: dict, appid: str, n: int = 3) -> list[str]:
    entry = tags_data.get(appid, {})
    app_tags = entry.get("tags", entry) if isinstance(entry, dict) else {}
    if not app_tags or not isinstance(app_tags, dict):
        return []
    sorted_tags = sorted(app_tags.items(), key=lambda item: -item[1])
    return [tag for tag, _ in sorted_tags if tag.lower() not in GENERIC_TAGS][:n]


def group_deals_by_tag(deals: list[dict], tags_data: dict, min_count: int = 3, *, get_top_tags_fn=get_top_tags) -> list[tuple[str, list[dict]]]:
    tag_to_deals: dict[str, list[dict]] = {}
    for deal in deals:
        for tag in get_top_tags_fn(tags_data, deal["appid"], n=5):
            tag_to_deals.setdefault(tag, []).append(deal)
    result = [(tag, grouped_deals) for tag, grouped_deals in tag_to_deals.items() if len(grouped_deals) >= min_count]
    result.sort(key=lambda item: -len(item[1]))
    return result[:10]


def _parse_owners(owners_str: str) -> tuple[int, int]:
    if not owners_str or ".." not in owners_str:
        return (0, 0)
    parts = owners_str.split("..")
    try:
        low = int(parts[0].strip().replace(",", ""))
        high = int(parts[1].strip().replace(",", ""))
        return (low, high)
    except (ValueError, IndexError):
        return (0, 0)


def _format_owner_count(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.0f}M"
    if count >= 1_000:
        return f"{count // 1_000}K"
    return str(count)


def players_badge(tags_entry: dict) -> str:
    players = tags_entry.get("players", {})
    owners = players.get("owners", "")
    _, high = _parse_owners(owners)
    if high == 0:
        return ""
    low, _ = _parse_owners(owners)
    return f"👥 {_format_owner_count(low)}-{_format_owner_count(high)}" if low else f"👥 <{_format_owner_count(high)}"


def achievements_badge(ach: dict | None) -> str:
    if not ach:
        return "—"
    return f"🏆 {ach['count']} ({ach['avg_completion']:.0f}%)"


def group_by_tier(games: list[dict]) -> list[tuple[str, list[dict]]]:
    tiers = [
        ("90%+", lambda discount: discount >= 90),
        ("80–89%", lambda discount: 80 <= discount < 90),
        ("70–79%", lambda discount: 70 <= discount < 80),
        ("60–69%", lambda discount: 60 <= discount < 70),
        ("50–59%", lambda discount: 50 <= discount < 60),
    ]
    return [(name, [game for game in games if predicate(game["discount"])]) for name, predicate in tiers]


def multiplayer_badges(categories: list[int]) -> str:
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
