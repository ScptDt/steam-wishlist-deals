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

    def test_parse_warm_cache_log_text_accepts_ascii_discount_threshold(self) -> None:
        text = "OK  411 deals (>=50%) - caché actualizada\n"

        summary = parse_warm_cache_log_text(text)

        self.assertEqual(summary.deals_count, 411)
        self.assertEqual(summary.min_discount, 50)

    def test_parse_warm_cache_log_text_extracts_direct_http_400_fallback(self) -> None:
        text = "Fallback individual directo por HTTP 400 repetido: 2,880 juegos en 144 tandas\n"

        summary = parse_warm_cache_log_text(text)
        output = format_warm_cache_summary(summary)

        self.assertEqual(summary.http_400_direct_fallback_count, 2880)
        self.assertEqual(summary.http_400_direct_fallback_batches, 144)
        self.assertIn("- Fallback directo HTTP 400: 2,880 juegos en 144 tandas", output)

    def test_parse_warm_cache_log_text_extracts_http_400_batch_breakdown(self) -> None:
        text = (
            "HTTP 400 en batch de 20 juegos; reduciendo lote\n"
            "HTTP 400 en batch de 10 juegos; reduciendo lote\n"
            "HTTP 400 en batch de 10 juegos; reduciendo lote\n"
            "HTTP 400 en batch, saltando\n"
            "HTTP 400 en batch, saltando\n"
        )

        summary = parse_warm_cache_log_text(text)
        output = format_warm_cache_summary(summary)

        self.assertEqual(summary.http_400_batch_size_counts, {"20": 1, "10": 2})
        self.assertEqual(summary.http_400_terminal_skip_count, 2)
        self.assertIn(
            "- Desglose HTTP 400: batch_size=10: 2 · batch_size=20: 1 · saltos a fallback=2",
            output,
        )

    def test_parse_warm_cache_log_text_extracts_http_400_diagnostic_samples(self) -> None:
        text = (
            'HTTP 400 diagnostic samples: '
            '[{"stage":"split","depth":0,"size":20,"appids":["10","20","30","40","50"]},'
            '{"stage":"fallback","depth":3,"size":2,"appids":["60"]}]\n'
        )

        summary = parse_warm_cache_log_text(text)
        output = format_warm_cache_summary(summary)

        self.assertEqual(summary.http_400_batch_samples[0]["stage"], "split")
        self.assertEqual(summary.http_400_batch_samples[0]["size"], 20)
        self.assertEqual(summary.http_400_batch_samples[1]["appids"], ["60"])
        self.assertIn(
            "HTTP 400 diagnostic samples: split depth=0 size=20 appids=10,20,30,40,… | fallback depth=3 size=2 appids=60",
            output,
        )

    def test_parse_warm_cache_log_text_extracts_fallback_workers_tuning(self) -> None:
        text = "Tuning precios activo: batch_size=20 · halving_limit=3 · fallback_workers=4\n"

        summary = parse_warm_cache_log_text(text)
        output = format_warm_cache_summary(summary)

        self.assertEqual(summary.batch_size, 20)
        self.assertEqual(summary.batch_halving_limit, 3)
        self.assertEqual(summary.individual_fallback_workers, 4)
        self.assertIn(
            "- Tuning precios: batch_size=20 · halving_limit=3 · fallback_workers=4",
            output,
        )

    def test_parse_warm_cache_log_text_extracts_adaptive_fallback_diagnostics(self) -> None:
        text = (
            "Fallback individual adaptativo: 1 bajadas de workers\n"
            "Fallback individual fallos por razón: http_429=12, no_price_data=34\n"
        )

        summary = parse_warm_cache_log_text(text)
        output = format_warm_cache_summary(summary)

        self.assertEqual(summary.individual_fallback_worker_downgrade_count, 1)
        self.assertEqual(
            summary.individual_fallback_failure_reasons,
            {"http_429": 12, "no_price_data": 34},
        )
        self.assertEqual(summary.individual_no_data, 34)
        self.assertIn("- Fallback adaptativo: 1 bajadas de workers", output)
        self.assertIn("- Fallback razones: http_429=12, no_price_data=34", output)

    def test_parse_warm_cache_log_text_extracts_rate_limit_waits(self) -> None:
        text = (
            "Rate limit — esperando 30s (intento 1/4)\n"
            "Rate limit — esperando 120s (intento 3/4)\n"
        )

        summary = parse_warm_cache_log_text(text)
        output = format_warm_cache_summary(summary)

        self.assertEqual(summary.rate_limit_wait_count, 2)
        self.assertEqual(summary.rate_limit_max_wait_seconds, 120)
        self.assertIn("- Rate-limit waits: 2 esperas (máx 120s)", output)

    def test_parse_warm_cache_log_text_extracts_fallback_budget_metrics(self) -> None:
        text = (
            "Fallback budget adaptativo: attempts=80 · no_data=72 · "
            "deferred=20 · old_cache_used=3 · reason=no_data_ratio:72/80\n"
        )

        summary = parse_warm_cache_log_text(text)
        output = format_warm_cache_summary(summary)

        self.assertEqual(summary.individual_attempts, 80)
        self.assertEqual(summary.individual_no_data, 72)
        self.assertEqual(summary.deferred_by_fallback_budget, 20)
        self.assertEqual(summary.old_cache_used_count, 3)
        self.assertEqual(summary.fallback_budget_reason, "no_data_ratio:72/80")
        self.assertIn(
            "- Fallback budget: attempts=80 · no_data=72 · deferred=20 · old_cache_used=3 · reason=no_data_ratio:72/80",
            output,
        )

    def test_parse_warm_cache_log_text_extracts_refresh_budget_metrics(self) -> None:
        text = (
            "Refresh budget resumible: processed=80 · deferred=20 · "
            "exhausted=true · next_resume_hint=12345\n"
        )

        summary = parse_warm_cache_log_text(text)
        output = format_warm_cache_summary(summary)

        self.assertEqual(summary.processed_count, 80)
        self.assertEqual(summary.deferred_by_time_budget, 20)
        self.assertEqual(summary.time_budget_exhausted, True)
        self.assertEqual(summary.next_resume_hint, "12345")
        self.assertIn(
            "- Refresh budget: processed=80 · deferred=20 · exhausted=true · next_resume_hint=12345",
            output,
        )
        self.assertIn(
            "- Cobertura parcial: se revalidaron 80/100 candidatos; quedan 20 pendientes/no revalidados en esta corrida.",
            output,
        )
        self.assertIn(
            "- Pendientes: no se sabe aún si los 20 pendientes tienen oferta.",
            output,
        )
        self.assertIn(
            "- Continuación sugerida: conserva el mismo cache dir y repite una corrida normal con `--warm-cache` para seguir desde el candidato 12345; no uses `--no-cache` salvo benchmark aprobado.",
            output,
        )
        self.assertIn(
            "processed=revalidado en esta corrida",
            output,
        )
        self.assertIn("fresh cache=dato válido", output)
        self.assertIn("failed/cooldown=no confirmado", output)

    def test_format_warm_cache_summary_clarifies_deferred_are_not_revalidated(self) -> None:
        summary = WarmCacheLogSummary(
            refresh_candidates=2935,
            processed_count=360,
            deferred_by_time_budget=2575,
            time_budget_exhausted=True,
            next_resume_hint="542050",
            deals_count=22,
        )

        output = format_warm_cache_summary(summary)

        self.assertIn(
            "Cobertura parcial: se revalidaron 360/2,935 candidatos",
            output,
        )
        self.assertIn(
            "2,575 pendientes/no revalidados en esta corrida",
            output,
        )
        self.assertIn(
            "Deals encontrados: 22 con la cobertura disponible",
            output,
        )
        self.assertIn(
            "no se sabe aún si los 2,575 pendientes tienen oferta",
            output,
        )
        self.assertIn(
            "conserva el mismo cache dir y repite una corrida normal con `--warm-cache` para seguir desde el candidato 542050",
            output,
        )
        self.assertIn("no uses `--no-cache` salvo benchmark aprobado", output)
        self.assertIn(
            "se detuvo a propósito por presupuesto",
            output,
        )
        self.assertNotIn("cobertura completa", output.lower())

    def test_format_warm_cache_summary_marks_no_pending_refresh_budget(self) -> None:
        summary = WarmCacheLogSummary(
            refresh_candidates=42,
            processed_count=42,
            deferred_by_time_budget=0,
            time_budget_exhausted=False,
        )

        output = format_warm_cache_summary(summary)

        self.assertIn(
            "- Cobertura refresh: 42/42 candidatos revalidados; sin pendientes por presupuesto.",
            output,
        )
        self.assertNotIn("Cobertura parcial", output)
        self.assertNotIn("no se sabe aún si", output)

    def test_parse_warm_cache_log_text_extracts_stale_revalidate_metrics(self) -> None:
        text = (
            "Stale-while-revalidate: stale_used=50 · stale_deferred=50 · "
            "ttl_jitter_buckets=0h=10, 1h=12\n"
        )

        summary = parse_warm_cache_log_text(text)
        output = format_warm_cache_summary(summary)

        self.assertEqual(summary.stale_used_count, 50)
        self.assertEqual(summary.stale_refresh_deferred_count, 50)
        self.assertEqual(
            summary.ttl_jitter_bucket_counts,
            {"0h": 10, "1h": 12},
        )
        self.assertIn(
            "- Stale-while-revalidate: 50 usados, 50 diferidos",
            output,
        )
        self.assertIn("- TTL jitter buckets: 0h=10, 1h=12", output)

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
            "| minimal.log | 2.1s (-82.1s) | 0 (-2,204) | 0 (-12) | 0 (sin cambio) | 0 (-3) | 0 (-20) | 0 (-13) | 0 (sin cambio) | 0 (sin cambio) |",
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

    def test_analyze_warm_cache_reports_batch_size_floor_for_repeated_http_400(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(degraded_batch_count=1, batch_size=1),
                WarmCacheLogSummary(degraded_batch_count=2, batch_size=1),
            ]
        )

        self.assertEqual(recommendations[0].code, "repeated-http-400")
        self.assertIn("ya estás en batch_size=1", recommendations[0].action)
        self.assertNotIn("STEAM_DEALS_PRICE_BATCH_SIZE=", recommendations[0].action)

    def test_analyze_warm_cache_marks_negative_lower_batch_experiment(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(degraded_batch_count=21),
                WarmCacheLogSummary(
                    degraded_batch_count=154,
                    batch_size=10,
                    rate_limit_wait_count=3,
                    rate_limit_max_wait_seconds=120,
                ),
            ]
        )

        codes = [recommendation.code for recommendation in recommendations]
        self.assertEqual(codes[0], "lower-batch-negative")
        self.assertIn("batch_size=10 generó 154 HTTP 400", recommendations[0].action)
        self.assertIn("batch_size=20", recommendations[0].action)
        self.assertIn("no bajes el default global", recommendations[0].action)
        self.assertNotIn("repeated-http-400", codes)
        self.assertIn("rate-limit-waits", codes)

    def test_analyze_warm_cache_recommends_http_400_diagnostic_samples_when_missing(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(degraded_batch_count=1),
                WarmCacheLogSummary(
                    degraded_batch_count=2,
                    http_400_terminal_skip_count=3,
                ),
            ]
        )

        action = next(
            recommendation.action
            for recommendation in recommendations
            if recommendation.code == "http-400-diagnostic-samples"
        )

        self.assertIn("STEAM_DEALS_HTTP_400_DIAGNOSTIC_SAMPLE_LIMIT=5", action)
        self.assertIn("3 saltos terminales", action)
        self.assertIn("antes de cambiar defaults", action)

    def test_analyze_warm_cache_recommends_fixture_when_http_400_samples_exist(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(degraded_batch_count=1),
                WarmCacheLogSummary(
                    degraded_batch_count=2,
                    http_400_batch_samples=[
                        {"stage": "split", "appids": ["10", "20"]},
                        {"stage": "fallback", "appids": ["20", "30"]},
                    ],
                ),
            ]
        )

        action = next(
            recommendation.action
            for recommendation in recommendations
            if recommendation.code == "http-400-samples-fixture"
        )
        codes = {recommendation.code for recommendation in recommendations}

        self.assertIn("2 muestras", action)
        self.assertIn("1 muestra terminal a fallback", action)
        self.assertIn("20×2", action)
        self.assertIn("fixture offline", action)
        self.assertIn("no cambies defaults", action)
        self.assertNotIn("http-400-diagnostic-samples", codes)

    def test_analyze_warm_cache_recognizes_http_400_direct_fallback(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(degraded_batch_count=21),
                WarmCacheLogSummary(
                    degraded_batch_count=21,
                    http_400_direct_fallback_count=20,
                    http_400_direct_fallback_batches=1,
                ),
            ]
        )

        codes = {recommendation.code for recommendation in recommendations}
        action = next(
            recommendation.action
            for recommendation in recommendations
            if recommendation.code == "http-400-direct-fallback-active"
        )

        self.assertIn("circuit breaker", action)
        self.assertIn("20 juegos en 1 tanda", action)
        self.assertIn("fixture offline", action)
        self.assertNotIn("http-400-diagnostic-samples", codes)
        self.assertNotIn("repeated-http-400", codes)

    def test_format_warm_cache_recommendations_mentions_rate_limit_waits(self) -> None:
        output = format_warm_cache_recommendations(
            [
                WarmCacheLogSummary(refresh_candidates=500, batch_size=20),
                WarmCacheLogSummary(
                    refresh_candidates=500,
                    batch_size=10,
                    rate_limit_wait_count=2,
                    rate_limit_max_wait_seconds=120,
                ),
            ]
        )

        self.assertIn("Rate-limit observado", output)
        self.assertIn("2 esperas", output)
        self.assertIn("máx 120s", output)

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

    def test_analyze_warm_cache_recommends_closeout_for_finished_queue_failures(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(processed_count=80, deferred_by_time_budget=20),
                WarmCacheLogSummary(
                    processed_count=100,
                    deferred_by_time_budget=0,
                    deferred_failure_count=3,
                    individual_fallback_count=20,
                    individual_fallback_failed_count=5,
                ),
            ]
        )

        action = next(
            recommendation.action
            for recommendation in recommendations
            if recommendation.code == "final-failures-closeout"
        )

        self.assertIn("cola resumible quedó sin deferred", action)
        self.assertIn("3 en cooldown", action)
        self.assertIn("5 sin oferta/datos", action)
        self.assertIn("misma caché", action)
        self.assertIn("`--warm-cache`", action)
        self.assertIn("No uses `--no-cache`", action)
        self.assertIn("no borres juegos", action)
        self.assertIn("no los excluyas automáticamente", action)

    def test_analyze_warm_cache_avoids_generic_fallback_when_cooldown_is_specific(self) -> None:
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

        codes = {recommendation.code for recommendation in recommendations}
        self.assertIn("fallback-no-data-cooldown", codes)
        self.assertNotIn("fallback-still-high", codes)

    def test_analyze_warm_cache_keeps_generic_fallback_when_no_specific_signal(self) -> None:
        recommendations = analyze_warm_cache_recommendations(
            [
                WarmCacheLogSummary(refresh_candidates=100),
                WarmCacheLogSummary(
                    refresh_candidates=80,
                    individual_fallback_count=20,
                    individual_fallback_failed_count=0,
                ),
            ]
        )

        self.assertIn(
            "fallback-still-high",
            {recommendation.code for recommendation in recommendations},
        )

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
