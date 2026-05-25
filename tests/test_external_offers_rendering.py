import json
from pathlib import Path
import unittest

from steam_deals_external_offers import normalize_external_offers
from steam_deals_generator import generate_html, generate_json, generate_md, generate_share_html
from steam_deals_itad import build_itad_external_offers_cache, itad_external_offers_from_cache


ROOT = Path(__file__).resolve().parents[1]


def blocked_external_offers_payload() -> dict:
    return {
        "summary": {"items_count": 2, "advisory_only": True, "ranking_impact": "none"},
        "items": [
            {
                "appid": "30",
                "name": "Risky Key",
                "store_name": "Key Market",
                "store_type": "marketplace_keyshop",
                "price": 1.0,
                "currency": "USD",
                "url": "https://keyshop.example/risky-key",
                "link_allowed": True,
                "visibility": "hidden",
                "risk_flags": ["marketplace_keyshop", "ownership_not_proven"],
            },
            {
                "appid": "40",
                "name": "Checkout Trap",
                "store_name": "GOG",
                "store_type": "official_store",
                "price": 3.0,
                "currency": "USD",
                "url": "https://gog.example/cart/add-to-cart/40",
                "link_allowed": True,
                "visibility": "review",
                "risk_flags": ["checkout_like_url", "ownership_not_proven"],
            },
        ],
    }


