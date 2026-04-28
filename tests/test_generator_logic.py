from __future__ import annotations

import json
import time
import unittest
from datetime import date
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import urllib.error

from steam_deals_itad import (
    itad_get_active_bundles as module_itad_get_active_bundles,
    itad_get_current_prices as module_itad_get_current_prices,
    itad_get_store_lows as module_itad_get_store_lows,
    itad_lookup_games as module_itad_lookup_games,
)
from steam_deals_config import (
    build_parser as module_build_parser,
    get_config as module_get_config,
    load_user_config as module_load_user_config,
    save_user_config as module_save_user_config,
)
from steam_deals_alerts import build_smart_alert_counts as module_build_smart_alert_counts
from steam_deals_cache_policy import (
    clear_cache_files as module_clear_cache_files,
    select_global_cache as module_select_global_cache,
    select_scoped_cache as module_select_scoped_cache,
)
from steam_deals_enrichment import (
    fetch_achievements as module_fetch_achievements,
    fetch_anticheat_db as module_fetch_anticheat_db,
    fetch_reviews as module_fetch_reviews,
    load_tags_cache as module_load_tags_cache,
)
from steam_deals_enrichment_orchestration import (
    build_enrichment_orchestration_contract as module_build_enrichment_orchestration_contract,
    build_global_cache_runtime as module_build_global_cache_runtime,
    build_message_formatters as module_build_message_formatters,
    build_progress_callbacks as module_build_progress_callbacks,
    build_scoped_cache_runtime as module_build_scoped_cache_runtime,
    run_achievements_orchestration as module_run_achievements_orchestration,
    run_deck_orchestration as module_run_deck_orchestration,
    run_protondb_anticheat_orchestration as module_run_protondb_anticheat_orchestration,
    run_reviews_orchestration as module_run_reviews_orchestration,
    run_tags_orchestration as module_run_tags_orchestration,
)
from steam_deals_itad_orchestration import (
    build_itad_orchestration_contract as module_build_itad_orchestration_contract,
    build_itad_runtime as module_build_itad_runtime,
    build_message_formatters as module_build_itad_message_formatters,
    build_progress_callbacks as module_build_itad_progress_callbacks,
    run_itad_orchestration as module_run_itad_orchestration,
)
from steam_deals_post_processing import (
    build_callbacks as module_build_post_processing_callbacks,
    build_message_formatters as module_build_post_processing_message_formatters,
    build_post_processing_contract as module_build_post_processing_contract,
    build_runtime as module_build_post_processing_runtime,
    run_post_processing as module_run_post_processing,
)
from steam_deals_engagement_post_run import (
    build_callbacks as module_build_engagement_callbacks,
    build_engagement_contract as module_build_engagement_contract,
    build_message_formatters as module_build_engagement_message_formatters,
    build_runtime as module_build_engagement_runtime,
    run_engagement_post_run as module_run_engagement_post_run,
)
from steam_deals_family import (
    FamilyContext as ModuleFamilyContext,
    build_family_renderer_kwargs as module_build_family_renderer_kwargs,
    cross_hltb_with_family_context as module_cross_hltb_with_family_context,
)
from steam_deals_prices import (
    count_refresh_candidates as module_count_refresh_candidates,
    get_deals_from_wishlist as module_get_deals_from_wishlist,
    load_price_cache as module_load_price_cache,
    parse_release_year as module_parse_release_year,
    process_app_entry as module_process_app_entry,
    save_price_cache as module_save_price_cache,
)
from steam_deals_steam_api import (
    build_active_promo_context as module_build_active_promo_context,
    classify_steam_promo_message as module_classify_steam_promo_message,
    compare_wishlists as module_compare_wishlists,
    get_active_promo_context as module_get_active_promo_context,
    get_active_sale as module_get_active_sale,
    get_owned_games as module_get_owned_games,
    get_wishlist as module_get_wishlist,
    load_family_games as module_load_family_games,
    resolve_profile_display_name as module_resolve_profile_display_name,
    resolve_steam_id as module_resolve_steam_id,
)
from steam_deals_notifications import (
    build_notification_summary as module_build_notification_summary,
    send_discord as module_send_discord,
    send_notifications as module_send_notifications,
    send_telegram as module_send_telegram,
)
from steam_deals_presentation import (
    achievements_badge as module_achievements_badge,
    get_top_tags as module_get_top_tags,
    group_by_tier as module_group_by_tier,
    linux_badge as module_linux_badge,
    multiplayer_badges as module_multiplayer_badges,
    players_badge as module_players_badge,
)
from steam_deals_run_output import (
    OutputArtifactPaths as ModuleOutputArtifactPaths,
    OutputArtifactPayloads as ModuleOutputArtifactPayloads,
    build_output_artifact_paths as module_build_output_artifact_paths,
    emit_final_closeout as module_emit_final_closeout,
    build_final_summary as module_build_final_summary,
    build_output_md_path as module_build_output_md_path,
    build_share_output_path as module_build_share_output_path,
    find_latest_artifact as module_find_latest_artifact,
    resolve_previous_context as module_resolve_previous_context,
    write_output_artifacts as module_write_output_artifacts,
    write_artifact as module_write_artifact,
)
from steam_deals_history import save_run_history as module_save_run_history
from steam_deals_runtime_reporting import (
    emit_event as module_emit_event,
    report_step as module_report_step,
    safe_symbol as module_safe_symbol,
)
from steam_deals_scheduler import (
    parse_schedule_hours as module_parse_schedule_hours,
    run_scheduled as module_run_scheduled,
)
from steam_deals_watchlist import (
    check_watchlist_alerts as module_check_watchlist_alerts,
    handle_watchlist_command as module_handle_watchlist_command,
    load_watchlist as module_load_watchlist,
    save_watchlist as module_save_watchlist,
)
from steam_deals_generator import (
    _format_cli_user_error,
    _handle_cli_value_error,
    _looks_like_placeholder_vanity,
    _resolve_max_workers,
    _run_entrypoint,
    apply_filters,
    analyze_trends,
    build_warm_cache_emit,
    build_final_summary as generator_build_final_summary,
    build_smart_alert_counts as generator_build_smart_alert_counts,
    build_gift_ideas,
    compute_budget_picks,
    compute_deal_comparison,
    compute_value_score,
    cross_hltb_with_deals,
    filter_by_genres,
    format_trend,
    generate_html,
    generate_json,
    generate_md,
    generate_share_html,
    is_same_game,
    load_previous_deal_appids,
    parse_hltb,
    resolve_price_fetch_tuning,
    run_price_cache_stage,
    run_warm_cache_mode,
    rank_top_picks,
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


class ConfigTests(unittest.TestCase):
    def test_load_and_save_user_config_roundtrip(self) -> None:
        config = {"vanity": "gaben", "discount": 50}

        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "steam_deals.json"
            module_save_user_config(config_path, config)
            loaded = module_load_user_config(config_path)

        self.assertEqual(loaded, config)

    def test_get_config_returns_expected_tuple_from_args(self) -> None:
        class FakeStdin:
            def isatty(self):
                return False

        result = module_get_config(
            script_path=Path("/tmp/fake_script.py"),
            load_user_config_fn=lambda: {},
            save_user_config_fn=lambda _cfg: None,
            handle_watchlist_command_fn=lambda _args: None,
            input_fn=lambda _prompt: "",
            stdin=FakeStdin(),
            exit_fn=lambda _code: None,
            argv=[
                "--vanity",
                "gaben",
                "--output",
                "/tmp/out",
                "--discount",
                "30",
                "--genre",
                "indie",
                "roguelike",
                "--top",
                "5",
                "--schedule",
                "6",
                "--max-workers",
                "16",
                "--md-frontmatter",
                "--warm-cache",
                "--alert-rise-pct",
                "12.5",
                "--alert-global-margin-pct",
                "3",
                "--alert-score-min",
                "80",
            ],
        )

        self.assertEqual(result[3], "gaben")
        self.assertEqual(result[5], Path("/tmp/out"))
        self.assertEqual(result[6], 30)
        self.assertEqual(result[7], ["indie", "roguelike"])
        self.assertEqual(result[11]["top"], 5)
        self.assertEqual(result[11]["schedule"], 6.0)
        self.assertEqual(result[11]["max_workers"], 16)
        self.assertEqual(result[11]["md_frontmatter"], True)
        self.assertEqual(result[11]["warm_cache"], True)
        self.assertEqual(result[11]["alert_rise_pct"], 12.5)
        self.assertEqual(result[11]["alert_global_margin_pct"], 3.0)
        self.assertEqual(result[11]["alert_score_min"], 80.0)

    def test_build_parser_documents_max_workers_default_as_16(self) -> None:
        parser = module_build_parser()
        action = next(
            action for action in parser._actions if "--max-workers" in action.option_strings
        )

        self.assertEqual(action.help, "Workers de fetch paralelo para enrichment (default: 16)")

    def test_resolve_max_workers_falls_back_to_new_default_of_16(self) -> None:
        self.assertEqual(_resolve_max_workers(None, 16), 16)
        self.assertEqual(_resolve_max_workers("0", 16), 16)
        self.assertEqual(_resolve_max_workers("bad", 16), 16)

    def test_get_config_handles_watchlist_and_exits_early(self) -> None:
        calls = []

        def fake_exit(code):
            raise SystemExit(code)

        with self.assertRaises(SystemExit):
            module_get_config(
                script_path=Path("/tmp/fake_script.py"),
                load_user_config_fn=lambda: {},
                save_user_config_fn=lambda _cfg: None,
                handle_watchlist_command_fn=lambda args: calls.append(args),
                input_fn=lambda _prompt: "",
                stdin=None,
                exit_fn=fake_exit,
                argv=["--watchlist", "list"],
            )

        self.assertEqual(calls, [["list"]])


class CliErrorHandlingTests(unittest.TestCase):
    def test_detects_placeholder_vanity_from_raw_or_url(self) -> None:
        self.assertEqual(_looks_like_placeholder_vanity("TU_VANITY_URL"), True)
        self.assertEqual(
            _looks_like_placeholder_vanity(
                "https://steamcommunity.com/id/TU_VANITY_URL/"
            ),
            True,
        )
        self.assertEqual(_looks_like_placeholder_vanity("gaben"), False)

    def test_format_cli_user_error_for_placeholder_vanity_is_actionable(self) -> None:
        message = _format_cli_user_error(
            ValueError("No se pudo resolver el perfil: TU_VANITY_URL"),
            "TU_VANITY_URL",
        )

        self.assertIn("placeholder `TU_VANITY_URL`", message)
        self.assertIn("Steam ID de 17 dígitos", message)

    def test_handle_cli_value_error_emits_warm_cache_follow_up(self) -> None:
        emitted = []

        result = _handle_cli_value_error(
            ValueError("No se pudo acceder a la wishlist (HTTP 403). ¿Es privada?"),
            "gaben",
            warm_cache=True,
            emit=emitted.append,
            err_fn=lambda text: f"ERR:{text}",
            dim_fn=lambda text: f"DIM:{text}",
        )

        self.assertEqual(result, 1)
        self.assertEqual(emitted[0], "")
        self.assertIn("ERR:No se pudo acceder a la wishlist", emitted[1])
        self.assertIn("wishlist sea pública", emitted[1])
        self.assertIn("Warm-cache cancelado", emitted[2])

    def test_run_entrypoint_returns_main_status_without_schedule(self) -> None:
        scheduled = []

        result = _run_entrypoint(
            ["prog"],
            main_fn=lambda: 1,
            run_scheduled_fn=lambda: scheduled.append("scheduled"),
        )

        self.assertEqual(result, 1)
        self.assertEqual(scheduled, [])

    def test_run_entrypoint_delegates_to_scheduler_when_schedule_flag_present(
        self,
    ) -> None:
        scheduled = []

        result = _run_entrypoint(
            ["prog", "--schedule", "1"],
            main_fn=lambda: 1,
            run_scheduled_fn=lambda: scheduled.append("scheduled"),
        )

        self.assertEqual(result, 0)
        self.assertEqual(scheduled, ["scheduled"])

    def test_run_entrypoint_ignores_invalid_schedule_value(self) -> None:
        scheduled = []

        result = _run_entrypoint(
            ["prog", "--schedule", "oops"],
            main_fn=lambda: 1,
            run_scheduled_fn=lambda: scheduled.append("scheduled"),
        )

        self.assertEqual(result, 1)
        self.assertEqual(scheduled, [])


class WarmCacheTests(unittest.TestCase):
    @staticmethod
    def _price_cache_entry(
        *,
        name: str,
        discount_percent: int,
        price_final: str,
        price_original: str,
        price_final_raw: int,
        fetched_at: float,
    ) -> dict:
        return {
            "name": name,
            "type": "game",
            "discount_percent": discount_percent,
            "price_final": price_final,
            "price_original": price_original,
            "price_final_raw": price_final_raw,
            "genres": [],
            "release_year": 2024,
            "description": "",
            "linux_native": False,
            "metacritic_score": None,
            "metacritic_url": "",
            "categories": [2],
            "_fetched_at": fetched_at,
        }

    def test_run_price_cache_stage_updates_cache_when_fetching_new_data(self) -> None:
        emitted = []
        saved = []
        cleared = []
        forwarded_emit = []

        def fake_get_deals(_wishlist, fetched_cache, _steam_id, **kwargs):
            forwarded_emit.append(kwargs.get("emit_fn"))
            fetched_cache["10"] = {"discount_percent": 70}
            return ([{"appid": "10"}], 1)

        result = run_price_cache_stage(
            ["10"],
            "steam-id",
            no_cache=False,
            min_discount=50,
            rate_limit=1.5,
            load_price_cache_fn=lambda _steam_id: ({}, 0.0),
            select_cache_fn=lambda *_args, **_kwargs: SimpleNamespace(
                status="empty", cache={}, missing_ids=("10",)
            ),
            clear_cache_files_fn=lambda paths: cleared.extend(paths) or tuple(paths),
            get_deals_from_wishlist_fn=fake_get_deals,
            save_price_cache_fn=lambda steam_id, fetched: saved.append(
                (steam_id, dict(fetched))
            ),
            emit_fn=emitted.append,
        )

        self.assertEqual(result["n_fetched"], 1)
        self.assertEqual(result["cache_status"], "empty")
        self.assertEqual(saved, [("steam-id", {"10": {"discount_percent": 70}})])
        self.assertEqual(cleared, [])
        self.assertEqual(forwarded_emit, [emitted.append])
        self.assertTrue(any("Sin caché" in line for line in emitted))
        self.assertTrue(any("caché actualizada" in line for line in emitted))

    def test_run_price_cache_stage_reuses_valid_cache_without_saving(self) -> None:
        emitted = []
        saved = []
        cached_payload = {"10": {"discount_percent": 70}}

        result = run_price_cache_stage(
            ["10"],
            "steam-id",
            no_cache=False,
            min_discount=50,
            rate_limit=1.5,
            load_price_cache_fn=lambda _steam_id: (cached_payload, 2.0),
            select_cache_fn=lambda *_args, **_kwargs: SimpleNamespace(
                status="valid", cache=cached_payload, missing_ids=()
            ),
            clear_cache_files_fn=lambda _paths: (),
            get_deals_from_wishlist_fn=lambda *_args, **_kwargs: ([{"appid": "10"}], 0),
            save_price_cache_fn=lambda steam_id, fetched: saved.append(
                (steam_id, fetched)
            ),
            emit_fn=emitted.append,
        )

        self.assertEqual(result["n_fetched"], 0)
        self.assertEqual(result["cache_status"], "valid")
        self.assertEqual(saved, [])
        self.assertTrue(any("Caché válida" in line for line in emitted))
        self.assertTrue(any("desde caché" in line for line in emitted))

    def test_run_warm_cache_mode_reports_summary_and_target_path(self) -> None:
        steps = []
        emitted = []

        result = run_warm_cache_mode(
            ["10", "20"],
            "steam-id",
            no_cache=False,
            min_discount=50,
            rate_limit=1.5,
            started_at=0.0,
            step_fn=steps.append,
            emit_fn=emitted.append,
            run_price_cache_stage_fn=lambda *_args, **_kwargs: {
                "deals": [{"appid": "10"}],
                "n_fetched": 1,
                "cache_age": 0.0,
                "cache_status": "empty",
                "cache_path": Path("/tmp/cache/prices_cache.json"),
            },
        )

        self.assertEqual(steps, ["Precalentando caché de precios..."])
        self.assertEqual(result["cache_status"], "empty")
        self.assertTrue(any("Warm cache listo" in line for line in emitted))
        self.assertTrue(any("Wishlist: 2 juegos" in line for line in emitted))
        self.assertTrue(
            any(
                Path("/tmp/cache/prices_cache.json").as_posix()
                in line.replace("\\", "/")
                for line in emitted
            )
        )

    def test_run_price_cache_stage_reports_refresh_count_and_hands_off_ids(self) -> None:
        emitted = []
        received = {}
        now_ts = 1_700_000_000.0
        fetched_cache = {
            "10": self._price_cache_entry(
                name="Alpha",
                discount_percent=70,
                price_final="$10",
                price_original="$20",
                price_final_raw=1000,
                fetched_at=now_ts,
            ),
            "20": self._price_cache_entry(
                name="Bravo",
                discount_percent=60,
                price_final="$8",
                price_original="$20",
                price_final_raw=800,
                fetched_at=now_ts - (25 * 3600),
            ),
        }

        def fake_get_deals(_wishlist, _cache, _steam_id, **kwargs):
            received["refresh_ids"] = tuple(kwargs.get("refresh_ids") or ())
            return ([{"appid": "10"}, {"appid": "20"}, {"appid": "30"}], 2)

        result = run_price_cache_stage(
            ["10", "20", "30"],
            "steam-id",
            no_cache=False,
            min_discount=50,
            rate_limit=1.5,
            load_price_cache_fn=lambda _steam_id: (fetched_cache, 2.0),
            select_cache_fn=module_select_scoped_cache,
            clear_cache_files_fn=lambda _paths: (),
            get_deals_from_wishlist_fn=fake_get_deals,
            save_price_cache_fn=lambda *_args, **_kwargs: None,
            emit_fn=emitted.append,
            current_time_fn=lambda: now_ts,
        )

        self.assertEqual(received["refresh_ids"], ("20", "30"))
        self.assertEqual(result["n_fetched"], 2)
        self.assertTrue(any("2 por fetchear" in line for line in emitted))

    def test_run_price_cache_stage_preserves_expired_cache_payload(self) -> None:
        emitted = []
        received = {}
        now_ts = 1_700_000_000.0
        fetched_cache = {
            "10": self._price_cache_entry(
                name="Alpha",
                discount_percent=70,
                price_final="$10",
                price_original="$20",
                price_final_raw=1000,
                fetched_at=now_ts - (25 * 3600),
            ),
            "20": self._price_cache_entry(
                name="Bravo",
                discount_percent=60,
                price_final="$8",
                price_original="$20",
                price_final_raw=800,
                fetched_at=now_ts,
            ),
            "40": {"_failed_at": now_ts - 3600, "_failure_reason": "no_price_data"},
        }

        def fake_get_deals(_wishlist, cache, _steam_id, **kwargs):
            received["cache"] = dict(cache)
            received["refresh_ids"] = tuple(kwargs.get("refresh_ids") or ())
            return ([{"appid": "10"}, {"appid": "20"}], len(received["refresh_ids"]))

        result = run_price_cache_stage(
            ["10", "20", "30", "40"],
            "steam-id",
            no_cache=False,
            min_discount=50,
            rate_limit=1.5,
            load_price_cache_fn=lambda _steam_id: (fetched_cache, 48.0),
            select_cache_fn=module_select_scoped_cache,
            clear_cache_files_fn=lambda _paths: (),
            get_deals_from_wishlist_fn=fake_get_deals,
            save_price_cache_fn=lambda *_args, **_kwargs: None,
            emit_fn=emitted.append,
            current_time_fn=lambda: now_ts,
        )

        self.assertEqual(result["cache_status"], "expired")
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["stale_count"], 1)
        self.assertEqual(result["deferred_failure_count"], 1)
        self.assertEqual(received["refresh_ids"], ("10", "30"))
        self.assertIn("20", received["cache"])
        self.assertIn("40", received["cache"])
        self.assertTrue(any("Caché expirada" in line for line in emitted))
        self.assertTrue(any("2 por revalidar" in line for line in emitted))

    def test_run_price_cache_stage_default_selector_accepts_expired_payload_opt_in(self) -> None:
        emitted = []
        now_ts = 1_700_000_000.0
        fetched_cache = {
            "10": self._price_cache_entry(
                name="Alpha",
                discount_percent=70,
                price_final="$10",
                price_original="$20",
                price_final_raw=1000,
                fetched_at=now_ts,
            )
        }

        result = run_price_cache_stage(
            ["10"],
            "steam-id",
            no_cache=False,
            min_discount=50,
            rate_limit=1.5,
            load_price_cache_fn=lambda _steam_id: (fetched_cache, 48.0),
            clear_cache_files_fn=lambda _paths: (),
            get_deals_from_wishlist_fn=lambda _wishlist, cache, _steam_id, **_kwargs: (
                [{"appid": "10"}] if "10" in cache else [],
                0,
            ),
            save_price_cache_fn=lambda *_args, **_kwargs: None,
            emit_fn=emitted.append,
            current_time_fn=lambda: now_ts,
        )

        self.assertEqual(result["cache_status"], "expired")
        self.assertEqual(result["refresh_candidate_count"], 0)
        self.assertTrue(any("Caché expirada" in line for line in emitted))
        self.assertTrue(any("desde caché" in line for line in emitted))

    def test_run_price_cache_stage_emits_observability_counts_and_tuning_info(
        self,
    ) -> None:
        emitted = []
        received = {}
        now_ts = 1_700_000_000.0
        fetched_cache = {
            "10": self._price_cache_entry(
                name="Alpha",
                discount_percent=70,
                price_final="$10",
                price_original="$20",
                price_final_raw=1000,
                fetched_at=now_ts,
            ),
            "20": self._price_cache_entry(
                name="Bravo",
                discount_percent=60,
                price_final="$8",
                price_original="$20",
                price_final_raw=800,
                fetched_at=now_ts - (25 * 3600),
            ),
        }

        def fake_get_deals(_wishlist, _cache, _steam_id, **kwargs):
            stats = kwargs.get("stats_out") or {}
            stats["degraded_batch_count"] = 3
            stats["individual_fallback_count"] = 20
            stats["individual_fallback_batches"] = 2
            stats["individual_fallback_resolved_count"] = 7
            stats["individual_fallback_failed_count"] = 13
            received["batch_size"] = kwargs.get("batch_size")
            received["max_batch_halving"] = kwargs.get("max_batch_halving")
            return ([{"appid": "10"}, {"appid": "20"}, {"appid": "30"}], 2)

        result = run_price_cache_stage(
            ["10", "20", "30"],
            "steam-id",
            no_cache=False,
            min_discount=50,
            rate_limit=1.5,
            load_price_cache_fn=lambda _steam_id: (fetched_cache, 2.0),
            select_cache_fn=module_select_scoped_cache,
            clear_cache_files_fn=lambda _paths: (),
            get_deals_from_wishlist_fn=fake_get_deals,
            save_price_cache_fn=lambda *_args, **_kwargs: None,
            emit_fn=emitted.append,
            current_time_fn=lambda: now_ts,
            env={
                "STEAM_DEALS_PRICE_BATCH_SIZE": "8",
                "STEAM_DEALS_PRICE_BATCH_HALVING_LIMIT": "5",
            },
        )

        self.assertEqual(received["batch_size"], 8)
        self.assertEqual(received["max_batch_halving"], 5)
        self.assertEqual(result["refresh_candidate_count"], 2)
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["stale_count"], 1)
        self.assertEqual(result["degraded_batch_count"], 3)
        self.assertEqual(result["individual_fallback_count"], 20)
        self.assertEqual(result["individual_fallback_resolved_count"], 7)
        self.assertEqual(result["individual_fallback_failed_count"], 13)
        self.assertEqual(result["batch_size"], 8)
        self.assertEqual(result["batch_halving_limit"], 5)
        self.assertTrue(
            any("Refresh candidates: 2 (1 nuevos, 1 stale)" in line for line in emitted)
        )
        self.assertTrue(
            any("Tuning precios activo: batch_size=8 · halving_limit=5" in line for line in emitted)
        )
        self.assertTrue(
            any("Batches degradados por HTTP 400: 3" in line for line in emitted)
        )
        self.assertTrue(
            any(
                "Fallback individual aplicado a 20 juegos en 2 tandas (7 resueltos, 13 sin oferta/datos)" in line
                for line in emitted
            )
        )

    def test_get_deals_from_wishlist_skips_fetch_when_all_entries_are_fresh(
        self,
    ) -> None:
        now_ts = 1_700_000_000.0
        emitted = []
        cache_entry = self._price_cache_entry(
            name="Alpha",
            discount_percent=70,
            price_final="$10",
            price_original="$20",
            price_final_raw=1000,
            fetched_at=now_ts,
        )

        deals, n_fetched = module_get_deals_from_wishlist(
            ["10"],
            {"10": cache_entry},
            "steam-id",
            min_discount=50,
            rate_limit=0.0,
            get_json=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("No debería iniciar fetch por batch")
            ),
            sleep_fn=lambda _delay: None,
            monotonic_fn=lambda: 0.0,
            save_price_cache_fn=lambda *_args, **_kwargs: None,
            fetch_single_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("No debería iniciar fetch individual")
            ),
            process_app_entry_fn=module_process_app_entry,
            emit=emitted.append,
            warn=lambda text: text,
            dim=lambda text: text,
            bar_fill="#",
            bar_empty="-",
            color_green="",
            color_dim="",
            color_reset="",
            batch_size=20,
            entry_ttl_hours=24.0,
            current_time_fn=lambda: now_ts + 60,
        )

        self.assertEqual(n_fetched, 0)
        self.assertEqual([deal["appid"] for deal in deals], ["10"])
        self.assertFalse(any("Fetching" in line for line in emitted))

    def test_get_deals_from_wishlist_defers_recent_failed_entries_without_refetching(
        self,
    ) -> None:
        now_ts = 1_700_000_000.0
        emitted = []
        stats = {}
        fetched_cache = {
            "10": {"_failed_at": now_ts - 60, "_failure_reason": "no_price_data"}
        }

        deals, n_fetched = module_get_deals_from_wishlist(
            ["10"],
            fetched_cache,
            "steam-id",
            min_discount=50,
            rate_limit=0.0,
            get_json=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("No debería iniciar fetch por batch")
            ),
            sleep_fn=lambda _delay: None,
            monotonic_fn=lambda: 0.0,
            save_price_cache_fn=lambda *_args, **_kwargs: None,
            fetch_single_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("No debería iniciar fetch individual")
            ),
            process_app_entry_fn=module_process_app_entry,
            emit=emitted.append,
            warn=lambda text: text,
            dim=lambda text: text,
            current_time_fn=lambda: now_ts,
            stats_out=stats,
        )

        self.assertEqual(n_fetched, 0)
        self.assertEqual(deals, [])
        self.assertEqual(stats["deferred_failure_count"], 1)
        self.assertFalse(any("Fetching" in line for line in emitted))

    def test_get_deals_from_wishlist_reports_fetch_count_for_missing_and_stale(
        self,
    ) -> None:
        now_ts = 1_700_000_000.0
        emitted = []
        fetched_cache = {
            "10": self._price_cache_entry(
                name="Alpha",
                discount_percent=70,
                price_final="$10",
                price_original="$20",
                price_final_raw=1000,
                fetched_at=now_ts,
            ),
            "20": self._price_cache_entry(
                name="Bravo",
                discount_percent=60,
                price_final="$8",
                price_original="$20",
                price_final_raw=800,
                fetched_at=now_ts - (25 * 3600),
            ),
        }

        def fake_get_json(_url, headers=None):
            self.assertEqual(headers, {"User-Agent": "Mozilla/5.0"})
            return {
                "20": {
                    "success": True,
                    "data": {
                        "name": "Bravo",
                        "type": "game",
                        "price_overview": {
                            "discount_percent": 60,
                            "final_formatted": "$8",
                            "initial_formatted": "$20",
                            "final": 800,
                        },
                        "genres": [],
                        "platforms": {"linux": False},
                        "release_date": {"coming_soon": False, "date": "Jan 1, 2023"},
                        "metacritic": {},
                        "categories": [{"id": 2}],
                    },
                },
                "30": {
                    "success": True,
                    "data": {
                        "name": "Charlie",
                        "type": "game",
                        "price_overview": {
                            "discount_percent": 55,
                            "final_formatted": "$6",
                            "initial_formatted": "$12",
                            "final": 600,
                        },
                        "genres": [],
                        "platforms": {"linux": False},
                        "release_date": {"coming_soon": False, "date": "Jan 1, 2022"},
                        "metacritic": {},
                        "categories": [{"id": 2}],
                    },
                },
            }

        refresh_counts = module_count_refresh_candidates(
            ["10", "20", "30"],
            dict(fetched_cache),
            now_ts=now_ts,
            entry_ttl_hours=24.0,
        )

        deals, n_fetched = module_get_deals_from_wishlist(
            ["10", "20", "30"],
            fetched_cache,
            "steam-id",
            min_discount=50,
            rate_limit=0.0,
            get_json=fake_get_json,
            sleep_fn=lambda _delay: None,
            monotonic_fn=lambda: 0.0,
            save_price_cache_fn=lambda *_args, **_kwargs: None,
            fetch_single_fn=lambda *_args, **_kwargs: None,
            process_app_entry_fn=module_process_app_entry,
            emit=emitted.append,
            warn=lambda text: text,
            dim=lambda text: text,
            bar_fill="#",
            bar_empty="-",
            color_green="",
            color_dim="",
            color_reset="",
            batch_size=20,
            entry_ttl_hours=24.0,
            current_time_fn=lambda: now_ts,
        )

        self.assertEqual(refresh_counts, (1, 1))
        self.assertEqual(n_fetched, 2)
        self.assertTrue(any("Fetching 2 juegos en 1 batches" in line for line in emitted))
        self.assertEqual([deal["appid"] for deal in deals], ["10", "20", "30"])

    def test_build_warm_cache_emit_keeps_terminal_output_and_strips_ansi_in_log(
        self,
    ) -> None:
        terminal_calls = []

        with TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "warm-cache.log"
            with log_path.open("w", encoding="utf-8") as log_handle:
                emit = build_warm_cache_emit(
                    log_handle,
                    terminal_emit=lambda message, **kwargs: terminal_calls.append(
                        (message, kwargs)
                    ),
                )
                emit("\x1b[32mOK\x1b[0m", flush=True)
                emit("\rprogress 10/20", end="", flush=True)

            content = log_path.read_text(encoding="utf-8")

        self.assertEqual(terminal_calls[0][0], "\x1b[32mOK\x1b[0m")
        self.assertIn("OK", content)
        self.assertIn("\nprogress 10/20", content)
        self.assertNotIn("\x1b", content)


