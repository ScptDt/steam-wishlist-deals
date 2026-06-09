from __future__ import annotations

import unittest

from steam_deals_price_fetch_strategy import FETCH_PLAN_BUCKETS
from steam_deals_price_fetch_strategy import PLAN_SCHEMA
from steam_deals_price_fetch_strategy import build_proactive_price_fetch_plan


class ProactivePriceFetchPlannerTests(unittest.TestCase):
    def test_plain_appids_mirror_current_batch_behavior(self) -> None:
        plan = build_proactive_price_fetch_plan(["10", "20", "30"])

        self.assertEqual(plan["schema"], PLAN_SCHEMA)
        self.assertEqual(plan["batch"], ["10", "20", "30"])
        for bucket in FETCH_PLAN_BUCKETS:
            if bucket != "batch":
                self.assertEqual(plan[bucket], [])
        self.assertEqual(plan["summary"]["batch_count"], 3)
        self.assertEqual(plan["summary"]["planned_fetch_count"], 3)
        self.assertEqual(plan["summary"]["non_fetch_count"], 0)

    def test_rich_candidates_route_to_explicit_future_buckets(self) -> None:
        plan = build_proactive_price_fetch_plan(
            [
                {"appid": "10", "state": "batch"},
                {"appid": "20", "state": "planned_individual"},
                {"appid": "30", "use_stale": True},
                {"appid": "40", "deferred": True},
                {"appid": "50", "state": "cooldown"},
            ]
        )

        self.assertEqual(plan["batch"], ["10"])
        self.assertEqual(plan["individual_planificado"], ["20"])
        self.assertEqual(plan["usar_stale"], ["30"])
        self.assertEqual(plan["defer"], ["40"])
        self.assertEqual(plan["cooldown"], ["50"])
        self.assertEqual(plan["fallback_reactivo"], [])
        self.assertEqual(plan["summary"]["total_candidates"], 5)
        self.assertEqual(plan["summary"]["planned_fetch_count"], 2)
        self.assertEqual(plan["summary"]["non_fetch_count"], 3)

    def test_http_429_failure_reason_routes_to_cooldown(self) -> None:
        plan = build_proactive_price_fetch_plan(
            [
                {"appid": "10", "failure_reason": "http_429", "state": "batch"},
                {"appid": "20", "bucket": "unknown"},
            ]
        )

        self.assertEqual(plan["cooldown"], ["10"])
        self.assertEqual(plan["batch"], ["20"])

    def test_blank_candidates_are_ignored(self) -> None:
        plan = build_proactive_price_fetch_plan(["", None, {"appid": ""}, {"id": "30"}])

        self.assertEqual(plan["batch"], ["30"])
        self.assertEqual(plan["summary"]["total_candidates"], 1)


if __name__ == "__main__":
    unittest.main()
