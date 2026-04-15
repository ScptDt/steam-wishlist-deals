from __future__ import annotations

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
    get_config as module_get_config,
    load_user_config as module_load_user_config,
    save_user_config as module_save_user_config,
)
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
from steam_deals_family import (
    FamilyContext as ModuleFamilyContext,
    build_family_renderer_kwargs as module_build_family_renderer_kwargs,
    cross_hltb_with_family_context as module_cross_hltb_with_family_context,
)
from steam_deals_prices import (
    get_deals_from_wishlist as module_get_deals_from_wishlist,
    load_price_cache as module_load_price_cache,
    parse_release_year as module_parse_release_year,
    process_app_entry as module_process_app_entry,
    save_price_cache as module_save_price_cache,
)
from steam_deals_steam_api import (
    compare_wishlists as module_compare_wishlists,
    get_active_sale as module_get_active_sale,
    get_owned_games as module_get_owned_games,
    get_wishlist as module_get_wishlist,
    load_family_games as module_load_family_games,
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
    resolve_previous_context as module_resolve_previous_context,
    write_output_artifacts as module_write_output_artifacts,
    write_artifact as module_write_artifact,
)
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
    apply_filters,
    analyze_trends,
    build_gift_ideas,
    compute_budget_picks,
    compute_deal_comparison,
    compute_value_score,
    cross_hltb_with_deals,
    filter_by_genres,
    format_trend,
    is_same_game,
    load_previous_deal_appids,
    parse_hltb,
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
        config = {"vanity": "BG00G", "discount": 50}

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
                "--vanity", "BG00G",
                "--output", "/tmp/out",
                "--discount", "30",
                "--genre", "indie", "roguelike",
                "--top", "5",
                "--schedule", "6",
            ],
        )

        self.assertEqual(result[3], "BG00G")
        self.assertEqual(result[5], Path("/tmp/out"))
        self.assertEqual(result[6], 30)
        self.assertEqual(result[7], ["indie", "roguelike"])
        self.assertEqual(result[11]["top"], 5)
        self.assertEqual(result[11]["schedule"], 6.0)

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
        self.assertEqual([name for name, games in grouped if games], ["90%+", "80–89%", "50–59%"])

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
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(status="empty", cache={}, missing_ids=()),
                fetch_data=lambda _appids, cached: dict(cached),
                save_cache=lambda _steam_id, _data: None,
                ttl_hours=24,
            )

        def default_global_runtime():
            return module_build_global_cache_runtime(
                load_cache=lambda: ({}, 0.0),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(status="empty", cache={}),
                fetch_data=lambda: {},
                save_cache=lambda _data: None,
                ttl_hours=24,
            )

        return module_build_enrichment_orchestration_contract(
            progress=module_build_progress_callbacks(step=steps.append, emit=emits.append),
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
            get_json=lambda _url, headers=None: {"query_summary": {"review_score_desc": "Positive", "total_positive": 40, "total_reviews": 50}},
        )

        self.assertEqual(result["10"]["pct"], 90)
        self.assertEqual(result["20"]["pct"], 80)

    def test_fetch_anticheat_db_parses_awacy_rows(self) -> None:
        data = [
            {"storeIds": {"steam": 10}, "status": "Supported", "anticheats": ["EAC"], "native": False},
            {"storeIds": {}, "status": "Broken"},
        ]

        result = module_fetch_anticheat_db(get_json=lambda _url, headers=None: data)

        self.assertEqual(result, {"10": {"status": "Supported", "anticheats": ["EAC"], "native": False}})

    def test_load_tags_cache_migrates_old_flat_format(self) -> None:
        tags, age = module_load_tags_cache(
            Path("/tmp/unused.json"),
            load_timestamped_cache=lambda _file, _key: ({"10": {"Roguelike": 100}}, 12.0),
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

    def test_reviews_and_deck_orchestration_preserve_step_order_and_messages(self) -> None:
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

        self.assertEqual(steps, [
            "Obteniendo reviews de Steam...",
            "Obteniendo compatibilidad Steam Deck...",
        ])
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
        self.assertEqual(review_saves, [("steam-id", {"10": {"pct": 90}, "20": {"pct": 80}})])
        self.assertEqual(deck_saves, [("steam-id", {"10": 3, "20": 2})])

    def test_linux_tags_and_achievements_orchestration_keep_observable_outputs(self) -> None:
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
                save_cache=lambda steam_id, data: protondb_saves.append((steam_id, data)),
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
                fetch_data=lambda _appids, _cached: {"10": {"tags": {"Action": 100}}, "20": {}},
                save_cache=lambda steam_id, data: tag_saves.append((steam_id, data)),
                ttl_hours=24,
            ),
            achievements_runtime=module_build_scoped_cache_runtime(
                load_cache=lambda _steam_id: ({"10": {"count": 10, "avg_completion": 12.0}}, 4.0),
                select_cache=lambda *_args, **_kwargs: SimpleNamespace(
                    status="valid",
                    cache={"10": {"count": 10, "avg_completion": 12.0}},
                    missing_ids=(),
                ),
                fetch_data=lambda _appids, cached: dict(cached),
                save_cache=lambda steam_id, data: achievement_saves.append((steam_id, data)),
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

        self.assertEqual(steps, [
            "Obteniendo datos Linux (ProtonDB + Anti-Cheat)...",
            "Obteniendo tags de Steam...",
            "Obteniendo achievements...",
        ])
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
        self.assertEqual(protondb_data, {"10": {"tier": "platinum"}, "20": {"tier": "native"}})
        self.assertEqual(anticheat_data, {"10": {"status": "Denied"}})
        self.assertEqual(tags_data, {"10": {"tags": {"Action": 100}}, "20": {}})
        self.assertEqual(achievements_data, {"10": {"count": 10, "avg_completion": 12.0}})
        self.assertEqual(anticheat_fetch_calls, [])
        self.assertEqual(protondb_saves, [("", {"10": {"tier": "platinum"}, "20": {"tier": "native"}})])
        self.assertEqual(tag_saves, [("", {"10": {"tags": {"Action": 100}}, "20": {}})])
        self.assertEqual(achievement_saves, [("steam-id", {"10": {"count": 10, "avg_completion": 12.0}})])


class PriceCacheTests(unittest.TestCase):
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

    def test_select_scoped_cache_clears_expired_payload(self) -> None:
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

    def test_select_global_cache_bypasses_when_no_cache_is_enabled(self) -> None:
        decision = module_select_global_cache(
            {"10": {"status": "Supported"}},
            1.0,
            no_cache=True,
            ttl_hours=168,
        )

        self.assertEqual(decision.status, "bypass")
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

        result = module_process_app_entry("10", data, parse_release_year_fn=module_parse_release_year)

        self.assertEqual(result["release_year"], 2011)
        self.assertEqual(result["description"], "Test description")
        self.assertEqual(result["linux_native"], True)

    def test_get_deals_from_wishlist_falls_back_to_individual_fetch_and_preserves_deal_shape(self) -> None:
        fetched_cache = {}

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
            process_app_entry_fn=lambda appid, data: module_process_app_entry(appid, data, parse_release_year_fn=module_parse_release_year),
            emit=lambda *_args, **_kwargs: None,
            warn=lambda text: text,
            dim=lambda text: text,
        )

        self.assertEqual(total, 2)
        self.assertEqual([deal["appid"] for deal in deals], ["10"])
        self.assertEqual(deals[0]["price_raw"], 600)


