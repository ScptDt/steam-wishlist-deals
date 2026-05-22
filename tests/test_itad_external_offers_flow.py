import unittest

from steam_deals_itad import (
    build_itad_external_offers_cache,
    itad_external_offers_from_cache,
    itad_get_prices_payload,
    itad_lookup_games_by_appid,
)


class ItadExternalOffersCacheTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