class ExternalOffersRenderingRegressionTests(unittest.TestCase):
    def test_itad_cache_fixture_stays_risk_gated_across_outputs(self) -> None:
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
                },
                {
                    "id": "itad-portal",
                    "title": "Portal 2",
                    "deals": [
                        {
                            "shop": {"id": 17, "name": "GOG"},
                            "price": {"amount": 2.49, "currency": "USD"},
                            "regular": {"amount": 9.99, "currency": "USD"},
                            "cut": 75,
                            "url": "https://gog.example/portal-2",
                        }
                    ],
                },
                {
                    "id": "itad-keyshop",
                    "title": "Risky Key",
                    "deals": [
                        {
                            "shop": {"id": 99, "name": "G2A"},
                            "price": {"amount": 1.99, "currency": "USD"},
                            "regular": {"amount": 9.99, "currency": "USD"},
                            "cut": 80,
                            "drm": [{"name": "Steam"}],
                            "url": "https://g2a.example/risky-key",
                        }
                    ],
                },
                {
                    "id": "itad-checkout",
                    "title": "Checkout Trap",
                    "deals": [
                        {
                            "shop": {"id": 17, "name": "GOG"},
                            "price": {"amount": 3.0, "currency": "USD"},
                            "regular": {"amount": 9.99, "currency": "USD"},
                            "cut": 70,
                            "drm": [{"name": "GOG"}],
                            "url": "https://gog.example/cart/add-to-cart/40",
                        }
                    ],
                },
            ],
            {
                "1145360": "itad-hades",
                "20": "itad-portal",
                "30": "itad-keyshop",
                "40": "itad-checkout",
            },
            country="MX",
        )

        external_offers = itad_external_offers_from_cache(
            cache_payload,
            appids=["1145360", "20", "30", "40"],
        )

        self.assertIsNotNone(external_offers)
        summary = external_offers["summary"]
        self.assertTrue(summary["advisory_only"])
        self.assertEqual(summary["ranking_impact"], "none")
        self.assertEqual(summary["items_count"], 4)
        self.assertEqual(summary["highlight_count"], 1)
        self.assertEqual(summary["review_count"], 1)
        self.assertEqual(summary["hidden_count"], 2)
        self.assertEqual(summary["marketplace_count"], 1)
        self.assertEqual(summary["best_external_price_count"], 1)

        payload = generate_json(
            deals=[{"appid": "1145360", "name": "Hades", "discount": 64}],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["1145360", "20", "30", "40"],
            min_discount=50,
            genres=[],
            external_offers=external_offers,
        )
        data = json.loads(payload)
        self.assertEqual(data["summary"]["external_offers_count"], 4)
        self.assertEqual(data["external_offers"]["summary"]["ranking_impact"], "none")
        self.assertEqual(data["external_offers"]["summary"]["marketplace_count"], 1)

        md = generate_md(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            external_offers=external_offers,
        )
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            external_offers=external_offers,
        )
        share_html = generate_share_html(
            deals=[],
            vanity="gaben",
            min_discount=50,
            recommended_collections=[],
            personalized_recommendations={"items": []},
            external_offers=external_offers,
        )

        for rendered in (md, html, share_html):
            self.assertIn("Comparativa externa", rendered)
            self.assertIn("Hades", rendered)
            self.assertIn("Fanatical", rendered)
            self.assertIn("Portal 2", rendered)
            self.assertIn("GOG", rendered)
            self.assertIn("Ver tienda (sin carrito)", rendered)
            self.assertNotIn("Risky Key", rendered)
            self.assertNotIn("G2A", rendered)
            self.assertNotIn("g2a.example", rendered)
            self.assertNotIn("Checkout Trap", rendered)
            self.assertNotIn("add-to-cart", rendered)

        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(encoding="utf-8")
        self.assertIn("payload.items.filter(latestExternalOfferIsVisible)", app_js)
        self.assertIn("'marketplace_keyshop'", app_js)
        self.assertIn("'checkout_like_url'", app_js)

    def test_opt_in_marketplace_review_never_renders_as_visible_comparison(self) -> None:
        external_offers = normalize_external_offers(
            [
                {
                    "appid": "50",
                    "name": "Grey Market Review",
                    "store": "G2A",
                    "price": 1.99,
                    "currency": "USD",
                    "url": "https://g2a.example/deal/50",
                    "drm": "steam",
                    "region": "global",
                    "confidence": "high",
                }
            ],
            include_marketplaces=True,
        )

        item = external_offers["items"][0]
        self.assertEqual(item["store_type"], "marketplace_keyshop")
        self.assertEqual(item["visibility"], "review")
        self.assertFalse(item["eligible_for_best_external_price"])
        self.assertIn("marketplace_keyshop", item["risk_flags"])
        self.assertEqual(external_offers["summary"]["marketplace_count"], 1)
        self.assertEqual(external_offers["summary"]["best_external_price_count"], 0)

        md = generate_md(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            external_offers=external_offers,
        )
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            external_offers=external_offers,
        )
        share_html = generate_share_html(
            deals=[],
            vanity="gaben",
            min_discount=50,
            recommended_collections=[],
            personalized_recommendations={"items": []},
            external_offers=external_offers,
        )

        for rendered in (md, html, share_html):
            self.assertNotIn("Comparativa externa", rendered)
            self.assertNotIn("Grey Market Review", rendered)
            self.assertNotIn("G2A", rendered)
            self.assertNotIn("g2a.example", rendered)
            self.assertNotIn("Ver tienda (sin carrito)", rendered)

    def test_blocked_external_offers_do_not_render_sections_chips_or_links(self) -> None:
        external_offers = blocked_external_offers_payload()
        md = generate_md(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            external_offers=external_offers,
        )
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            external_offers=external_offers,
        )
        share_html = generate_share_html(
            deals=[],
            vanity="gaben",
            min_discount=50,
            recommended_collections=[],
            personalized_recommendations={"items": []},
            external_offers=external_offers,
        )

        for rendered in (md, html, share_html):
            self.assertNotIn("Comparativa externa", rendered)
            self.assertNotIn("Mejor fuera de Steam", rendered)
            self.assertNotIn("Tienda autorizada", rendered)
            self.assertNotIn("Revisar DRM/región", rendered)
            self.assertNotIn("Risky Key", rendered)
            self.assertNotIn("Checkout Trap", rendered)
            self.assertNotIn("keyshop.example", rendered)
            self.assertNotIn("add-to-cart", rendered)
            self.assertNotIn("Ver tienda (sin carrito)", rendered)

    def test_latest_report_chips_are_rendered_after_visibility_filtering(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(encoding="utf-8")
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(encoding="utf-8")

        self.assertIn("payload.items.filter(latestExternalOfferIsVisible)", app_js)
        self.assertIn("LATEST_EXTERNAL_OFFER_BLOCKING_RISKS.some", app_js)
        self.assertIn("renderLatestExternalOfferChips(source)", app_js)
        self.assertIn("Mejor fuera de Steam", app_js)
        self.assertIn("Tienda autorizada", app_js)
        self.assertIn("Revisar DRM/región", app_js)
        self.assertIn(".latest-external-offer-chips", app_css)
        self.assertIn(".latest-external-offer-chip", app_css)


if __name__ == "__main__":
    unittest.main()