class PresentationHelpersTests(unittest.TestCase):
    def test_linux_badge_combines_native_deck_proton_and_anticheat(self) -> None:
        badge = module_linux_badge(
            3,
            {"tier": "gold"},
            {"status": "Supported", "anticheats": ["EAC"]},
            linux_native=True,
        )

        self.assertEqual(badge, "🐧 Native · ✅ Verified · 🥇 Gold · ✅ EAC")

    def test_get_top_tags_and_group_by_tier_keep_expected_outputs(self) -> None:
        tags_data = {
            "10": {"tags": {"Roguelike": 100, "Action": 90, "Deckbuilder": 80}},
            "20": {"tags": {"Deckbuilder": 90, "Indie": 50, "Puzzle": 20}},
            "30": {"tags": {"Deckbuilder": 40, "Strategy": 30}},
        }
        deals = [
            {"appid": "10", "discount": 95},
            {"appid": "20", "discount": 82},
            {"appid": "30", "discount": 55},
        ]

        top_tags = module_get_top_tags(tags_data, "10", n=3)
        grouped = module_group_by_tier(deals)

        self.assertEqual(top_tags, ["Roguelike", "Deckbuilder"])
        self.assertEqual(
            [name for name, games in grouped if games], ["90%+", "80–89%", "50–59%"]
        )

    def test_players_multiplayer_and_achievements_badges_keep_format(self) -> None:
        players = module_players_badge({"players": {"owners": "200,000 .. 500,000"}})
        mode = module_multiplayer_badges([2, 9, 38])
        achievements = module_achievements_badge({"count": 50, "avg_completion": 12.4})

        self.assertEqual(players, "👥 200K-500K")
        self.assertEqual(mode, "Co-op")
        self.assertEqual(achievements, "🏆 50 (12%)")


