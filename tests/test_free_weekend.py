from __future__ import annotations

import unittest
from datetime import datetime, timezone

from steam_deals_free_weekend import (
    build_free_weekend_candidates,
    enrich_free_weekend_cross_signals,
)


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

    def test_enrich_free_weekend_cross_signals_adds_advisory_local_context(self) -> None:
        payload = {
            "generated_at": "2026-05-19T12:00:00Z",
            "source_policy": "fixture_or_cached_store_signals_v1",
            "summary": {"count": 2, "confidence_counts": {"medium": 2}},
            "items": [
                {"appid": "10", "title": "Wishlist Owned Candidate"},
                {"appid": "20", "title": "Family Taste Candidate"},
            ],
        }

        enriched = enrich_free_weekend_cross_signals(
            payload,
            wishlist_appids=["10"],
            owned={"10": "Wishlist Owned Candidate"},
            family_appids={"20"},
            personalized_recommendations={
                "items": [
                    {
                        "appid": "20",
                        "name": "Family Taste Candidate",
                        "affinity_score": 28.0,
                        "reasons": ["coincide con tu biblioteca: Co-op"],
                    }
                ]
            },
        )

        by_appid = {item["appid"]: item for item in enriched["items"]}
        self.assertEqual(payload["items"][0].get("cross_reasons"), None)
        self.assertEqual(
            by_appid["10"]["cross_signals"],
            {"in_wishlist": True, "owned_or_family": "owned", "similar_to_profile": False},
        )
        self.assertEqual(by_appid["10"]["cross_reasons"], ["en tu wishlist", "ya en biblioteca"])
        self.assertEqual(
            by_appid["20"]["cross_signals"],
            {"in_wishlist": False, "owned_or_family": "family", "similar_to_profile": True},
        )
        self.assertIn("disponible en biblioteca familiar", by_appid["20"]["cross_reasons"])
        self.assertIn("similar a tus gustos: coincide con tu biblioteca: Co-op", by_appid["20"]["cross_reasons"])

    def test_enrich_free_weekend_cross_signals_preserves_existing_payload_reasons(self) -> None:
        payload = {
            "generated_at": "2026-05-19T12:00:00Z",
            "source_policy": "fixture_or_cached_store_signals_v1",
            "summary": {"count": 1, "confidence_counts": {"high": 1}},
            "items": [
                {
                    "appid": "10",
                    "title": "Existing Cross Signal Candidate",
                    "cross_signals": {
                        "in_wishlist": True,
                        "owned_or_family": None,
                        "similar_to_profile": True,
                    },
                    "cross_reasons": ["en tu wishlist", "similar a tus gustos: Co-op"],
                }
            ],
        }

        enriched = enrich_free_weekend_cross_signals(payload)
        item = enriched["items"][0]

        self.assertEqual(
            item["cross_signals"],
            {"in_wishlist": True, "owned_or_family": None, "similar_to_profile": True},
        )
        self.assertEqual(item["cross_reasons"], ["en tu wishlist", "similar a tus gustos: Co-op"])

    def test_enrich_free_weekend_cross_signals_is_advisory_and_preserves_order(self) -> None:
        payload = {
            "generated_at": "2026-05-19T12:00:00Z",
            "source_policy": "fixture_or_cached_store_signals_v1",
            "summary": {"count": 3, "confidence_counts": {"medium": 3}},
            "items": [
                {"appid": "30", "title": "Third", "score": 10, "rank": 3},
                {"appid": "10", "title": "First", "score": 90, "rank": 1},
                {"appid": "20", "title": "Second", "score": 50, "rank": 2},
            ],
        }

        enriched = enrich_free_weekend_cross_signals(
            payload,
            wishlist_appids=["10", "20"],
            owned={"20": "Second"},
            preference_relations={"30": ["perfil local: estrategia"]},
        )

        self.assertEqual([item["appid"] for item in enriched["items"]], ["30", "10", "20"])
        self.assertEqual([item.get("score") for item in enriched["items"]], [10, 90, 50])
        self.assertEqual([item.get("rank") for item in enriched["items"]], [3, 1, 2])
        self.assertEqual(enriched["summary"], payload["summary"])
        self.assertEqual(payload["items"][0].get("cross_signals"), None)
        self.assertEqual(
            enriched["items"][0]["cross_reasons"],
            ["similar a tus gustos: perfil local: estrategia"],
        )

    def test_enrich_free_weekend_cross_signals_handles_invalid_payloads_without_noise(self) -> None:
        self.assertIsNone(enrich_free_weekend_cross_signals(None, wishlist_appids=["10"]))
        self.assertEqual(enrich_free_weekend_cross_signals([], wishlist_appids=["10"]), [])
        self.assertEqual(
            enrich_free_weekend_cross_signals({"items": [None, "bad"]}, wishlist_appids=["10"]),
            {"items": []},
        )


if __name__ == "__main__":
    unittest.main()
