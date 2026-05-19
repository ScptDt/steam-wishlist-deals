from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from steam_deals_free_weekend import (
    build_free_weekend_candidates,
    enrich_free_weekend_cross_signals,
    filter_current_free_weekend_payload,
    fetch_free_weekend_store_payloads,
    resolve_free_weekend_now_payload,
    save_free_weekend_candidate_cache,
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

    def test_filter_current_free_weekend_payload_removes_expired_candidates(self) -> None:
        payload = {
            "generated_at": "2026-05-19T12:00:00Z",
            "source_policy": "fixture_or_cached_store_signals_v1",
            "items": [
                {"appid": "10", "title": "Expired", "valid_until": "2020-01-01T00:00:00Z"},
                {"appid": "20", "title": "Current", "valid_until": "2030-01-01T00:00:00Z"},
            ],
        }

        filtered = filter_current_free_weekend_payload(payload, now=OBSERVED_AT)

        self.assertEqual([item["appid"] for item in filtered["items"]], ["20"])
        self.assertEqual(filtered["summary"], {"count": 1, "confidence_counts": {"unknown": 1}})

    def test_resolve_free_weekend_now_payload_uses_fresh_cache_without_fetch(self) -> None:
        payload = build_free_weekend_candidates(
            {"specials": {"items": [featured_item(90, "Cached Candidate")]}},
            dict([appdetails_entry(90, "Cached Candidate")]),
            observed_at=OBSERVED_AT,
            now=OBSERVED_AT,
        )

        with TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "free_weekend_candidates.json"
            save_free_weekend_candidate_cache(cache_path, payload)

            resolved = resolve_free_weekend_now_payload(
                cache_path,
                live_enabled=True,
                now=OBSERVED_AT,
                fetch_json=lambda *_args, **_kwargs: self.fail("fresh cache should not fetch"),
            )

        self.assertEqual(resolved["items"][0]["appid"], "90")

    def test_resolve_free_weekend_now_payload_ignores_stale_cache_without_opt_in(self) -> None:
        stale_cache = {
            "saved_at": "2000-01-01T00:00:00",
            "free_weekend_now": {
                "generated_at": "2000-01-01T00:00:00Z",
                "source_policy": "fixture_or_cached_store_signals_v1",
                "items": [
                    {"appid": "10", "title": "Stale", "valid_until": "2030-01-01T00:00:00Z"}
                ],
            },
        }

        with TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "free_weekend_candidates.json"
            cache_path.write_text(json.dumps(stale_cache), encoding="utf-8")
            resolved = resolve_free_weekend_now_payload(
                cache_path,
                live_enabled=False,
                now=OBSERVED_AT,
                fetch_json=lambda *_args, **_kwargs: self.fail("non opt-in should not fetch"),
            )

        self.assertIsNone(resolved)

    def test_resolve_free_weekend_now_payload_live_opt_in_fetches_and_saves_cache(self) -> None:
        appid, details = appdetails_entry(100, "Live Candidate")
        calls = []

        def fake_fetch(url, **_kwargs):
            calls.append(url)
            if "featuredcategories" in url:
                return {"specials": {"items": [featured_item(100, "Live Candidate")]}}
            if "appdetails" in url:
                return {appid: details}
            self.fail(f"unexpected url: {url}")

        with TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "free_weekend_candidates.json"
            resolved = resolve_free_weekend_now_payload(
                cache_path,
                live_enabled=True,
                now=OBSERVED_AT,
                fetch_json=fake_fetch,
            )
            cached = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(len(calls), 2)
        self.assertTrue(any("featuredcategories" in url for url in calls))
        self.assertTrue(any("appdetails" in url and "appids=100" in url for url in calls))
        self.assertEqual(resolved["items"][0]["appid"], "100")
        self.assertIn("free_weekend_now", cached)
        self.assertNotIn("prices_cache", cached)

    def test_fetch_free_weekend_store_payloads_fetches_appdetails_one_appid_at_a_time(self) -> None:
        details_by_appid = dict(
            [
                appdetails_entry(101, "First Candidate"),
                appdetails_entry(102, "Second Candidate"),
            ]
        )
        calls = []

        def fake_fetch(url, **_kwargs):
            calls.append(url)
            if "featuredcategories" in url:
                return {
                    "specials": {
                        "items": [
                            featured_item(101, "First Candidate"),
                            featured_item(102, "Second Candidate"),
                        ]
                    }
                }
            if "appids=101" in url:
                return {"101": details_by_appid["101"]}
            if "appids=102" in url:
                return {"102": details_by_appid["102"]}
            self.fail(f"unexpected url: {url}")

        _featured, appdetails = fetch_free_weekend_store_payloads(fetch_json=fake_fetch)

        appdetails_calls = [url for url in calls if "appdetails" in url]
        self.assertEqual(len(appdetails_calls), 2)
        self.assertTrue(all("," not in url.split("appids=", 1)[1].split("&", 1)[0] for url in appdetails_calls))
        self.assertEqual(set(appdetails), {"101", "102"})

    def test_fetch_free_weekend_store_payloads_skips_failed_appdetails_without_aborting(self) -> None:
        appid, details = appdetails_entry(202, "Surviving Candidate")

        def fake_fetch(url, **_kwargs):
            if "featuredcategories" in url:
                return {
                    "specials": {
                        "items": [
                            featured_item(201, "Failing Candidate"),
                            featured_item(202, "Surviving Candidate"),
                        ]
                    }
                }
            if "appids=201" in url:
                raise RuntimeError("HTTP 400")
            if "appids=202" in url:
                return {appid: details}
            self.fail(f"unexpected url: {url}")

        _featured, appdetails = fetch_free_weekend_store_payloads(fetch_json=fake_fetch)

        self.assertEqual(set(appdetails), {"202"})


if __name__ == "__main__":
    unittest.main()
