from __future__ import annotations

import unittest
from datetime import date

from steam_deals_generator import (
    apply_filters,
    build_gift_ideas,
    compute_budget_picks,
    compute_value_score,
    is_same_game,
)


class ComputeValueScoreTests(unittest.TestCase):
    def test_uses_expected_defaults_when_optional_signals_are_missing(self) -> None:
        score = compute_value_score(
            discount=80,
            review_pct=None,
            priority=0,
            price_per_hour=None,
            deck_cat=0,
            release_year=None,
            metacritic_score=None,
        )

        self.assertAlmostEqual(score, 53.0)

    def test_rewards_strong_signals_consistently(self) -> None:
        score = compute_value_score(
            discount=90,
            review_pct=90,
            priority=5,
            price_per_hour=5.0,
            deck_cat=3,
            release_year=date.today().year,
            metacritic_score=90,
        )

        self.assertAlmostEqual(score, 93.8)


class ApplyFiltersTests(unittest.TestCase):
    def test_applies_combined_filters_and_keeps_only_matching_deals(self) -> None:
        deals = [
            {"appid": "a", "price_raw": 1200},
            {"appid": "b", "price_raw": 900},
            {"appid": "c", "price_raw": 800},
        ]
        filters = {
            "max_price": 10,
            "deck_only": True,
            "min_reviews": 80,
            "min_review_count": 500,
            "max_hours": 20,
            "new_only": True,
        }
        reviews = {
            "b": {"pct": 92, "total": 1200},
            "c": {"pct": 79, "total": 2000},
        }
        deck_compat = {"a": 3, "b": 2, "c": 3}
        hltb_hours = {"b": 12.0, "c": 8.0}
        comparison = {"new_deals": {"b"}}

        filtered = apply_filters(
            deals=deals,
            filters=filters,
            reviews=reviews,
            deck_compat=deck_compat,
            hltb_hours=hltb_hours,
            previous_appids={"a", "c"},
            comparison=comparison,
        )

        self.assertEqual([deal["appid"] for deal in filtered], ["b"])

    def test_new_only_falls_back_to_previous_appids_when_comparison_is_empty(self) -> None:
        deals = [{"appid": "a"}, {"appid": "b"}, {"appid": "c"}]

        filtered = apply_filters(
            deals=deals,
            filters={"new_only": True},
            reviews={},
            deck_compat={},
            hltb_hours={},
            previous_appids={"a", "c"},
            comparison={},
        )

        self.assertEqual([deal["appid"] for deal in filtered], ["b"])


class MatchingAndRecommendationTests(unittest.TestCase):
    def test_is_same_game_accepts_edition_variants(self) -> None:
        self.assertTrue(is_same_game("Portal 2 Game of the Year Edition", "Portal 2"))

    def test_is_same_game_rejects_number_mismatch(self) -> None:
        self.assertFalse(is_same_game("Portal 2", "Portal 3"))

    def test_build_gift_ideas_excludes_owned_and_sorts_by_discount(self) -> None:
        deals = [
            {"appid": "1", "discount": 20, "name": "Low"},
            {"appid": "2", "discount": 80, "name": "Owned"},
            {"appid": "3", "discount": 50, "name": "Mid"},
        ]

        ideas = build_gift_ideas(friend_set={"1", "2", "3"}, deals=deals, owned={"2": "Owned"})

        self.assertEqual([deal["appid"] for deal in ideas], ["3", "1"])


class BudgetPickTests(unittest.TestCase):
    def test_prioritizes_watchlist_hits_then_fills_remaining_budget_by_efficiency(self) -> None:
        deals = [
            {"appid": "a", "price_raw": 1000, "discount": 50, "name": "Alpha"},
            {"appid": "b", "price_raw": 500, "discount": 50, "name": "Bravo"},
            {"appid": "c", "price_raw": 1200, "discount": 10, "name": "Charlie"},
        ]
        top_picks = [
            {"appid": "a", "score": 90.0},
            {"appid": "b", "score": 10.0},
            {"appid": "c", "score": 95.0},
        ]
        watchlist_alerts = [{"appid": "b", "price_raw": 500, "discount": 50, "name": "Bravo"}]

        result = compute_budget_picks(
            deals=deals,
            budget_mxn=15,
            top_picks=top_picks,
            watchlist_alerts=watchlist_alerts,
        )

        self.assertEqual([deal["appid"] for deal in result["selected"]], ["b", "a"])
        self.assertEqual(result["games_count"], 2)
        self.assertEqual(result["total_spent"], 15.0)
        self.assertEqual(result["remaining"], 0.0)
        self.assertEqual(result["total_savings"], 15.0)


if __name__ == "__main__":
    unittest.main()
