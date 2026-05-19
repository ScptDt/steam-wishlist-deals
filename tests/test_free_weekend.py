from __future__ import annotations

import unittest
from datetime import datetime, timezone

from steam_deals_free_weekend import build_free_weekend_candidates


OBSERVED_AT = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
FUTURE_EXPIRATION = 1_800_000_000
PAST_EXPIRATION = 1_700_000_000


def featured_item(appid: int, name: str, **overrides) -> dict:
    item = {
        "id": appid,
        "name": name,
        "discount_percent": 100,
        "final_price": 0,
        "original_price": 1999,
        "discount_expiration": FUTURE_EXPIRATION,
    }
    item.update(overrides)
    return item


def appdetails_entry(appid: int, name: str, **overrides) -> tuple[str, dict]:
    data = {
        "type": "game",
        "name": name,
        "is_free": False,
        "packages": [appid + 1000],
        "price_overview": {
            "initial": 1999,
            "final": 0,
            "discount_percent": 100,
            "discount_expiration": FUTURE_EXPIRATION,
        },
    }
    data.update(overrides)
    return str(appid), {"success": True, "data": data}


class FreeWeekendCandidateTests(unittest.TestCase):
    def test_build_free_weekend_candidates_marks_medium_from_free_price_with_expiration(self) -> None:
        featuredcategories = {"specials": {"items": [featured_item(10, "Paid Co-op")]}}
        appid, details = appdetails_entry(10, "Paid Co-op")

        payload = build_free_weekend_candidates(
            featuredcategories,
            {appid: details},
            observed_at=OBSERVED_AT,
            now=OBSERVED_AT,
        )

        self.assertEqual(payload["source_policy"], "fixture_or_cached_store_signals_v1")
        self.assertEqual(payload["summary"], {"count": 1, "confidence_counts": {"medium": 1}})
        item = payload["items"][0]
        self.assertEqual(item["appid"], "10")
        self.assertEqual(item["confidence"], "medium")
        self.assertEqual(item["sources"], ["featuredcategories", "appdetails"])
        self.assertEqual(item["signals"]["discount_percent"], 100)
        self.assertEqual(item["signals"]["final_price"], 0)
        self.assertIn("valid_until", item)
        self.assertEqual(item["store_url"], "https://store.steampowered.com/app/10/")

    def test_build_free_weekend_candidates_marks_high_when_text_is_correlated_with_store_signals(self) -> None:
        featuredcategories = {
            "specials": {
                "items": [
                    featured_item(
                        20,
                        "Free Weekend - Tactical Co-op",
                        header="Play for free this weekend",
                    )
                ]
            }
        }
        appid, details = appdetails_entry(
            20,
            "Tactical Co-op",
            short_description="Free Weekend event is live now.",
        )

        payload = build_free_weekend_candidates(
            featuredcategories,
            {appid: details},
            observed_at=OBSERVED_AT,
            now=OBSERVED_AT,
        )

        item = payload["items"][0]
        self.assertEqual(item["confidence"], "high")
        self.assertIn("Free Weekend", item["signals"]["matched_text"])
        self.assertEqual(item["signals"]["package_ids"], ["1020"])

    def test_build_free_weekend_candidates_excludes_false_positive_shapes(self) -> None:
        featuredcategories = {
            "specials": {
                "items": [
                    featured_item(30, "Permanent F2P", original_price=0),
                    featured_item(40, "Action Demo"),
                    featured_item(50, "Free to Keep Giveaway", title="Free to keep forever"),
                    featured_item(60, "Expired Trial", discount_expiration=PAST_EXPIRATION),
                    featured_item(70, "Valid Weekend Candidate"),
                ]
            }
        }
        details = dict(
            [
                appdetails_entry(30, "Permanent F2P", is_free=True, price_overview={}),
                appdetails_entry(40, "Action Demo", type="demo"),
                appdetails_entry(50, "Free to Keep Giveaway"),
                appdetails_entry(60, "Expired Trial"),
                appdetails_entry(70, "Valid Weekend Candidate"),
            ]
        )

        payload = build_free_weekend_candidates(
            featuredcategories,
            details,
            observed_at=OBSERVED_AT,
            now=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual([item["appid"] for item in payload["items"]], ["70"])

    def test_build_free_weekend_candidates_dedupes_feature_records(self) -> None:
        featuredcategories = {
            "specials": {
                "items": [
                    featured_item(80, "Duplicate Candidate", discount_percent=50, final_price=999),
                    featured_item(80, "Duplicate Candidate", discount_percent=100, final_price=0),
                ]
            }
        }
        appid, details = appdetails_entry(80, "Duplicate Candidate")

        payload = build_free_weekend_candidates(
            featuredcategories,
            {appid: details},
            observed_at=OBSERVED_AT,
            now=OBSERVED_AT,
        )

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["appid"], "80")
        self.assertEqual(payload["items"][0]["signals"]["discount_percent"], 100)


if __name__ == "__main__":
    unittest.main()
