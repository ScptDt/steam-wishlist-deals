from __future__ import annotations

from typing import Any, Iterable


STEAM_TAG_ALIASES = {
    "clicker": "Incremental",
    "conversation": "Dialogue Heavy",
    "jet": "Flight",
    "pool": "Billiards",
    "unforgiving": "Difficult",
    "dog": "Dogs",
    "fox": "Foxes",
    "vampire": "Vampires",
    "elf": "Elves",
    "dwarf": "Dwarves",
    "assassin": "Assassins",
}

REMOVED_STEAM_TAGS = {
    "3d vision",
    "ambient",
    "america",
    "blood",
    "crowdfunded",
    "cult classic",
    "documentary",
    "drama",
    "dungeons & dragons",
    "electronic",
    "experience",
    "feature film",
    "foreign",
    "gamemaker",
    "games workshop",
    "illuminati",
    "kickstarter",
    "lego",
    "masterpiece",
    "mature",
    "movie",
    "narration",
    "nsfw",
    "roguevania",
    "rpgmaker",
    "warhammer 40k",
    "web publishing",
    "well written",
}


def steam_tag_key(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
    return " ".join(normalized.split())


def normalize_steam_tag_label(tag: Any) -> str:
    text = str(tag or "").strip()
    if not text:
        return ""
    return STEAM_TAG_ALIASES.get(steam_tag_key(text), text)


def canonical_steam_tag_key(tag: Any) -> str:
    return steam_tag_key(normalize_steam_tag_label(tag))


def is_removed_steam_tag(tag: Any) -> bool:
    return steam_tag_key(tag) in REMOVED_STEAM_TAGS


def normalize_steam_tag_terms(terms: Iterable[Any]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if is_removed_steam_tag(term):
            continue
        label = normalize_steam_tag_label(term)
        key = canonical_steam_tag_key(label)
        if label and key not in seen:
            seen.add(key)
            normalized.append(label)
    return normalized


def _tag_weight(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def normalize_steam_tag_weights(tags: dict[Any, Any]) -> dict[str, Any]:
    if not isinstance(tags, dict):
        return {}
    merged: dict[str, tuple[str, Any]] = {}
    for raw_label, weight in tags.items():
        if is_removed_steam_tag(raw_label):
            continue
        label = normalize_steam_tag_label(raw_label)
        key = canonical_steam_tag_key(label)
        if not label or not key:
            continue
        current = merged.get(key)
        if current is None or _tag_weight(weight) > _tag_weight(current[1]):
            merged[key] = (label, weight)
    return {label: weight for label, weight in merged.values()}
