from __future__ import annotations

import csv
import re
from difflib import SequenceMatcher
from pathlib import Path


EDITION_WORDS = {
    "definitive",
    "remastered",
    "complete",
    "deluxe",
    "hd",
    "edition",
    "goty",
    "collection",
    "director",
    "cut",
    "enhanced",
    "anniversary",
    "intergrade",
    "gold",
    "platinum",
    "ultimate",
}
ROMAN = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
    "xi": "11",
    "xii": "12",
    "xiii": "13",
    "xiv": "14",
    "xv": "15",
}
STOP_WORDS = {"the", "a", "an", "of", "in", "and", "or", "to", "is", "it", "at", "on", "for"}
HLTB_STATUSES = ("backlog", "completed", "playing", "retired")


def _parse_hltb_hours(value: str) -> float | None:
    if not value or value.strip() == "--":
        return None
    parts = value.strip().split(":")
    try:
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        seconds = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        return None
    return hours + minutes / 60 + seconds / 3600


def _empty_hltb_groups() -> dict[str, list[dict]]:
    return {status: [] for status in HLTB_STATUSES}


def _hltb_entry(row: dict) -> dict:
    hours = _parse_hltb_hours(row.get("Main + Extras", ""))
    if hours is None:
        hours = _parse_hltb_hours(row.get("Main Story", ""))
    return {
        "title": row["Title"].strip(),
        "storefront": row.get("Storefront", "").strip(),
        "hours": hours,
    }


def _row_status(row: dict) -> str | None:
    if row.get("Backlog", "").strip() == "X":
        return "backlog"
    if row.get("Completed", "").strip() == "X":
        return "completed"
    if row.get("Playing", "").strip() == "X":
        return "playing"
    if row.get("Retired", "").strip() == "X":
        return "retired"
    return None


def parse_hltb(csv_path: Path) -> dict[str, list[dict]]:
    result = _empty_hltb_groups()
    with open(csv_path, encoding="utf-8") as file_handle:
        for row in csv.DictReader(file_handle):
            status = _row_status(row)
            if status is None:
                continue
            result[status].append(_hltb_entry(row))
    return result


def normalize(text: str) -> str:
    cleaned = re.sub(r"[®™©]", "", text.lower())
    cleaned = re.sub(r"[^a-z0-9 ]", " ", cleaned)
    words = re.sub(r"\s+", " ", cleaned).strip().split()
    return " ".join(ROMAN.get(word, word) for word in words)


def extract_numbers(text: str) -> set[str]:
    return set(re.findall(r"\b\d+\b", normalize(text)))


def significant_words(text: str) -> set[str]:
    return set(normalize(text).split()) - STOP_WORDS


def is_same_game(left: str, right: str) -> bool:
    left_numbers = extract_numbers(left)
    right_numbers = extract_numbers(right)
    if left_numbers and right_numbers and left_numbers != right_numbers:
        return False
    if bool(left_numbers) != bool(right_numbers):
        return False
    left_words = significant_words(left)
    right_words = significant_words(right)
    only_left = (left_words - right_words) - EDITION_WORDS
    only_right = (right_words - left_words) - EDITION_WORDS
    if only_left and only_right:
        return False
    shared = left_words & right_words
    if not shared:
        return False
    shorter = left_words if len(left_words) <= len(right_words) else right_words
    return len(shared) / len(shorter) >= 0.7


def find_best_match(hltb_title: str, deals: list[dict], threshold: float = 0.75):
    normalized_title = normalize(hltb_title)
    best_score = 0.0
    best_deal = None
    for deal in deals:
        if deal.get("type", "game") != "game":
            continue
        score = SequenceMatcher(None, normalized_title, normalize(deal["name"])).ratio()
        if score > best_score:
            best_score = score
            best_deal = deal
    if best_score >= threshold and best_deal and is_same_game(hltb_title, best_deal["name"]):
        return best_score, best_deal
    return 0.0, None


def _price_per_hour(hours: float | None, price_raw: int) -> float | None:
    if hours and hours > 0 and price_raw > 0:
        return (price_raw / 100) / hours
    return None


def _crossed_entry(status: str, game: dict, deal: dict, score: float, family_appids: set[str]) -> dict:
    return {
        "appid": deal["appid"],
        "hltb_title": game["title"],
        "steam_name": deal["name"],
        "storefront": game["storefront"],
        "discount": deal["discount"],
        "price": deal["price_final"],
        "price_original": deal["price_original"],
        "score": round(score, 2),
        "status": status,
        "in_family": deal["appid"] in family_appids,
        "hours": game.get("hours"),
        "price_per_hour": _price_per_hour(game.get("hours"), deal.get("price_raw", 0)),
    }


def cross_hltb_with_deals(
    hltb: dict[str, list[dict]],
    deals: list[dict],
    threshold: float = 0.75,
    family_appids: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    used_names = set()
    backlog_on_sale = []
    have_on_sale = []
    family_appids = family_appids or set()

    for status in HLTB_STATUSES:
        for game in hltb[status]:
            score, deal = find_best_match(game["title"], deals, threshold=threshold)
            if not deal or deal["name"] in used_names:
                continue
            entry = _crossed_entry(status, game, deal, score, family_appids)
            if status == "backlog":
                backlog_on_sale.append(entry)
            else:
                have_on_sale.append(entry)
            used_names.add(deal["name"])

    backlog_on_sale.sort(key=lambda deal: -deal["discount"])
    have_on_sale.sort(key=lambda deal: -deal["discount"])
    return backlog_on_sale, have_on_sale
