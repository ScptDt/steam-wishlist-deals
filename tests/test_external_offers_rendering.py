from pathlib import Path
import unittest

from steam_deals_generator import generate_html, generate_md, generate_share_html


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