class EnrichmentTests(unittest.TestCase):
    def _build_enrichment_contract(
        self,
        *,
        steps: list[str],
        emits: list[str],
        reviews_runtime=None,
        deck_runtime=None,
        protondb_runtime=None,
        anticheat_runtime=None,
        tags_runtime=None,
        achievements_runtime=None,
    ):
        def default_scoped_runtime():
            return module_build_scoped_cache_runtime(
                load_cache=lambda _steam_id: ({}, 0.0),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(
                    status="empty", cache={}, missing_ids=()
                ),
                fetch_data=lambda _appids, cached: dict(cached),
                save_cache=lambda _steam_id, _data: None,
                ttl_hours=24,
            )

        def default_global_runtime():
            return module_build_global_cache_runtime(
                load_cache=lambda: ({}, 0.0),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(
                    status="empty", cache={}
                ),
                fetch_data=lambda: {},
                save_cache=lambda _data: None,
                ttl_hours=24,
            )

        return module_build_enrichment_orchestration_contract(
            progress=module_build_progress_callbacks(
                step=steps.append, emit=emits.append
            ),
            messages=module_build_message_formatters(
                ok=lambda text: f"OK:{text}",
                warn=lambda text: f"WARN:{text}",
                dim=lambda text: f"DIM:{text}",
            ),
            reviews=reviews_runtime or default_scoped_runtime(),
            deck=deck_runtime or default_scoped_runtime(),
            protondb=protondb_runtime or default_scoped_runtime(),
            anticheat=anticheat_runtime or default_global_runtime(),
            tags=tags_runtime or default_scoped_runtime(),
            achievements=achievements_runtime or default_scoped_runtime(),
        )

    def test_fetch_reviews_merges_cached_and_fetched_entries(self) -> None:
        def fake_fetch_parallel(items, fetch_fn, _label, rate_limit=0.15):
            return {appid: fetch_fn(appid) for appid in items}

        result = module_fetch_reviews(
            ["10", "20"],
            {"10": {"desc": "Very Positive", "pct": 90, "total": 100}},
            fetch_parallel_fn=fake_fetch_parallel,
            get_json=lambda _url, headers=None: {
                "query_summary": {
                    "review_score_desc": "Positive",
                    "total_positive": 40,
                    "total_reviews": 50,
                }
            },
        )

        self.assertEqual(result["10"]["pct"], 90)
        self.assertEqual(result["20"]["pct"], 80)

    def test_fetch_anticheat_db_parses_awacy_rows(self) -> None:
        data = [
            {
                "storeIds": {"steam": 10},
                "status": "Supported",
                "anticheats": ["EAC"],
                "native": False,
            },
            {"storeIds": {}, "status": "Broken"},
        ]

        result = module_fetch_anticheat_db(get_json=lambda _url, headers=None: data)

        self.assertEqual(
            result,
            {"10": {"status": "Supported", "anticheats": ["EAC"], "native": False}},
        )

    def test_load_tags_cache_migrates_old_flat_format(self) -> None:
        tags, age = module_load_tags_cache(
            Path("/tmp/unused.json"),
            load_timestamped_cache=lambda _file, _key: (
                {"10": {"Roguelike": 100}},
                12.0,
            ),
        )

        self.assertEqual(age, 12.0)
        self.assertEqual(tags["10"], {"tags": {"Roguelike": 100}, "players": {}})

    def test_fetch_achievements_merges_cached_and_new_entries(self) -> None:
        def fake_fetch_parallel(items, fetch_fn, _label, rate_limit=0.15):
            return {appid: fetch_fn(appid) for appid in items}

        result = module_fetch_achievements(
            ["10", "20"],
            {"10": {"count": 10, "avg_completion": 30.0}},
            fetch_parallel_fn=fake_fetch_parallel,
            get_json=lambda _url, headers=None: {
                "achievementpercentages": {
                    "achievements": [
                        {"percent": 10.0},
                        {"percent": 20.0},
                    ]
                }
            },
        )

        self.assertEqual(result["10"]["count"], 10)
        self.assertEqual(result["20"], {"count": 2, "avg_completion": 15.0})

    def test_reviews_and_deck_orchestration_preserve_step_order_and_messages(
        self,
    ) -> None:
        steps: list[str] = []
        emits: list[str] = []
        review_saves: list[tuple[str, dict]] = []
        deck_saves: list[tuple[str, dict]] = []

        contract = self._build_enrichment_contract(
            steps=steps,
            emits=emits,
            reviews_runtime=module_build_scoped_cache_runtime(
                load_cache=lambda _steam_id: ({"10": {"pct": 90}}, 6.0),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(
                    status="valid",
                    cache={"10": {"pct": 90}},
                    missing_ids=("20",),
                ),
                fetch_data=lambda _appids, cached: {**cached, "20": {"pct": 80}},
                save_cache=lambda steam_id, data: review_saves.append((steam_id, data)),
                ttl_hours=24,
            ),
            deck_runtime=module_build_scoped_cache_runtime(
                load_cache=lambda _steam_id: ({}, 30.0),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(
                    status="expired",
                    cache={},
                    missing_ids=("10", "20"),
                ),
                fetch_data=lambda _appids, _cached: {"10": 3, "20": 2},
                save_cache=lambda steam_id, data: deck_saves.append((steam_id, data)),
                ttl_hours=24,
            ),
        )

        reviews_data = module_run_reviews_orchestration(
            "steam-id",
            ["10", "20"],
            no_cache=False,
            contract=contract,
        )
        deck_data = module_run_deck_orchestration(
            "steam-id",
            ["10", "20"],
            no_cache=False,
            contract=contract,
        )

        self.assertEqual(
            steps,
            [
                "Obteniendo reviews de Steam...",
                "Obteniendo compatibilidad Steam Deck...",
            ],
        )
        self.assertEqual(
            emits,
            [
                "  OK:Caché válida (6h) — 1 nuevos por fetchear",
                "  OK:2/2 deals con reviews",
                "  WARN:Caché expirada (30h) — re-fetching",
                "  OK:1 Verified · 1 Playable",
            ],
        )
        self.assertEqual(reviews_data, {"10": {"pct": 90}, "20": {"pct": 80}})
        self.assertEqual(deck_data, {"10": 3, "20": 2})
        self.assertEqual(
            review_saves, [("steam-id", {"10": {"pct": 90}, "20": {"pct": 80}})]
        )
        self.assertEqual(deck_saves, [("steam-id", {"10": 3, "20": 2})])

    def test_linux_tags_and_achievements_orchestration_keep_observable_outputs(
        self,
    ) -> None:
        steps: list[str] = []
        emits: list[str] = []
        protondb_saves: list[tuple[str, dict]] = []
        tag_saves: list[tuple[str, dict]] = []
        achievement_saves: list[tuple[str, dict]] = []
        anticheat_fetch_calls: list[bool] = []

        contract = self._build_enrichment_contract(
            steps=steps,
            emits=emits,
            protondb_runtime=module_build_scoped_cache_runtime(
                load_cache=lambda _steam_id: ({"10": {"tier": "platinum"}}, 5.0),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(
                    status="valid",
                    cache={"10": {"tier": "platinum"}},
                    missing_ids=("20",),
                ),
                fetch_data=lambda _appids, cached: {**cached, "20": {"tier": "native"}},
                save_cache=lambda steam_id, data: protondb_saves.append(
                    (steam_id, data)
                ),
                ttl_hours=24,
            ),
            anticheat_runtime=module_build_global_cache_runtime(
                load_cache=lambda: ({"10": {"status": "Denied"}}, 3.0),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(
                    status="valid",
                    cache={"10": {"status": "Denied"}},
                ),
                fetch_data=lambda: anticheat_fetch_calls.append(True) or {},
                save_cache=lambda _data: None,
                ttl_hours=24,
            ),
            tags_runtime=module_build_scoped_cache_runtime(
                load_cache=lambda _steam_id: ({}, 50.0),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(
                    status="expired",
                    cache={},
                    missing_ids=("10", "20"),
                ),
                fetch_data=lambda _appids, _cached: {
                    "10": {"tags": {"Action": 100}},
                    "20": {},
                },
                save_cache=lambda steam_id, data: tag_saves.append((steam_id, data)),
                ttl_hours=24,
            ),
            achievements_runtime=module_build_scoped_cache_runtime(
                load_cache=lambda _steam_id: (
                    {"10": {"count": 10, "avg_completion": 12.0}},
                    4.0,
                ),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(
                    status="valid",
                    cache={"10": {"count": 10, "avg_completion": 12.0}},
                    missing_ids=(),
                ),
                fetch_data=lambda _appids, cached: dict(cached),
                save_cache=lambda steam_id, data: achievement_saves.append(
                    (steam_id, data)
                ),
                ttl_hours=24,
            ),
        )

        protondb_data, anticheat_data = module_run_protondb_anticheat_orchestration(
            "steam-id",
            ["10", "20"],
            no_cache=False,
            contract=contract,
        )
        tags_data = module_run_tags_orchestration(
            "steam-id",
            ["10", "20"],
            no_cache=False,
            contract=contract,
        )
        achievements_data = module_run_achievements_orchestration(
            "steam-id",
            ["10", "20"],
            no_cache=False,
            contract=contract,
        )

        self.assertEqual(
            steps,
            [
                "Obteniendo datos Linux (ProtonDB + Anti-Cheat)...",
                "Obteniendo tags de Steam...",
                "Obteniendo achievements...",
            ],
        )
        self.assertEqual(
            emits,
            [
                "  OK:ProtonDB caché válida (5h) — 1 nuevos",
                "  OK:ProtonDB: 2/2 · 2 Platinum/Native",
                "  OK:Anti-Cheat DB desde caché (3h)",
                "  WARN:1 deals con problemas de anti-cheat en Linux",
                "  WARN:Caché expirada (50h) — re-fetching",
                "  OK:1/2 deals con tags",
                "  OK:Caché válida (4h) — DIM:todos en caché",
                "  OK:1/2 deals con achievements",
            ],
        )
        self.assertEqual(
            protondb_data, {"10": {"tier": "platinum"}, "20": {"tier": "native"}}
        )
        self.assertEqual(anticheat_data, {"10": {"status": "Denied"}})
        self.assertEqual(tags_data, {"10": {"tags": {"Action": 100}}, "20": {}})
        self.assertEqual(
            achievements_data, {"10": {"count": 10, "avg_completion": 12.0}}
        )
        self.assertEqual(anticheat_fetch_calls, [])
        self.assertEqual(
            protondb_saves,
            [("", {"10": {"tier": "platinum"}, "20": {"tier": "native"}})],
        )
        self.assertEqual(tag_saves, [("", {"10": {"tags": {"Action": 100}}, "20": {}})])
        self.assertEqual(
            achievement_saves,
            [("steam-id", {"10": {"count": 10, "avg_completion": 12.0}})],
        )


class PriceCacheTests(unittest.TestCase):
    def test_resolve_price_fetch_tuning_uses_defaults_and_env_overrides(self) -> None:
        self.assertEqual(
            resolve_price_fetch_tuning(env={}),
            {
                "batch_size": 20,
                "batch_halving_limit": 3,
                "is_custom": False,
            },
        )
        self.assertEqual(
            resolve_price_fetch_tuning(
                env={
                    "STEAM_DEALS_PRICE_BATCH_SIZE": "8",
                    "STEAM_DEALS_PRICE_BATCH_HALVING_LIMIT": "5",
                }
            ),
            {
                "batch_size": 8,
                "batch_halving_limit": 5,
                "is_custom": True,
            },
        )

    def test_select_scoped_cache_reports_missing_ids_for_valid_cache(self) -> None:
        decision = module_select_scoped_cache(
            ["10", "20"],
            {"10": {"discount_percent": 70}},
            12.0,
            no_cache=False,
            ttl_hours=24,
        )

        self.assertEqual(decision.status, "valid")
        self.assertEqual(decision.cache, {"10": {"discount_percent": 70}})
        self.assertEqual(decision.missing_ids, ("20",))
        self.assertEqual(decision.refresh_ids, ("10", "20"))

    def test_select_scoped_cache_reports_stale_and_missing_refresh_ids(self) -> None:
        now_ts = 1_700_000_000.0
        decision = module_select_scoped_cache(
            ["10", "20", "30"],
            {
                "10": {"discount_percent": 70, "_fetched_at": now_ts},
                "20": {"discount_percent": 60, "_fetched_at": now_ts - (25 * 3600)},
            },
            2.0,
            no_cache=False,
            ttl_hours=24,
            current_time_fn=lambda: now_ts,
            entry_ttl_hours=24,
        )

        self.assertEqual(decision.status, "valid")
        self.assertEqual(decision.missing_ids, ("30",))
        self.assertEqual(decision.refresh_ids, ("20", "30"))

    def test_select_scoped_cache_defers_recent_failed_entries_until_retry_window(self) -> None:
        now_ts = 1_700_000_000.0
        decision = module_select_scoped_cache(
            ["10", "20"],
            {
                "10": {"_failed_at": now_ts - 3600, "_failure_reason": "no_price_data"},
                "20": {"_failed_at": now_ts - (3 * 3600), "_failure_reason": "no_price_data"},
            },
            2.0,
            no_cache=False,
            ttl_hours=24,
            current_time_fn=lambda: now_ts,
            entry_ttl_hours=24,
            failure_retry_hours=2,
        )

        self.assertEqual(decision.status, "valid")
        self.assertEqual(decision.refresh_ids, ("20",))
        self.assertEqual(decision.deferred_failure_ids, ("10",))

    def test_select_scoped_cache_clears_expired_payload_by_default(self) -> None:
        decision = module_select_scoped_cache(
            ["10", "20"],
            {"10": {"discount_percent": 70}},
            48.0,
            no_cache=False,
            ttl_hours=24,
        )

        self.assertEqual(decision.status, "expired")
        self.assertEqual(decision.cache, {})
        self.assertEqual(decision.missing_ids, ("10", "20"))
        self.assertEqual(decision.refresh_ids, ("10", "20"))

    def test_select_scoped_cache_preserves_expired_payload_when_enabled(self) -> None:
        now_ts = 1_700_000_000.0
        decision = module_select_scoped_cache(
            ["10", "20", "30"],
            {
                "10": {"discount_percent": 70, "_fetched_at": now_ts - (25 * 3600)},
                "20": {"discount_percent": 60, "_fetched_at": now_ts},
            },
            48.0,
            no_cache=False,
            ttl_hours=24,
            current_time_fn=lambda: now_ts,
            entry_ttl_hours=24,
            preserve_expired_payload=True,
        )

        self.assertEqual(decision.status, "expired")
        self.assertEqual(
            decision.cache,
            {
                "10": {"discount_percent": 70, "_fetched_at": now_ts - (25 * 3600)},
                "20": {"discount_percent": 60, "_fetched_at": now_ts},
            },
        )
        self.assertEqual(decision.missing_ids, ("30",))
        self.assertEqual(decision.refresh_ids, ("10", "30"))

    def test_select_scoped_cache_expires_exactly_at_ttl_boundary(self) -> None:
        now_ts = 1_700_000_000.0
        decision = module_select_scoped_cache(
            ["10", "20"],
            {
                "10": {"discount_percent": 70, "_fetched_at": now_ts - (25 * 3600)},
                "20": {"_failed_at": now_ts - 3600, "_failure_reason": "no_price_data"},
            },
            24.0,
            no_cache=False,
            ttl_hours=24,
            current_time_fn=lambda: now_ts,
            entry_ttl_hours=24,
            failure_retry_hours=2,
            preserve_expired_payload=True,
        )

        self.assertEqual(decision.status, "expired")
        self.assertEqual(decision.missing_ids, ())
        self.assertEqual(decision.refresh_ids, ("10",))
        self.assertEqual(decision.deferred_failure_ids, ("20",))

    def test_select_global_cache_bypasses_when_no_cache_is_enabled(self) -> None:
        decision = module_select_global_cache(
            {"10": {"status": "Supported"}},
            1.0,
            no_cache=True,
            ttl_hours=168,
        )

        self.assertEqual(decision.status, "bypass")
        self.assertEqual(decision.cache, {})

    def test_select_global_cache_expires_exactly_at_ttl_boundary(self) -> None:
        decision = module_select_global_cache(
            {"10": {"status": "Supported"}},
            168.0,
            no_cache=False,
            ttl_hours=168,
        )

        self.assertEqual(decision.status, "expired")
        self.assertEqual(decision.cache, {})

    def test_clear_cache_files_only_unlinks_existing_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "reviews_cache.json"
            existing.write_text("{}", encoding="utf-8")
            missing = Path(temp_dir) / "deck_cache.json"

            cleared = module_clear_cache_files([existing, missing])

        self.assertEqual(cleared, (existing,))
        self.assertFalse(existing.exists())

    def test_save_and_load_price_cache_roundtrip(self) -> None:
        fetched = {"10": {"discount_percent": 70}, "20": None}

        with TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "prices_cache.json"
            module_save_price_cache(cache_path, "steam-id", fetched)
            loaded, age = module_load_price_cache(cache_path, "steam-id")

        self.assertEqual(loaded, fetched)
        self.assertTrue(age >= 0)

    def test_process_app_entry_strips_html_and_parses_release_year(self) -> None:
        data = {
            "10": {
                "success": True,
                "data": {
                    "name": "Portal 2",
                    "type": "game",
                    "price_overview": {
                        "discount_percent": 80,
                        "final_formatted": "$8",
                        "initial_formatted": "$40",
                        "final": 800,
                    },
                    "genres": [{"description": "Puzzle"}],
                    "release_date": {"coming_soon": False, "date": "Apr 18, 2011"},
                    "short_description": "<b>Test</b> description",
                    "platforms": {"linux": True},
                    "metacritic": {"score": 95, "url": "meta"},
                    "categories": [{"id": 2}],
                },
            }
        }

        result = module_process_app_entry(
            "10", data, parse_release_year_fn=module_parse_release_year
        )

        self.assertEqual(result["release_year"], 2011)
        self.assertEqual(result["description"], "Test description")
        self.assertEqual(result["linux_native"], True)

    def test_get_deals_from_wishlist_falls_back_to_individual_fetch_and_preserves_deal_shape(
        self,
    ) -> None:
        fetched_cache = {}
        stats = {}

        def fake_batch_get_json(_url, headers=None):
            return {"10": None, "20": None}

        def fake_fetch_single(appid, _country, _delay):
            return {
                appid: {
                    "success": True,
                    "data": {
                        "name": f"Game {appid}",
                        "type": "game",
                        "price_overview": {
                            "discount_percent": 60 if appid == "10" else 40,
                            "final_formatted": "$6" if appid == "10" else "$4",
                            "initial_formatted": "$15" if appid == "10" else "$10",
                            "final": 600 if appid == "10" else 400,
                        },
                        "genres": [{"description": "Action"}],
                        "release_date": {"coming_soon": False, "date": "2020"},
                        "short_description": "desc",
                        "platforms": {"linux": False},
                        "metacritic": {"score": 80, "url": "meta"},
                        "categories": [{"id": 1}],
                    },
                }
            }

        deals, total = module_get_deals_from_wishlist(
            ["10", "20"],
            fetched_cache,
            "steam-id",
            min_discount=50,
            get_json=fake_batch_get_json,
            sleep_fn=lambda _seconds: None,
            monotonic_fn=lambda: 0.0,
            save_price_cache_fn=lambda _steam_id, _cache: None,
            fetch_single_fn=fake_fetch_single,
            process_app_entry_fn=lambda appid, data: module_process_app_entry(
                appid, data, parse_release_year_fn=module_parse_release_year
            ),
            emit=lambda *_args, **_kwargs: None,
            warn=lambda text: text,
            dim=lambda text: text,
            stats_out=stats,
        )

        self.assertEqual(total, 2)
        self.assertEqual([deal["appid"] for deal in deals], ["10"])
        self.assertEqual(deals[0]["price_raw"], 600)
        self.assertEqual(stats["individual_fallback_count"], 2)
        self.assertEqual(stats["individual_fallback_resolved_count"], 2)
        self.assertEqual(stats["individual_fallback_failed_count"], 0)

    def test_count_refresh_candidates_reports_missing_and_stale_entries(self) -> None:
        now_ts = 200000.0
        cache = {
            "10": {"discount_percent": 70, "_fetched_at": now_ts - (2 * 3600)},
            "20": {"discount_percent": 60, "_fetched_at": now_ts - (30 * 3600)},
            "30": {"discount_percent": 50},
        }

        missing, stale = module_count_refresh_candidates(
            ["10", "20", "30", "40"],
            cache,
            now_ts=now_ts,
            entry_ttl_hours=24,
        )

        self.assertEqual(missing, 1)
        self.assertEqual(stale, 2)

    def test_get_deals_from_wishlist_refetches_stale_entries_and_stamps_timestamp(
        self,
    ) -> None:
        now_ts = 200000.0
        stale_ts = now_ts - (30 * 3600)
        fresh_ts = now_ts - (2 * 3600)
        fetched_cache = {
            "10": {
                "name": "Game 10",
                "type": "game",
                "discount_percent": 60,
                "price_final": "$6",
                "price_original": "$15",
                "price_final_raw": 600,
                "genres": ["action"],
                "release_year": 2020,
                "description": "desc",
                "linux_native": False,
                "metacritic_score": 80,
                "metacritic_url": "meta",
                "categories": [1],
                "_fetched_at": stale_ts,
            },
            "20": {
                "name": "Game 20",
                "type": "game",
                "discount_percent": 60,
                "price_final": "$6",
                "price_original": "$15",
                "price_final_raw": 600,
                "genres": ["action"],
                "release_year": 2020,
                "description": "desc",
                "linux_native": False,
                "metacritic_score": 80,
                "metacritic_url": "meta",
                "categories": [1],
                "_fetched_at": fresh_ts,
            },
        }

        fetched_ids: list[str] = []

        def fake_fetch_single(appid, _country, _delay):
            fetched_ids.append(appid)
            return {
                appid: {
                    "success": True,
                    "data": {
                        "name": f"Game {appid}",
                        "type": "game",
                        "price_overview": {
                            "discount_percent": 70,
                            "final_formatted": "$7",
                            "initial_formatted": "$20",
                            "final": 700,
                        },
                        "genres": [{"description": "Action"}],
                        "release_date": {"coming_soon": False, "date": "2020"},
                        "short_description": "desc",
                        "platforms": {"linux": False},
                        "metacritic": {"score": 81, "url": "meta"},
                        "categories": [{"id": 1}],
                    },
                }
            }

        deals, total = module_get_deals_from_wishlist(
            ["10", "20"],
            fetched_cache,
            "steam-id",
            min_discount=50,
            get_json=lambda _url, headers=None: {},
            sleep_fn=lambda _seconds: None,
            monotonic_fn=lambda: 0.0,
            current_time_fn=lambda: now_ts,
            save_price_cache_fn=lambda _steam_id, _cache: None,
            fetch_single_fn=fake_fetch_single,
            process_app_entry_fn=lambda appid, data: module_process_app_entry(
                appid, data, parse_release_year_fn=module_parse_release_year
            ),
            emit=lambda *_args, **_kwargs: None,
            warn=lambda text: text,
            dim=lambda text: text,
        )

        self.assertEqual(total, 1)
        self.assertEqual(fetched_ids, ["10"])
        self.assertEqual([deal["appid"] for deal in deals], ["10", "20"])
        self.assertEqual(fetched_cache["10"].get("_fetched_at"), now_ts)
        self.assertEqual(fetched_cache["20"].get("_fetched_at"), fresh_ts)

    def test_get_deals_from_wishlist_keeps_failed_entries_retryable(self) -> None:
        now_ts = 200000.0
        fetched_cache = {}

        deals, total = module_get_deals_from_wishlist(
            ["10"],
            fetched_cache,
            "steam-id",
            min_discount=50,
            get_json=lambda _url, headers=None: {"10": None},
            sleep_fn=lambda _seconds: None,
            monotonic_fn=lambda: 0.0,
            current_time_fn=lambda: now_ts,
            save_price_cache_fn=lambda _steam_id, _cache: None,
            fetch_single_fn=lambda _appid, _country, _delay: None,
            process_app_entry_fn=lambda appid, data: module_process_app_entry(
                appid, data, parse_release_year_fn=module_parse_release_year
            ),
            emit=lambda *_args, **_kwargs: None,
            warn=lambda text: text,
            dim=lambda text: text,
        )

        missing, stale = module_count_refresh_candidates(
            ["10"],
            fetched_cache,
            now_ts=now_ts + 60,
            entry_ttl_hours=24,
        )
        missing_after_retry, stale_after_retry = module_count_refresh_candidates(
            ["10"],
            fetched_cache,
            now_ts=now_ts + (3 * 3600),
            entry_ttl_hours=24,
        )

        self.assertEqual(total, 1)
        self.assertEqual(deals, [])
        self.assertEqual(fetched_cache["10"].get("_failed_at"), now_ts)
        self.assertEqual(fetched_cache["10"].get("_failure_reason"), "no_price_data")
        self.assertNotIn("_fetched_at", fetched_cache["10"])
        self.assertEqual(missing, 0)
        self.assertEqual(stale, 0)
        self.assertEqual(missing_after_retry, 0)
        self.assertEqual(stale_after_retry, 1)

    def test_get_deals_from_wishlist_reports_http_400_batch_degradation_and_keeps_entries_retryable(
        self,
    ) -> None:
        now_ts = 200000.0
        emitted = []
        fetched_cache = {}
        single_calls = []

        def fake_get_json(_url, headers=None):
            raise urllib.error.HTTPError(
                _url, 400, "Bad Request", hdrs=None, fp=None
            )

        def fake_fetch_single(appid, _country, _delay):
            single_calls.append(appid)
            return None

        deals, total = module_get_deals_from_wishlist(
            ["10", "20", "30", "40"],
            fetched_cache,
            "steam-id",
            min_discount=50,
            get_json=fake_get_json,
            sleep_fn=lambda _seconds: None,
            monotonic_fn=lambda: 0.0,
            current_time_fn=lambda: now_ts,
            save_price_cache_fn=lambda _steam_id, _cache: None,
            fetch_single_fn=fake_fetch_single,
            process_app_entry_fn=lambda appid, data: module_process_app_entry(
                appid, data, parse_release_year_fn=module_parse_release_year
            ),
            emit=emitted.append,
            warn=lambda text: f"WARN:{text}",
            dim=lambda text: f"DIM:{text}",
            batch_size=2,
        )

        missing, stale = module_count_refresh_candidates(
            ["10", "20", "30", "40"],
            fetched_cache,
            now_ts=now_ts + 60,
            entry_ttl_hours=24,
        )
        missing_after_retry, stale_after_retry = module_count_refresh_candidates(
            ["10", "20", "30", "40"],
            fetched_cache,
            now_ts=now_ts + (3 * 3600),
            entry_ttl_hours=24,
        )

        self.assertEqual(total, 4)
        self.assertEqual(deals, [])
        self.assertEqual(single_calls, ["10", "20", "30", "40"])
        self.assertTrue(
            any("WARN:HTTP 400 en batch de 2 juegos; reduciendo lote" in line for line in emitted)
        )
        self.assertTrue(
            any("DIM:Batch falló, intentando individualmente..." in line for line in emitted)
        )
        self.assertEqual(missing, 0)
        self.assertEqual(stale, 0)
        self.assertEqual(missing_after_retry, 0)
        self.assertEqual(stale_after_retry, 4)
        self.assertTrue(all(entry.get("_failed_at") == now_ts for entry in fetched_cache.values()))
        self.assertTrue(all("_fetched_at" not in entry for entry in fetched_cache.values()))

    def test_get_deals_from_wishlist_halves_http_400_batches_before_individual_fallback(
        self,
    ) -> None:
        emitted = []
        fetched_cache = {}
        requested_batches = []
        single_calls = []

        def fake_get_json(url, headers=None):
            self.assertEqual(headers, {"User-Agent": "Mozilla/5.0"})
            requested_batches.append(url.split("appids=", 1)[1].split("&", 1)[0])
            raise urllib.error.HTTPError(url, 400, "Bad Request", hdrs=None, fp=None)

        def fake_fetch_single(appid, _country, _delay):
            single_calls.append(appid)
            return None

        deals, total = module_get_deals_from_wishlist(
            ["10", "20", "30", "40"],
            fetched_cache,
            "steam-id",
            min_discount=50,
            get_json=fake_get_json,
            sleep_fn=lambda _seconds: None,
            monotonic_fn=lambda: 0.0,
            current_time_fn=lambda: 200000.0,
            save_price_cache_fn=lambda _steam_id, _cache: None,
            fetch_single_fn=fake_fetch_single,
            process_app_entry_fn=lambda appid, data: module_process_app_entry(
                appid, data, parse_release_year_fn=module_parse_release_year
            ),
            emit=emitted.append,
            warn=lambda text: f"WARN:{text}",
            dim=lambda text: f"DIM:{text}",
            batch_size=4,
        )

        self.assertEqual(total, 4)
        self.assertEqual(deals, [])
        self.assertEqual(requested_batches, ["10,20,30,40", "10,20", "10", "20", "30,40", "30", "40"])
        self.assertEqual(single_calls, ["10", "20", "30", "40"])
        self.assertTrue(
            any("reduciendo lote" in line for line in emitted)
        )

    def test_get_deals_from_wishlist_skips_extra_sleep_before_http_400_fallback(
        self,
    ) -> None:
        fetched_cache = {}
        sleep_calls = []
        single_calls = []

        def fake_get_json(url, headers=None):
            raise urllib.error.HTTPError(url, 400, "Bad Request", hdrs=None, fp=None)

        def fake_fetch_single(appid, _country, _delay):
            single_calls.append(appid)
            return None

        deals, total = module_get_deals_from_wishlist(
            ["10", "20"],
            fetched_cache,
            "steam-id",
            min_discount=50,
            get_json=fake_get_json,
            sleep_fn=sleep_calls.append,
            monotonic_fn=lambda: 0.0,
            current_time_fn=lambda: 200000.0,
            save_price_cache_fn=lambda _steam_id, _cache: None,
            fetch_single_fn=fake_fetch_single,
            process_app_entry_fn=lambda appid, data: module_process_app_entry(
                appid, data, parse_release_year_fn=module_parse_release_year
            ),
            emit=lambda *_args, **_kwargs: None,
            warn=lambda text: text,
            dim=lambda text: text,
            batch_size=2,
            max_batch_halving=1,
        )

        self.assertEqual(total, 2)
        self.assertEqual(deals, [])
        self.assertEqual(single_calls, ["10", "20"])
        self.assertEqual(sleep_calls, [])

    def test_get_deals_from_wishlist_switches_to_direct_fallback_after_repeated_http_400(
        self,
    ) -> None:
        fetched_cache = {}
        emitted = []
        requested_batches = []
        single_calls = []
        stats = {}

        def fake_get_json(url, headers=None):
            requested_batches.append(url.split("appids=", 1)[1].split("&", 1)[0])
            raise urllib.error.HTTPError(url, 400, "Bad Request", hdrs=None, fp=None)

        def fake_fetch_single(appid, _country, _delay):
            single_calls.append(appid)
            return None

        appids = ["10", "20", "30", "40", "50", "60", "70", "80"]

        deals, total = module_get_deals_from_wishlist(
            appids,
            fetched_cache,
            "steam-id",
            min_discount=50,
            get_json=fake_get_json,
            sleep_fn=lambda _seconds: None,
            monotonic_fn=lambda: 0.0,
            current_time_fn=lambda: 200000.0,
            save_price_cache_fn=lambda _steam_id, _cache: None,
            fetch_single_fn=fake_fetch_single,
            process_app_entry_fn=lambda appid, data: module_process_app_entry(
                appid, data, parse_release_year_fn=module_parse_release_year
            ),
            emit=emitted.append,
            warn=lambda text: f"WARN:{text}",
            dim=lambda text: f"DIM:{text}",
            batch_size=2,
            max_batch_halving=1,
            http_400_circuit_breaker_threshold=2,
            stats_out=stats,
        )

        self.assertEqual(total, 8)
        self.assertEqual(deals, [])
        self.assertEqual(
            requested_batches,
            ["10,20", "10", "20", "30,40", "30", "40"],
        )
        self.assertEqual(single_calls, appids)
        self.assertEqual(stats["http_400_direct_fallback_batches"], 2)
        self.assertEqual(stats["http_400_direct_fallback_count"], 4)
        self.assertTrue(
            any("fallback individual directo" in line for line in emitted)
        )


