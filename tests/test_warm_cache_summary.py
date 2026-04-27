from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

from steam_deals_warm_cache_summary import (
    WarmCacheLogSummary,
    analyze_warm_cache_recommendations,
    format_warm_cache_comparison,
    format_warm_cache_recommendations,
    format_warm_cache_summary,
    main as warm_cache_summary_main,
    parse_warm_cache_log_file,
    parse_warm_cache_log_text,
)


FIXTURES = Path(__file__).parent / "fixtures" / "warm_cache_logs"


class WarmCacheSummaryTests(unittest.TestCase):
    def test_parse_warm_cache_log_extracts_comparable_metrics(self) -> None:
        summary = parse_warm_cache_log_file(FIXTURES / "full.log")

        self.assertEqual(summary.cache_status, "valid")
        self.assertEqual(summary.cache_age_hours, 22.9)
        self.assertEqual(summary.refresh_candidates, 2204)
        self.assertEqual(summary.missing_count, 2110)
        self.assertEqual(summary.stale_count, 94)
        self.assertEqual(summary.deferred_failure_count, 12)
        self.assertEqual(summary.degraded_batch_count, 3)
        self.assertEqual(summary.individual_fallback_count, 20)
        self.assertEqual(summary.individual_fallback_batches, 2)
        self.assertEqual(summary.individual_fallback_resolved_count, 7)
        self.assertEqual(summary.individual_fallback_failed_count, 13)
        self.assertEqual(summary.batch_size, 8)
        self.assertEqual(summary.batch_halving_limit, 5)
        self.assertEqual(summary.deals_count, 411)
        self.assertEqual(summary.min_discount, 50)
        self.assertEqual(summary.wishlist_count, 2941)
        self.assertEqual(summary.elapsed_seconds, 84.2)
        self.assertEqual(
            summary.cache_path,
            "/home/adolfo/.cache/steam_deals/prices_cache.json",
        )

    def test_parse_warm_cache_log_defaults_missing_optional_counts_to_zero(self) -> None:
        summary = parse_warm_cache_log_file(FIXTURES / "minimal.log")

        self.assertEqual(summary.cache_status, "valid")
        self.assertEqual(summary.refresh_candidates, 0)
        self.assertEqual(summary.missing_count, 0)
        self.assertEqual(summary.stale_count, 0)
        self.assertEqual(summary.deferred_failure_count, 0)
        self.assertEqual(summary.degraded_batch_count, 0)
        self.assertEqual(summary.individual_fallback_count, 0)
        self.assertIsNone(summary.batch_size)
        self.assertIsNone(summary.batch_halving_limit)

    def test_parse_warm_cache_log_text_ignores_ansi_sequences(self) -> None:
        text = "\x1b[32m  Warm cache listo en 3.5s\x1b[0m\n"

        summary = parse_warm_cache_log_text(text)

        self.assertEqual(summary.elapsed_seconds, 3.5)

    def test_format_warm_cache_summary_outputs_bitacora_friendly_markdown(self) -> None:
        summary = parse_warm_cache_log_file(FIXTURES / "full.log")

        output = format_warm_cache_summary(summary)

        self.assertIn("## Warm-cache summary", output)
        self.assertIn("- Duración: 84.2s", output)
        self.assertIn("- Wishlist/deals: 2,941 / 411", output)
        self.assertIn(
            "- Refresh candidates: 2,204 (2,110 nuevos, 94 stale, 12 cooldown)",
            output,
        )
        self.assertIn(
            "- Fallback individual: 20 juegos en 2 tandas (7 resueltos, 13 sin oferta/datos)",
            output,
        )

    def test_format_warm_cache_comparison_outputs_delta_table_for_multiple_logs(self) -> None:
        summaries = [
            parse_warm_cache_log_file(FIXTURES / "full.log"),
            parse_warm_cache_log_file(FIXTURES / "minimal.log"),
        ]

        output = format_warm_cache_comparison(summaries)

        self.assertIn("## Warm-cache comparison", output)
        self.assertIn(
            "| minimal.log | 2.1s (-82.1s) | 0 (-2,204) | 0 (-12) | 0 (-3) | 0 (-20) | 0 (-13) |",
            output,
        )

    def test_analyze_warm_cache_recommends_batch_tuning_for_repeated_http_400(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(degraded_batch_count=2, refresh_candidates=100),
                WarmCacheLogSummary(degraded_batch_count=3, refresh_candidates=80),
            ]
        )

        self.assertEqual(recommendations[0].code, "repeated-http-400")
        self.assertIn("STEAM_DEALS_PRICE_BATCH_SIZE", recommendations[0].action)
        self.assertIn("STEAM_DEALS_PRICE_BATCH_SIZE=10", recommendations[0].action)

    def test_analyze_warm_cache_recommends_half_detected_batch_size(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(degraded_batch_count=1, batch_size=8),
                WarmCacheLogSummary(degraded_batch_count=2, batch_size=8),
            ]
        )

        self.assertEqual(recommendations[0].code, "repeated-http-400")
        self.assertIn("STEAM_DEALS_PRICE_BATCH_SIZE=4", recommendations[0].action)
        self.assertIn("actual/base 8", recommendations[0].action)

    def test_analyze_warm_cache_recommends_cooldown_for_no_data_fallback(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(refresh_candidates=100),
                WarmCacheLogSummary(
                    refresh_candidates=80,
                    individual_fallback_count=20,
                    individual_fallback_failed_count=13,
                ),
            ]
        )

        self.assertIn(
            "fallback-no-data-cooldown",
            {recommendation.code for recommendation in recommendations},
        )
        action = next(
            recommendation.action
            for recommendation in recommendations
            if recommendation.code == "fallback-no-data-cooldown"
        )
        self.assertIn("13/20", action)
        self.assertIn("2h", action)

    def test_analyze_warm_cache_marks_effective_cache_when_refreshes_drop(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                parse_warm_cache_log_file(FIXTURES / "full.log"),
                parse_warm_cache_log_file(FIXTURES / "minimal.log"),
            ]
        )

        self.assertIn(
            "cache-effective",
            {recommendation.code for recommendation in recommendations},
        )

    def test_format_warm_cache_recommendations_outputs_stable_no_action(self) -> None:
        output = format_warm_cache_recommendations(
            [
                WarmCacheLogSummary(refresh_candidates=10, elapsed_seconds=5.0),
                WarmCacheLogSummary(refresh_candidates=9, elapsed_seconds=5.2),
            ]
        )

        self.assertIn("## Warm-cache next actions", output)
        self.assertIn("Sin acción automática", output)

    def test_cli_prints_markdown_summary_for_log_path(self) -> None:
        stdout = io.StringIO()

        exit_code = warm_cache_summary_main([str(FIXTURES / "minimal.log")], stdout=stdout)

        self.assertEqual(exit_code, 0)
        self.assertIn("## Warm-cache summary", stdout.getvalue())
        self.assertIn("- Batches degradados HTTP 400: 0", stdout.getvalue())

    def test_cli_appends_comparison_when_multiple_markdown_logs_are_passed(self) -> None:
        stdout = io.StringIO()

        exit_code = warm_cache_summary_main(
            [str(FIXTURES / "full.log"), str(FIXTURES / "minimal.log")],
            stdout=stdout,
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("## Warm-cache comparison", stdout.getvalue())
        self.assertIn("## Warm-cache next actions", stdout.getvalue())
        self.assertIn("minimal.log", stdout.getvalue())

    def test_cli_can_emit_json_summary_for_one_log(self) -> None:
        stdout = io.StringIO()

        exit_code = warm_cache_summary_main(
            [str(FIXTURES / "full.log"), "--json"], stdout=stdout
        )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["refresh_candidates"], 2204)
        self.assertEqual(payload["individual_fallback_failed_count"], 13)


if __name__ == "__main__":
    unittest.main()
