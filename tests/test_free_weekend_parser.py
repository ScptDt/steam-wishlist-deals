from __future__ import annotations

import json
import unittest
from pathlib import Path

from steam_deals_free_weekend import (
    build_free_weekend_candidate_items,
    build_free_weekend_candidates,
    classify_free_weekend_candidate,
    extract_featured_category_items,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "free_weekend"
OBSERVED_AT = "2026-01-02T12:00:00Z"
CURRENT_TIMESTAMP = 1767312000


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class FreeWeekendParserTests(unittest.TestCase):
    def test_build_free_weekend_candidates_classifies_fixture_signals(self) -> None:
        payload = build_free_weekend_candidates(
            load_fixture("featuredcategories.json"),
            load_fixture("appdetails.json"),
            observed_at=OBSERVED_AT,
            current_timestamp=CURRENT_TIMESTAMP,
        )

        candidates = payload["items"]
        by_appid = {candidate["appid"]: candidate for candidate in candidates}
        self.assertEqual(payload["source_policy"], "fixture_or_cached_store_signals_v1")
        self.assertEqual(payload["summary"], {"count": 2, "confidence_counts": {"medium": 1, "high": 1}})
        self.assertEqual(set(by_appid), {"1001", "1002"})
        self.assertEqual(by_appid["1001"]["confidence"], "medium")
        self.assertEqual(by_appid["1001"]["sources"], ["featuredcategories", "appdetails"])
        self.assertEqual(by_appid["1001"]["signals"]["discount_percent"], 100)
        self.assertEqual(by_appid["1001"]["signals"]["final_price"], 0)
        self.assertEqual(by_appid["1001"]["signals"]["original_price"], 1999)
        self.assertEqual(by_appid["1001"]["signals"]["package_ids"], ["5001"])
        self.assertTrue(by_appid["1001"]["valid_until"].endswith("Z"))

        self.assertEqual(by_appid["1002"]["confidence"], "high")
        self.assertIn("Free Weekend", by_appid["1002"]["signals"]["matched_text"])
        self.assertEqual(by_appid["1002"]["signals"]["package_ids"], ["5002"])
        self.assertIn("Explicit Free Weekend", by_appid["1002"]["reason"])

    def test_build_free_weekend_candidates_excludes_false_positives(self) -> None:
        candidates = build_free_weekend_candidate_items(
            load_fixture("featuredcategories.json"),
            load_fixture("appdetails.json"),
            observed_at=OBSERVED_AT,
            current_timestamp=CURRENT_TIMESTAMP,
        )

        appids = {candidate["appid"] for candidate in candidates}
        self.assertNotIn("1003", appids)
        self.assertNotIn("1004", appids)
        self.assertNotIn("1005", appids)
        self.assertNotIn("1006", appids)

    def test_extract_featured_category_items_ignores_malformed_non_item_data(self) -> None:
        payload = load_fixture("featuredcategories.json")

        items = extract_featured_category_items(payload)

        self.assertGreaterEqual(len(items), 6)
        self.assertTrue(any(item.get("name") == "Malformed Store Item" for item in items))

    def test_classify_free_weekend_candidate_rejects_expired_and_malformed_items(self) -> None:
        appdetails = {
            "success": True,
            "data": {
                "name": "Expired Free Weekend",
                "type": "game",
                "is_free": False,
                "price_overview": {
                    "discount_percent": 100,
                    "final": 0,
                    "initial": 1999,
                    "discount_expiration": 1767225600,
                },
            },
        }

        expired = classify_free_weekend_candidate(
            {
                "id": 2001,
                "name": "Free Weekend - Expired Game",
                "discount_percent": 100,
                "final_price": 0,
                "original_price": 1999,
                "discount_expiration": 1767225600,
            },
            appdetails,
            observed_at=OBSERVED_AT,
            current_timestamp=CURRENT_TIMESTAMP,
        )
        malformed = classify_free_weekend_candidate(
            {"name": "Missing AppID", "discount_percent": 100, "final_price": 0},
            appdetails,
            observed_at=OBSERVED_AT,
            current_timestamp=CURRENT_TIMESTAMP,
        )

        self.assertIsNone(expired)
        self.assertIsNone(malformed)


if __name__ == "__main__":
    unittest.main()