class RunOutputTests(unittest.TestCase):
    def test_build_output_md_path_sanitizes_sale_name(self) -> None:
        output = module_build_output_md_path("/tmp/out", 'Steam: Sale/?*', today_obj=date(2026, 4, 14))

        self.assertEqual(output, Path("/tmp/out/Steam Deals Steam Sale 2026-04-14.md"))

    def test_build_output_artifact_paths_keeps_output_contract(self) -> None:
        artifacts = module_build_output_artifact_paths(
            Path("/tmp/out/Steam Deals 2026-04-14.md"),
            today_obj=date(2026, 4, 14),
            include_csv=True,
        )

        self.assertEqual(artifacts.output_md, Path("/tmp/out/Steam Deals 2026-04-14.md"))
        self.assertEqual(artifacts.output_html, Path("/tmp/out/Steam Deals 2026-04-14.html"))
        self.assertEqual(artifacts.output_share, Path("/tmp/out/Steam Deals Share 2026-04-14.html"))
        self.assertEqual(artifacts.output_csv, Path("/tmp/out/Steam Deals 2026-04-14.csv"))

    def test_resolve_previous_context_uses_markdown_fallback_only_without_previous_run(self) -> None:
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
            share_path = module_build_share_output_path(temp_dir, today_obj=date(2026, 4, 14))
            module_write_artifact(output_md, "md", emit_event_fn=lambda event_type, **payload: emitted.append((event_type, payload)))
            module_write_artifact(share_path, "share", emit_event_fn=lambda event_type, **payload: emitted.append((event_type, payload)))

            self.assertEqual(output_md.read_text(encoding="utf-8"), "md")
            self.assertEqual(share_path.read_text(encoding="utf-8"), "share")

        self.assertEqual(emitted[0][0], "file")
        self.assertTrue(emitted[0][1]["path"].endswith("Steam Deals 2026-04-14.md"))
        self.assertTrue(emitted[1][1]["path"].endswith("Steam Deals Share 2026-04-14.html"))

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
                output_csv=Path("/tmp/out/Steam Deals 2026-04-14.csv"),
            ),
            ModuleOutputArtifactPayloads(
                markdown="md",
                html="html",
                share_html="share",
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
                (Path("/tmp/out/Steam Deals 2026-04-14.csv"), "csv"),
            ],
        )
        self.assertEqual(result["markdown"], Path("/tmp/out/Steam Deals 2026-04-14.md"))
        self.assertEqual(result["csv"], Path("/tmp/out/Steam Deals 2026-04-14.csv"))

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
        self.assertEqual(summary, "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · Steam Deals 2026-04-14.md")

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
        self.assertEqual(summary, "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · Steam Deals 2026-04-14.md")
        self.assertEqual(
            emitted,
            [
                "\n<g>──────────────────────────────────────────</g>",
                "  **Listo** en 12.3s",
                "  2 deals · 1 backlog · 1 nuevos · Top pick: Portal 2 (95.4) · Steam Deals 2026-04-14.md",
                "<g>──────────────────────────────────────────</g>\n",
            ],
        )