class RunOutputTests(unittest.TestCase):
    def test_build_output_md_path_sanitizes_sale_name(self) -> None:
        output = module_build_output_md_path(
            "/tmp/out", "Steam: Sale/?*", today_obj=date(2026, 4, 14)
        )

        self.assertEqual(output, Path("/tmp/out/Steam Deals Steam Sale 2026-04-14.md"))

    def test_build_output_artifact_paths_keeps_output_contract(self) -> None:
        artifacts = module_build_output_artifact_paths(
            Path("/tmp/out/Steam Deals 2026-04-14.md"),
            today_obj=date(2026, 4, 14),
            include_csv=True,
        )

        self.assertEqual(
            artifacts.output_md, Path("/tmp/out/Steam Deals 2026-04-14.md")
        )
        self.assertEqual(
            artifacts.output_html, Path("/tmp/out/Steam Deals 2026-04-14.html")
        )
        self.assertEqual(
            artifacts.output_share, Path("/tmp/out/Steam Deals Share 2026-04-14.html")
        )
        self.assertEqual(
            artifacts.output_json, Path("/tmp/out/Steam Deals 2026-04-14.json")
        )
        self.assertEqual(
            artifacts.output_csv, Path("/tmp/out/Steam Deals 2026-04-14.csv")
        )

    def test_resolve_previous_context_uses_markdown_fallback_only_without_previous_run(
        self,
    ) -> None:
        result = module_resolve_previous_context(
            "/tmp/out",
            "Steam Deals 2026-04-14.md",
            "steam-id",
            load_previous_run_fn=lambda _steam_id: None,
            load_run_history_fn=lambda _steam_id: [{"ignored": True}],
            load_previous_deal_appids_fn=lambda _output_dir, _filename: {"10", "20"},
        )

        self.assertEqual(result["previous_run"], None)
        self.assertEqual(result["run_history"], [])
        self.assertEqual(result["previous_appids"], {"10", "20"})

    def test_write_artifact_and_share_path_preserve_output_contract(self) -> None:
        emitted = []

        with TemporaryDirectory() as temp_dir:
            output_md = Path(temp_dir) / "Steam Deals 2026-04-14.md"
            share_path = module_build_share_output_path(
                temp_dir, today_obj=date(2026, 4, 14)
            )
            module_write_artifact(
                output_md,
                "md",
                emit_event_fn=lambda event_type, **payload: emitted.append(
                    (event_type, payload)
                ),
            )
            module_write_artifact(
                share_path,
                "share",
                emit_event_fn=lambda event_type, **payload: emitted.append(
                    (event_type, payload)
                ),
            )

            self.assertEqual(output_md.read_text(encoding="utf-8"), "md")
            self.assertEqual(share_path.read_text(encoding="utf-8"), "share")

        self.assertEqual(emitted[0][0], "file")
        self.assertTrue(emitted[0][1]["path"].endswith("Steam Deals 2026-04-14.md"))
        self.assertTrue(
            emitted[1][1]["path"].endswith("Steam Deals Share 2026-04-14.html")
        )

    def test_find_latest_artifact_returns_newest_matching_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            older = out_dir / "Steam Deals 2026-04-14.json"
            newer = out_dir / "Steam Deals 2026-04-15.json"
            older.write_text("{}", encoding="utf-8")
            time.sleep(0.02)
            newer.write_text("{}", encoding="utf-8")

            latest = module_find_latest_artifact(out_dir, "Steam Deals*.json")

        self.assertEqual(latest, newer)

    def test_write_output_artifacts_writes_all_enabled_outputs(self) -> None:
        written = []

        def fake_write_artifact(path: Path, content: str) -> Path:
            written.append((path, content))
            return path

        result = module_write_output_artifacts(
            ModuleOutputArtifactPaths(
                output_md=Path("/tmp/out/Steam Deals 2026-04-14.md"),
                output_html=Path("/tmp/out/Steam Deals 2026-04-14.html"),
                output_share=Path("/tmp/out/Steam Deals Share 2026-04-14.html"),
                output_json=Path("/tmp/out/Steam Deals 2026-04-14.json"),
                output_csv=Path("/tmp/out/Steam Deals 2026-04-14.csv"),
            ),
            ModuleOutputArtifactPayloads(
                markdown="md",
                html="html",
                share_html="share",
                json_content="json",
                csv_content="csv",
            ),
            write_artifact_fn=fake_write_artifact,
        )

        self.assertEqual(
            written,
            [
                (Path("/tmp/out/Steam Deals 2026-04-14.md"), "md"),
                (Path("/tmp/out/Steam Deals 2026-04-14.html"), "html"),
                (Path("/tmp/out/Steam Deals Share 2026-04-14.html"), "share"),
                (Path("/tmp/out/Steam Deals 2026-04-14.json"), "json"),
                (Path("/tmp/out/Steam Deals 2026-04-14.csv"), "csv"),
            ],
        )
        self.assertEqual(result["markdown"], Path("/tmp/out/Steam Deals 2026-04-14.md"))
        self.assertEqual(result["json"], Path("/tmp/out/Steam Deals 2026-04-14.json"))
        self.assertEqual(result["csv"], Path("/tmp/out/Steam Deals 2026-04-14.csv"))


