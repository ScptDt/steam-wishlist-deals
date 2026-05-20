from __future__ import annotations

import unittest

from steam_deals_generator import build_price_cache_coverage


class WarmCacheFinalActionsTests(unittest.TestCase):
    def test_finished_queue_exposes_conservative_final_failure_actions(self) -> None:
        coverage = build_price_cache_coverage(
            {
                "deals": [{"appid": "10"}],
                "refresh_candidate_count": 2934,
                "processed_count": 2934,
                "deferred_by_time_budget": 0,
                "time_budget_exhausted": False,
                "cache_state_counts": {
                    "fresh": 2435,
                    "cooldown": 110,
                    "failed_no_data": 389,
                    "missing": 0,
                },
                "no_price_classification_counts": {
                    "coming_soon": 12,
                    "unavailable_or_removed_review": 8,
                    "temporary_unconfirmed": 110,
                },
            }
        )

        self.assertIsNotNone(coverage)
        actions = {item["action"]: item for item in coverage["final_failure_actions"]}

        self.assertEqual(coverage["resumable_queue_status"], "finished")
        self.assertEqual(actions["wait_cooldown"]["count"], 110)
        self.assertEqual(actions["retry_failed_eligible"]["count"], 389)
        self.assertEqual(actions["review_no_price"]["count"], 20)
        self.assertTrue(actions["retry_failed_eligible"]["can_retry"])
        self.assertTrue(all(action["destructive"] is False for action in actions.values()))
        self.assertIn("--warm-cache", actions["wait_cooldown"]["detail"])
        self.assertIn("sin --no-cache", actions["wait_cooldown"]["detail"])
        self.assertIn("no borra", actions["retry_failed_eligible"]["detail"])
        self.assertIn("no asumir retirado", actions["review_no_price"]["detail"])
        self.assertIn("acciones sugeridas", coverage["detail"])

    def test_partial_queue_does_not_offer_final_failure_actions_yet(self) -> None:
        coverage = build_price_cache_coverage(
            {
                "refresh_candidate_count": 100,
                "processed_count": 60,
                "deferred_by_time_budget": 40,
                "cache_state_counts": {"cooldown": 5, "failed_no_data": 8},
            }
        )

        self.assertIsNotNone(coverage)
        self.assertEqual(coverage["resumable_queue_status"], "pending")
        self.assertNotIn("final_failure_actions", coverage)


if __name__ == "__main__":
    unittest.main()