class RuntimeReportingTests(unittest.TestCase):
    def test_safe_symbol_uses_fallback_for_incompatible_encoding(self) -> None:
        result = module_safe_symbol("🎯", "[ALERT]", stdout_encoding="ascii")

        self.assertEqual(result, "[ALERT]")

    def test_emit_event_prints_prefixed_json_only_in_web_mode(self) -> None:
        emitted = []

        module_emit_event("progress", web_event_mode=True, emit=lambda text, **_kwargs: emitted.append(text), current=1, total=2, label="Paso")
        module_emit_event("progress", web_event_mode=False, emit=lambda text, **_kwargs: emitted.append(text), current=2, total=2, label="Nope")

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
            emit_event_fn=lambda event_type, **payload: events.append((event_type, payload)),
            bold_fn=lambda text: f"<b>{text}</b>",
            color_cyan="[CYAN]",
            color_reset="[/CYAN]",
        )

        self.assertEqual(emitted, ["\n[CYAN][2/5][/CYAN] <b>Obteniendo wishlist...</b>"])
        self.assertEqual(events, [("progress", {"current": 2, "total": 5, "label": "Obteniendo wishlist..."})])


class ApplyFiltersTests(unittest.TestCase):
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
            (output_dir / "Steam Deals 2026-04-14.md").write_text("current", encoding="utf-8")

            previous_appids = load_previous_deal_appids(output_dir, "Steam Deals 2026-04-14.md")

        self.assertEqual(previous_appids, {"10", "20"})

    def test_compute_deal_comparison_tracks_new_changes_disappeared_and_streak(self) -> None:
        current_deals = [
            {"appid": "a", "price_raw": 500, "price_final": "$5", "discount": 50},
            {"appid": "b", "price_raw": 900, "price_final": "$9", "discount": 60},
        ]
        previous_run = {
            "date": "2026-04-13",
            "deals": {
                "a": {"name": "Alpha", "discount": 40, "price_final": "$6", "price_raw": 600},
                "c": {"name": "Charlie", "discount": 30, "price_final": "$7", "price_raw": 700},
            },
        }
        run_history = [{"deals": {"a": {}, "b": {}}}, {"deals": {"a": {}}}]

        comparison = compute_deal_comparison(current_deals, previous_run, run_history)

        self.assertEqual(comparison["new_deals"], {"b"})
        self.assertEqual(comparison["price_changes"]["a"]["direction"], "down")
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