class StopApiContractTests(unittest.TestCase):
    def test_build_stop_response_returns_status_and_message(self) -> None:
        from steam_deals_web import _build_stop_response

        self.assertEqual(
            _build_stop_response("stopped", "ok"),
            {"status": "stopped", "message": "ok"},
        )

    def test_stop_contract_examples_match_expected_ui_states(self) -> None:
        self.assertEqual(
            {
                "status": "stopped",
                "message": "La ejecución se detuvo correctamente.",
            },
            {
                "status": "stopped",
                "message": "La ejecución se detuvo correctamente.",
            },
        )
        self.assertEqual(
            {
                "status": "not_running",
                "message": "No había una ejecución activa para detener.",
            },
            {
                "status": "not_running",
                "message": "No había una ejecución activa para detener.",
            },
        )
        self.assertEqual(
            {
                "status": "stop_timeout",
                "message": "Se intentó detener la ejecución, pero el proceso sigue activo.",
            },
            {
                "status": "stop_timeout",
                "message": "Se intentó detener la ejecución, pero el proceso sigue activo.",
            },
        )

    def test_write_output_artifacts_preserves_required_desktop_closeout_outputs(
        self,
    ) -> None:
        written = []

        def fake_write_artifact(path: Path, content: str) -> Path:
            written.append(path)
            return path

        module_write_output_artifacts(
            ModuleOutputArtifactPaths(
                output_md=Path("/tmp/out/Steam Deals 2026-04-14.md"),
                output_html=Path("/tmp/out/Steam Deals 2026-04-14.html"),
                output_share=Path("/tmp/out/Steam Deals Share 2026-04-14.html"),
                output_json=Path("/tmp/out/Steam Deals 2026-04-14.json"),
                output_csv=Path("/tmp/out/Steam Deals 2026-04-14.csv"),
            ),
            ModuleOutputArtifactPayloads(
                markdown="md",
                html="html",
                share_html="share",
                json_content="json",
                csv_content="csv",
            ),
            write_artifact_fn=fake_write_artifact,
        )

        self.assertTrue(any(path.suffix == ".md" for path in written))
        self.assertTrue(any(path.suffix == ".html" and "Share" not in path.name for path in written))
        self.assertTrue(any(path.suffix == ".csv" for path in written))

    def test_generate_json_serializes_summary_and_set_based_comparison(self) -> None:
        payload = generate_json(
            deals=[
                {"appid": "10", "name": "Portal 2", "discount": 80, "price_final": "$8"}
            ],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={"20": "Half-Life"},
            wishlist_appids=["10", "20"],
            min_discount=50,
            genres=["puzzle"],
            sale_name="Steam Sale",
            previous_appids={"20"},
            top_picks=[{"appid": "10", "name": "Portal 2", "score": 95.4}],
            comparison={"new_deals": {"10"}, "disappeared": [{"appid": "20"}]},
            profile_display_name="gaben Display",
        )

        data = json.loads(payload)

        self.assertEqual(data["meta"]["profile"], "gaben Display")
        self.assertEqual(data["summary"]["deals_count"], 1)
        self.assertEqual(data["summary"]["new_deals_count"], 1)
        self.assertEqual(data["inputs"]["wishlist_count"], 2)
        self.assertEqual(data["comparison"]["new_deals"], ["10"])
        self.assertEqual(data["top_picks"][0]["score"], 95.4)

    def test_generate_json_includes_active_promo_context_when_provided(self) -> None:
        promo_context = {
            "sale_name": "Steam Farming Fest",
            "primary": {"title": "Steam Farming Fest", "type": 1, "category": "fest"},
            "promos": [
                {"title": "Steam Farming Fest", "type": 1, "category": "fest"},
                {"title": "Weeklong Deals", "type": 11, "category": "weeklong"},
            ],
            "categories": {"fest", "weeklong"},
        }

        payload = generate_json(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            sale_name="Steam Farming Fest",
            active_promo_context=promo_context,
        )

        data = json.loads(payload)

        self.assertEqual(data["meta"]["sale_name"], "Steam Farming Fest")
        self.assertEqual(data["meta"]["active_promo_context"]["primary"]["category"], "fest")
        self.assertEqual(data["meta"]["active_promo_context"]["categories"], ["fest", "weeklong"])

    def test_generate_json_omits_active_promo_context_when_absent(self) -> None:
        payload = generate_json(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
        )

        data = json.loads(payload)

        self.assertNotIn("active_promo_context", data["meta"])

    def test_save_run_history_persists_active_promo_context_when_provided(self) -> None:
        promo_context = {
            "sale_name": "Steam Farming Fest",
            "primary": {"title": "Steam Farming Fest", "type": 1, "category": "fest"},
            "promos": [{"title": "Steam Farming Fest", "type": 1, "category": "fest"}],
            "categories": ["fest"],
        }

        with TemporaryDirectory() as temp_dir:
            path = module_save_run_history(
                "steam-id",
                "gaben",
                "Steam Farming Fest",
                50,
                [
                    {
                        "appid": "10",
                        "name": "Alpha",
                        "discount": 60,
                        "price_final": "$6",
                        "price_raw": 600,
                    }
                ],
                history_dir=Path(temp_dir),
                history_max_files=10,
                now=datetime(2026, 4, 24, 10, 0, 0),
                active_promo_context=promo_context,
            )

            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["sale_name"], "Steam Farming Fest")
        self.assertEqual(data["active_promo_context"]["primary"]["category"], "fest")
        self.assertEqual(data["deals"]["10"]["price_raw"], 600)

    def test_save_run_history_keeps_existing_shape_without_promo_context(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = module_save_run_history(
                "steam-id",
                "gaben",
                "Steam Sale",
                50,
                [],
                history_dir=Path(temp_dir),
                history_max_files=10,
                now=datetime(2026, 4, 24, 10, 0, 0),
            )

            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["sale_name"], "Steam Sale")
        self.assertNotIn("active_promo_context", data)

    def test_generate_json_preserves_extended_budget_payload(self) -> None:
        budget_result = compute_budget_picks(
            deals=[
                {"appid": "a", "price_raw": 1500, "discount": 50, "name": "Alpha"},
                {"appid": "b", "price_raw": 1000, "discount": 50, "name": "Bravo"},
                {"appid": "c", "price_raw": 500, "discount": 50, "name": "Charlie"},
                {"appid": "d", "price_raw": 400, "discount": 50, "name": "Delta"},
            ],
            budget_mxn=15,
            top_picks=[
                {"appid": "a", "score": 95.0},
                {"appid": "b", "score": 80.0},
                {"appid": "c", "score": 60.0},
                {"appid": "d", "score": 30.0},
            ],
            watchlist_alerts=[],
        )

        payload = generate_json(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            budget_result=budget_result,
        )

        data = json.loads(payload)

        self.assertEqual(data["budget_result"]["selected_variant"], "balanced")
        self.assertEqual(
            [variant["id"] for variant in data["budget_result"]["variants"]],
            ["small", "balanced", "large"],
        )
        self.assertIn("actions", data["budget_result"])

    def test_build_final_summary_preserves_current_fields(self) -> None:
        new_count, summary = module_build_final_summary(
            12.3,
            [{"appid": "10"}, {"appid": "20"}],
            [{"appid": "10"}],
            {"10"},
            [{"name": "Portal 2", "score": 95.4}],
            Path("/tmp/Steam Deals 2026-04-14.md"),
        )

        self.assertEqual(new_count, 1)
        self.assertEqual(
            summary,
            "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · Steam Deals 2026-04-14.md",
        )

    def test_build_final_summary_appends_smart_alerts_when_present(self) -> None:
        new_count, summary = module_build_final_summary(
            12.3,
            [{"appid": "10"}, {"appid": "20"}],
            [{"appid": "10"}],
            {"10"},
            [{"name": "Portal 2", "score": 95.4}],
            Path("/tmp/Steam Deals 2026-04-14.md"),
            {
                "best_local_count": 2,
                "price_up_count": 1,
                "global_historical_low_count": 3,
                "active_bundles_count": 2,
            },
        )

        self.assertEqual(new_count, 1)
        self.assertEqual(
            summary,
            "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · 2 mejor local · 1 subieron · 3 mín. global · 2 bundles activos · Steam Deals 2026-04-14.md",
        )

    def test_generator_build_final_summary_accepts_smart_alerts(self) -> None:
        new_count, summary = generator_build_final_summary(
            12.3,
            [{"appid": "10"}, {"appid": "20"}],
            [{"appid": "10"}],
            {"10"},
            [{"name": "Portal 2", "score": 95.4}],
            Path("/tmp/Steam Deals 2026-04-14.md"),
            {
                "best_local_count": 2,
                "price_up_count": 1,
                "global_historical_low_count": 3,
                "active_bundles_count": 2,
            },
        )

        self.assertEqual(new_count, 1)
        self.assertEqual(
            summary,
            "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · 2 mejor local · 1 subieron · 3 mín. global · 2 bundles activos · Steam Deals 2026-04-14.md",
        )

    def test_emit_final_closeout_preserves_visible_summary_output(self) -> None:
        emitted = []

        new_count, summary = module_emit_final_closeout(
            12.3,
            [{"appid": "10"}, {"appid": "20"}],
            [{"appid": "10"}],
            {"10"},
            [{"name": "Portal 2", "score": 95.4}],
            Path("/tmp/Steam Deals 2026-04-14.md"),
            build_final_summary_fn=module_build_final_summary,
            emit_fn=emitted.append,
            bold_fn=lambda text: f"**{text}**",
            color_green="<g>",
            color_reset="</g>",
        )

        self.assertEqual(new_count, 1)
        self.assertEqual(
            summary,
            "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · Steam Deals 2026-04-14.md",
        )
        self.assertEqual(
            emitted,
            [
                "\n<g>──────────────────────────────────────────</g>",
                "  **Listo** en 12.3s",
                "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · Steam Deals 2026-04-14.md",
                "<g>──────────────────────────────────────────</g>\n",
            ],
        )

    def test_emit_final_closeout_includes_smart_alerts_in_visible_summary(self) -> None:
        emitted = []

        new_count, summary = module_emit_final_closeout(
            12.3,
            [{"appid": "10"}, {"appid": "20"}],
            [{"appid": "10"}],
            {"10"},
            [{"name": "Portal 2", "score": 95.4}],
            Path("/tmp/Steam Deals 2026-04-14.md"),
            smart_alerts={
                "best_local_count": 2,
                "price_up_count": 1,
                "global_historical_low_count": 3,
                "active_bundles_count": 2,
            },
            build_final_summary_fn=module_build_final_summary,
            emit_fn=emitted.append,
            bold_fn=lambda text: f"**{text}**",
            color_green="<g>",
            color_reset="</g>",
        )

        self.assertEqual(new_count, 1)
        self.assertEqual(
            summary,
            "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · 2 mejor local · 1 subieron · 3 mín. global · 2 bundles activos · Steam Deals 2026-04-14.md",
        )
        self.assertEqual(
            emitted,
            [
                "\n<g>──────────────────────────────────────────</g>",
                "  **Listo** en 12.3s",
                "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · 2 mejor local · 1 subieron · 3 mín. global · 2 bundles activos · Steam Deals 2026-04-14.md",
                "<g>──────────────────────────────────────────</g>\n",
            ],
        )


class SmartAlertsTests(unittest.TestCase):
    def test_smart_alerts_calibrate_unscored_fixture(self) -> None:
        result = module_build_smart_alert_counts(
            deals=[
                {"appid": "10", "price_raw": 1000},
                {"appid": "20", "price_raw": 1300},
                {"appid": "30", "price_raw": 500},
            ],
            historical_lows={
                "10": {"price": 9.80},
                "20": {"price": 12.00},
                "30": {"price": None},
            },
            active_bundles={
                "10": [{"title": "Bundle Alpha"}, {"title": "Bundle Shared"}],
                "20": [{"title": "Bundle Shared"}],
            },
            comparison={
                "price_changes": {
                    "10": {"direction": "up", "change_pct": 12.5},
                    "20": {"direction": "up", "change_pct": 9.9},
                    "30": {"direction": "down", "change_pct": 20.0},
                }
            },
            local_trends={
                "10": {"is_best_local": True, "is_first_time": False},
                "20": {"is_best_local": True, "is_first_time": True},
                "30": {"is_best_local": False, "is_first_time": False},
            },
            alert_global_margin_pct=3.0,
            alert_rise_pct=10.0,
        )

        self.assertEqual(
            result,
            {
                "best_local_count": 1,
                "price_up_count": 1,
                "global_historical_low_count": 1,
                "active_bundles_count": 2,
                "active_bundle_games_count": 2,
            },
        )

    def test_smart_alerts_apply_score_minimum_to_top_picks(self) -> None:
        result = module_build_smart_alert_counts(
            deals=[
                {"appid": "10", "price_raw": 1000},
                {"appid": "20", "price_raw": 700},
                {"appid": "30", "price_raw": 500},
            ],
            historical_lows={
                "10": {"price": 10.00},
                "20": {"price": 7.00},
                "30": {"price": 5.00},
            },
            active_bundles={
                "10": [{"title": "Bundle Alpha"}],
                "20": [{"title": "Bundle Beta"}],
                "30": [{"title": "Bundle Alpha"}],
            },
            comparison={
                "price_changes": {
                    "10": {"direction": "up", "change_pct": 15.0},
                    "20": {"direction": "up", "change_pct": 15.0},
                    "30": {"direction": "up", "change_pct": 5.0},
                }
            },
            local_trends={
                "10": {"is_best_local": True, "is_first_time": False},
                "20": {"is_best_local": True, "is_first_time": False},
                "30": {"is_best_local": True, "is_first_time": False},
            },
            top_picks=[
                {"appid": "10", "score": 90.0},
                {"appid": "20", "score": 79.9},
                {"appid": "30", "score": 85.0},
            ],
            alert_global_margin_pct=0.0,
            alert_rise_pct=10.0,
            alert_score_min=80.0,
        )

        self.assertEqual(
            result,
            {
                "best_local_count": 2,
                "price_up_count": 1,
                "global_historical_low_count": 2,
                "active_bundles_count": 1,
                "active_bundle_games_count": 2,
            },
        )

    def test_generator_smart_alerts_wrapper_accepts_empty_sources(self) -> None:
        result = generator_build_smart_alert_counts(
            deals=[],
            historical_lows=None,
            active_bundles=None,
            comparison=None,
            local_trends=None,
        )

        self.assertEqual(
            result,
            {
                "best_local_count": 0,
                "price_up_count": 0,
                "global_historical_low_count": 0,
                "active_bundles_count": 0,
                "active_bundle_games_count": 0,
            },
        )


class RuntimeReportingTests(unittest.TestCase):
    def test_safe_symbol_uses_fallback_for_incompatible_encoding(self) -> None:
        result = module_safe_symbol("🎯", "[ALERT]", stdout_encoding="ascii")

        self.assertEqual(result, "[ALERT]")

    def test_emit_event_prints_prefixed_json_only_in_web_mode(self) -> None:
        emitted = []

        module_emit_event(
            "progress",
            web_event_mode=True,
            emit=lambda text, **_kwargs: emitted.append(text),
            current=1,
            total=2,
            label="Paso",
        )
        module_emit_event(
            "progress",
            web_event_mode=False,
            emit=lambda text, **_kwargs: emitted.append(text),
            current=2,
            total=2,
            label="Nope",
        )

        self.assertEqual(len(emitted), 1)
        self.assertTrue(emitted[0].startswith("__STEAM_EVENT__"))
        self.assertIn('"label": "Paso"', emitted[0])

    def test_report_step_emits_cli_line_and_progress_event(self) -> None:
        emitted = []
        events = []

        module_report_step(
            2,
            5,
            "Obteniendo wishlist...",
            emit=lambda text, **_kwargs: emitted.append(text),
            emit_event_fn=lambda event_type, **payload: events.append(
                (event_type, payload)
            ),
            bold_fn=lambda text: f"<b>{text}</b>",
            color_cyan="[CYAN]",
            color_reset="[/CYAN]",
        )

        self.assertEqual(
            emitted, ["\n[CYAN][2/5][/CYAN] <b>Obteniendo wishlist...</b>"]
        )
        self.assertEqual(
            events,
            [
                (
                    "progress",
                    {"current": 2, "total": 5, "label": "Obteniendo wishlist..."},
                )
            ],
        )


class ApplyFiltersTests(unittest.TestCase):
    def test_post_processing_preserves_hltb_hours_filtered_deals_and_top_picks(
        self,
    ) -> None:
        emitted: list[str] = []
        contract = module_build_post_processing_contract(
            messages=module_build_post_processing_message_formatters(
                ok=lambda text: f"OK:{text}"
            ),
            callbacks=module_build_post_processing_callbacks(emit=emitted.append),
            runtime=module_build_post_processing_runtime(
                apply_filters=lambda deals, *_args: deals[1:],
                rank_top_picks=lambda deals, *_args, **_kwargs: [
                    {"appid": deal["appid"], "score": 99.0} for deal in deals
                ],
            ),
        )

        outputs = module_run_post_processing(
            [{"appid": "a"}, {"appid": "b"}, {"appid": "c"}],
            [{"appid": "a", "hours": 10.0}],
            [{"appid": "b", "hours": 5.5}, {"appid": "c", "hours": None}],
            filters={"top": 5},
            priorities={},
            reviews_data={},
            deck_data={},
            previous_appids=set(),
            comparison=None,
            contract=contract,
        )

        self.assertEqual(outputs.hltb_hours, {"a": 10.0, "b": 5.5})
        self.assertEqual([deal["appid"] for deal in outputs.deals], ["b", "c"])
        self.assertEqual(
            outputs.top_picks,
            [{"appid": "b", "score": 99.0}, {"appid": "c", "score": 99.0}],
        )
        self.assertEqual(emitted, ["  OK:Filtros aplicados: 3 → 2 deals"])

    def test_post_processing_passes_active_promo_context_to_ranker(self) -> None:
        received = {}

        def fake_rank_top_picks(deals, *_args, **kwargs):
            received["promo_context"] = kwargs.get("active_promo_context")
            return [{"appid": deal["appid"], "score": 99.0} for deal in deals]

        contract = module_build_post_processing_contract(
            messages=module_build_post_processing_message_formatters(
                ok=lambda text: f"OK:{text}"
            ),
            callbacks=module_build_post_processing_callbacks(emit=lambda _text: None),
            runtime=module_build_post_processing_runtime(
                apply_filters=lambda deals, *_args: deals,
                rank_top_picks=fake_rank_top_picks,
            ),
        )
        promo_context = {
            "sale_name": "Steam Farming Fest",
            "primary": {"title": "Steam Farming Fest", "category": "fest"},
            "categories": ["fest"],
        }

        module_run_post_processing(
            [{"appid": "a"}],
            [],
            [],
            filters={"top": 5},
            priorities={},
            reviews_data={},
            deck_data={},
            previous_appids=set(),
            comparison=None,
            contract=contract,
            active_promo_context=promo_context,
        )

        self.assertEqual(received["promo_context"], promo_context)

    def test_filter_by_genres_returns_discount_sorted_matches(self) -> None:
        deals = [
            {"appid": "a", "discount": 40, "genres": ["roguelike", "action"]},
            {"appid": "b", "discount": 80, "genres": ["indie"]},
            {"appid": "c", "discount": 60, "genres": ["roguelike deckbuilder"]},
        ]

        filtered = filter_by_genres(deals, ["roguelike"])

        self.assertEqual([deal["appid"] for deal in filtered], ["c", "a"])

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


