from __future__ import annotations

import unittest

from steam_deals_price_fetch_strategy import DEFAULT_REPEATED_HTTP_400_THRESHOLD
from steam_deals_price_fetch_strategy import COMPARISON_SCHEMA
from steam_deals_price_fetch_strategy import FETCH_PLAN_BUCKETS
from steam_deals_price_fetch_strategy import PLAN_SCHEMA
from steam_deals_price_fetch_strategy import build_proactive_price_fetch_plan
from steam_deals_price_fetch_strategy import build_proactive_price_fetch_plan_comparison
from steam_deals_price_fetch_strategy import format_proactive_price_fetch_plan_comparison
from steam_deals_price_fetch_strategy import format_proactive_price_fetch_plan_summary


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
        self.assertEqual(plan["summary"]["batch_fetch_count"], 1)
        self.assertEqual(plan["summary"]["planned_individual_count"], 1)
        self.assertEqual(plan["summary"]["reactive_fallback_count"], 0)
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

    def test_repeated_http_400_routes_batch_candidates_to_planned_individual(
        self,
    ) -> None:
        plan = build_proactive_price_fetch_plan(
            ["10", {"appid": "20", "state": "batch"}],
            planner_context={
                "http_400_degradation_streak": DEFAULT_REPEATED_HTTP_400_THRESHOLD,
            },
        )

        self.assertEqual(plan["batch"], [])
        self.assertEqual(plan["individual_planificado"], ["10", "20"])
        self.assertEqual(plan["signals"], {"repeated_http_400": True})
        self.assertEqual(plan["summary"]["planned_fetch_count"], 2)

    def test_repeated_http_400_preserves_non_batch_buckets(self) -> None:
        plan = build_proactive_price_fetch_plan(
            [
                {"appid": "10", "state": "cooldown"},
                {"appid": "20", "use_stale": True},
                {"appid": "30", "deferred": True},
                {"appid": "40", "state": "reactive_fallback"},
                {"appid": "50", "state": "planned_individual"},
                {"appid": "60", "state": "batch"},
            ],
            planner_context={"repeated_http_400": True},
        )

        self.assertEqual(plan["cooldown"], ["10"])
        self.assertEqual(plan["usar_stale"], ["20"])
        self.assertEqual(plan["defer"], ["30"])
        self.assertEqual(plan["fallback_reactivo"], ["40"])
        self.assertEqual(plan["individual_planificado"], ["50", "60"])
        self.assertEqual(plan["batch"], [])

    def test_http_400_streak_below_threshold_keeps_batch_candidates(self) -> None:
        plan = build_proactive_price_fetch_plan(
            ["10", "20"],
            planner_context={
                "http_400_degradation_streak": DEFAULT_REPEATED_HTTP_400_THRESHOLD - 1,
                "http_400_circuit_breaker_threshold": DEFAULT_REPEATED_HTTP_400_THRESHOLD,
            },
        )

        self.assertEqual(plan["batch"], ["10", "20"])
        self.assertEqual(plan["individual_planificado"], [])
        self.assertEqual(plan["signals"], {"repeated_http_400": False})

    def test_blank_candidates_are_ignored(self) -> None:
        plan = build_proactive_price_fetch_plan(["", None, {"appid": ""}, {"id": "30"}])

        self.assertEqual(plan["batch"], ["30"])
        self.assertEqual(plan["summary"]["total_candidates"], 1)

    def test_plan_summary_copy_distinguishes_planned_individual_and_reactive_fallback(
        self,
    ) -> None:
        plan = build_proactive_price_fetch_plan(
            [
                {"appid": "10", "state": "batch"},
                {"appid": "20", "state": "planned_individual"},
                {"appid": "30", "state": "reactive_fallback"},
                {"appid": "40", "use_stale": True},
            ]
        )

        copy = format_proactive_price_fetch_plan_summary(plan)

        self.assertEqual(plan["summary"]["planned_individual_count"], 1)
        self.assertEqual(plan["summary"]["reactive_fallback_count"], 1)
        self.assertIn("1 batch", copy)
        self.assertIn("1 individual planificado", copy)
        self.assertIn("1 fallback reactivo", copy)
        self.assertIn("safety net", copy)
        self.assertIn("no cambia defaults, score, ranking, cache policy ni fetching", copy)

    def test_plan_summary_copy_mentions_http_400_planned_individual_signal(self) -> None:
        plan = build_proactive_price_fetch_plan(
            ["10", "20"],
            planner_context={"repeated_http_400": True},
        )

        copy = format_proactive_price_fetch_plan_summary(plan)

        self.assertIn("Señal HTTP 400 repetido", copy)
        self.assertIn("`individual_planificado`", copy)
        self.assertIn("2 candidato(s)", copy)
        self.assertNotIn("Fallback reactivo: 2", copy)

    def test_plan_summary_copy_handles_empty_plan(self) -> None:
        plan = build_proactive_price_fetch_plan([])

        copy = format_proactive_price_fetch_plan_summary(plan)

        self.assertIn("Sin candidatos para planificar", copy)
        self.assertIn("Fallback reactivo: 0 candidatos", copy)

    def test_plan_comparison_uses_external_reactive_baseline(self) -> None:
        plan = build_proactive_price_fetch_plan(
            [
                {"appid": "10", "state": "batch"},
                {"appid": "20", "state": "planned_individual"},
                {"appid": "30", "state": "reactive_fallback"},
                {"appid": "40", "state": "cooldown"},
            ]
        )

        comparison = build_proactive_price_fetch_plan_comparison(
            plan,
            reactive_baseline={"reactive_fallback_count": 5},
        )
        copy = format_proactive_price_fetch_plan_comparison(comparison)

        self.assertEqual(comparison["schema"], COMPARISON_SCHEMA)
        self.assertEqual(comparison["baseline_source"], "external")
        self.assertEqual(comparison["baseline_reactive_fallback_count"], 5)
        self.assertEqual(comparison["planned_individual_count"], 1)
        self.assertEqual(comparison["reactive_fallback_count"], 1)
        self.assertEqual(comparison["reactive_dependency_reduction_count"], 4)
        self.assertEqual(comparison["planned_fetch_count"], 2)
        self.assertEqual(comparison["non_fetch_count"], 1)
        self.assertIn("baseline externo", copy)
        self.assertIn("1 individual_planificado", copy)
        self.assertIn("1 fallback_reactivo", copy)
        self.assertIn("4 candidato(s)", copy)
        self.assertIn("resumen offline", copy)

    def test_plan_comparison_uses_plan_distribution_without_external_baseline(self) -> None:
        plan = build_proactive_price_fetch_plan(
            [
                {"appid": "10", "state": "planned_individual"},
                {"appid": "20", "state": "planned_individual"},
                {"appid": "30", "state": "reactive_fallback"},
            ]
        )

        comparison = build_proactive_price_fetch_plan_comparison(plan)
        copy = format_proactive_price_fetch_plan_comparison(comparison)

        self.assertEqual(comparison["baseline_source"], "plan")
        self.assertEqual(comparison["baseline_reactive_fallback_count"], 3)
        self.assertEqual(comparison["planned_individual_count"], 2)
        self.assertEqual(comparison["reactive_fallback_count"], 1)
        self.assertEqual(comparison["reactive_dependency_reduction_count"], 2)
        self.assertEqual(comparison["planned_individual_pct"], 66.7)
        self.assertEqual(comparison["reactive_remaining_pct"], 33.3)
        self.assertIn("baseline del plan", copy)
        self.assertIn("2 candidato(s)", copy)

    def test_plan_comparison_handles_empty_plan_without_overclaiming(self) -> None:
        plan = build_proactive_price_fetch_plan([])

        comparison = build_proactive_price_fetch_plan_comparison(plan)
        copy = format_proactive_price_fetch_plan_comparison(comparison)

        self.assertEqual(comparison["baseline_reactive_fallback_count"], 0)
        self.assertEqual(comparison["reactive_dependency_reduction_count"], 0)
        self.assertIn("no reduce dependencia", copy)
        self.assertIn("no cambia runtime, defaults, score, ranking, cache policy ni fetching", copy)


if __name__ == "__main__":
    unittest.main()
