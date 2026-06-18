import urllib.error
import unittest

from steam_deals_itad import (
    build_itad_external_offers_cache,
    diagnose_itad_deals_v2_payload,
    diagnose_itad_external_offers_cache,
    itad_deals_v2_to_external_offers,
    itad_external_offers_from_cache,
    itad_get_prices_payload,
    itad_lookup_games,
    itad_lookup_games_by_appid,
)


class ItadExternalOffersCacheTests(unittest.TestCase):
    def test_deals_v2_payload_normalizes_oauth_deals_with_known_mapping(self) -> None:
        payload = {
            "hasMore": False,
            "nextOffset": 0,
            "list": [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deal": {
                        "shop": {"id": 35, "name": "Fanatical"},
                        "price": {"amount": 8.99, "currency": "USD"},
                        "regular": {"amount": 24.99, "currency": "USD"},
                        "cut": 64,
                        "drm": [{"id": 1, "name": "Steam"}],
                        "url": "https://next.isthereanydeal.com/link/hades",
                        "timestamp": "2026-06-17T12:00:00Z",
                        "expiry": "2026-06-20T12:00:00Z",
                    },
                },
                {
                    "id": "itad-steam-only",
                    "title": "Steam Only",
                    "deal": {
                        "shop": {"id": 61, "name": "Steam"},
                        "price": {"amount": 9.99, "currency": "USD"},
                        "regular": {"amount": 19.99, "currency": "USD"},
                        "cut": 50,
                        "drm": [{"name": "Steam"}],
                        "url": "https://store.steampowered.com/app/20",
                    },
                },
            ],
        }

        external_offers = itad_deals_v2_to_external_offers(
            payload,
            itad_id_to_appid={"itad-hades": "1145360", "itad-steam-only": "20"},
            country="MX",
        )

        self.assertEqual(len(external_offers["items"]), 1)
        item = external_offers["items"][0]
        self.assertEqual(item["appid"], "1145360")
        self.assertEqual(item["name"], "Hades")
        self.assertEqual(item["store_id"], "fanatical")
        self.assertEqual(item["store_type"], "authorized_key_reseller")
        self.assertEqual(item["visibility"], "highlight")
        self.assertEqual(item["price"], 8.99)
        self.assertEqual(item["currency"], "USD")
        self.assertEqual(item["drm"], "steam")
        self.assertEqual(item["region"], "mx")
        self.assertEqual(item["source"], "itad")
        self.assertEqual(external_offers["summary"]["ranking_impact"], "none")
        self.assertTrue(external_offers["summary"]["advisory_only"])

    def test_deals_v2_payload_without_appid_mapping_stays_hidden_and_advisory(self) -> None:
        payload = {
            "list": [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deal": {
                        "shop": {"id": 35, "name": "Fanatical"},
                        "price": {"amountInt": 899, "currency": "USD"},
                        "regular": {"amount": 24.99, "currency": "USD"},
                        "cut": 64,
                        "drm": [{"name": "Steam"}],
                        "url": "https://next.isthereanydeal.com/link/hades",
                    },
                }
            ]
        }

        external_offers = itad_deals_v2_to_external_offers(payload)

        self.assertEqual(len(external_offers["items"]), 1)
        item = external_offers["items"][0]
        self.assertEqual(item["appid"], "")
        self.assertEqual(item["visibility"], "hidden")
        self.assertFalse(item["eligible_for_best_external_price"])
        self.assertIn("appid_missing", item["risk_flags"])
        self.assertIn("ownership_not_proven", item["risk_flags"])
        self.assertEqual(external_offers["summary"]["best_external_price_count"], 0)

    def test_deals_v2_payload_keeps_marketplaces_and_checkout_urls_hidden(self) -> None:
        payload = {
            "list": [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deal": {
                        "shop": {"id": 99, "name": "G2A"},
                        "price": {"amount": 7.50, "currency": "USD"},
                        "regular": {"amount": 24.99, "currency": "USD"},
                        "cut": 70,
                        "drm": [{"name": "Steam"}],
                        "url": "https://g2a.example/hades",
                    },
                },
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deal": {
                        "shop": {"id": 35, "name": "Fanatical"},
                        "price": {"amount": 8.50, "currency": "USD"},
                        "regular": {"amount": 24.99, "currency": "USD"},
                        "cut": 66,
                        "drm": [{"name": "Steam"}],
                        "url": "https://fanatical.example/checkout/hades",
                    },
                },
            ]
        }

        external_offers = itad_deals_v2_to_external_offers(
            payload,
            itad_id_to_appid={"itad-hades": "1145360"},
        )

        items_by_store = {item["store_id"]: item for item in external_offers["items"]}
        self.assertEqual(external_offers["summary"]["hidden_count"], 2)
        self.assertEqual(external_offers["summary"]["best_external_price_count"], 0)
        self.assertIn("marketplace_keyshop", items_by_store["g2a"]["risk_flags"])
        self.assertFalse(items_by_store["g2a"]["eligible_for_best_external_price"])
        self.assertIn("checkout_like_url", items_by_store["fanatical"]["risk_flags"])
        self.assertEqual(items_by_store["fanatical"]["url"], "")
        self.assertFalse(items_by_store["fanatical"]["link_allowed"])
        self.assertNotIn("wishlist_hygiene", external_offers)
        self.assertNotIn("top_picks", external_offers["summary"])

    def test_deals_v2_payload_degrades_empty_or_malformed_to_empty_contract(self) -> None:
        for payload in (None, {}, {"list": [None, "bad", {"deal": None}]}, {"list": []}):
            with self.subTest(payload=payload):
                external_offers = itad_deals_v2_to_external_offers(payload)

                self.assertEqual(external_offers["items"], [])
                self.assertEqual(external_offers["summary"]["items_count"], 0)
                self.assertEqual(external_offers["summary"]["ranking_impact"], "none")

    def test_deals_v2_diagnostic_reports_coverage_stores_and_risks(self) -> None:
        payload = {
            "hasMore": False,
            "nextOffset": 0,
            "list": [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deal": {
                        "shop": {"id": 35, "name": "Fanatical"},
                        "price": {"amount": 8.99, "currency": "USD"},
                        "regular": {"amount": 24.99, "currency": "USD"},
                        "cut": 64,
                        "drm": [{"name": "Steam"}],
                        "url": "https://fanatical.example/hades",
                    },
                },
                {
                    "id": "itad-unmapped",
                    "title": "Unmapped",
                    "deal": {
                        "shop": {"id": 35, "name": "Fanatical"},
                        "price": {"amount": 6.99, "currency": "USD"},
                        "regular": {"amount": 19.99, "currency": "USD"},
                        "drm": [{"name": "Steam"}],
                        "url": "https://fanatical.example/unmapped",
                    },
                },
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deal": {
                        "shop": {"id": 99, "name": "G2A"},
                        "price": {"amount": 7.50, "currency": "USD"},
                        "regular": {"amount": 24.99, "currency": "USD"},
                        "drm": [{"name": "Steam"}],
                        "url": "https://g2a.example/hades",
                    },
                },
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deal": {
                        "shop": {"id": 61, "name": "Steam"},
                        "price": {"amount": 9.99, "currency": "USD"},
                        "regular": {"amount": 24.99, "currency": "USD"},
                        "drm": [{"name": "Steam"}],
                        "url": "https://store.steampowered.com/app/1145360",
                    },
                },
                "bad-item",
            ],
        }

        diagnostic = diagnose_itad_deals_v2_payload(
            payload,
            itad_id_to_appid={"itad-hades": "1145360"},
            country="MX",
        )

        self.assertEqual(diagnostic["status"], "warning")
        self.assertEqual(diagnostic["issues"][0]["code"], "malformed_deals_v2_items")
        summary = diagnostic["summary"]
        self.assertEqual(summary["raw_items_count"], 5)
        self.assertEqual(summary["payload_items_count"], 4)
        self.assertEqual(summary["malformed_items_count"], 1)
        self.assertEqual(summary["deal_items_count"], 4)
        self.assertEqual(summary["steam_deals_count"], 1)
        self.assertEqual(summary["external_offer_items_count"], 3)
        self.assertEqual(summary["mapped_external_offer_count"], 2)
        self.assertEqual(summary["missing_appid_count"], 1)
        self.assertEqual(summary["highlight_count"], 1)
        self.assertEqual(summary["hidden_count"], 2)
        self.assertEqual(summary["marketplace_count"], 1)
        self.assertEqual(summary["store_counts"], {"fanatical": 2, "g2a": 1})
        self.assertEqual(summary["risk_counts"]["appid_missing"], 1)
        self.assertEqual(summary["risk_counts"]["marketplace_keyshop"], 1)
        self.assertEqual(summary["coverage"]["valid_items"], 0.8)
        self.assertEqual(summary["coverage"]["external_offers"], 1.0)
        self.assertEqual(summary["coverage"]["mapped_external_offers"], 0.6667)
        self.assertTrue(summary["advisory_only"])
        self.assertEqual(summary["ranking_impact"], "none")
        self.assertNotIn("wishlist_hygiene", diagnostic)

    def test_deals_v2_diagnostic_reports_empty_and_invalid_payloads(self) -> None:
        empty = diagnose_itad_deals_v2_payload(None)

        self.assertEqual(empty["status"], "warning")
        self.assertEqual(empty["issues"][0]["code"], "payload_empty")
        self.assertEqual(empty["summary"]["external_offer_items_count"], 0)
        self.assertEqual(empty["summary"]["ranking_impact"], "none")

        invalid = diagnose_itad_deals_v2_payload("bad-payload")

        self.assertEqual(invalid["status"], "error")
        self.assertEqual(invalid["issues"][0]["code"], "invalid_itad_deals_v2_payload")
        self.assertEqual(invalid["items"], [])

        invalid_items = diagnose_itad_deals_v2_payload({"list": "bad-list"})

        self.assertEqual(invalid_items["status"], "error")
        self.assertEqual(invalid_items["issues"][0]["code"], "invalid_deals_v2_items")

    def test_cache_payload_normalizes_fanatical_for_requested_appids_only(self) -> None:
        cache_payload = build_itad_external_offers_cache(
            [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deals": [
                        {
                            "shop": {"id": 35, "name": "Fanatical"},
                            "price": {"amountInt": 899, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 64,
                            "drm": [{"id": 1, "name": "Steam"}],
                            "url": "https://next.isthereanydeal.com/link/hades",
                        }
                    ],
                },
                {
                    "id": "itad-other",
                    "title": "Other Game",
                    "deals": [
                        {
                            "shop": {"id": 17, "name": "GOG"},
                            "price": {"amount": 3.5, "currency": "USD"},
                            "regular": {"amount": 10.0, "currency": "USD"},
                            "cut": 65,
                            "drm": [{"name": "GOG"}],
                            "url": "https://gog.example/game",
                        }
                    ],
                },
            ],
            {"1145360": "itad-hades", "20": "itad-other"},
            country="MX",
            fetched_at="2026-05-21T12:00:00Z",
        )

        external_offers = itad_external_offers_from_cache(
            cache_payload,
            appids=["1145360"],
        )

        self.assertIsNotNone(external_offers)
        items = external_offers["items"]
        self.assertEqual([item["appid"] for item in items], ["1145360"])
        self.assertEqual(items[0]["store_id"], "fanatical")
        self.assertEqual(items[0]["store_type"], "authorized_key_reseller")
        self.assertEqual(items[0]["price"], 8.99)
        self.assertEqual(items[0]["source"], "itad")
        self.assertEqual(items[0]["region"], "mx")
        self.assertIn("ownership_not_proven", items[0]["risk_flags"])
        self.assertEqual(external_offers["summary"]["ranking_impact"], "none")
        self.assertEqual(cache_payload["options"], {"deals_only": True, "capacity": 3})

    def test_cache_reader_returns_none_for_missing_or_unmapped_payload(self) -> None:
        self.assertIsNone(itad_external_offers_from_cache(None, appids=["10"]))
        self.assertIsNone(itad_external_offers_from_cache({}, appids=["10"]))
        self.assertIsNone(
            itad_external_offers_from_cache(
                {"appid_to_itad_id": {"20": "itad-20"}, "prices": []},
                appids=["10"],
            )
        )

    def test_diagnose_cache_reports_empty_and_malformed_payloads(self) -> None:
        empty = diagnose_itad_external_offers_cache({}, appids=["10"])

        self.assertEqual(empty["status"], "warning")
        self.assertEqual(empty["issues"][0]["code"], "cache_empty")
        self.assertEqual(empty["items"][0]["code"], "missing_itad_mapping")
        self.assertEqual(empty["summary"]["missing_mapping_count"], 1)
        self.assertEqual(empty["summary"]["coverage"]["mapping"], 0.0)

        malformed = diagnose_itad_external_offers_cache(["bad-cache"], appids=["10"])

        self.assertEqual(malformed["status"], "error")
        self.assertEqual(malformed["issues"][0]["code"], "invalid_itad_external_offers_cache")
        self.assertEqual(malformed["summary"]["advisory_only"], True)
        self.assertEqual(malformed["summary"]["ranking_impact"], "none")

    def test_diagnose_cache_reports_mapping_price_and_offer_coverage(self) -> None:
        cache_payload = build_itad_external_offers_cache(
            [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deals": [
                        {
                            "shop": {"id": 35, "name": "Fanatical"},
                            "price": {"amount": 8.99, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 64,
                            "drm": [{"name": "Steam"}],
                            "url": "https://fanatical.example/hades",
                        }
                    ],
                }
            ],
            {"1145360": "itad-hades", "20": "itad-missing"},
            country="MX",
        )

        diagnostic = diagnose_itad_external_offers_cache(
            cache_payload,
            appids=["1145360", "20", "30"],
        )

        items = {item["appid"]: item for item in diagnostic["items"]}
        self.assertEqual(diagnostic["status"], "warning")
        self.assertEqual(items["1145360"]["code"], "offers_available")
        self.assertEqual(items["20"]["code"], "missing_price_payload")
        self.assertEqual(items["30"]["code"], "missing_itad_mapping")
        summary = diagnostic["summary"]
        self.assertEqual(summary["mapped_appids_count"], 2)
        self.assertEqual(summary["appids_with_price_payload_count"], 1)
        self.assertEqual(summary["appids_with_external_offers_count"], 1)
        self.assertEqual(summary["highlight_count"], 1)
        self.assertEqual(summary["coverage"]["mapping"], 0.6667)
        self.assertEqual(summary["coverage"]["price_payload"], 0.3333)
        self.assertEqual(summary["coverage"]["external_offers"], 0.3333)

    def test_diagnose_cache_counts_hidden_risky_offers_without_ownership_or_ranking(self) -> None:
        cache_payload = build_itad_external_offers_cache(
            [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deals": [
                        {
                            "shop": {"id": 35, "name": "Fanatical"},
                            "price": {"amount": 8.99, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 64,
                            "drm": [{"name": "Steam"}],
                            "url": "https://fanatical.example/hades",
                        },
                        {
                            "shop": {"id": 99, "name": "G2A"},
                            "price": {"amount": 7.50, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 70,
                            "drm": [{"name": "Steam"}],
                            "url": "https://g2a.example/hades",
                        },
                        {
                            "shop": {"id": 35, "name": "Fanatical"},
                            "price": {"amount": 8.50, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 66,
                            "drm": [{"name": "Steam"}],
                            "url": "https://fanatical.example/checkout/hades",
                        },
                    ],
                }
            ],
            {"1145360": "itad-hades"},
            country="MX",
        )

        diagnostic = diagnose_itad_external_offers_cache(cache_payload, appids=["1145360"])

        self.assertEqual(diagnostic["status"], "warning")
        self.assertEqual(diagnostic["items"][0]["code"], "offers_available_with_hidden_risks")
        summary = diagnostic["summary"]
        self.assertEqual(summary["offers_count"], 3)
        self.assertEqual(summary["highlight_count"], 1)
        self.assertEqual(summary["hidden_count"], 2)
        self.assertEqual(summary["risky_offer_count"], 2)
        self.assertEqual(summary["risk_counts"]["marketplace_keyshop"], 1)
        self.assertEqual(summary["risk_counts"]["checkout_like_url"], 1)
        self.assertTrue(summary["advisory_only"])
        self.assertEqual(summary["ranking_impact"], "none")
        self.assertNotIn("wishlist_hygiene", diagnostic)
        self.assertNotIn("top_picks", summary)

    def test_diagnose_cache_reports_mapped_app_without_external_offers(self) -> None:
        cache_payload = build_itad_external_offers_cache(
            [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deals": [
                        {
                            "shop": {"id": 61, "name": "Steam"},
                            "price": {"amount": 9.99, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 60,
                            "drm": [{"name": "Steam"}],
                            "url": "https://store.steampowered.com/app/1145360",
                        }
                    ],
                }
            ],
            {"1145360": "itad-hades"},
        )

        diagnostic = diagnose_itad_external_offers_cache(cache_payload, appids=["1145360"])

        self.assertEqual(diagnostic["status"], "warning")
        self.assertEqual(diagnostic["items"][0]["code"], "no_external_offers")
        self.assertTrue(diagnostic["items"][0]["has_price_payload"])
        self.assertFalse(diagnostic["items"][0]["has_external_offers"])
        self.assertEqual(diagnostic["summary"]["appids_with_price_payload_count"], 1)
        self.assertEqual(diagnostic["summary"]["appids_with_external_offers_count"], 0)

    def test_itad_get_prices_payload_uses_header_auth_without_logging_key(self) -> None:
        calls = []

        def fake_post_json(url, body, headers=None):
            calls.append((url, body, headers))
            return [{"id": body[0], "deals": []}]

        payload = itad_get_prices_payload(
            {"10": "itad-10"},
            "SECRET-ITAD",
            post_json=fake_post_json,
            sleep_fn=lambda _seconds: None,
        )

        self.assertEqual(payload, [{"id": "itad-10", "deals": []}])
        self.assertNotIn("SECRET-ITAD", calls[0][0])
        self.assertIn("deals=true", calls[0][0])
        self.assertIn("capacity=3", calls[0][0])
        self.assertEqual(calls[0][2], {"ITAD-API-Key": "SECRET-ITAD"})

    def test_itad_get_prices_payload_requires_header_capable_client_without_key_url_fallback(self) -> None:
        errors = []

        def headerless_post_json(_url, _body):
            self.fail("post_json without headers must not be retried")

        with self.assertRaises(RuntimeError) as context:
            itad_get_prices_payload(
                {"10": "itad-10"},
                "SECRET-ITAD",
                post_json=headerless_post_json,
                sleep_fn=lambda _seconds: None,
                on_error=errors.append,
            )

        self.assertIn("post_json no acepta headers", str(context.exception))
        self.assertIn("post_json no acepta headers", errors[0])

    def test_itad_lookup_games_by_appid_uses_header_auth_without_logging_key(self) -> None:
        calls = []

        def fake_get_json(url, headers=None):
            calls.append((url, headers))
            return {"found": True, "game": {"id": "itad-10"}}

        result = itad_lookup_games_by_appid(
            ["10", "not-an-appid"],
            "SECRET-ITAD",
            get_json=fake_get_json,
            sleep_fn=lambda _seconds: None,
        )

        self.assertEqual(result, {"10": "itad-10"})
        self.assertEqual(len(calls), 1)
        self.assertIn("appid=10", calls[0][0])
        self.assertNotIn("SECRET-ITAD", calls[0][0])
        self.assertEqual(calls[0][1], {"ITAD-API-Key": "SECRET-ITAD"})

    def test_itad_lookup_games_by_appid_stops_after_auth_error_without_key_leak(self) -> None:
        calls = []
        errors = []

        def forbidden_get_json(url, headers=None):
            calls.append((url, headers))
            raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

        result = itad_lookup_games_by_appid(
            ["10", "20", "30"],
            "SECRET-ITAD",
            get_json=forbidden_get_json,
            sleep_fn=lambda _seconds: None,
            on_error=errors.append,
        )

        self.assertEqual(result, {})
        self.assertEqual(len(calls), 1)
        self.assertIn("ITAD appid lookup auth error: HTTP 403", errors[0])
        self.assertNotIn("SECRET-ITAD", errors[0])

    def test_itad_lookup_games_stops_batches_after_auth_error_without_key_leak(self) -> None:
        calls = []
        errors = []

        def forbidden_post_json(url, body):
            calls.append((url, body))
            raise urllib.error.HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)

        result = itad_lookup_games(
            [str(appid) for appid in range(1, 80)],
            "SECRET-ITAD",
            post_json=forbidden_post_json,
            sleep_fn=lambda _seconds: None,
            on_error=errors.append,
        )

        self.assertEqual(result, {})
        self.assertEqual(len(calls), 1)
        self.assertIn("ITAD lookup auth error: HTTP 401", errors[0])
        self.assertNotIn("SECRET-ITAD", errors[0])

    def test_itad_get_prices_payload_raises_on_fetch_error_to_preserve_stale_cache(self) -> None:
        errors = []

        def broken_post_json(_url, _body, headers=None):
            raise RuntimeError("429 Too Many Requests")

        with self.assertRaises(RuntimeError):
            itad_get_prices_payload(
                {"10": "itad-10"},
                "SECRET-ITAD",
                post_json=broken_post_json,
                sleep_fn=lambda _seconds: None,
                on_error=errors.append,
            )

        self.assertIn("ITAD external offers prices error", errors[0])

    def test_itad_get_prices_payload_stops_after_auth_error_without_key_leak(self) -> None:
        calls = []
        errors = []

        def forbidden_post_json(url, body, headers=None):
            calls.append((url, body, headers))
            raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

        with self.assertRaises(RuntimeError) as context:
            itad_get_prices_payload(
                {str(appid): f"itad-{appid}" for appid in range(1, 205)},
                "SECRET-ITAD",
                post_json=forbidden_post_json,
                sleep_fn=lambda _seconds: None,
                on_error=errors.append,
            )

        self.assertEqual(len(calls), 1)
        self.assertIn("ITAD external offers prices auth error: HTTP 403", str(context.exception))
        self.assertIn("ITAD external offers prices auth error: HTTP 403", errors[0])
        self.assertNotIn("SECRET-ITAD", str(context.exception))
        self.assertNotIn("SECRET-ITAD", errors[0])

    def test_cache_payload_keeps_risky_itad_offers_hidden_and_advisory_only(self) -> None:
        cache_payload = build_itad_external_offers_cache(
            [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deals": [
                        {
                            "shop": {"id": 35, "name": "Fanatical"},
                            "price": {"amount": 8.99, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 64,
                            "drm": [{"name": "Steam"}],
                            "url": "https://fanatical.example/hades",
                        },
                        {
                            "shop": {"id": 99, "name": "G2A"},
                            "price": {"amount": 7.50, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 70,
                            "drm": [{"name": "Steam"}],
                            "url": "https://g2a.example/hades",
                        },
                        {
                            "shop": {"id": 35, "name": "Fanatical"},
                            "price": {"amount": 8.50, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 66,
                            "drm": [{"name": "Steam"}],
                            "url": "https://fanatical.example/cart/hades",
                        },
                    ],
                }
            ],
            {"1145360": "itad-hades"},
            country="MX",
        )

        external_offers = itad_external_offers_from_cache(
            cache_payload,
            appids=["1145360"],
        )

        self.assertIsNotNone(external_offers)
        summary = external_offers["summary"]
        self.assertTrue(summary["advisory_only"])
        self.assertEqual(summary["ranking_impact"], "none")
        fanatical_highlights = [
            item
            for item in external_offers["items"]
            if item["store_id"] == "fanatical" and item["visibility"] == "highlight"
        ]
        self.assertEqual(len(fanatical_highlights), 1)
        g2a_offer = [item for item in external_offers["items"] if item["store_id"] == "g2a"][0]
        self.assertEqual(g2a_offer["visibility"], "hidden")
        self.assertFalse(g2a_offer["eligible_for_best_external_price"])
        hidden_checkout = [
            item for item in external_offers["items"] if "checkout_like_url" in item["risk_flags"]
        ][0]
        self.assertEqual(hidden_checkout["visibility"], "hidden")
        self.assertFalse(hidden_checkout["link_allowed"])
        for item in external_offers["items"]:
            self.assertNotIn("wishlist_hygiene", item)
            self.assertNotIn("owned", item)


if __name__ == "__main__":
    unittest.main()