class HistoryAndTrendTests(unittest.TestCase):
    def test_load_previous_deal_appids_reads_previous_markdown_fallback(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "Steam Deals 2026-04-13.md").write_text(
                "https://store.steampowered.com/app/10/\nhttps://store.steampowered.com/app/20/\n",
                encoding="utf-8",
            )
            (output_dir / "Steam Deals 2026-04-14.md").write_text(
                "current", encoding="utf-8"
            )

            previous_appids = load_previous_deal_appids(
                output_dir, "Steam Deals 2026-04-14.md"
            )

        self.assertEqual(previous_appids, {"10", "20"})

    def test_compute_deal_comparison_tracks_new_changes_disappeared_and_streak(
        self,
    ) -> None:
        current_deals = [
            {"appid": "a", "price_raw": 500, "price_final": "$5", "discount": 50},
            {"appid": "b", "price_raw": 900, "price_final": "$9", "discount": 60},
        ]
        previous_run = {
            "date": "2026-04-13",
            "deals": {
                "a": {
                    "name": "Alpha",
                    "discount": 40,
                    "price_final": "$6",
                    "price_raw": 600,
                },
                "c": {
                    "name": "Charlie",
                    "discount": 30,
                    "price_final": "$7",
                    "price_raw": 700,
                },
            },
        }
        run_history = [{"deals": {"a": {}, "b": {}}}, {"deals": {"a": {}}}]

        comparison = compute_deal_comparison(current_deals, previous_run, run_history)

        self.assertEqual(comparison["new_deals"], {"b"})
        self.assertEqual(comparison["price_changes"]["a"]["direction"], "down")
        self.assertEqual(comparison["price_changes"]["a"]["prev_price_raw"], 600)
        self.assertEqual(comparison["price_changes"]["a"]["change_pct"], -16.67)
        self.assertEqual(comparison["disappeared"][0]["appid"], "c")
        self.assertEqual(comparison["deal_streak"]["a"], 3)

    def test_analyze_trends_and_format_trend_surface_local_best_price(self) -> None:
        today_str = date.today().isoformat()
        history = {
            "games": {
                "a": {
                    "name": "Alpha",
                    "snapshots": [
                        {"date": "2026-04-10", "discount": 40, "price_raw": 900},
                        {"date": today_str, "discount": 50, "price_raw": 800},
                    ],
                }
            }
        }
        deals = [{"appid": "a", "price_raw": 800}]

        trends = analyze_trends(history, deals)

        self.assertEqual(trends["a"]["is_best_local"], True)
        self.assertEqual(format_trend(trends["a"]), "🔥 Mín. local")

    def test_format_trend_uses_clear_copy_for_generic_history(self) -> None:
        label = format_trend(
            {
                "times_on_sale": 3,
                "is_first_time": False,
                "is_best_local": False,
                "is_first_at_price": False,
                "avg_fmt": "$10",
            }
        )

        self.assertEqual(label, "Historial local: 3x · prom $10")

    def test_generate_md_hides_trend_column_when_only_low_signal_history_exists(self) -> None:
        md = generate_md(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 50,
                    "price_final": "$10",
                    "price_original": "$20",
                    "price_raw": 1000,
                    "categories": [],
                }
            ],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            local_trends={"a": {"times_on_sale": 1, "is_first_time": True}},
        )

        self.assertNotIn("Historial local", md)
        self.assertNotIn("1ra vez", md)

    def test_generate_md_shows_only_useful_local_trend_signals(self) -> None:
        md = generate_md(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 50,
                    "price_final": "$10",
                    "price_original": "$20",
                    "price_raw": 1000,
                    "categories": [],
                },
                {
                    "appid": "b",
                    "name": "Bravo",
                    "discount": 50,
                    "price_final": "$11",
                    "price_original": "$22",
                    "price_raw": 1100,
                    "categories": [],
                },
            ],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a", "b"],
            min_discount=50,
            genres=[],
            local_trends={
                "a": {
                    "times_on_sale": 2,
                    "is_first_time": False,
                    "is_best_local": True,
                    "is_first_at_price": False,
                    "avg_fmt": "$12",
                },
                "b": {
                    "times_on_sale": 3,
                    "is_first_time": False,
                    "is_best_local": False,
                    "is_first_at_price": False,
                    "avg_fmt": "$11",
                },
            },
        )

        self.assertIn("Historial local = señal útil", md)
        self.assertIn("| Historial local |", md)
        self.assertIn("🔥 Mín. local", md)
        self.assertNotIn("Historial local: 3x", md)


class ItadAdapterTests(unittest.TestCase):
    def test_itad_orchestration_preserves_visible_messages_and_outputs(self) -> None:
        steps: list[str] = []
        emits: list[str] = []

        contract = module_build_itad_orchestration_contract(
            progress=module_build_itad_progress_callbacks(
                step=steps.append, emit=emits.append
            ),
            messages=module_build_itad_message_formatters(
                ok=lambda text: f"OK:{text}",
                dim=lambda text: f"DIM:{text}",
            ),
            runtime=module_build_itad_runtime(
                lookup_games=lambda _appids, _key: {"10": "itad-10", "20": "itad-20"},
                get_store_lows=lambda _ids, _key, country="MX": {"10": {"price": 100}},
                get_current_prices=lambda _ids, _key, country="MX": {
                    "20": {"store": "Fanatical", "price": 80}
                },
                get_active_bundles=lambda _ids, _key, country="US": {
                    "10": [{"title": "Bundle A"}],
                    "20": [{"title": "Bundle B"}],
                },
            ),
        )

        outputs = module_run_itad_orchestration(
            ["10", "20", "30"], "itad-key", contract=contract
        )

        self.assertEqual(steps, ["Obteniendo datos de IsThereAnyDeal..."])
        self.assertEqual(
            emits,
            [
                "  OK:2/3 juegos encontrados en ITAD",
                "  OK:1 mínimos históricos obtenidos",
                "  OK:1 juegos más baratos en otra tienda",
                "  OK:2 juegos en 2 bundle(s)",
            ],
        )
        self.assertEqual(outputs.itad_ids, {"10": "itad-10", "20": "itad-20"})
        self.assertEqual(outputs.historical_lows, {"10": {"price": 100}})
        self.assertEqual(
            outputs.current_prices, {"20": {"store": "Fanatical", "price": 80}}
        )
        self.assertEqual(outputs.active_bundles["10"][0]["title"], "Bundle A")

    def test_itad_lookup_games_maps_found_entries_by_appid(self) -> None:
        def fake_post_json(_url, _body):
            return [
                {"found": True, "game": {"id": "itad-10"}},
                {"found": False},
            ]

        result = module_itad_lookup_games(
            ["10", "20"],
            "key",
            post_json=fake_post_json,
            sleep_fn=lambda _seconds: None,
        )

        self.assertEqual(result, {"10": "itad-10"})

    def test_itad_get_store_lows_preserves_expected_shape(self) -> None:
        def fake_post_json(_url, _body):
            return [
                {
                    "id": "itad-10",
                    "lows": [
                        {
                            "price": {"amount": 99, "currency": "MXN"},
                            "cut": 80,
                            "timestamp": "2026-04-10T00:00:00Z",
                        }
                    ],
                }
            ]

        result = module_itad_get_store_lows(
            {"10": "itad-10"},
            "key",
            post_json=fake_post_json,
            sleep_fn=lambda _seconds: None,
        )

        self.assertEqual(result["10"]["price"], 99)
        self.assertEqual(result["10"]["currency"], "MXN")
        self.assertEqual(result["10"]["date"], "2026-04-10")

    def test_itad_get_current_prices_only_returns_better_non_steam_prices(self) -> None:
        def fake_post_json(_url, _body):
            return [
                {
                    "id": "itad-10",
                    "deals": [
                        {
                            "shop": {"id": 61, "name": "Steam"},
                            "price": {"amount": 100},
                            "url": "steam",
                        },
                        {
                            "shop": {"id": 2, "name": "Fanatical"},
                            "price": {"amount": 80},
                            "url": "fan",
                        },
                    ],
                }
            ]

        result = module_itad_get_current_prices(
            {"10": "itad-10"},
            "key",
            post_json=fake_post_json,
            sleep_fn=lambda _seconds: None,
        )

        self.assertEqual(result["10"]["store"], "Fanatical")
        self.assertEqual(result["10"]["price"], 80)

    def test_itad_get_active_bundles_deduplicates_by_title_per_appid(self) -> None:
        def fake_post_json(_url, _body):
            return {
                "bundles": [
                    {
                        "title": "Bundle A",
                        "page": {"name": "Humble"},
                        "url": "bundle-a",
                        "tiers": [
                            {
                                "price": {"amount": 12, "currency": "USD"},
                                "games": [{"id": "itad-10"}, {"id": "itad-10"}],
                            }
                        ],
                    }
                ]
            }

        result = module_itad_get_active_bundles(
            {"10": "itad-10"},
            "key",
            post_json=fake_post_json,
            sleep_fn=lambda _seconds: None,
        )

        self.assertEqual(len(result["10"]), 1)
        self.assertEqual(result["10"][0]["title"], "Bundle A")

    def test_new_only_falls_back_to_previous_appids_when_comparison_is_empty(
        self,
    ) -> None:
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


class WatchlistTests(unittest.TestCase):
    def test_engagement_post_run_preserves_visible_outputs_and_notifications(
        self,
    ) -> None:
        steps: list[str] = []
        emits: list[str] = []
        sent_notifications: list[tuple[dict, dict]] = []

        contract = module_build_engagement_contract(
            messages=module_build_engagement_message_formatters(
                ok=lambda text: f"OK:{text}",
                dim=lambda text: f"DIM:{text}",
            ),
            callbacks=module_build_engagement_callbacks(
                step=steps.append,
                emit=emits.append,
            ),
            runtime=module_build_engagement_runtime(
                load_watchlist=lambda: [
                    {"appid": "10", "name": "Portal 2", "target_price": 9.0}
                ],
                check_watchlist_alerts=lambda _deals, _watchlist: [
                    {
                        "appid": "10",
                        "name": "Portal 2",
                        "price_final": "$8",
                        "target_price": 9.0,
                        "price_raw": 800,
                    }
                ],
                compute_budget_picks=lambda _deals, budget, _top_picks, _watchlist_alerts: {
                    "budget": budget,
                    "games_count": 1,
                    "total_spent": 8.0,
                },
                build_gift_ideas=lambda _friend_set, _deals, _owned: [
                    {"appid": "20", "name": "Hades"}
                ],
                build_notification_summary=lambda _deals, _comparison, _top_picks, _watchlist_alerts: {
                    "total_deals": 1
                },
                send_notifications=lambda filters, summary: sent_notifications.append(
                    (filters, summary)
                ),
            ),
        )

        outputs = module_run_engagement_post_run(
            [
                {
                    "appid": "10",
                    "name": "Portal 2",
                    "price_final": "$8",
                    "price_raw": 800,
                }
            ],
            filters={"budget": 10.0, "telegram_token": "token"},
            top_picks=[{"appid": "10", "score": 95.0}],
            compare_data={"friend_set": {"20"}},
            owned={"10": "Portal 2"},
            comparison={"new_deals": {"10"}},
            contract=contract,
            sym_target="🎯",
            sym_budget="💸",
            sym_gift="🎁",
        )

        self.assertEqual(steps, ["Enviando notificaciones..."])
        self.assertEqual(
            emits,
            [
                "  OK:🎯 1 watchlist alerts!",
                "    Portal 2 — $8 (objetivo: $9)",
                "  OK:💸 Budget $10: 1 juegos, $8 gastados",
                "  OK:🎁 1 gift ideas en oferta",
            ],
        )
        self.assertEqual(outputs.watchlist_alerts[0]["appid"], "10")
        self.assertEqual(outputs.budget_result["games_count"], 1)
        self.assertEqual(outputs.gift_ideas[0]["appid"], "20")
        self.assertEqual(outputs.notification_summary, {"total_deals": 1})
        self.assertEqual(
            sent_notifications,
            [({"budget": 10.0, "telegram_token": "token"}, {"total_deals": 1})],
        )

    def test_save_and_load_watchlist_roundtrip(self) -> None:
        items = [{"appid": "10", "name": "Portal 2", "target_price": 99.0}]

        with TemporaryDirectory() as temp_dir:
            watchlist_file = Path(temp_dir) / "watchlist.json"
            module_save_watchlist(items, watchlist_file)
            loaded = module_load_watchlist(watchlist_file)

        self.assertEqual(loaded, items)

    def test_handle_watchlist_command_add_resolves_name_and_saves_entry(self) -> None:
        emitted = []

        with TemporaryDirectory() as temp_dir:
            watchlist_file = Path(temp_dir) / "watchlist.json"
            handled = module_handle_watchlist_command(
                ["add", "10", "99"],
                watchlist_file=watchlist_file,
                resolve_name=lambda _appid: "Portal 2",
                emit=emitted.append,
            )
            loaded = module_load_watchlist(watchlist_file)

        self.assertEqual(handled, True)
        self.assertEqual(loaded[0]["name"], "Portal 2")

    def test_check_watchlist_alerts_returns_matching_deals_with_target_price(
        self,
    ) -> None:
        deals = [{"appid": "10", "price_raw": 800, "discount": 50, "name": "Portal 2"}]
        watchlist = [{"appid": "10", "name": "Portal 2", "target_price": 9.0}]

        alerts = module_check_watchlist_alerts(deals, watchlist)

        self.assertEqual(alerts[0]["appid"], "10")
        self.assertEqual(alerts[0]["target_price"], 9.0)


class SteamAdapterTests(unittest.TestCase):
    def test_resolve_steam_id_uses_public_xml_fallback_without_key(self) -> None:
        steam_id = module_resolve_steam_id(
            None,
            "gaben",
            get_json=lambda _url: {},
            fetch_public_profile_xml=lambda _vanity: (
                "<steamID64>76561198000000000</steamID64>"
            ),
        )

        self.assertEqual(steam_id, "76561198000000000")

    def test_get_wishlist_returns_appids_and_priorities(self) -> None:
        appids, priorities = module_get_wishlist(
            "key",
            "steam-id",
            get_json=lambda _url: {
                "response": {
                    "items": [
                        {"appid": 10, "priority": 1},
                        {"appid": 20, "priority": 5},
                    ]
                }
            },
        )

        self.assertEqual(appids, ["10", "20"])
        self.assertEqual(priorities["20"], 5)

    def test_get_wishlist_converts_private_http_error_to_value_error(self) -> None:
        def fake_get_json(_url):
            raise urllib.error.HTTPError(_url, 403, "Forbidden", hdrs=None, fp=None)

        with self.assertRaises(ValueError):
            module_get_wishlist(None, "steam-id", get_json=fake_get_json)

    def test_compare_wishlists_returns_friend_payload(self) -> None:
        comparison = module_compare_wishlists(
            "key",
            "me",
            "friend",
            resolve_steam_id_fn=lambda _api_key, _vanity: "friend-id",
            get_wishlist_fn=lambda _api_key, _steam_id: (["10", "20"], {"10": 1}),
            resolve_profile_display_name_fn=lambda _steam_id, _vanity, _api_key: "Johnny",
        )

        self.assertEqual(comparison["friend_id"], "friend-id")
        self.assertEqual(comparison["friend_name"], "Johnny")
        self.assertEqual(comparison["friend_set"], {"10", "20"})

    def test_load_family_games_supports_dict_shape(self) -> None:
        with TemporaryDirectory() as temp_dir:
            family_path = Path(temp_dir) / "family.json"
            family_path.write_text(
                '{"10": "Portal 2", "20": "Hades"}', encoding="utf-8"
            )

            appids = module_load_family_games(family_path)

        self.assertEqual(appids, {"10", "20"})

    def test_cross_hltb_with_family_context_passes_family_appids_to_matcher(
        self,
    ) -> None:
        captured = {}

        def fake_cross_hltb(hltb, deals, *, family_appids):
            captured["hltb"] = hltb
            captured["deals"] = deals
            captured["family_appids"] = family_appids
            return ([{"appid": "10", "in_family": True}], [])

        backlog_on_sale, have_on_sale = module_cross_hltb_with_family_context(
            {"backlog": [], "completed": [], "playing": [], "retired": []},
            [{"appid": "10", "name": "Portal 2"}],
            ModuleFamilyContext(family_appids={"10", "20"}),
            cross_hltb_with_deals_fn=fake_cross_hltb,
        )

        self.assertEqual(captured["family_appids"], {"10", "20"})
        self.assertEqual(backlog_on_sale, [{"appid": "10", "in_family": True}])
        self.assertEqual(have_on_sale, [])

    def test_build_family_renderer_kwargs_clones_family_appids(self) -> None:
        family_context = ModuleFamilyContext(family_appids={"10", "20"})
        kwargs = module_build_family_renderer_kwargs(family_context)

        self.assertEqual(kwargs, {"family_appids": {"10", "20"}})
        self.assertIsNot(kwargs["family_appids"], family_context.family_appids)

    def test_get_active_sale_prefers_primary_event_type(self) -> None:
        sale_name = module_get_active_sale(
            get_json=lambda _url: {
                "response": {
                    "messages": [
                        {"type": 11, "title": "Weeklong Deals"},
                        {"type": 1, "title": "Steam Summer Sale"},
                    ]
                }
            }
        )

        self.assertEqual(sale_name, "Steam Summer Sale")

    def test_classify_steam_promo_message_detects_known_promo_categories(self) -> None:
        cases = [
            ({"type": 11, "title": "Weeklong Deals"}, "weeklong"),
            ({"type": 11, "title": "Midweek Madness"}, "midweek"),
            ({"type": 11, "title": "Weekend Deal"}, "weekend"),
            ({"type": 1, "title": "Steam Summer Sale"}, "major_sale"),
            ({"type": 1, "title": "Steam Farming Fest"}, "fest"),
            ({"type": 1, "title": "Puzzle Sale"}, "themed"),
        ]

        for message, expected_category in cases:
            with self.subTest(title=message["title"]):
                self.assertEqual(
                    module_classify_steam_promo_message(message)["category"],
                    expected_category,
                )

    def test_build_active_promo_context_preserves_primary_and_all_promos(self) -> None:
        context = module_build_active_promo_context(
            [
                {"type": 11, "title": "Weeklong Deals"},
                {"type": 1, "title": "Steam Farming Fest"},
                {"type": 99, "title": "Publisher Sale"},
                {"type": 11, "title": ""},
            ]
        )

        self.assertEqual(context["sale_name"], "Steam Farming Fest")
        self.assertEqual(context["primary"]["category"], "fest")
        self.assertEqual(
            [promo["category"] for promo in context["promos"]],
            ["weeklong", "fest", "themed"],
        )
        self.assertEqual(context["categories"], ["fest", "themed", "weeklong"])

    def test_get_active_promo_context_handles_api_errors_as_empty_context(self) -> None:
        context = module_get_active_promo_context(
            get_json=lambda _url: (_ for _ in ()).throw(RuntimeError("network"))
        )

        self.assertEqual(context["sale_name"], "")
        self.assertEqual(context["primary"], None)
        self.assertEqual(context["promos"], [])

    def test_resolve_profile_display_name_prefers_player_summary(self) -> None:
        display_name = module_resolve_profile_display_name(
            "76561198000000000",
            "https://steamcommunity.com/profiles/76561198000000000/",
            api_key="key",
            get_json=lambda _url: {"response": {"players": [{"personaname": "gaben"}]}},
            fetch_public_profile_xml=lambda _v: "",
        )

        self.assertEqual(display_name, "gaben")

    def test_resolve_profile_display_name_falls_back_to_xml_when_no_key(self) -> None:
        display_name = module_resolve_profile_display_name(
            "76561198000000000",
            "gaben",
            api_key=None,
            get_json=lambda _url: {},
            fetch_public_profile_xml=lambda _v: (
                "<steamID><![CDATA[gaben Public]]></steamID>"
            ),
        )

        self.assertEqual(display_name, "gaben Public")


