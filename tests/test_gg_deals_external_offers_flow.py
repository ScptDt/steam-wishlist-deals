from pathlib import Path
import unittest

from steam_deals_config import get_config
from steam_deals_gg_deals import gg_deals_prices_to_external_offers
from steam_deals_generator import (
    merge_external_offers_payloads,
    resolve_gg_deals_external_offers_cache,
)


class FakeStdin:
    def isatty(self):
        return False


class GGDealsExternalOffersFlowTests(unittest.TestCase):
    def test_get_config_exposes_local_gg_deals_external_offers_cache_flag(self) -> None:
        result = get_config(
            script_path=Path("/tmp/fake_script.py"),
            load_user_config_fn=lambda: {},
            save_user_config_fn=lambda _cfg: None,
            handle_watchlist_command_fn=lambda _args: None,
            input_fn=lambda _prompt: "",
            stdin=FakeStdin(),
            exit_fn=lambda _code: None,
            argv=[
                "--vanity",
                "gaben",
                "--gg-deals-external-offers-cache",
                "./gg-deals-external-offers.json",
            ],
        )

        self.assertEqual(
            result[11]["gg_deals_external_offers_cache"],
            Path("gg-deals-external-offers.json"),
        )

    def test_resolve_gg_deals_external_offers_cache_loads_local_cache_without_network(self) -> None:
        cache_payload = {
            "success": True,
            "data": {
                "1145360": {
                    "title": "Hades",
                    "url": "https://gg.deals/game/hades/",
                    "prices": {"currentRetail": "8.99", "currency": "USD"},
                },
                "999999": {
                    "title": "Out of scope",
                    "url": "https://gg.deals/game/out/",
                    "prices": {"currentRetail": "1.99", "currency": "USD"},
                },
            },
        }
        emitted: list[str] = []

        external_offers = resolve_gg_deals_external_offers_cache(
            Path("gg-deals-cache.json"),
            ["1145360"],
            load_cache_fn=lambda _path: cache_payload,
            emit_fn=emitted.append,
        )

        self.assertIsNotNone(external_offers)
        self.assertEqual(len(external_offers["items"]), 1)
        item = external_offers["items"][0]
        self.assertEqual(item["appid"], "1145360")
        self.assertEqual(item["store_id"], "gg_deals")
        self.assertEqual(item["store_type"], "aggregator")
        self.assertEqual(item["visibility"], "hidden")
        self.assertEqual(external_offers["summary"]["ranking_impact"], "none")
        self.assertIn("Ofertas externas GG.deals desde caché local: 1", emitted[0])

    def test_resolve_gg_deals_external_offers_cache_degrades_on_cache_error(self) -> None:
        emitted: list[str] = []

        def broken_loader(_path):
            raise ValueError("JSON inválido")

        external_offers = resolve_gg_deals_external_offers_cache(
            Path("gg-deals-cache.json"),
            ["10"],
            load_cache_fn=broken_loader,
            emit_fn=emitted.append,
        )

        self.assertIsNone(external_offers)
        self.assertIn("No se pudo cargar caché GG.deals external_offers", emitted[0])

    def test_merge_external_offers_payloads_keeps_itad_and_gg_deals_items_advisory(self) -> None:
        itad_external_offers = {
            "items": [
                {
                    "appid": "1145360",
                    "name": "Hades",
                    "store_id": "fanatical",
                    "price": 8.99,
                    "currency": "USD",
                    "drm": "steam",
                    "region": "global",
                    "source": "itad",
                    "confidence": "high",
                }
            ]
        }
        gg_external_offers = gg_deals_prices_to_external_offers(
            {
                "data": {
                    "1145360": {
                        "title": "Hades",
                        "prices": {"currentRetail": "7.99", "currency": "USD"},
                    }
                }
            }
        )

        merged = merge_external_offers_payloads(itad_external_offers, gg_external_offers)

        self.assertIsNotNone(merged)
        items = {item["store_id"]: item for item in merged["items"]}
        self.assertEqual(items["fanatical"]["visibility"], "highlight")
        self.assertEqual(items["gg_deals"]["visibility"], "hidden")
        self.assertFalse(items["gg_deals"]["eligible_for_best_external_price"])
        self.assertEqual(merged["summary"]["ranking_impact"], "none")

    def test_prices_payload_normalizes_retail_and_keyshops_as_hidden_advisory_sources(self) -> None:
        payload = {
            "success": True,
            "data": {
                "1145360": {
                    "title": "Hades",
                    "url": "https://gg.deals/game/hades/",
                    "prices": {
                        "currentRetail": "8.99",
                        "currentKeyshops": "6.49",
                        "historicalRetail": "5.99",
                        "historicalKeyshops": "4.99",
                        "currency": "USD",
                    },
                }
            },
        }

        external_offers = gg_deals_prices_to_external_offers(payload, region="us")

        items = {item["store_id"]: item for item in external_offers["items"]}
        retail = items["gg_deals"]
        keyshops = items["gg_deals_keyshops"]
        self.assertEqual(retail["appid"], "1145360")
        self.assertEqual(retail["name"], "Hades")
        self.assertEqual(retail["price"], 8.99)
        self.assertEqual(retail["currency"], "USD")
        self.assertEqual(retail["source"], "gg_deals")
        self.assertEqual(retail["store_type"], "aggregator")
        self.assertEqual(retail["visibility"], "hidden")
        self.assertFalse(retail["eligible_for_best_external_price"])
        self.assertIn("aggregator_source", retail["risk_flags"])
        self.assertIn("ownership_not_proven", retail["risk_flags"])
        self.assertEqual(keyshops["store_type"], "marketplace_keyshop")
        self.assertEqual(keyshops["visibility"], "hidden")
        self.assertFalse(keyshops["eligible_for_best_external_price"])
        self.assertIn("marketplace_keyshop", keyshops["risk_flags"])
        self.assertEqual(external_offers["summary"]["ranking_impact"], "none")
        self.assertTrue(external_offers["summary"]["advisory_only"])

    def test_keyshops_can_be_review_only_when_marketplaces_are_explicitly_included(self) -> None:
        payload = {
            "data": {
                "20": {
                    "title": "Risky Key",
                    "url": "https://gg.deals/game/risky-key/",
                    "prices": {"currentRetail": None, "currentKeyshops": "1.99", "currency": "USD"},
                }
            }
        }

        external_offers = gg_deals_prices_to_external_offers(
            payload,
            include_marketplaces=True,
        )

        self.assertEqual(len(external_offers["items"]), 1)
        item = external_offers["items"][0]
        self.assertEqual(item["store_id"], "gg_deals_keyshops")
        self.assertEqual(item["visibility"], "review")
        self.assertFalse(item["eligible_for_best_external_price"])

    def test_empty_null_and_malformed_prices_payloads_degrade_to_empty_contract(self) -> None:
        for payload in (
            None,
            [],
            {"success": True, "data": {"10": None}},
            {"success": True, "data": {"10": {"title": "No price", "prices": {}}}},
        ):
            with self.subTest(payload=payload):
                external_offers = gg_deals_prices_to_external_offers(payload)

                self.assertEqual(external_offers["items"], [])
                self.assertEqual(external_offers["summary"]["items_count"], 0)
                self.assertEqual(external_offers["summary"]["ranking_impact"], "none")

    def test_checkout_like_gg_deals_url_is_blocked_and_never_competes(self) -> None:
        payload = {
            "data": {
                "30": {
                    "title": "Checkout Trap",
                    "url": "https://gg.deals/cart/add-to-cart/30",
                    "prices": {"currentRetail": "3.50", "currency": "USD"},
                }
            }
        }

        external_offers = gg_deals_prices_to_external_offers(payload)

        item = external_offers["items"][0]
        self.assertEqual(item["store_id"], "gg_deals")
        self.assertEqual(item["visibility"], "hidden")
        self.assertEqual(item["url"], "")
        self.assertFalse(item["link_allowed"])
        self.assertFalse(item["eligible_for_best_external_price"])
        self.assertIn("checkout_like_url", item["risk_flags"])


if __name__ == "__main__":
    unittest.main()