class ItadAdapterTests(unittest.TestCase):
    def test_itad_lookup_games_maps_found_entries_by_appid(self) -> None:
        def fake_post_json(_url, _body):
            return [
                {"found": True, "game": {"id": "itad-10"}},
                {"found": False},
            ]

        result = module_itad_lookup_games(["10", "20"], "key", post_json=fake_post_json, sleep_fn=lambda _seconds: None)

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

        result = module_itad_get_store_lows({"10": "itad-10"}, "key", post_json=fake_post_json, sleep_fn=lambda _seconds: None)

        self.assertEqual(result["10"]["price"], 99)
        self.assertEqual(result["10"]["currency"], "MXN")
        self.assertEqual(result["10"]["date"], "2026-04-10")

    def test_itad_get_current_prices_only_returns_better_non_steam_prices(self) -> None:
        def fake_post_json(_url, _body):
            return [
                {
                    "id": "itad-10",
                    "deals": [
                        {"shop": {"id": 61, "name": "Steam"}, "price": {"amount": 100}, "url": "steam"},
                        {"shop": {"id": 2, "name": "Fanatical"}, "price": {"amount": 80}, "url": "fan"},
                    ],
                }
            ]

        result = module_itad_get_current_prices({"10": "itad-10"}, "key", post_json=fake_post_json, sleep_fn=lambda _seconds: None)

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

        result = module_itad_get_active_bundles({"10": "itad-10"}, "key", post_json=fake_post_json, sleep_fn=lambda _seconds: None)

        self.assertEqual(len(result["10"]), 1)
        self.assertEqual(result["10"][0]["title"], "Bundle A")

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


class WatchlistTests(unittest.TestCase):
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

    def test_check_watchlist_alerts_returns_matching_deals_with_target_price(self) -> None:
        deals = [{"appid": "10", "price_raw": 800, "discount": 50, "name": "Portal 2"}]
        watchlist = [{"appid": "10", "name": "Portal 2", "target_price": 9.0}]

        alerts = module_check_watchlist_alerts(deals, watchlist)

        self.assertEqual(alerts[0]["appid"], "10")
        self.assertEqual(alerts[0]["target_price"], 9.0)


class SteamAdapterTests(unittest.TestCase):
    def test_resolve_steam_id_uses_public_xml_fallback_without_key(self) -> None:
        steam_id = module_resolve_steam_id(
            None,
            "bg00g",
            get_json=lambda _url: {},
            fetch_public_profile_xml=lambda _vanity: "<steamID64>76561198000000000</steamID64>",
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
        )

        self.assertEqual(comparison["friend_id"], "friend-id")
        self.assertEqual(comparison["friend_set"], {"10", "20"})

    def test_load_family_games_supports_dict_shape(self) -> None:
        with TemporaryDirectory() as temp_dir:
            family_path = Path(temp_dir) / "family.json"
            family_path.write_text('{"10": "Portal 2", "20": "Hades"}', encoding="utf-8")

            appids = module_load_family_games(family_path)

        self.assertEqual(appids, {"10", "20"})

    def test_cross_hltb_with_family_context_passes_family_appids_to_matcher(self) -> None:
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