class NotificationsTests(unittest.TestCase):
    def test_build_notification_summary_returns_none_when_nothing_notable(self) -> None:
        summary = module_build_notification_summary([], {}, [], watchlist_alerts=[])

        self.assertEqual(summary, None)

    def test_build_notification_summary_surfaces_top_picks_drops_and_watchlist(
        self,
    ) -> None:
        deals = [{"appid": "10", "name": "Portal 2"}]
        comparison = {
            "new_deals": {"10"},
            "price_changes": {
                "10": {
                    "direction": "down",
                    "delta_raw": -200,
                    "delta_str": "$2",
                    "prev_price": "$10",
                }
            },
        }
        top_picks = [
            {"name": "Portal 2", "discount": 80, "price_final": "$8", "score": 90.0}
        ]
        watchlist_alerts = [
            {"name": "Portal 2", "price_final": "$8", "target_price": 9.0}
        ]

        summary = module_build_notification_summary(
            deals, comparison, top_picks, watchlist_alerts=watchlist_alerts
        )

        self.assertEqual(summary["new_count"], 1)
        self.assertEqual(summary["top_3"][0]["name"], "Portal 2")
        self.assertEqual(summary["watchlist_hits"][0]["target"], 9.0)

    def test_send_telegram_returns_false_on_request_error(self) -> None:
        ok = module_send_telegram(
            "token",
            "chat",
            {
                "total_deals": 1,
                "new_count": 0,
                "top_3": [],
                "price_drops": [],
                "watchlist_hits": [],
            },
            post_json_request=lambda _url, _body, timeout=15: (_ for _ in ()).throw(
                RuntimeError("boom")
            ),
        )

        self.assertEqual(ok, False)

    def test_send_discord_returns_true_when_request_succeeds(self) -> None:
        ok = module_send_discord(
            "https://discord.invalid/webhook",
            {
                "total_deals": 1,
                "new_count": 0,
                "top_3": [],
                "price_drops": [],
                "watchlist_hits": [],
            },
            post_json_request=lambda _url, _body, timeout=15: {},
        )

        self.assertEqual(ok, True)

    def test_send_notifications_emits_success_messages_for_configured_channels(
        self,
    ) -> None:
        emitted = []

        module_send_notifications(
            {
                "telegram_token": "token",
                "telegram_chat": "chat",
                "discord_webhook": "hook",
            },
            {
                "total_deals": 1,
                "new_count": 0,
                "top_3": [],
                "price_drops": [],
                "watchlist_hits": [],
            },
            send_telegram_fn=lambda _token, _chat, _summary: True,
            send_discord_fn=lambda _webhook, _summary: True,
            emit=emitted.append,
        )

        self.assertEqual(len(emitted), 2)


class SchedulerTests(unittest.TestCase):
    def test_parse_schedule_hours_returns_none_for_missing_or_invalid_values(
        self,
    ) -> None:
        self.assertEqual(module_parse_schedule_hours(["prog"]), None)
        self.assertEqual(
            module_parse_schedule_hours(["prog", "--schedule", "oops"]), None
        )

    def test_run_scheduled_runs_once_without_schedule(self) -> None:
        calls = []

        module_run_scheduled(lambda: calls.append("main"), argv=["prog"])

        self.assertEqual(calls, ["main"])

    def test_run_scheduled_runs_once_for_zero_schedule(self) -> None:
        calls = []

        module_run_scheduled(
            lambda: calls.append("main"), argv=["prog", "--schedule", "0"]
        )

        self.assertEqual(calls, ["main"])

    def test_run_scheduled_loops_and_logs_next_run_until_sleep_interrupt(self) -> None:
        calls = []
        emitted = []
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            raise KeyboardInterrupt()

        module_run_scheduled(
            lambda: calls.append("main"),
            argv=["prog", "--schedule", "1"],
            now_fn=lambda: datetime(2026, 4, 14, 12, 0),
            fromtimestamp_fn=lambda _timestamp: datetime(2026, 4, 14, 13, 0),
            sleep_fn=fake_sleep,
            emit=emitted.append,
        )

        self.assertEqual(calls, ["main"])
        self.assertEqual(sleeps, [3600.0])
        self.assertTrue(any("Próximo run a las 13:00" in line for line in emitted))

    def test_run_scheduled_continues_after_generic_error(self) -> None:
        emitted = []
        main_calls = []

        def flaky_main():
            main_calls.append("run")
            raise RuntimeError("boom")

        module_run_scheduled(
            flaky_main,
            argv=["prog", "--schedule", "1"],
            now_fn=lambda: datetime(2026, 4, 14, 12, 0),
            fromtimestamp_fn=lambda _timestamp: datetime(2026, 4, 14, 13, 0),
            sleep_fn=lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt()),
            emit=emitted.append,
        )

        self.assertEqual(main_calls, ["run"])
        self.assertTrue(any("Error en run #1: boom" in line for line in emitted))


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

        ideas = build_gift_ideas(
            friend_set={"1", "2", "3"}, deals=deals, owned={"2": "Owned"}
        )

        self.assertEqual([deal["appid"] for deal in ideas], ["3", "1"])

    def test_parse_hltb_uses_main_story_as_fallback_and_groups_statuses(self) -> None:
        csv_content = (
            "Title,Main + Extras,Main Story,Storefront,Backlog,Completed,Playing,Retired\n"
            "Portal 2,,12:00:00,Steam,X,,,\n"
            "Hades,25:30:00,20:00:00,Epic,,X,,\n"
        )

        with TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "hltb.csv"
            csv_path.write_text(csv_content, encoding="utf-8")

            parsed = parse_hltb(csv_path)

        self.assertEqual(parsed["backlog"][0]["hours"], 12.0)
        self.assertEqual(parsed["completed"][0]["hours"], 25.5)

    def test_cross_hltb_with_deals_preserves_expected_output_shape(self) -> None:
        hltb = {
            "backlog": [{"title": "Portal 2", "storefront": "Steam", "hours": 12.0}],
            "completed": [
                {"title": "Half-Life 2", "storefront": "Steam", "hours": 15.0}
            ],
            "playing": [],
            "retired": [],
        }
        deals = [
            {
                "appid": "1",
                "name": "Portal 2",
                "discount": 80,
                "price_final": "$12",
                "price_original": "$60",
                "price_raw": 1200,
                "type": "game",
            },
            {
                "appid": "2",
                "name": "Half-Life 2",
                "discount": 60,
                "price_final": "$20",
                "price_original": "$50",
                "price_raw": 2000,
                "type": "game",
            },
        ]

        backlog_on_sale, have_on_sale = cross_hltb_with_deals(
            hltb, deals, family_appids={"1"}
        )

        self.assertEqual(backlog_on_sale[0]["appid"], "1")
        self.assertEqual(backlog_on_sale[0]["in_family"], True)
        self.assertEqual(backlog_on_sale[0]["price_per_hour"], 1.0)
        self.assertEqual(have_on_sale[0]["status"], "completed")


class BudgetPickTests(unittest.TestCase):
    def test_prioritizes_watchlist_hits_then_fills_remaining_budget_by_efficiency(
        self,
    ) -> None:
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
        watchlist_alerts = [
            {"appid": "b", "price_raw": 500, "discount": 50, "name": "Bravo"}
        ]

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
        self.assertEqual(
            result["selected"][0]["recommendation"], "Solo si ya lo traías en radar"
        )
        self.assertEqual(result["selected"][1]["recommendation"], "Comprar ahora")

    def test_budget_payload_exposes_variants_and_replacement_actions(self) -> None:
        deals = [
            {"appid": "a", "price_raw": 1500, "discount": 50, "name": "Alpha"},
            {"appid": "b", "price_raw": 1000, "discount": 50, "name": "Bravo"},
            {"appid": "c", "price_raw": 500, "discount": 50, "name": "Charlie"},
            {"appid": "d", "price_raw": 400, "discount": 50, "name": "Delta"},
        ]
        top_picks = [
            {"appid": "a", "score": 95.0, "recommendation": "Comprar ahora"},
            {"appid": "b", "score": 80.0, "recommendation": "Muy buena oferta"},
            {"appid": "c", "score": 60.0, "recommendation": "Vale la pena"},
            {"appid": "d", "score": 30.0, "recommendation": "Solo si ya lo traías en radar"},
        ]

        result = compute_budget_picks(
            deals=deals,
            budget_mxn=15,
            top_picks=top_picks,
            watchlist_alerts=[],
        )

        variants = {variant["id"]: variant for variant in result["variants"]}

        self.assertEqual(result["selected_variant"], "balanced")
        self.assertEqual(list(variants.keys()), ["small", "balanced", "large"])
        self.assertEqual(
            [deal["appid"] for deal in variants["small"]["selected"]], ["a"]
        )
        self.assertEqual(
            [deal["appid"] for deal in variants["balanced"]["selected"]],
            ["c", "b"],
        )
        self.assertEqual(
            [deal["appid"] for deal in variants["large"]["selected"]], ["d", "c"]
        )
        self.assertEqual(
            [deal["appid"] for deal in result["selected"]], ["c", "b"]
        )
        self.assertTrue(result["actions"]["reroll_list"]["available"])
        self.assertEqual(
            result["actions"]["reroll_list"]["variant_ids"],
            ["small", "balanced", "large"],
        )
        self.assertTrue(result["actions"]["replace_game"]["available"])
        self.assertEqual(
            result["actions"]["replace_game"]["replaceable_by_variant"]["balanced"],
            ["c", "b"],
        )
        self.assertEqual(
            result["selected"][0]["replacement_candidates"][0]["appid"], "d"
        )

    def test_budget_variants_and_replacements_preserve_budget_totals(self) -> None:
        result = compute_budget_picks(
            deals=[
                {"appid": "a", "price_raw": 1500, "discount": 50, "name": "Alpha"},
                {"appid": "b", "price_raw": 1000, "discount": 50, "name": "Bravo"},
                {"appid": "c", "price_raw": 500, "discount": 50, "name": "Charlie"},
                {"appid": "d", "price_raw": 400, "discount": 50, "name": "Delta"},
            ],
            budget_mxn=15,
            top_picks=[
                {"appid": "a", "score": 95.0},
                {"appid": "b", "score": 80.0},
                {"appid": "c", "score": 60.0},
                {"appid": "d", "score": 30.0},
            ],
            watchlist_alerts=[],
        )

        self.assertEqual(
            [deal["appid"] for deal in result["selected"]],
            [deal["appid"] for deal in result["variants"][1]["selected"]],
        )

        for variant in result["variants"]:
            self.assertLessEqual(variant["total_spent"], result["budget"])
            self.assertEqual(variant["games_count"], len(variant["selected"]))
            self.assertAlmostEqual(
                variant["remaining"],
                round(result["budget"] - variant["total_spent"], 2),
            )
            selected_appids = {deal["appid"] for deal in variant["selected"]}
            for pick in variant["selected"]:
                for candidate in pick.get("replacement_candidates", []):
                    self.assertNotIn(candidate["appid"], selected_appids)
                    self.assertLessEqual(candidate["swap_total_spent"], result["budget"])
                    self.assertAlmostEqual(
                        candidate["swap_remaining"],
                        round(result["budget"] - candidate["swap_total_spent"], 2),
                    )

    def test_budget_variants_softly_reduce_overlap_when_alternatives_exist(self) -> None:
        result = compute_budget_picks(
            deals=[
                {"appid": "a", "price_raw": 1500, "discount": 50, "name": "Alpha"},
                {"appid": "b", "price_raw": 1000, "discount": 50, "name": "Bravo"},
                {"appid": "c", "price_raw": 500, "discount": 50, "name": "Charlie"},
                {"appid": "d", "price_raw": 400, "discount": 50, "name": "Delta"},
                {"appid": "e", "price_raw": 600, "discount": 50, "name": "Echo"},
                {"appid": "f", "price_raw": 700, "discount": 50, "name": "Foxtrot"},
            ],
            budget_mxn=20,
            top_picks=[
                {"appid": "a", "score": 95.0},
                {"appid": "b", "score": 85.0},
                {"appid": "c", "score": 60.0},
                {"appid": "d", "score": 58.0},
                {"appid": "e", "score": 57.0},
                {"appid": "f", "score": 56.0},
            ],
            watchlist_alerts=[],
        )

        variants = {variant["id"]: variant for variant in result["variants"]}
        balanced_appids = {deal["appid"] for deal in variants["balanced"]["selected"]}
        small_appids = {deal["appid"] for deal in variants["small"]["selected"]}
        large_appids = {deal["appid"] for deal in variants["large"]["selected"]}

        self.assertLess(len(small_appids & balanced_appids), len(balanced_appids))
        self.assertLess(len(large_appids & balanced_appids), len(balanced_appids))
        for variant in variants.values():
            self.assertLessEqual(variant["total_spent"], result["budget"])

    def test_budget_replacements_diversify_primary_suggestions_when_possible(self) -> None:
        result = compute_budget_picks(
            deals=[
                {"appid": "s1", "price_raw": 500, "discount": 50, "name": "Selected One"},
                {"appid": "s2", "price_raw": 500, "discount": 50, "name": "Selected Two"},
                {"appid": "x", "price_raw": 500, "discount": 50, "name": "Replacement X"},
                {"appid": "y", "price_raw": 500, "discount": 50, "name": "Replacement Y"},
            ],
            budget_mxn=10,
            top_picks=[
                {"appid": "s1", "score": 100.0},
                {"appid": "s2", "score": 90.0},
                {"appid": "x", "score": 80.0},
                {"appid": "y", "score": 70.0},
            ],
            watchlist_alerts=[],
        )

        balanced = next(
            variant for variant in result["variants"] if variant["id"] == "balanced"
        )
        first_replacements = [
            pick["replacement_candidates"][0]["appid"]
            for pick in balanced["selected"]
        ]

        self.assertEqual([deal["appid"] for deal in balanced["selected"]], ["s1", "s2"])
        self.assertEqual(first_replacements, ["x", "y"])


