import unittest

from steam_deals_gg_deals import gg_deals_prices_to_external_offers


class GGDealsExternalOffersFlowTests(unittest.TestCase):
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