class NotificationsTests(unittest.TestCase):
    def test_build_notification_summary_returns_none_when_nothing_notable(self) -> None:
        summary = module_build_notification_summary([], {}, [], watchlist_alerts=[])

        self.assertEqual(summary, None)

    def test_build_notification_summary_surfaces_top_picks_drops_and_watchlist(self) -> None:
        deals = [{"appid": "10", "name": "Portal 2"}]
        comparison = {
            "new_deals": {"10"},
            "price_changes": {"10": {"direction": "down", "delta_raw": -200, "delta_str": "$2", "prev_price": "$10"}},
        }
        top_picks = [{"name": "Portal 2", "discount": 80, "price_final": "$8", "score": 90.0}]
        watchlist_alerts = [{"name": "Portal 2", "price_final": "$8", "target_price": 9.0}]

        summary = module_build_notification_summary(deals, comparison, top_picks, watchlist_alerts=watchlist_alerts)

        self.assertEqual(summary["new_count"], 1)
        self.assertEqual(summary["top_3"][0]["name"], "Portal 2")
        self.assertEqual(summary["watchlist_hits"][0]["target"], 9.0)

    def test_send_telegram_returns_false_on_request_error(self) -> None:
        ok = module_send_telegram(
            "token",
            "chat",
            {"total_deals": 1, "new_count": 0, "top_3": [], "price_drops": [], "watchlist_hits": []},
            post_json_request=lambda _url, _body, timeout=15: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        self.assertEqual(ok, False)

    def test_send_discord_returns_true_when_request_succeeds(self) -> None:
        ok = module_send_discord(
            "https://discord.invalid/webhook",
            {"total_deals": 1, "new_count": 0, "top_3": [], "price_drops": [], "watchlist_hits": []},
            post_json_request=lambda _url, _body, timeout=15: {},
        )

        self.assertEqual(ok, True)

    def test_send_notifications_emits_success_messages_for_configured_channels(self) -> None:
        emitted = []

        module_send_notifications(
            {"telegram_token": "token", "telegram_chat": "chat", "discord_webhook": "hook"},
            {"total_deals": 1, "new_count": 0, "top_3": [], "price_drops": [], "watchlist_hits": []},
            send_telegram_fn=lambda _token, _chat, _summary: True,
            send_discord_fn=lambda _webhook, _summary: True,
            emit=emitted.append,
        )

        self.assertEqual(len(emitted), 2)


class SchedulerTests(unittest.TestCase):
    def test_parse_schedule_hours_returns_none_for_missing_or_invalid_values(self) -> None:
        self.assertEqual(module_parse_schedule_hours(["prog"]), None)
        self.assertEqual(module_parse_schedule_hours(["prog", "--schedule", "oops"]), None)

    def test_run_scheduled_runs_once_without_schedule(self) -> None:
        calls = []

        module_run_scheduled(lambda: calls.append("main"), argv=["prog"])

        self.assertEqual(calls, ["main"])

    def test_run_scheduled_runs_once_for_zero_schedule(self) -> None:
        calls = []

        module_run_scheduled(lambda: calls.append("main"), argv=["prog", "--schedule", "0"])

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

        ideas = build_gift_ideas(friend_set={"1", "2", "3"}, deals=deals, owned={"2": "Owned"})

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
            "completed": [{"title": "Half-Life 2", "storefront": "Steam", "hours": 15.0}],
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

        backlog_on_sale, have_on_sale = cross_hltb_with_deals(hltb, deals, family_appids={"1"})

        self.assertEqual(backlog_on_sale[0]["appid"], "1")
        self.assertEqual(backlog_on_sale[0]["in_family"], True)
        self.assertEqual(backlog_on_sale[0]["price_per_hour"], 1.0)
        self.assertEqual(have_on_sale[0]["status"], "completed")


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


if __name__ == "__main__":
    unittest.main()