class RankTopPicksTests(unittest.TestCase):
    def test_returns_highest_scoring_deals_first_and_limits_result_count(self) -> None:
        deals = [
            {
                "appid": "a",
                "name": "Alpha",
                "discount": 90,
                "price_final": "$10",
                "price_raw": 1000,
                "release_year": date.today().year,
                "metacritic_score": 90,
                "categories": [2],
            },
            {
                "appid": "b",
                "name": "Bravo",
                "discount": 40,
                "price_final": "$25",
                "price_raw": 2500,
                "release_year": date.today().year - 8,
                "metacritic_score": 65,
                "categories": [2],
            },
        ]

        ranked = rank_top_picks(
            deals=deals,
            priorities={"a": 5, "b": 400},
            reviews={"a": {"pct": 92}, "b": {"pct": 70}},
            hltb_hours={"a": 10.0, "b": 5.0},
            deck_compat={"a": 3, "b": 0},
            n=1,
        )

        self.assertEqual([deal["appid"] for deal in ranked], ["a"])
        self.assertEqual(ranked[0]["score"], 95.4)

    def test_top_pick_includes_recommendation_and_score_reasons(self) -> None:
        ranked = rank_top_picks(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "price_raw": 1000,
                    "release_year": date.today().year,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
            priorities={"a": 5},
            reviews={"a": {"pct": 92, "desc": "Very Positive", "total": 100}},
            hltb_hours={"a": 10.0},
            deck_compat={"a": 3},
            n=1,
        )

        self.assertEqual(ranked[0]["recommendation"], "Comprar ahora")
        self.assertIn("reviews muy positivas", ranked[0]["score_reasons"])

    def test_top_pick_adds_conservative_promo_reason_without_changing_score(self) -> None:
        ranked = rank_top_picks(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "price_raw": 1000,
                    "release_year": date.today().year,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
            priorities={"a": 5},
            reviews={"a": {"pct": 92, "desc": "Very Positive", "total": 100}},
            hltb_hours={"a": 10.0},
            deck_compat={"a": 3},
            n=1,
            active_promo_context={
                "sale_name": "Steam Farming Fest",
                "primary": {"title": "Steam Farming Fest", "category": "fest"},
                "categories": ["fest"],
            },
        )

        self.assertEqual(ranked[0]["score"], 95.4)
        self.assertIn(
            "contexto de festival: revisa si encaja con la temática activa",
            ranked[0]["score_reasons"],
        )

    def test_top_pick_keeps_existing_reasons_without_promo_context(self) -> None:
        ranked = rank_top_picks(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "price_raw": 1000,
                    "release_year": date.today().year,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
            priorities={"a": 5},
            reviews={"a": {"pct": 92, "desc": "Very Positive", "total": 100}},
            hltb_hours={"a": 10.0},
            deck_compat={"a": 3},
            n=1,
        )

        self.assertFalse(
            any("contexto" in reason or "promo" in reason for reason in ranked[0]["score_reasons"])
        )

    def test_generate_md_includes_score_explanation_for_top_picks(self) -> None:
        md = generate_md(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            top_picks=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "score": 95.4,
                    "review": {"pct": 92, "desc": "Very Positive", "total": 100},
                    "deck": 3,
                    "priority": 5,
                    "release_year": date.today().year,
                    "linux_native": False,
                    "metacritic_score": 90,
                    "categories": [2],
                    "recommendation": "Comprar ahora",
                    "score_reasons": [
                        "reviews muy positivas",
                        "descuento muy raro de ver",
                    ],
                }
            ],
        )

        self.assertIn("¿Por qué salió arriba?", md)
        self.assertIn("Comprar ahora", md)
        self.assertIn("reviews muy positivas", md)
        self.assertIn("Score = recomendación compuesta para priorizar qué revisar primero.", md)

    def test_generate_md_surfaces_active_promo_context(self) -> None:
        md = generate_md(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            sale_name="Steam Farming Fest",
            active_promo_context={
                "sale_name": "Steam Farming Fest",
                "primary": {"title": "Steam Farming Fest", "type": 1, "category": "fest"},
                "promos": [
                    {"title": "Steam Farming Fest", "type": 1, "category": "fest"},
                    {"title": "Weeklong Deals", "type": 11, "category": "weeklong"},
                ],
                "categories": ["fest", "weeklong"],
            },
        )

        self.assertIn("Promo activa: **Steam Farming Fest**", md)
        self.assertIn("Contexto promo: Fest · Weeklong", md)
        self.assertIn("También activas: Weeklong Deals", md)

    def test_generate_md_can_include_obsidian_notion_frontmatter(self) -> None:
        md = generate_md(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a", "b"],
            min_discount=50,
            genres=[],
            sale_name="Steam Sale",
            top_picks=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "score": 95.4,
                    "discount": 90,
                    "price_final": "$10",
                    "review": {"pct": 92, "desc": "Very Positive", "total": 100},
                    "deck": 3,
                    "priority": 5,
                    "release_year": date.today().year,
                    "linux_native": False,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
            include_frontmatter=True,
        )

        self.assertTrue(md.startswith("---\n"))
        self.assertIn('title: "Steam Wishlist Deals — gaben"', md)
        self.assertIn('profile: "gaben"', md)
        self.assertIn('sale_name: "Steam Sale"', md)
        self.assertIn("wishlist_count: 2", md)
        self.assertIn("top_picks_count: 1", md)
        self.assertIn("# Steam Wishlist Deals — gaben", md)

    def test_generate_html_includes_score_explanation_for_top_picks(self) -> None:
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            top_picks=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "score": 95.4,
                    "review": {"pct": 92, "desc": "Very Positive", "total": 100},
                    "deck": 3,
                    "priority": 5,
                    "release_year": date.today().year,
                    "linux_native": False,
                    "metacritic_score": 90,
                    "categories": [2],
                    "recommendation": "Comprar ahora",
                    "score_reasons": [
                        "reviews muy positivas",
                        "descuento muy raro de ver",
                    ],
                }
            ],
        )

        self.assertIn("pick-recommendation", html)
        self.assertIn("Comprar ahora", html)
        self.assertIn("reviews muy positivas", html)
        self.assertIn("Score 95.4", html)
        self.assertIn("Metacritic 90", html)
        self.assertIn("Score = recomendación compuesta para priorizar qué revisar primero.", html)
        self.assertIn('data-top-picks-section', html)
        self.assertIn('data-top-pick-filter="all" aria-pressed="true"', html)
        self.assertIn('data-top-pick-filter="Comprar ahora" aria-pressed="false"', html)
        self.assertIn('data-top-pick-filter="Muy buena oferta" aria-pressed="false"', html)
        self.assertIn('data-recommendation="Comprar ahora"', html)
        self.assertIn("applyTopPickRecommendationFilter", html)
        self.assertIn("data-top-pick-filter-count", html)
        self.assertIn("No hay Top Picks con esa recomendación.", html)

    def test_generate_html_uses_safe_fallbacks_for_empty_visible_stats(self) -> None:
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
        )

        self.assertIn('id="stat-avg-disc">Promedio: sin datos</span>', html)
        self.assertIn('id="stat-avg-price">Precio medio: sin datos</span>', html)
        self.assertIn(
            "setAverageStat('stat-avg-disc', 'Promedio', totalD, discountCount",
            html,
        )
        self.assertIn(
            "setAverageStat('stat-avg-price', 'Precio medio', totalP, priceCount",
            html,
        )
        self.assertNotIn("Math.round(totalD / totalV)", html)
        self.assertNotIn("Math.round(totalP / totalV)", html)
        self.assertNotIn("NaN", html)

    def test_generate_html_header_prefers_profile_display_name(self) -> None:
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="https://steamcommunity.com/id/gaben/",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            profile_display_name="Gabe Newell",
        )

        self.assertIn("<title>Steam Deals &mdash; Gabe Newell</title>", html)
        self.assertIn("<h1>Ofertas de Steam &mdash; Gabe Newell</h1>", html)
        self.assertNotIn(
            "<h1>Ofertas de Steam &mdash; https://steamcommunity.com/id/gaben/</h1>",
            html,
        )

    def test_generate_html_surfaces_active_promo_context(self) -> None:
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=[],
            min_discount=50,
            genres=[],
            sale_name="Steam Farming Fest",
            active_promo_context={
                "sale_name": "Steam Farming Fest",
                "primary": {"title": "Steam Farming Fest", "type": 1, "category": "fest"},
                "promos": [
                    {"title": "Steam Farming Fest", "type": 1, "category": "fest"},
                    {"title": "Weeklong Deals", "type": 11, "category": "weeklong"},
                ],
                "categories": ["fest", "weeklong"],
            },
        )

        self.assertIn("promo-context-card", html)
        self.assertIn("<strong>Promo activa:</strong> Steam Farming Fest", html)
        self.assertIn("Fest", html)
        self.assertIn("Weeklong", html)
        self.assertIn("También activas: Weeklong Deals", html)

    def test_generate_share_html_labels_top_pick_score_and_metacritic(self) -> None:
        html = generate_share_html(
            deals=[],
            vanity="gaben",
            min_discount=50,
            top_picks=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "score": 95.4,
                    "metacritic_score": 90,
                }
            ],
        )

        self.assertIn("Score 95.4", html)
        self.assertIn("Metacritic 90", html)
        self.assertIn("Score = recomendación compuesta para priorizar qué revisar primero.", html)
        self.assertIn("Mínimo histórico en Steam", html)

    def test_generate_html_share_payload_keeps_aliases_for_renderer_buttons(self) -> None:
        html = generate_html(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "price_original": "$20",
                    "price_raw": 1000,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            historical_lows={"a": {"price": 5, "date": "2026-04-20"}},
            top_picks=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "score": 95.4,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
        )

        self.assertIn("data-share-game=", html)
        self.assertIn("original_price", html)
        self.assertIn("price_original", html)
        self.assertIn("min_historical", html)

    def test_generate_share_html_renders_share_buttons_with_normalized_payload(self) -> None:
        html = generate_share_html(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "price_original": "$20",
                }
            ],
            vanity="gaben",
            min_discount=50,
            top_picks=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "score": 95.4,
                    "metacritic_score": 90,
                }
            ],
            historical_lows={"a": {"price": 5, "date": "2026-04-20"}},
        )

        self.assertIn("share-btn-inline", html)
        self.assertIn("data-share-game=", html)
        self.assertIn("original_price", html)
        self.assertIn("min_historical", html)

    def test_generate_html_share_surfaces_include_modal_and_share_actions(self) -> None:
        html = generate_html(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "price_original": "$20",
                    "price_raw": 1000,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            historical_lows={"a": {"price": 5, "date": "2026-04-20"}},
            top_picks=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "score": 95.4,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
        )

        self.assertIn('id="share-modal"', html)
        self.assertIn("Compartir oferta", html)
        self.assertIn("Copiar link steamtools://", html)
        self.assertIn("Abrir en Steam", html)
        self.assertIn("¡Copiado!", html)
        self.assertIn("data-share-game=", html)
        self.assertIn("bindShareModalInteractions", html)
        self.assertNotIn("Compartir Deal", html)

    def test_generate_share_html_surfaces_include_modal_and_share_actions(self) -> None:
        html = generate_share_html(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "price_original": "$20",
                }
            ],
            vanity="gaben",
            min_discount=50,
            top_picks=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "score": 95.4,
                    "metacritic_score": 90,
                }
            ],
            historical_lows={"a": {"price": 5, "date": "2026-04-20"}},
        )

        self.assertIn('id="share-modal"', html)
        self.assertIn("Compartir oferta", html)
        self.assertIn("Copiar link steamtools://", html)
        self.assertIn("Abrir en Steam", html)
        self.assertIn("¡Copiado!", html)
        self.assertIn("data-share-game=", html)
        self.assertIn("bindShareModalInteractions", html)
        self.assertNotIn("Compartir Deal", html)

    def test_generate_md_includes_budget_recommendation_context(self) -> None:
        md = generate_md(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            budget_result={
                "budget": 500,
                "selected": [
                    {
                        "appid": "a",
                        "name": "Alpha",
                        "discount": 90,
                        "price_final": "$10",
                        "score": 95.4,
                        "recommendation": "Comprar ahora",
                        "score_reasons": [
                            "reviews muy positivas",
                            "descuento muy raro de ver",
                        ],
                    }
                ],
                "total_spent": 10,
                "total_savings": 90,
                "remaining": 490,
                "games_count": 1,
            },
        )

        self.assertIn("Tu Presupuesto Ideal", md)
        self.assertIn("Comprar ahora", md)
        self.assertIn("descuento muy raro de ver", md)

    def test_generate_html_includes_budget_recommendation_context(self) -> None:
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            budget_result={
                "budget": 500,
                "selected": [
                    {
                        "appid": "a",
                        "name": "Alpha",
                        "discount": 90,
                        "price_final": "$10",
                        "score": 95.4,
                        "recommendation": "Comprar ahora",
                        "score_reasons": [
                            "reviews muy positivas",
                            "descuento muy raro de ver",
                        ],
                    }
                ],
                "total_spent": 10,
                "total_savings": 90,
                "remaining": 490,
                "games_count": 1,
            },
        )

        self.assertIn("Tu Presupuesto Ideal", html)
        self.assertIn("Comprar ahora", html)
        self.assertIn("reviews muy positivas", html)

    def test_generate_md_includes_budget_variants_and_replacements(self) -> None:
        budget_result = compute_budget_picks(
            deals=[
                {"appid": "a", "name": "Alpha", "discount": 50, "price_raw": 1500, "price_final": "$15"},
                {"appid": "b", "name": "Bravo", "discount": 50, "price_raw": 1000, "price_final": "$10"},
                {"appid": "c", "name": "Charlie", "discount": 50, "price_raw": 500, "price_final": "$5"},
                {"appid": "d", "name": "Delta", "discount": 50, "price_raw": 400, "price_final": "$4"},
            ],
            budget_mxn=15,
            top_picks=[
                {"appid": "a", "score": 95.0, "recommendation": "Comprar ahora", "score_reasons": ["score más alto"]},
                {"appid": "b", "score": 80.0, "recommendation": "Muy buena oferta", "score_reasons": ["balance sólido"]},
                {"appid": "c", "score": 60.0, "recommendation": "Vale la pena", "score_reasons": ["ticket accesible"]},
                {"appid": "d", "score": 30.0, "recommendation": "Solo si ya lo traías en radar", "score_reasons": ["relleno barato"]},
            ],
            watchlist_alerts=[],
        )
        md = generate_md(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            budget_result=budget_result,
        )

        self.assertIn("### 🔁 Probar otra lista", md)
        self.assertIn("Lista chica", md)
        self.assertIn("Lista media", md)
        self.assertIn("Lista grande", md)
        self.assertIn("### 🔄 Cambiar este juego", md)
        self.assertIn("Delta", md)
        self.assertIn("Nuevo total: $14", md)

    def test_generate_html_includes_budget_variants_and_replacements(self) -> None:
        budget_result = compute_budget_picks(
            deals=[
                {"appid": "a", "name": "Alpha", "discount": 50, "price_raw": 1500, "price_final": "$15"},
                {"appid": "b", "name": "Bravo", "discount": 50, "price_raw": 1000, "price_final": "$10"},
                {"appid": "c", "name": "Charlie", "discount": 50, "price_raw": 500, "price_final": "$5"},
                {"appid": "d", "name": "Delta", "discount": 50, "price_raw": 400, "price_final": "$4"},
            ],
            budget_mxn=15,
            top_picks=[
                {"appid": "a", "score": 95.0, "recommendation": "Comprar ahora", "score_reasons": ["score más alto"]},
                {"appid": "b", "score": 80.0, "recommendation": "Muy buena oferta", "score_reasons": ["balance sólido"]},
                {"appid": "c", "score": 60.0, "recommendation": "Vale la pena", "score_reasons": ["ticket accesible"]},
                {"appid": "d", "score": 30.0, "recommendation": "Solo si ya lo traías en radar", "score_reasons": ["relleno barato"]},
            ],
            watchlist_alerts=[],
        )
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            budget_result=budget_result,
        )

        self.assertIn("Rerrollear todos", html)
        self.assertIn("Lista chica", html)
        self.assertIn("Lista media", html)
        self.assertIn("Lista grande", html)
        self.assertIn("cambiar este juego", html.lower())
        self.assertIn("data-budget-variant-btn=", html)
        self.assertIn("data-budget-options=", html)
        self.assertIn("&quot;image_url&quot;", html)
        self.assertIn("steam/apps/d/capsule_231x87.jpg", html)
        self.assertIn("const imageEl = row.querySelector('.game-thumb');", html)
        self.assertIn("imageEl.src = option.image_url;", html)
        self.assertIn("share-btn-close", html)

    def test_generate_html_hides_local_history_column_without_useful_snapshots(self) -> None:
        html = generate_html(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "price_original": "$20",
                    "price_raw": 1000,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            price_history={"games": {"a": {"snapshots": [{"price_raw": 1000}]}}},
        )

        self.assertNotIn("Historial local", html)
        self.assertNotIn('data-trend-cell="a"', html)

    def test_generate_html_adds_min_historical_trend_jump_when_both_signals_exist(self) -> None:
        html = generate_html(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "price_original": "$20",
                    "price_raw": 1000,
                    "metacritic_score": 90,
                    "categories": [2],
                }
            ],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a"],
            min_discount=50,
            genres=[],
            historical_lows={"a": {"price": 5, "date": "2026-04-20"}},
            price_history={
                "games": {
                    "a": {
                        "snapshots": [
                            {"price_raw": 2000},
                            {"price_raw": 1500},
                            {"price_raw": 1000},
                        ]
                    }
                }
            },
        )

        self.assertIn("Historial local", html)
        self.assertIn("no es predicción", html)
        self.assertIn("min-hist-cell", html)
        self.assertIn("Ir rápido al historial local de este juego", html)
        self.assertIn("Ver historial", html)
        self.assertIn('data-trend-cell="a"', html)
        self.assertIn("focusTrendCell", html)

    def test_generate_html_fallback_adds_min_historical_trend_jump(self) -> None:
        original_renderer = generate_html.__globals__.get("_generate_html_renderer")
        try:
            generate_html.__globals__["_generate_html_renderer"] = None
            html = generate_html(
                deals=[
                    {
                        "appid": "a",
                        "name": "Alpha",
                        "discount": 90,
                        "price_final": "$10",
                        "price_original": "$20",
                        "price_raw": 1000,
                        "metacritic_score": 90,
                        "categories": [2],
                    }
                ],
                backlog_on_sale=[],
                have_on_sale=[],
                vanity="gaben",
                owned={},
                wishlist_appids=["a"],
                min_discount=50,
                genres=[],
                historical_lows={"a": {"price": 5, "date": "2026-04-20"}},
                price_history={
                    "games": {
                        "a": {
                            "snapshots": [
                                {"price_raw": 2000},
                                {"price_raw": 1500},
                                {"price_raw": 1000},
                            ]
                        }
                    }
                },
            )
        finally:
            generate_html.__globals__["_generate_html_renderer"] = original_renderer

        self.assertIn("Historial local", html)
        self.assertIn("no es predicción", html)
        self.assertIn("min-hist-cell", html)
        self.assertIn("Ver historial", html)
        self.assertIn('data-trend-cell="a"', html)
        self.assertIn("focusTrendCell", html)

    def test_generate_html_adds_shuffle_one_game_from_top_picks(self) -> None:
        html = generate_html(
            deals=[],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a", "b"],
            min_discount=50,
            genres=[],
            top_picks=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 90,
                    "price_final": "$10",
                    "score": 95.0,
                    "recommendation": "Comprar ahora",
                    "score_reasons": ["score más alto"],
                    "categories": [],
                },
                {
                    "appid": "b",
                    "name": "Bravo",
                    "discount": 80,
                    "price_final": "$12",
                    "score": 82.0,
                    "recommendation": "Muy buena oferta",
                    "score_reasons": ["balance sólido"],
                    "categories": [],
                },
            ],
        )

        self.assertIn("Shuffle 1 juego", html)
        self.assertIn("data-shuffle-one", html)
        self.assertIn("data-shuffle-candidates", html)
        self.assertIn("Dame otro", html)
        self.assertIn("bindShuffleOneGame", html)
        self.assertIn("Alpha", html)
        self.assertIn("Bravo", html)
        self.assertIn("Score 95.0", html)
        self.assertIn("Comprar ahora", html)
        self.assertIn("1/2", html)

    def test_generate_html_adds_shuffle_one_game_from_deals_without_top_picks(self) -> None:
        html = generate_html(
            deals=[
                {
                    "appid": "a",
                    "name": "Alpha",
                    "discount": 70,
                    "price_final": "$10",
                    "price_original": "$20",
                    "price_raw": 1000,
                    "categories": [],
                },
                {
                    "appid": "b",
                    "name": "Bravo",
                    "discount": 90,
                    "price_final": "$5",
                    "price_original": "$50",
                    "price_raw": 500,
                    "categories": [],
                },
            ],
            backlog_on_sale=[],
            have_on_sale=[],
            vanity="gaben",
            owned={},
            wishlist_appids=["a", "b"],
            min_discount=50,
            genres=[],
        )

        self.assertIn("Shuffle 1 juego", html)
        self.assertIn("Bravo", html)
        self.assertIn("-90% descuento", html)
        self.assertIn("Buen candidato para revisar sin recorrer toda la lista.", html)
        self.assertIn("1/2", html)

    def test_generate_html_fallback_adds_shuffle_one_game(self) -> None:
        original_renderer = generate_html.__globals__.get("_generate_html_renderer")
        try:
            generate_html.__globals__["_generate_html_renderer"] = None
            html = generate_html(
                deals=[],
                backlog_on_sale=[],
                have_on_sale=[],
                vanity="gaben",
                owned={},
                wishlist_appids=["a"],
                min_discount=50,
                genres=[],
                top_picks=[
                    {
                        "appid": "a",
                        "name": "Alpha",
                        "discount": 90,
                        "price_final": "$10",
                        "score": 95.0,
                        "recommendation": "Comprar ahora",
                        "score_reasons": ["score más alto"],
                        "categories": [],
                    }
                ],
            )
        finally:
            generate_html.__globals__["_generate_html_renderer"] = original_renderer

        self.assertIn("Shuffle 1 juego", html)
        self.assertIn("data-shuffle-one", html)
        self.assertIn("Dame otro", html)
        self.assertIn("bindShuffleOneGame", html)
        self.assertIn("Alpha", html)


if __name__ == "__main__":
    unittest.main()
