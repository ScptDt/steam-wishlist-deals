from __future__ import annotations

import unittest

from app.steam_deals_recommendations import build_selection_review


class SelectionReviewTests(unittest.TestCase):
    def test_local_profile_signals_promote_matching_selected_game(self) -> None:
        review = build_selection_review(
            ["10", "20"],
            deals=[
                {
                    "appid": "10",
                    "name": "Deep Action",
                    "score": 60,
                    "discount": 45,
                    "genres": ["Action", "Roguelike"],
                },
                {
                    "appid": "20",
                    "name": "Quiet Builder",
                    "score": 68,
                    "discount": 20,
                    "genres": ["Simulation"],
                },
            ],
            activity_games=[
                {
                    "appid": "90",
                    "name": "Hades",
                    "playtime_2weeks": 180,
                    "genres": ["Action", "Roguelike"],
                }
            ],
            library_games=[
                {"appid": "91", "name": "Dead Cells", "genres": ["Action", "Roguelike"]},
            ],
            liked_appids={"10"},
            preference_relations={"10": ["similar a Hades"]},
            max_reasons=4,
        )

        by_appid = {item["appid"]: item for item in review["items"]}
        self.assertEqual(by_appid["10"]["decision"], "conservar")
        self.assertEqual(by_appid["10"]["personalized_score"], 100.0)
        self.assertGreater(by_appid["10"]["affinity_score"], 0)
        self.assertIn("personalized_score", by_appid["10"]["signals"])
        self.assertIn("affinity", by_appid["10"]["signals"])
        self.assertIn("similar a Hades", by_appid["10"]["reasons"])
        self.assertEqual(by_appid["20"]["decision"], "dudar")
        self.assertEqual(review["summary"]["conservar"], 1)
        self.assertEqual(review["summary"]["dudar"], 1)

    def test_recommended_collections_add_local_signal_without_recalibrating_score(self) -> None:
        review = build_selection_review(
            ["70"],
            deals=[
                {
                    "appid": "70",
                    "name": "Deck Gem",
                    "score": 74,
                    "discount": 25,
                    "genres": ["Adventure"],
                },
            ],
            recommended_collections=[
                {
                    "id": "steam_deck",
                    "label": "Steam Deck",
                    "items": [
                        {
                            "appid": "70",
                            "name": "Deck Gem",
                            "reason": "Steam Deck Verified",
                            "score": 74,
                            "discount": 25,
                        }
                    ],
                }
            ],
            max_reasons=3,
        )

        item = review["items"][0]
        self.assertEqual(item["decision"], "dudar")
        self.assertEqual(item["base_score"], 74.0)
        self.assertIn("recommended_collection", item["signals"])
        self.assertIn("Steam Deck: Steam Deck Verified", item["reasons"])
        self.assertIn("recommended_collections", review["source_signals"])

    def test_collection_reasons_do_not_displace_stronger_limited_reasons(self) -> None:
        review = build_selection_review(
            ["80"],
            deals=[
                {"appid": "80", "name": "Curated Gem", "score": 70, "discount": 90},
            ],
            personalized_recommendations={
                "items": [
                    {
                        "appid": "80",
                        "name": "Curated Gem",
                        "base_score": 70,
                        "affinity_score": 20,
                        "personalized_score": 95,
                        "reasons": ["curated personal fit"],
                    }
                ]
            },
            recommended_collections=[
                {
                    "id": "best_savings",
                    "label": "Mayor ahorro",
                    "items": [{"appid": "80", "reason": "90% de descuento"}],
                }
            ],
            max_reasons=2,
        )

        item = review["items"][0]
        self.assertEqual(item["reasons"], ["curated personal fit", "score personal alto: 95.0"])
        self.assertIn("recommended_collection", item["signals"])

    def test_duplicate_collection_reasons_are_deduped(self) -> None:
        review = build_selection_review(
            ["90"],
            recommended_collections=[
                {
                    "id": "steam_deck",
                    "label": "Steam Deck",
                    "items": [{"appid": "90", "reason": "Steam Deck Verified"}],
                },
                {
                    "id": "steam_deck",
                    "label": "Steam Deck",
                    "items": [{"appid": "90", "reason": "Steam Deck Verified"}],
                },
            ],
            max_reasons=4,
        )

        item = review["items"][0]
        self.assertEqual(item["reasons"].count("Steam Deck: Steam Deck Verified"), 1)
        self.assertEqual(item["reasons"], ["Steam Deck: Steam Deck Verified"])

    def test_marks_owned_family_invalid_and_duplicate_selection_items(self) -> None:
        review = build_selection_review(
            ["30", {"appid": "40"}, "30", ""],
            deals=[
                {"appid": "30", "name": "Owned Hit", "score": 95, "genres": ["Action"]},
                {"appid": "40", "name": "Family Hit", "score": 95, "genres": ["Action"]},
            ],
            owned={"30": "Owned Hit"},
            family_appids=["40"],
            max_reasons=3,
        )

        self.assertEqual([item["appid"] for item in review["items"]], ["30", "40", ""])
        by_appid = {item["appid"]: item for item in review["items"]}
        self.assertEqual(by_appid["30"]["decision"], "quitar")
        self.assertIn("owned", by_appid["30"]["signals"])
        self.assertIn("ya está en tu biblioteca", by_appid["30"]["reasons"])
        self.assertEqual(by_appid["40"]["decision"], "quitar")
        self.assertIn("family", by_appid["40"]["signals"])
        self.assertIn("ya disponible en biblioteca familiar", by_appid["40"]["reasons"])
        self.assertEqual(by_appid[""]["decision"], "quitar")
        self.assertIn("invalid_appid", by_appid[""]["signals"])
        self.assertEqual(review["summary"]["duplicate_count"], 1)
        self.assertEqual(review["summary"]["quitar"], 3)

    def test_existing_personalized_recommendations_are_reused(self) -> None:
        review = build_selection_review(
            ["50"],
            deals=[
                {"appid": "50", "name": "Base Name", "score": 50, "genres": ["Puzzle"]},
            ],
            personalized_recommendations={
                "items": [
                    {
                        "appid": "50",
                        "name": "Curated Pick",
                        "base_score": 50,
                        "affinity_score": 40,
                        "personalized_score": 90,
                        "reasons": ["curated existing signal"],
                    }
                ]
            },
            activity_games=[{"appid": "90", "genres": ["Action"]}],
            max_reasons=3,
        )

        item = review["items"][0]
        self.assertEqual(item["name"], "Curated Pick")
        self.assertEqual(item["decision"], "conservar")
        self.assertEqual(item["personalized_score"], 90.0)
        self.assertIn("curated existing signal", item["reasons"])

    def test_review_items_include_advisory_v2_fields(self) -> None:
        review = build_selection_review(
            ["10", "20", "30", "999"],
            deals=[
                {"appid": "10", "name": "Strong Fit", "score": 70, "discount": 80},
                {"appid": "20", "name": "Maybe Later", "score": 62},
                {"appid": "30", "name": "Already Owned", "score": 95},
            ],
            personalized_recommendations={
                "items": [
                    {
                        "appid": "10",
                        "name": "Strong Fit",
                        "base_score": 70,
                        "affinity_score": 28,
                        "personalized_score": 92,
                        "reasons": ["similar a Hades"],
                    }
                ]
            },
            owned={"30": "Already Owned"},
            max_reasons=3,
        )

        by_appid = {item["appid"]: item for item in review["items"]}
        self.assertEqual(by_appid["10"]["confidence"], "high")
        self.assertIn("mantener", by_appid["10"]["next_step"])
        self.assertIn("similar a Hades", by_appid["10"]["why"]["positive"])
        self.assertEqual(by_appid["20"]["confidence"], "medium")
        self.assertIn("backlog", by_appid["20"]["next_step"])
        self.assertTrue(by_appid["20"]["why"]["context"])
        self.assertEqual(by_appid["30"]["confidence"], "high")
        self.assertIn("ya está en tu biblioteca", by_appid["30"]["why"]["caution"])
        self.assertEqual(by_appid["999"]["confidence"], "low")
        self.assertIn("solo aparece en tu selección manual", by_appid["999"]["why"]["context"])

    def test_review_contract_strips_commerce_fields_from_report_context(self) -> None:
        review = build_selection_review(
            ["60"],
            deals=[
                {
                    "appid": "60",
                    "name": "Safe Local Pick",
                    "score": 92,
                    "discount": 75,
                    "checkout_url": "https://example.invalid/checkout",
                    "cart_id": "external-cart",
                    "external_store": "Fanatical",
                    "payment_provider": "ExamplePay",
                    "remove_action": "remove-automatically",
                }
            ],
        )

        item = review["items"][0]
        forbidden_keys = {
            "checkout_url",
            "cart_id",
            "external_store",
            "payment_provider",
            "remove_action",
            "shop",
            "store",
        }
        forbidden_text = ("checkout", "fanatical", "payment", "external-cart", "remove-automatically")

        self.assertTrue(forbidden_keys.isdisjoint(item.keys()))
        self.assertTrue(
            all(text not in str(review).lower() for text in forbidden_text),
            msg="selection review must stay a local no-commerce contract",
        )


if __name__ == "__main__":
    unittest.main()
