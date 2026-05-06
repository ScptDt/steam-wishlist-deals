#!/usr/bin/env python3
"""
Steam Wishlist Deals Generator
Genera reportes de deals de tu wishlist cruzados con HLTB y señales externas.

Uso:
    python3 steam_deals_generator.py --vanity gaben
    python3 steam_deals_generator.py --vanity https://steamcommunity.com/id/gaben/
    python3 steam_deals_generator.py --key TU_KEY --vanity gaben --discount 60
    python3 steam_deals_generator.py --genre roguelike --genre indie
    python3 steam_deals_generator.py --no-cache        # re-fetch aunque haya caché
    python3 steam_deals_generator.py --family-json ~/familia.json
    python3 steam_deals_generator.py --itad-key TU_ITAD_KEY  # precio mínimo histórico

La Steam API Key es opcional. Sin key: funciona con endpoints públicos (wishlist
debe ser pública). Con key: además muestra juegos propios para limpiar la wishlist.

Config guardada en ~/.config/steam_deals.json tras el primer run interactivo.
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path
from shared.io_utils import (
    http_get_json,
    http_post_json,
    load_json_file,
    write_json_file,
)

try:
    from renderers.common import html_escape as _renderer_html_escape
except Exception:
    # Compatibility fallback for contexts where the scaffold package is not yet
    # present in the runtime path. Behavior stays equivalent to the in-file
    # helper.
    def _renderer_html_escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


try:
    from renderers.markdown_renderer import generate_md as _generate_md_renderer
except Exception:
    _generate_md_renderer = None


try:
    from renderers.html_renderer import generate_html as _generate_html_renderer
except Exception:
    _generate_html_renderer = None


try:
    from renderers.html_fallback_renderer import generate_html as _generate_html_fallback_renderer
except Exception:
    _generate_html_fallback_renderer = None


try:
    from renderers.share_html_renderer import (
        generate_share_html as _generate_share_html_renderer,
    )
except Exception:
    _generate_share_html_renderer = None


try:
    from renderers.share_fallback_renderer import (
        generate_share_html as _generate_share_html_fallback_renderer,
    )
except Exception:
    _generate_share_html_fallback_renderer = None


try:
    from renderers.csv_renderer import generate_csv as _generate_csv_renderer
except Exception:
    _generate_csv_renderer = None


try:
    from renderers.json_renderer import generate_json as _generate_json_renderer
except Exception:
    _generate_json_renderer = None


try:
    from steam_deals_recommendations import (
        build_gift_ideas as _build_gift_ideas_impl,
        build_recommended_collections as _build_recommended_collections_impl,
        compute_budget_picks as _compute_budget_picks_impl,
        compute_value_score as _compute_value_score_impl,
        rank_top_picks as _rank_top_picks_impl,
    )
except Exception:
    _build_gift_ideas_impl = None
    _build_recommended_collections_impl = None
    _compute_budget_picks_impl = None
    _compute_value_score_impl = None
    _rank_top_picks_impl = None


try:
    from steam_deals_hltb import (
        cross_hltb_with_deals as _cross_hltb_with_deals_impl,
        extract_numbers as _extract_numbers_impl,
        find_best_match as _find_best_match_impl,
        is_same_game as _is_same_game_impl,
        normalize as _normalize_impl,
        parse_hltb as _parse_hltb_impl,
        significant_words as _significant_words_impl,
    )
except Exception:
    _cross_hltb_with_deals_impl = None
    _extract_numbers_impl = None
    _find_best_match_impl = None
    _is_same_game_impl = None
    _normalize_impl = None
    _parse_hltb_impl = None
    _significant_words_impl = None


try:
    from steam_deals_filters import (
        apply_filters as _apply_filters_impl,
        filter_by_genres as _filter_by_genres_impl,
    )
except Exception:
    _apply_filters_impl = None
    _filter_by_genres_impl = None


try:
    from steam_deals_alerts import build_smart_alert_counts as _build_smart_alert_counts_impl
except Exception:
    _build_smart_alert_counts_impl = None


try:
    from steam_deals_history import (
        analyze_trends as _analyze_trends_impl,
        compute_deal_comparison as _compute_deal_comparison_impl,
        format_trend as _format_trend_impl,
        load_previous_deal_appids as _load_previous_deal_appids_impl,
        load_previous_run as _load_previous_run_impl,
        load_price_history as _load_price_history_impl,
        load_run_history as _load_run_history_impl,
        log_price_snapshot as _log_price_snapshot_impl,
        save_price_history as _save_price_history_impl,
        save_run_history as _save_run_history_impl,
    )
except Exception:
    _analyze_trends_impl = None
    _compute_deal_comparison_impl = None
    _format_trend_impl = None
    _load_previous_deal_appids_impl = None
    _load_previous_run_impl = None
    _load_price_history_impl = None
    _load_run_history_impl = None
    _log_price_snapshot_impl = None
    _save_price_history_impl = None
    _save_run_history_impl = None


try:
    from steam_deals_itad import (
        itad_get_active_bundles as _itad_get_active_bundles_impl,
        itad_get_current_prices as _itad_get_current_prices_impl,
        itad_get_store_lows as _itad_get_store_lows_impl,
        itad_lookup_games as _itad_lookup_games_impl,
    )
except Exception:
    _itad_get_active_bundles_impl = None
    _itad_get_current_prices_impl = None
    _itad_get_store_lows_impl = None
    _itad_lookup_games_impl = None


try:
    from steam_deals_watchlist import (
        check_watchlist_alerts as _check_watchlist_alerts_impl,
        handle_watchlist_command as _handle_watchlist_command_impl,
        load_watchlist as _load_watchlist_impl,
        save_watchlist as _save_watchlist_impl,
    )
except Exception:
    _check_watchlist_alerts_impl = None
    _handle_watchlist_command_impl = None
    _load_watchlist_impl = None
    _save_watchlist_impl = None


try:
    from steam_deals_steam_api import (
        compare_wishlists as _compare_wishlists_impl,
        get_active_promo_context as _get_active_promo_context_impl,
        get_active_sale as _get_active_sale_impl,
        get_owned_games as _get_owned_games_impl,
        get_wishlist as _get_wishlist_impl,
        load_family_games as _load_family_games_impl,
        resolve_profile_display_name as _resolve_profile_display_name_impl,
        resolve_steam_id as _resolve_steam_id_impl,
    )
except Exception:
    _compare_wishlists_impl = None
    _get_active_promo_context_impl = None
    _get_active_sale_impl = None
    _get_owned_games_impl = None
    _get_wishlist_impl = None
    _load_family_games_impl = None
    _resolve_profile_display_name_impl = None
    _resolve_steam_id_impl = None


try:
    import steam_deals_family as _family_module
except Exception:
    _family_module = None


try:
    import steam_deals_itad_orchestration as _itad_orchestration_module
except Exception:
    _itad_orchestration_module = None


try:
    import steam_deals_post_processing as _post_processing_module
except Exception:
    _post_processing_module = None


try:
    import steam_deals_engagement_post_run as _engagement_post_run_module
except Exception:
    _engagement_post_run_module = None


try:
    from steam_deals_notifications import (
        build_notification_summary as _build_notification_summary_impl,
        send_discord as _send_discord_impl,
        send_notifications as _send_notifications_impl,
        send_telegram as _send_telegram_impl,
    )
except Exception:
    _build_notification_summary_impl = None
    _send_discord_impl = None
    _send_notifications_impl = None
    _send_telegram_impl = None


try:
    from steam_deals_scheduler import run_scheduled as _run_scheduled_impl
except Exception:
    _run_scheduled_impl = None


try:
    from steam_deals_config import (
        get_config as _get_config_impl,
        load_user_config as _load_user_config_impl,
        save_user_config as _save_user_config_impl,
    )
except Exception:
    _get_config_impl = None
    _load_user_config_impl = None
    _save_user_config_impl = None


try:
    from steam_deals_presentation import (
        achievements_badge as _achievements_badge_impl,
        deck_badge as _deck_badge_impl,
        get_top_tags as _get_top_tags_impl,
        group_by_tier as _group_by_tier_impl,
        group_deals_by_tag as _group_deals_by_tag_impl,
        linux_badge as _linux_badge_impl,
        multiplayer_badges as _multiplayer_badges_impl,
        players_badge as _players_badge_impl,
        protondb_badge as _protondb_badge_impl,
    )
except Exception:
    _achievements_badge_impl = None
    _deck_badge_impl = None
    _get_top_tags_impl = None
    _group_by_tier_impl = None
    _group_deals_by_tag_impl = None
    _linux_badge_impl = None
    _multiplayer_badges_impl = None
    _players_badge_impl = None
    _protondb_badge_impl = None


try:
    import steam_deals_enrichment as _enrichment_module
except Exception:
    _enrichment_module = None


try:
    import steam_deals_prices as _prices_module
except Exception:
    _prices_module = None


try:
    import steam_deals_cache_policy as _cache_policy_module
except Exception:
    _cache_policy_module = None


try:
    import steam_deals_enrichment_orchestration as _enrichment_orchestration_module
except Exception:
    _enrichment_orchestration_module = None


try:
    import steam_deals_run_output as _run_output_module
except Exception:
    _run_output_module = None

try:
    from steam_deals_paths import (
        resolve_cache_dir as _resolve_cache_dir_impl,
        resolve_logs_dir as _resolve_logs_dir_impl,
    )
except Exception:
    _resolve_cache_dir_impl = None
    _resolve_logs_dir_impl = None


try:
    from steam_deals_runtime_reporting import (
        AnsiColors as _RuntimeAnsiColors,
        EVENT_PREFIX as _RUNTIME_EVENT_PREFIX,
        bold_text as _bold_text_impl,
        dim_text as _dim_text_impl,
        emit_event as _emit_event_impl,
        err_text as _err_text_impl,
        ok_text as _ok_text_impl,
        report_step as _report_step_impl,
        safe_symbol as _safe_symbol_impl,
        warn_text as _warn_text_impl,
    )
except Exception:
    _RuntimeAnsiColors = None
    _RUNTIME_EVENT_PREFIX = "__STEAM_EVENT__"
    _bold_text_impl = None
    _dim_text_impl = None
    _emit_event_impl = None
    _err_text_impl = None
    _ok_text_impl = None
    _report_step_impl = None
    _safe_symbol_impl = None
    _warn_text_impl = None


# ─────────────────────────────────────────────
# COLORES ANSI
# ─────────────────────────────────────────────


class C:
    RST = _RuntimeAnsiColors.RST if _RuntimeAnsiColors else "\033[0m"
    BOLD = _RuntimeAnsiColors.BOLD if _RuntimeAnsiColors else "\033[1m"
    DIM = _RuntimeAnsiColors.DIM if _RuntimeAnsiColors else "\033[2m"
    GRN = _RuntimeAnsiColors.GRN if _RuntimeAnsiColors else "\033[32m"
    YLW = _RuntimeAnsiColors.YLW if _RuntimeAnsiColors else "\033[33m"
    RED = _RuntimeAnsiColors.RED if _RuntimeAnsiColors else "\033[31m"
    CYN = _RuntimeAnsiColors.CYN if _RuntimeAnsiColors else "\033[36m"


def _safe_symbol(unicode_symbol: str, fallback: str) -> str:
    if _safe_symbol_impl is not None:
        return _safe_symbol_impl(
            unicode_symbol, fallback, stdout_encoding=(sys.stdout.encoding or "utf-8")
        )
    enc = sys.stdout.encoding or "utf-8"
    try:
        unicode_symbol.encode(enc)
        return unicode_symbol
    except Exception:
        return fallback


SYM_OK = _safe_symbol("✓", "OK")
SYM_WARN = _safe_symbol("⚠", "!")
SYM_ERR = _safe_symbol("✗", "X")
SYM_TAG = _safe_symbol("🏷️", "[SALE]")
SYM_TARGET = _safe_symbol("🎯", "[ALERT]")
SYM_BUDGET = _safe_symbol("💰", "[BUDGET]")
SYM_GIFT = _safe_symbol("🎁", "[GIFT]")
BAR_FILL = _safe_symbol("█", "#")
BAR_EMPTY = _safe_symbol("░", "-")
EVENT_PREFIX = _RUNTIME_EVENT_PREFIX
WEB_EVENT_MODE = False


def _ok(msg):
    if _ok_text_impl is not None:
        return _ok_text_impl(msg, green=C.GRN, reset=C.RST, symbol=SYM_OK)
    return f"{C.GRN}{SYM_OK}{C.RST}  {msg}"


def _warn(msg):
    if _warn_text_impl is not None:
        return _warn_text_impl(msg, yellow=C.YLW, reset=C.RST, symbol=SYM_WARN)
    return f"{C.YLW}{SYM_WARN}{C.RST}  {msg}"


def _err(msg):
    if _err_text_impl is not None:
        return _err_text_impl(msg, red=C.RED, reset=C.RST, symbol=SYM_ERR)
    return f"{C.RED}{SYM_ERR}{C.RST}  {msg}"


def _dim(msg):
    if _dim_text_impl is not None:
        return _dim_text_impl(msg, dim=C.DIM, reset=C.RST)
    return f"{C.DIM}{msg}{C.RST}"


def _bold(msg):
    if _bold_text_impl is not None:
        return _bold_text_impl(msg, bold=C.BOLD, reset=C.RST)
    return f"{C.BOLD}{msg}{C.RST}"


def emit_event(event_type: str, **payload) -> None:
    if _emit_event_impl is not None:
        _emit_event_impl(
            event_type,
            web_event_mode=WEB_EVENT_MODE,
            emit=print,
            event_prefix=EVENT_PREFIX,
            **payload,
        )
        return
    if not WEB_EVENT_MODE:
        return
    try:
        msg = {"type": event_type, **payload}
        print(f"{EVENT_PREFIX}{json.dumps(msg, ensure_ascii=False)}", flush=True)
    except Exception:
        # Los eventos son opcionales; nunca deben romper el flujo principal.
        return


# ─────────────────────────────────────────────
# CONFIG FILE (~/.config/steam_deals.json)
# ─────────────────────────────────────────────

CONFIG_FILE = Path.home() / ".config" / "steam_deals.json"


def load_user_config() -> dict:
    if _load_user_config_impl is None:
        raise RuntimeError("Config module is not available")
    return _load_user_config_impl(CONFIG_FILE, load_json_file=load_json_file)


def save_user_config(cfg: dict) -> None:
    if _save_user_config_impl is None:
        raise RuntimeError("Config module is not available")
    _save_user_config_impl(CONFIG_FILE, cfg, write_json_file=write_json_file)
    print(f"  {_ok(f'Config guardada en {CONFIG_FILE}')}")


# ─────────────────────────────────────────────
# WATCHLIST (PRICE ALERTS)
# ─────────────────────────────────────────────


def _resolve_watchlist_name(appid: str) -> str:
    name = appid
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=basic"
        data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"})
        info = data.get(appid, {}).get("data", {})
        name = info.get("name", appid)
    except Exception:
        pass
    return name


def load_watchlist() -> list[dict]:
    if _load_watchlist_impl is None:
        raise RuntimeError("Watchlist module is not available")
    return _load_watchlist_impl()


def save_watchlist(items: list[dict]) -> None:
    if _save_watchlist_impl is None:
        raise RuntimeError("Watchlist module is not available")
    _save_watchlist_impl(items)


def handle_watchlist_command(args: list[str]) -> bool:
    """Handle --watchlist subcommands. Returns True if handled (should exit)."""
    if _handle_watchlist_command_impl is None:
        raise RuntimeError("Watchlist module is not available")
    return _handle_watchlist_command_impl(
        args,
        resolve_name=_resolve_watchlist_name,
        emit=print,
        ok=_ok,
        warn=_warn,
        err=_err,
        dim=_dim,
        bold=_bold,
    )


def check_watchlist_alerts(deals: list[dict], watchlist: list[dict]) -> list[dict]:
    """Check which watchlist games have hit their target price."""
    if _check_watchlist_alerts_impl is None:
        raise RuntimeError("Watchlist module is not available")
    return _check_watchlist_alerts_impl(deals, watchlist)


# ─────────────────────────────────────────────
# ARGUMENTOS + CONFIG FILE + FALLBACK INTERACTIVO
# ─────────────────────────────────────────────


def get_config():
    if _get_config_impl is None:
        raise RuntimeError("Config module is not available")
    return _get_config_impl(
        script_path=Path(__file__).resolve(),
        load_user_config_fn=load_user_config,
        save_user_config_fn=save_user_config,
        handle_watchlist_command_fn=handle_watchlist_command,
        input_fn=input,
        stdin=sys.stdin,
        exit_fn=sys.exit,
    )


# ─────────────────────────────────────────────
# STEAM API
# ─────────────────────────────────────────────


def _fetch_public_profile_xml(vanity: str) -> str:
    if vanity.isdigit() and len(vanity) >= 16:
        url = f"https://steamcommunity.com/profiles/{vanity}/?xml=1"
    else:
        url = f"https://steamcommunity.com/id/{vanity}/?xml=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read().decode("utf-8")


def resolve_steam_id(api_key: str | None, vanity: str) -> str:
    """Convierte vanity URL, link de perfil, o Steam ID numérico a Steam ID."""
    if _resolve_steam_id_impl is None:
        raise RuntimeError("Steam adapter module is not available")
    try:
        return _resolve_steam_id_impl(
            api_key,
            vanity,
            get_json=_get_json,
            fetch_public_profile_xml=_fetch_public_profile_xml,
        )
    except urllib.error.HTTPError as exc:
        if not api_key or exc.code not in (401, 403):
            raise
        print(
            _warn(
                f"Steam rechazó la API key al resolver el perfil (HTTP {exc.code}). "
                "Intentando fallback público sin key..."
            ),
            flush=True,
        )
        return _resolve_steam_id_impl(
            None,
            vanity,
            get_json=_get_json,
            fetch_public_profile_xml=_fetch_public_profile_xml,
        )


def resolve_profile_display_name(
    steam_id: str,
    vanity_input: str,
    api_key: str | None,
) -> str:
    if _resolve_profile_display_name_impl is None:
        return vanity_input
    return _resolve_profile_display_name_impl(
        steam_id,
        vanity_input,
        api_key=api_key,
        get_json=_get_json,
        fetch_public_profile_xml=_fetch_public_profile_xml,
    )


def get_wishlist(
    api_key: str | None, steam_id: str
) -> tuple[list[str], dict[str, int]]:
    """Devuelve (lista de appids, dict appid→priority). Funciona con o sin API key."""
    if _get_wishlist_impl is None:
        raise RuntimeError("Steam adapter module is not available")
    return _get_wishlist_impl(api_key, steam_id, get_json=_get_json)


def get_owned_games(api_key: str, steam_id: str) -> dict[str, str]:
    """Devuelve dict appid → nombre de juegos propios en Steam."""
    if _get_owned_games_impl is None:
        raise RuntimeError("Steam adapter module is not available")
    return _get_owned_games_impl(api_key, steam_id, get_json=_get_json)


def compare_wishlists(api_key, steam_id_1, vanity_2):
    """Compare two wishlists. Returns overlap, unique to each, friend info."""
    if _compare_wishlists_impl is None:
        raise RuntimeError("Steam adapter module is not available")
    return _compare_wishlists_impl(
        api_key,
        steam_id_1,
        vanity_2,
        resolve_steam_id_fn=resolve_steam_id,
        get_wishlist_fn=get_wishlist,
        resolve_profile_display_name_fn=resolve_profile_display_name,
    )


def build_gift_ideas(friend_set, deals, owned):
    """Find deals that the friend wants but you don't own."""
    if _build_gift_ideas_impl is None:
        raise RuntimeError("Recommendations module is not available")
    return _build_gift_ideas_impl(friend_set, deals, owned)


def load_family_games(json_path: Path) -> set[str]:
    """Carga un JSON de biblioteca familiar → set de appids."""
    if _load_family_games_impl is None:
        raise RuntimeError("Steam adapter module is not available")
    return _load_family_games_impl(json_path)


def empty_family_context():
    if _family_module is None:
        raise RuntimeError("Family module is not available")
    return _family_module.empty_family_context()


def load_family_context(family_json: Path | None, *, step_fn):
    if _family_module is None:
        raise RuntimeError("Family module is not available")
    return _family_module.load_family_context(
        family_json,
        load_family_games_fn=load_family_games,
        step_fn=step_fn,
        emit_fn=print,
        ok_fn=_ok,
    )


def cross_hltb_with_family_context(
    hltb: dict[str, list[dict]],
    deals: list[dict],
    family_context,
):
    if _family_module is None:
        raise RuntimeError("Family module is not available")
    return _family_module.cross_hltb_with_family_context(
        hltb,
        deals,
        family_context,
        cross_hltb_with_deals_fn=cross_hltb_with_deals,
    )


def build_family_renderer_kwargs(family_context):
    if _family_module is None:
        raise RuntimeError("Family module is not available")
    return _family_module.build_family_renderer_kwargs(family_context)


def build_itad_message_formatters(*, ok_fn, dim_fn):
    if _itad_orchestration_module is None:
        raise RuntimeError("ITAD orchestration module is not available")
    return _itad_orchestration_module.build_message_formatters(
        ok=ok_fn,
        dim=dim_fn,
    )


def build_itad_progress_callbacks(*, step_fn, emit_fn):
    if _itad_orchestration_module is None:
        raise RuntimeError("ITAD orchestration module is not available")
    return _itad_orchestration_module.build_progress_callbacks(
        step=step_fn,
        emit=emit_fn,
    )


def build_itad_runtime(
    *, lookup_games_fn, get_store_lows_fn, get_current_prices_fn, get_active_bundles_fn
):
    if _itad_orchestration_module is None:
        raise RuntimeError("ITAD orchestration module is not available")
    return _itad_orchestration_module.build_itad_runtime(
        lookup_games=lookup_games_fn,
        get_store_lows=get_store_lows_fn,
        get_current_prices=get_current_prices_fn,
        get_active_bundles=get_active_bundles_fn,
    )


def build_itad_orchestration_contract(*, progress, messages, runtime):
    if _itad_orchestration_module is None:
        raise RuntimeError("ITAD orchestration module is not available")
    return _itad_orchestration_module.build_itad_orchestration_contract(
        progress=progress,
        messages=messages,
        runtime=runtime,
    )


def build_generator_itad_contract(step_fn):
    progress = build_itad_progress_callbacks(step_fn=step_fn, emit_fn=print)
    messages = build_itad_message_formatters(ok_fn=_ok, dim_fn=_dim)
    runtime = build_itad_runtime(
        lookup_games_fn=itad_lookup_games,
        get_store_lows_fn=itad_get_store_lows,
        get_current_prices_fn=itad_get_current_prices,
        get_active_bundles_fn=itad_get_active_bundles,
    )
    return build_itad_orchestration_contract(
        progress=progress,
        messages=messages,
        runtime=runtime,
    )


def run_itad_orchestration(deal_appids: list[str], itad_key: str | None, *, contract):
    if _itad_orchestration_module is None:
        raise RuntimeError("ITAD orchestration module is not available")
    return _itad_orchestration_module.run_itad_orchestration(
        deal_appids,
        itad_key,
        contract=contract,
    )


def build_post_processing_message_formatters(*, ok_fn):
    if _post_processing_module is None:
        raise RuntimeError("Post-processing module is not available")
    return _post_processing_module.build_message_formatters(ok=ok_fn)


def build_post_processing_callbacks(*, emit_fn):
    if _post_processing_module is None:
        raise RuntimeError("Post-processing module is not available")
    return _post_processing_module.build_callbacks(emit=emit_fn)


def build_post_processing_runtime(*, apply_filters_fn, rank_top_picks_fn):
    if _post_processing_module is None:
        raise RuntimeError("Post-processing module is not available")
    return _post_processing_module.build_runtime(
        apply_filters=apply_filters_fn,
        rank_top_picks=rank_top_picks_fn,
    )


def build_post_processing_contract(*, messages, callbacks, runtime):
    if _post_processing_module is None:
        raise RuntimeError("Post-processing module is not available")
    return _post_processing_module.build_post_processing_contract(
        messages=messages,
        callbacks=callbacks,
        runtime=runtime,
    )


def build_generator_post_processing_contract():
    messages = build_post_processing_message_formatters(ok_fn=_ok)
    callbacks = build_post_processing_callbacks(emit_fn=print)
    runtime = build_post_processing_runtime(
        apply_filters_fn=apply_filters,
        rank_top_picks_fn=rank_top_picks,
    )
    return build_post_processing_contract(
        messages=messages,
        callbacks=callbacks,
        runtime=runtime,
    )


def run_post_processing(
    deals: list[dict],
    backlog_on_sale: list[dict],
    have_on_sale: list[dict],
    *,
    filters: dict,
    priorities: dict[str, int],
    reviews_data: dict[str, dict],
    deck_data: dict[str, int],
    previous_appids: set[str],
    comparison: dict | None,
    contract,
    active_promo_context: dict | None = None,
):
    if _post_processing_module is None:
        raise RuntimeError("Post-processing module is not available")
    return _post_processing_module.run_post_processing(
        deals,
        backlog_on_sale,
        have_on_sale,
        filters=filters,
        priorities=priorities,
        reviews_data=reviews_data,
        deck_data=deck_data,
        previous_appids=previous_appids,
        comparison=comparison,
        contract=contract,
        active_promo_context=active_promo_context,
    )


def build_engagement_message_formatters(*, ok_fn, dim_fn):
    if _engagement_post_run_module is None:
        raise RuntimeError("Engagement post-run module is not available")
    return _engagement_post_run_module.build_message_formatters(
        ok=ok_fn,
        dim=dim_fn,
    )


def build_engagement_callbacks(*, step_fn, emit_fn):
    if _engagement_post_run_module is None:
        raise RuntimeError("Engagement post-run module is not available")
    return _engagement_post_run_module.build_callbacks(
        step=step_fn,
        emit=emit_fn,
    )


def build_engagement_runtime(
    *,
    load_watchlist_fn,
    check_watchlist_alerts_fn,
    compute_budget_picks_fn,
    build_gift_ideas_fn,
    build_notification_summary_fn,
    send_notifications_fn,
):
    if _engagement_post_run_module is None:
        raise RuntimeError("Engagement post-run module is not available")
    return _engagement_post_run_module.build_runtime(
        load_watchlist=load_watchlist_fn,
        check_watchlist_alerts=check_watchlist_alerts_fn,
        compute_budget_picks=compute_budget_picks_fn,
        build_gift_ideas=build_gift_ideas_fn,
        build_notification_summary=build_notification_summary_fn,
        send_notifications=send_notifications_fn,
    )


def build_engagement_contract(*, messages, callbacks, runtime):
    if _engagement_post_run_module is None:
        raise RuntimeError("Engagement post-run module is not available")
    return _engagement_post_run_module.build_engagement_contract(
        messages=messages,
        callbacks=callbacks,
        runtime=runtime,
    )


def build_generator_engagement_contract(step_fn):
    messages = build_engagement_message_formatters(ok_fn=_ok, dim_fn=_dim)
    callbacks = build_engagement_callbacks(step_fn=step_fn, emit_fn=print)
    runtime = build_engagement_runtime(
        load_watchlist_fn=load_watchlist,
        check_watchlist_alerts_fn=check_watchlist_alerts,
        compute_budget_picks_fn=compute_budget_picks,
        build_gift_ideas_fn=build_gift_ideas,
        build_notification_summary_fn=build_notification_summary,
        send_notifications_fn=send_notifications,
    )
    return build_engagement_contract(
        messages=messages,
        callbacks=callbacks,
        runtime=runtime,
    )


def run_engagement_post_run(
    deals: list[dict],
    *,
    filters: dict,
    top_picks: list[dict],
    compare_data: dict | None,
    owned: dict[str, str],
    comparison: dict | None,
    contract,
):
    if _engagement_post_run_module is None:
        raise RuntimeError("Engagement post-run module is not available")
    return _engagement_post_run_module.run_engagement_post_run(
        deals,
        filters=filters,
        top_picks=top_picks,
        compare_data=compare_data,
        owned=owned,
        comparison=comparison,
        contract=contract,
        sym_target=SYM_TARGET,
        sym_budget=SYM_BUDGET,
        sym_gift=SYM_GIFT,
    )


def get_active_sale() -> str:
    """Detecta la oferta/evento activo en Steam via marketing messages API."""
    if _get_active_sale_impl is None:
        raise RuntimeError("Steam adapter module is not available")
    return _get_active_sale_impl(get_json=_get_json)


def get_active_promo_context() -> dict:
    """Detecta promos activas de Steam con contexto estructurado."""
    if _get_active_promo_context_impl is None:
        raise RuntimeError("Steam adapter module is not available")
    return _get_active_promo_context_impl(get_json=_get_json)


# ─────────────────────────────────────────────
# IsThereAnyDeal API (mínimo histórico)
# ─────────────────────────────────────────────


def itad_lookup_games(appids: list[str], itad_key: str) -> dict[str, str]:
    """Resuelve Steam appids → ITAD game IDs. Devuelve {appid: itad_id}."""
    if _itad_lookup_games_impl is None:
        raise RuntimeError("ITAD module is not available")
    return _itad_lookup_games_impl(
        appids,
        itad_key,
        post_json=_post_json,
        sleep_fn=time.sleep,
        on_error=lambda message: print(f"\n  {_warn(message)}", flush=True),
    )


def itad_get_store_lows(
    itad_ids: dict[str, str], itad_key: str, country: str = "MX"
) -> dict[str, dict]:
    """Obtiene mínimo histórico en Steam. Devuelve {appid: {price, cut, date}}."""
    if _itad_get_store_lows_impl is None:
        raise RuntimeError("ITAD module is not available")
    return _itad_get_store_lows_impl(
        itad_ids,
        itad_key,
        country=country,
        post_json=_post_json,
        sleep_fn=time.sleep,
        on_error=lambda message: print(f"\n  {_warn(message)}", flush=True),
    )


def itad_get_current_prices(
    itad_ids: dict[str, str], itad_key: str, country: str = "MX"
) -> dict[str, dict]:
    """Current best prices across stores. Returns {appid: {store, price, url}} only when another store beats Steam."""
    if _itad_get_current_prices_impl is None:
        raise RuntimeError("ITAD module is not available")
    return _itad_get_current_prices_impl(
        itad_ids,
        itad_key,
        country=country,
        post_json=_post_json,
        sleep_fn=time.sleep,
        on_error=lambda message: print(f"\n  {_warn(message)}", flush=True),
    )


def itad_get_active_bundles(
    itad_ids: dict[str, str], itad_key: str, country: str = "US"
) -> dict[str, list[dict]]:
    """Active bundles containing deal games. Returns {appid: [{title, store, price, currency, url}]}."""
    if _itad_get_active_bundles_impl is None:
        raise RuntimeError("ITAD module is not available")
    return _itad_get_active_bundles_impl(
        itad_ids,
        itad_key,
        country=country,
        post_json=_post_json,
        sleep_fn=time.sleep,
        on_error=lambda message: print(f"\n  {_warn(message)}", flush=True),
    )


# ─────────────────────────────────────────────
# COMPARAR CON MD ANTERIOR
# ─────────────────────────────────────────────


def load_previous_deal_appids(output_dir: Path, current_filename: str) -> set[str]:
    """Busca el MD anterior más reciente y extrae los appids de deals."""
    if _load_previous_deal_appids_impl is None:
        raise RuntimeError("History module is not available")
    return _load_previous_deal_appids_impl(output_dir, current_filename)


# ─────────────────────────────────────────────
# HISTORIAL DE RUNS
# ─────────────────────────────────────────────


def save_run_history(
    steam_id: str,
    vanity: str,
    sale_name: str,
    min_discount: int,
    deals: list[dict],
    *,
    active_promo_context: dict | None = None,
) -> Path:
    """Guarda snapshot del run actual en historial JSON."""
    if _save_run_history_impl is None:
        raise RuntimeError("History module is not available")
    return _save_run_history_impl(
        steam_id,
        vanity,
        sale_name,
        min_discount,
        deals,
        history_dir=HISTORY_DIR,
        history_max_files=HISTORY_MAX_FILES,
        active_promo_context=active_promo_context,
    )


def load_previous_run(steam_id: str) -> dict | None:
    """Carga el run anterior más reciente del historial."""
    if _load_previous_run_impl is None:
        raise RuntimeError("History module is not available")
    return _load_previous_run_impl(steam_id, history_dir=HISTORY_DIR)


def load_run_history(steam_id: str, max_runs: int = 30) -> list[dict]:
    """Carga los últimos N runs para deal streak tracking."""
    if _load_run_history_impl is None:
        raise RuntimeError("History module is not available")
    return _load_run_history_impl(steam_id, history_dir=HISTORY_DIR, max_runs=max_runs)


def compute_deal_comparison(
    current_deals: list[dict],
    previous_run: dict | None,
    run_history: list[dict],
) -> dict:
    """Compara deals actuales con run anterior y historial."""
    if _compute_deal_comparison_impl is None:
        raise RuntimeError("History module is not available")
    return _compute_deal_comparison_impl(current_deals, previous_run, run_history)


# ─────────────────────────────────────────────
# HISTORIAL LOCAL DE PRECIOS
# ─────────────────────────────────────────────


def load_price_history(steam_id: str) -> dict:
    if _load_price_history_impl is None:
        raise RuntimeError("History module is not available")
    return _load_price_history_impl(
        steam_id,
        price_history_file=PRICE_HISTORY_FILE,
        load_json_file=load_json_file,
    )


def save_price_history(history: dict) -> None:
    if _save_price_history_impl is None:
        raise RuntimeError("History module is not available")
    _save_price_history_impl(
        history,
        price_history_file=PRICE_HISTORY_FILE,
        write_json_file=write_json_file,
    )


def log_price_snapshot(history: dict, deals: list[dict]) -> None:
    """Register current run's prices into the history."""
    if _log_price_snapshot_impl is None:
        raise RuntimeError("History module is not available")
    _log_price_snapshot_impl(history, deals)


def analyze_trends(history: dict, deals: list[dict]) -> dict[str, dict]:
    """Analyze price trends for current deals. Returns {appid: trend_info}."""
    if _analyze_trends_impl is None:
        raise RuntimeError("History module is not available")
    return _analyze_trends_impl(history, deals)


def format_trend(trend: dict) -> str:
    if _format_trend_impl is None:
        raise RuntimeError("History module is not available")
    return _format_trend_impl(trend)


def build_output_md_path(
    output_dir: str | Path, sale_name: str, *, today_obj: date | None = None
) -> Path:
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.build_output_md_path(
        output_dir, sale_name, today_obj=today_obj
    )


def resolve_previous_context(
    output_dir: str | Path, current_filename: str, steam_id: str
) -> dict:
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.resolve_previous_context(
        output_dir,
        current_filename,
        steam_id,
        load_previous_run_fn=load_previous_run,
        load_run_history_fn=load_run_history,
        load_previous_deal_appids_fn=load_previous_deal_appids,
    )


def build_share_output_path(
    output_dir: str | Path, *, today_obj: date | None = None
) -> Path:
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.build_share_output_path(output_dir, today_obj=today_obj)


def build_output_artifact_paths(
    output_md: Path,
    *,
    today_obj: date | None = None,
    include_csv: bool = False,
):
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.build_output_artifact_paths(
        output_md,
        today_obj=today_obj,
        include_csv=include_csv,
    )


def write_artifact(path: Path, content: str) -> Path:
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.write_artifact(path, content, emit_event_fn=emit_event)


def write_output_artifacts(paths, payloads):
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.write_output_artifacts(
        paths,
        payloads,
        write_artifact_fn=write_artifact,
    )


def build_final_summary(
    elapsed: float,
    deals: list[dict],
    backlog_on_sale: list[dict],
    previous_appids: set[str],
    top_picks: list[dict] | None,
    output_md: Path,
    smart_alerts: dict[str, int] | None = None,
) -> tuple[int, str]:
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.build_final_summary(
        elapsed,
        deals,
        backlog_on_sale,
        previous_appids,
        top_picks,
        output_md,
        smart_alerts,
    )


def build_smart_alert_counts(**kwargs) -> dict[str, int]:
    if _build_smart_alert_counts_impl is None:
        raise RuntimeError("Alerts module is not available")
    return _build_smart_alert_counts_impl(**kwargs)


def emit_final_closeout(
    elapsed: float,
    deals: list[dict],
    backlog_on_sale: list[dict],
    previous_appids: set[str],
    top_picks: list[dict] | None,
    output_md: Path,
    smart_alerts: dict[str, int] | None = None,
):
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.emit_final_closeout(
        elapsed,
        deals,
        backlog_on_sale,
        previous_appids,
        top_picks,
        output_md,
        smart_alerts=smart_alerts,
        build_final_summary_fn=build_final_summary,
        emit_fn=print,
        bold_fn=_bold,
        color_green=C.GRN,
        color_reset=C.RST,
    )


# ─────────────────────────────────────────────
# CACHÉ DE PRECIOS (smart partial refresh)
# ─────────────────────────────────────────────

PROJECT_DIR = Path(__file__).resolve().parent
if _resolve_cache_dir_impl is None:
    CACHE_DIR = PROJECT_DIR / ".cache" / "steam_deals"
else:
    CACHE_DIR = _resolve_cache_dir_impl(
        PROJECT_DIR,
        frozen=getattr(sys, "frozen", False),
    )
CACHE_FILE = CACHE_DIR / "prices_cache.json"
CACHE_MAX_HOURS = 24
PRICE_BATCH_HALVING_LIMIT = 3
REVIEWS_CACHE_FILE = CACHE_DIR / "reviews_cache.json"
DECK_CACHE_FILE = CACHE_DIR / "deck_cache.json"
EXTRA_CACHE_TTL = 168  # 7 days in hours
HISTORY_DIR = CACHE_DIR / "history"
HISTORY_MAX_FILES = 100
TAGS_CACHE_FILE = CACHE_DIR / "tags_cache.json"
TAGS_CACHE_TTL = 720  # 30 days in hours
PRICE_HISTORY_FILE = CACHE_DIR / "price_history.json"
PROTONDB_CACHE_FILE = CACHE_DIR / "protondb_cache.json"
ANTICHEAT_CACHE_FILE = CACHE_DIR / "anticheat_cache.json"
ACHIEVEMENTS_CACHE_FILE = CACHE_DIR / "achievements_cache.json"
ACHIEVEMENTS_CACHE_TTL = 720  # 30 days in hours
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def resolve_logs_dir(*, env=None, frozen: bool = False) -> Path:
    if _resolve_logs_dir_impl is None:
        return PROJECT_DIR / "logs"
    return _resolve_logs_dir_impl(PROJECT_DIR, env=env, frozen=frozen)


def _resolve_positive_int_env(
    name: str,
    default: int,
    *,
    env=None,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    source_env = os.environ if env is None else env
    raw = source_env.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    if value < minimum:
        return default
    if maximum is not None:
        return min(value, maximum)
    return value


def _resolve_positive_float_env(
    name: str,
    default: float | None,
    *,
    env=None,
    minimum: float = 0.0,
) -> float | None:
    source_env = os.environ if env is None else env
    raw = source_env.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(str(raw).strip())
    except ValueError:
        return default
    return value if value >= minimum else default


def resolve_price_fetch_tuning(*, env=None) -> dict[str, int | float | bool | None]:
    batch_size = _resolve_positive_int_env(
        "STEAM_DEALS_PRICE_BATCH_SIZE",
        BATCH_SIZE,
        env=env,
        minimum=1,
    )
    batch_halving_limit = _resolve_positive_int_env(
        "STEAM_DEALS_PRICE_BATCH_HALVING_LIMIT",
        PRICE_BATCH_HALVING_LIMIT,
        env=env,
        minimum=0,
    )
    individual_fallback_workers = _resolve_positive_int_env(
        "STEAM_DEALS_INDIVIDUAL_FALLBACK_WORKERS",
        PRICE_INDIVIDUAL_FALLBACK_WORKERS,
        env=env,
        minimum=1,
        maximum=PRICE_INDIVIDUAL_FALLBACK_WORKERS_MAX,
    )
    max_refresh_candidates_per_run = _resolve_positive_int_env(
        "STEAM_DEALS_MAX_REFRESH_CANDIDATES_PER_RUN",
        PRICE_MAX_REFRESH_CANDIDATES_PER_RUN,
        env=env,
        minimum=0,
    )
    refresh_time_budget_seconds = _resolve_positive_float_env(
        "STEAM_DEALS_PRICE_REFRESH_TIME_BUDGET_SECONDS",
        PRICE_REFRESH_TIME_BUDGET_SECONDS,
        env=env,
        minimum=0.0,
    )
    return {
        "batch_size": batch_size,
        "batch_halving_limit": batch_halving_limit,
        "individual_fallback_workers": individual_fallback_workers,
        "max_refresh_candidates_per_run": max_refresh_candidates_per_run,
        "refresh_time_budget_seconds": refresh_time_budget_seconds,
        "is_custom": batch_size != BATCH_SIZE
        or batch_halving_limit != PRICE_BATCH_HALVING_LIMIT
        or individual_fallback_workers != PRICE_INDIVIDUAL_FALLBACK_WORKERS
        or max_refresh_candidates_per_run != PRICE_MAX_REFRESH_CANDIDATES_PER_RUN
        or refresh_time_budget_seconds != PRICE_REFRESH_TIME_BUDGET_SECONDS,
    }


def build_warm_cache_log_path(logs_dir: Path, *, now_fn=datetime.now) -> Path:
    timestamp = now_fn().strftime("%Y-%m-%d_%H-%M-%S")
    return logs_dir / f"warm-cache-{timestamp}.log"


def strip_ansi_for_log(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def write_warm_cache_log(
    log_handle, message: str, *, end: str = "\n", flush: bool = False
) -> None:
    clean_message = strip_ansi_for_log(str(message)).replace("\r", "\n")
    clean_end = strip_ansi_for_log(str(end)).replace("\r", "\n")
    log_handle.write(clean_message)
    log_handle.write(clean_end)
    if flush:
        log_handle.flush()


def build_warm_cache_emit(log_handle, *, terminal_emit=print):
    def emit(message="", **kwargs):
        try:
            terminal_emit(message, **kwargs)
        except TypeError:
            terminal_emit(message)
        write_warm_cache_log(
            log_handle,
            str(message),
            end=str(kwargs.get("end", "\n")),
            flush=bool(kwargs.get("flush", False)),
        )

    return emit


def open_warm_cache_log_file(*, env=None, frozen: bool = False, now_fn=datetime.now):
    logs_dir = resolve_logs_dir(env=env, frozen=frozen)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = build_warm_cache_log_path(logs_dir, now_fn=now_fn)
    return log_path, log_path.open("w", encoding="utf-8")


def build_price_related_cache_files() -> tuple[Path, ...]:
    return (
        REVIEWS_CACHE_FILE,
        DECK_CACHE_FILE,
        TAGS_CACHE_FILE,
        PROTONDB_CACHE_FILE,
        ANTICHEAT_CACHE_FILE,
        ACHIEVEMENTS_CACHE_FILE,
    )


def clear_cache_files(cache_files: list[Path]) -> tuple[Path, ...]:
    if _cache_policy_module is None:
        raise RuntimeError("Cache policy module is not available")
    return _cache_policy_module.clear_cache_files(cache_files)


def select_scoped_cache(
    target_ids: list[str],
    cached: dict,
    cache_age: float,
    *,
    no_cache: bool,
    ttl_hours: float,
    current_time_fn=time.time,
    entry_ttl_hours: float | None = None,
    failure_retry_hours: float = 2.0,
    preserve_expired_payload: bool = False,
    stale_grace_hours: float = 0.0,
    ttl_jitter_hours: int | float = 0,
    max_stale_refresh_per_run: int | None = None,
    min_discount: int = 0,
):
    if _cache_policy_module is None:
        raise RuntimeError("Cache policy module is not available")
    return _cache_policy_module.select_scoped_cache(
        target_ids,
        cached,
        cache_age,
        no_cache=no_cache,
        ttl_hours=ttl_hours,
        current_time_fn=current_time_fn,
        entry_ttl_hours=entry_ttl_hours,
        failure_retry_hours=failure_retry_hours,
        preserve_expired_payload=preserve_expired_payload,
        stale_grace_hours=stale_grace_hours,
        ttl_jitter_hours=ttl_jitter_hours,
        max_stale_refresh_per_run=max_stale_refresh_per_run,
        min_discount=min_discount,
    )


def select_global_cache(
    cached: dict,
    cache_age: float,
    *,
    no_cache: bool,
    ttl_hours: float,
):
    if _cache_policy_module is None:
        raise RuntimeError("Cache policy module is not available")
    return _cache_policy_module.select_global_cache(
        cached,
        cache_age,
        no_cache=no_cache,
        ttl_hours=ttl_hours,
    )


def build_enrichment_message_formatters(*, ok_fn, warn_fn, dim_fn):
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.build_message_formatters(
        ok=ok_fn,
        warn=warn_fn,
        dim=dim_fn,
    )


def build_enrichment_progress_callbacks(*, step_fn, emit_fn):
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.build_progress_callbacks(
        step=step_fn,
        emit=emit_fn,
    )


def build_scoped_enrichment_runtime(
    *, load_cache_fn, select_cache_fn, fetch_data_fn, save_cache_fn, ttl_hours: float
):
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.build_scoped_cache_runtime(
        load_cache=load_cache_fn,
        select_cache=select_cache_fn,
        fetch_data=fetch_data_fn,
        save_cache=save_cache_fn,
        ttl_hours=ttl_hours,
    )


def build_global_enrichment_runtime(
    *, load_cache_fn, select_cache_fn, fetch_data_fn, save_cache_fn, ttl_hours: float
):
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.build_global_cache_runtime(
        load_cache=load_cache_fn,
        select_cache=select_cache_fn,
        fetch_data=fetch_data_fn,
        save_cache=save_cache_fn,
        ttl_hours=ttl_hours,
    )


def build_enrichment_orchestration_contract(
    *,
    progress,
    messages,
    reviews_runtime,
    deck_runtime,
    protondb_runtime,
    anticheat_runtime,
    tags_runtime,
    achievements_runtime,
):
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.build_enrichment_orchestration_contract(
        progress=progress,
        messages=messages,
        reviews=reviews_runtime,
        deck=deck_runtime,
        protondb=protondb_runtime,
        anticheat=anticheat_runtime,
        tags=tags_runtime,
        achievements=achievements_runtime,
    )


def build_generator_enrichment_contract(step_fn):
    progress = build_enrichment_progress_callbacks(step_fn=step_fn, emit_fn=print)
    messages = build_enrichment_message_formatters(
        ok_fn=_ok, warn_fn=_warn, dim_fn=_dim
    )
    return build_enrichment_orchestration_contract(
        progress=progress,
        messages=messages,
        reviews_runtime=build_scoped_enrichment_runtime(
            load_cache_fn=load_reviews_cache,
            select_cache_fn=select_scoped_cache,
            fetch_data_fn=fetch_reviews,
            save_cache_fn=save_reviews_cache,
            ttl_hours=EXTRA_CACHE_TTL,
        ),
        deck_runtime=build_scoped_enrichment_runtime(
            load_cache_fn=load_deck_cache,
            select_cache_fn=select_scoped_cache,
            fetch_data_fn=fetch_deck_compat,
            save_cache_fn=save_deck_cache,
            ttl_hours=EXTRA_CACHE_TTL,
        ),
        protondb_runtime=build_scoped_enrichment_runtime(
            load_cache_fn=lambda _steam_id: load_protondb_cache(),
            select_cache_fn=select_scoped_cache,
            fetch_data_fn=fetch_protondb,
            save_cache_fn=lambda _steam_id, data: save_protondb_cache(data),
            ttl_hours=EXTRA_CACHE_TTL,
        ),
        anticheat_runtime=build_global_enrichment_runtime(
            load_cache_fn=load_anticheat_cache,
            select_cache_fn=select_global_cache,
            fetch_data_fn=fetch_anticheat_db,
            save_cache_fn=save_anticheat_cache,
            ttl_hours=EXTRA_CACHE_TTL,
        ),
        tags_runtime=build_scoped_enrichment_runtime(
            load_cache_fn=lambda _steam_id: load_tags_cache(),
            select_cache_fn=select_scoped_cache,
            fetch_data_fn=fetch_tags,
            save_cache_fn=lambda _steam_id, data: save_tags_cache(data),
            ttl_hours=TAGS_CACHE_TTL,
        ),
        achievements_runtime=build_scoped_enrichment_runtime(
            load_cache_fn=load_achievements_cache,
            select_cache_fn=select_scoped_cache,
            fetch_data_fn=fetch_achievements,
            save_cache_fn=save_achievements_cache,
            ttl_hours=ACHIEVEMENTS_CACHE_TTL,
        ),
    )


def run_reviews_enrichment_orchestration(
    contract, steam_id: str, deal_appids: list[str], *, no_cache: bool
) -> dict[str, dict]:
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.run_reviews_orchestration(
        steam_id,
        deal_appids,
        no_cache=no_cache,
        contract=contract,
    )


def run_deck_enrichment_orchestration(
    contract, steam_id: str, deal_appids: list[str], *, no_cache: bool
) -> dict[str, int]:
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.run_deck_orchestration(
        steam_id,
        deal_appids,
        no_cache=no_cache,
        contract=contract,
    )


def run_protondb_anticheat_enrichment_orchestration(
    contract, steam_id: str, deal_appids: list[str], *, no_cache: bool
) -> tuple[dict[str, dict], dict[str, dict]]:
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.run_protondb_anticheat_orchestration(
        steam_id,
        deal_appids,
        no_cache=no_cache,
        contract=contract,
    )


def run_tags_enrichment_orchestration(
    contract, steam_id: str, deal_appids: list[str], *, no_cache: bool
) -> dict[str, dict]:
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.run_tags_orchestration(
        steam_id,
        deal_appids,
        no_cache=no_cache,
        contract=contract,
    )


def run_achievements_enrichment_orchestration(
    contract, steam_id: str, deal_appids: list[str], *, no_cache: bool
) -> dict[str, dict]:
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.run_achievements_orchestration(
        steam_id,
        deal_appids,
        no_cache=no_cache,
        contract=contract,
    )


def load_price_cache(steam_id: str) -> tuple[dict, float]:
    if _prices_module is None:
        raise RuntimeError("Prices module is not available")
    return _prices_module.load_price_cache(CACHE_FILE, steam_id)


def save_price_cache(steam_id: str, fetched: dict) -> None:
    if _prices_module is None:
        raise RuntimeError("Prices module is not available")
    _prices_module.save_price_cache(CACHE_FILE, steam_id, fetched)


def _format_price_refresh_details(price_cache_policy, *, action_label: str) -> str:
    missing_ids = tuple(getattr(price_cache_policy, "missing_ids", ()) or ())
    refresh_ids = tuple(
        getattr(price_cache_policy, "refresh_ids", missing_ids) or ()
    )
    deferred_failure_ids = tuple(
        getattr(price_cache_policy, "deferred_failure_ids", ()) or ()
    )
    stale_count = sum(1 for appid in refresh_ids if appid not in missing_ids)
    if refresh_ids:
        details = []
        if missing_ids:
            details.append(f"{len(missing_ids)} nuevos")
        if stale_count:
            details.append(f"{stale_count} stale")
        if deferred_failure_ids:
            details.append(f"{len(deferred_failure_ids)} fallos recientes en cooldown")
        details_msg = f" ({', '.join(details)})" if details else ""
        return f"{len(refresh_ids)} {action_label}{details_msg}"
    status_msg = _dim("sin nuevos, skip fetch")
    if deferred_failure_ids:
        status_msg = f"{status_msg} ({len(deferred_failure_ids)} fallos recientes en cooldown)"
    return status_msg


def _count_ttl_jitter_buckets(price_cache_policy) -> dict[int, int]:
    buckets = getattr(price_cache_policy, "ttl_jitter_buckets", {}) or {}
    if not isinstance(buckets, dict):
        return {}
    counts: dict[int, int] = {}
    for raw_bucket in buckets.values():
        if not isinstance(raw_bucket, int):
            continue
        counts[raw_bucket] = counts.get(raw_bucket, 0) + 1
    return dict(sorted(counts.items()))


def _format_ttl_jitter_bucket_counts(bucket_counts: dict[int, int]) -> str:
    if not bucket_counts:
        return "none"
    return ", ".join(
        f"{bucket}h={count:,}" for bucket, count in sorted(bucket_counts.items())
    )


def format_price_cache_status(price_cache_policy, cache_age: float) -> str:
    status = getattr(price_cache_policy, "status", "empty")
    if status == "bypass":
        return _warn("--no-cache: ignorando caché existente")
    if status == "valid":
        status_msg = _format_price_refresh_details(
            price_cache_policy,
            action_label="por fetchear",
        )
        return f"{_ok(f'Caché válida ({cache_age:.1f}h)')} — {status_msg}"
    if status == "expired":
        status_msg = _format_price_refresh_details(
            price_cache_policy,
            action_label="por revalidar",
        )
        return f"{_warn(f'Caché expirada ({cache_age:.0f}h)')} — {status_msg}"
    return _dim("Sin caché — fetch completo")


def build_price_cache_completion_message(
    deals: list[dict], min_discount: int, n_fetched: int
) -> str:
    suffix = "caché actualizada" if n_fetched > 0 else "desde caché"
    return _ok(f"{len(deals):,} deals (≥{min_discount}%) — {suffix}")


def run_price_cache_stage(
    wishlist_appids: list[str],
    steam_id: str,
    *,
    no_cache: bool,
    min_discount: int,
    rate_limit: float,
    load_price_cache_fn=load_price_cache,
    select_cache_fn=select_scoped_cache,
    clear_cache_files_fn=clear_cache_files,
    get_deals_from_wishlist_fn=None,
    save_price_cache_fn=save_price_cache,
    emit_fn=print,
    current_time_fn=time.time,
    env=None,
) -> dict:
    if get_deals_from_wishlist_fn is None:
        get_deals_from_wishlist_fn = get_deals_from_wishlist

    fetched_cache, cache_age = load_price_cache_fn(steam_id)
    price_cache_policy = select_cache_fn(
        wishlist_appids,
        fetched_cache,
        cache_age,
        no_cache=no_cache,
        ttl_hours=CACHE_MAX_HOURS,
        current_time_fn=current_time_fn,
        entry_ttl_hours=ENTRY_REFRESH_TTL_HOURS,
        failure_retry_hours=PRICE_FAILURE_RETRY_HOURS,
        preserve_expired_payload=True,
        stale_grace_hours=PRICE_STALE_GRACE_HOURS,
        ttl_jitter_hours=PRICE_TTL_JITTER_HOURS,
        max_stale_refresh_per_run=PRICE_MAX_STALE_REFRESH_PER_RUN,
        min_discount=min_discount,
    )
    fetched_cache = price_cache_policy.cache

    if price_cache_policy.status == "bypass":
        clear_cache_files_fn(list(build_price_related_cache_files()))
    emit_fn(f"  {format_price_cache_status(price_cache_policy, cache_age)}")

    refresh_ids = tuple(getattr(price_cache_policy, "refresh_ids", ()) or ())
    missing_count = len(tuple(getattr(price_cache_policy, "missing_ids", ()) or ()))
    deferred_failure_count = len(
        tuple(getattr(price_cache_policy, "deferred_failure_ids", ()) or ())
    )
    stale_count = max(0, len(refresh_ids) - missing_count)
    stale_used_count = len(tuple(getattr(price_cache_policy, "stale_used_ids", ()) or ()))
    stale_refresh_deferred_count = len(
        tuple(getattr(price_cache_policy, "stale_refresh_deferred_ids", ()) or ())
    )
    ttl_jitter_bucket_counts = _count_ttl_jitter_buckets(price_cache_policy)
    if refresh_ids:
        emit_fn(
            f"  {_dim(f'Refresh candidates: {len(refresh_ids):,} ({missing_count} nuevos, {stale_count} stale)')}"
        )
    if stale_used_count or stale_refresh_deferred_count:
        stale_msg = (
            "Stale-while-revalidate: "
            f"stale_used={stale_used_count:,} · "
            f"stale_deferred={stale_refresh_deferred_count:,} · "
            "ttl_jitter_buckets="
            f"{_format_ttl_jitter_bucket_counts(ttl_jitter_bucket_counts)}"
        )
        emit_fn(f"  {_dim(stale_msg)}")

    price_tuning = resolve_price_fetch_tuning(env=env)
    resolved_max_refresh_candidates = price_tuning["max_refresh_candidates_per_run"]
    resolved_time_budget_seconds = price_tuning["refresh_time_budget_seconds"]
    max_refresh_candidates_per_run = None
    if not no_cache and isinstance(resolved_max_refresh_candidates, int):
        max_refresh_candidates_per_run = (
            resolved_max_refresh_candidates
            if resolved_max_refresh_candidates > 0
            else None
        )
    refresh_time_budget_seconds = None
    if not no_cache and isinstance(resolved_time_budget_seconds, (int, float)):
        refresh_time_budget_seconds = (
            float(resolved_time_budget_seconds)
            if float(resolved_time_budget_seconds) > 0
            else None
        )
    if price_tuning["is_custom"]:
        tuning_msg = (
            "Tuning precios activo: "
            f"batch_size={price_tuning['batch_size']} · "
            f"halving_limit={price_tuning['batch_halving_limit']} · "
            f"fallback_workers={price_tuning['individual_fallback_workers']}"
        )
        if (
            price_tuning.get("max_refresh_candidates_per_run")
            != PRICE_MAX_REFRESH_CANDIDATES_PER_RUN
            and max_refresh_candidates_per_run is not None
        ):
            tuning_msg = (
                f"{tuning_msg} · "
                f"max_refresh_candidates={max_refresh_candidates_per_run}"
            )
        if (
            price_tuning.get("refresh_time_budget_seconds")
            != PRICE_REFRESH_TIME_BUDGET_SECONDS
            and refresh_time_budget_seconds is not None
        ):
            tuning_msg = (
                f"{tuning_msg} · "
                f"time_budget_seconds={refresh_time_budget_seconds:g}"
            )
        emit_fn(
            f"  {_dim(tuning_msg)}"
        )

    price_fetch_stats = {
        "refresh_candidate_count": len(refresh_ids),
        "missing_count": missing_count,
        "stale_count": stale_count,
        "deferred_failure_count": deferred_failure_count,
        "stale_used_count": stale_used_count,
        "stale_refresh_deferred_count": stale_refresh_deferred_count,
        "ttl_jitter_bucket_counts": ttl_jitter_bucket_counts,
        "degraded_batch_count": 0,
        "individual_fallback_count": 0,
        "individual_fallback_batches": 0,
        "individual_fallback_resolved_count": 0,
        "individual_fallback_failed_count": 0,
        "individual_attempts": 0,
        "individual_no_data": 0,
        "deferred_by_fallback_budget": 0,
        "fallback_budget_reason": "",
        "old_cache_used_count": 0,
        "processed_count": 0,
        "deferred_by_time_budget": 0,
        "time_budget_exhausted": False,
        "next_resume_hint": "",
        "http_400_direct_fallback_count": 0,
        "http_400_direct_fallback_batches": 0,
        "individual_fallback_worker_count": int(
            price_tuning["individual_fallback_workers"]
        ),
        "individual_fallback_worker_downgrade_count": 0,
        "individual_fallback_failure_reasons": {},
        "null_batch_count": 0,
    }

    try:
        deals, n_fetched = get_deals_from_wishlist_fn(
            wishlist_appids,
            fetched_cache,
            steam_id,
            country="mx",
            min_discount=min_discount,
            rate_limit=rate_limit,
            emit_fn=emit_fn,
            refresh_ids=refresh_ids,
            current_time_fn=current_time_fn,
            batch_size=int(price_tuning["batch_size"]),
            max_batch_halving=int(price_tuning["batch_halving_limit"]),
            individual_fallback_workers=int(price_tuning["individual_fallback_workers"]),
            max_refresh_candidates_per_run=max_refresh_candidates_per_run,
            refresh_time_budget_seconds=refresh_time_budget_seconds,
            stats_out=price_fetch_stats,
        )
    except KeyboardInterrupt as exc:
        emit_fn(f"\n  {_warn('Interrumpido — guardando caché parcial...')}")
        save_price_cache_fn(steam_id, fetched_cache)
        emit_fn(
            f"  {_ok('Caché guardada. Ejecuta de nuevo para continuar donde quedó.')}"
        )
        raise SystemExit(1) from exc

    if n_fetched > 0:
        save_price_cache_fn(steam_id, fetched_cache)
    if not price_fetch_stats["individual_attempts"]:
        price_fetch_stats["individual_attempts"] = price_fetch_stats[
            "individual_fallback_count"
        ]
    if not price_fetch_stats["individual_no_data"]:
        failure_reasons = price_fetch_stats.get("individual_fallback_failure_reasons")
        if isinstance(failure_reasons, dict):
            price_fetch_stats["individual_no_data"] = int(
                failure_reasons.get("no_price_data", 0) or 0
            )
    if price_fetch_stats["degraded_batch_count"]:
        degraded_msg = (
            f"Batches degradados por HTTP 400: {price_fetch_stats['degraded_batch_count']}"
        )
        emit_fn(
            f"  {_dim(degraded_msg)}"
        )
    if price_fetch_stats["individual_fallback_count"]:
        fallback_msg = (
            "Fallback individual aplicado a "
            f"{price_fetch_stats['individual_fallback_count']:,} juegos en "
            f"{price_fetch_stats['individual_fallback_batches']} tandas "
            f"({price_fetch_stats['individual_fallback_resolved_count']:,} resueltos, "
            f"{price_fetch_stats['individual_fallback_failed_count']:,} sin oferta/datos)"
        )
        emit_fn(
            f"  {_dim(fallback_msg)}"
        )
    if price_fetch_stats["http_400_direct_fallback_count"]:
        direct_fallback_msg = (
            "Fallback individual directo por HTTP 400 repetido: "
            f"{price_fetch_stats['http_400_direct_fallback_count']:,} juegos en "
            f"{price_fetch_stats['http_400_direct_fallback_batches']} tandas"
        )
        emit_fn(
            f"  {_dim(direct_fallback_msg)}"
        )
    if price_fetch_stats["individual_fallback_worker_downgrade_count"]:
        downgrade_msg = (
            "Fallback individual adaptativo: "
            f"{price_fetch_stats['individual_fallback_worker_downgrade_count']} bajadas de workers"
        )
        emit_fn(f"  {_dim(downgrade_msg)}")
    failure_reasons = price_fetch_stats.get("individual_fallback_failure_reasons")
    if isinstance(failure_reasons, dict) and failure_reasons:
        reason_parts = [
            f"{reason}={count:,}"
            for reason, count in sorted(failure_reasons.items())
        ]
        emit_fn(
            f"  {_dim('Fallback individual fallos por razón: ' + ', '.join(reason_parts))}"
        )
    if (
        price_fetch_stats["individual_attempts"]
        or price_fetch_stats["deferred_by_fallback_budget"]
        or price_fetch_stats["old_cache_used_count"]
    ):
        budget_msg = (
            "Fallback budget adaptativo: "
            f"attempts={price_fetch_stats['individual_attempts']:,} · "
            f"no_data={price_fetch_stats['individual_no_data']:,} · "
            f"deferred={price_fetch_stats['deferred_by_fallback_budget']:,} · "
            f"old_cache_used={price_fetch_stats['old_cache_used_count']:,}"
        )
        fallback_budget_reason = str(
            price_fetch_stats.get("fallback_budget_reason") or "none"
        )
        budget_msg = f"{budget_msg} · reason={fallback_budget_reason}"
        emit_fn(f"  {_dim(budget_msg)}")
    if (
        price_fetch_stats["processed_count"]
        or price_fetch_stats["deferred_by_time_budget"]
        or price_fetch_stats["time_budget_exhausted"]
    ):
        resume_hint = str(price_fetch_stats.get("next_resume_hint") or "none")
        time_budget_msg = (
            "Refresh budget resumible: "
            f"processed={price_fetch_stats['processed_count']:,} · "
            f"deferred={price_fetch_stats['deferred_by_time_budget']:,} · "
            f"exhausted={str(bool(price_fetch_stats['time_budget_exhausted'])).lower()} · "
            f"next_resume_hint={resume_hint}"
        )
        emit_fn(f"  {_dim(time_budget_msg)}")
    emit_fn(f"  {build_price_cache_completion_message(deals, min_discount, n_fetched)}")
    return {
        "deals": deals,
        "n_fetched": n_fetched,
        "cache_age": cache_age,
        "cache_status": price_cache_policy.status,
        "cache_path": CACHE_FILE,
        "refresh_candidate_count": price_fetch_stats["refresh_candidate_count"],
        "missing_count": price_fetch_stats["missing_count"],
        "stale_count": price_fetch_stats["stale_count"],
        "deferred_failure_count": price_fetch_stats["deferred_failure_count"],
        "stale_used_count": price_fetch_stats["stale_used_count"],
        "stale_refresh_deferred_count": price_fetch_stats[
            "stale_refresh_deferred_count"
        ],
        "ttl_jitter_bucket_counts": price_fetch_stats["ttl_jitter_bucket_counts"],
        "degraded_batch_count": price_fetch_stats["degraded_batch_count"],
        "individual_fallback_count": price_fetch_stats["individual_fallback_count"],
        "individual_fallback_batches": price_fetch_stats["individual_fallback_batches"],
        "individual_fallback_resolved_count": price_fetch_stats["individual_fallback_resolved_count"],
        "individual_fallback_failed_count": price_fetch_stats["individual_fallback_failed_count"],
        "individual_attempts": price_fetch_stats["individual_attempts"],
        "individual_no_data": price_fetch_stats["individual_no_data"],
        "deferred_by_fallback_budget": price_fetch_stats[
            "deferred_by_fallback_budget"
        ],
        "fallback_budget_reason": price_fetch_stats["fallback_budget_reason"],
        "old_cache_used_count": price_fetch_stats["old_cache_used_count"],
        "processed_count": price_fetch_stats["processed_count"],
        "deferred_by_time_budget": price_fetch_stats["deferred_by_time_budget"],
        "time_budget_exhausted": price_fetch_stats["time_budget_exhausted"],
        "next_resume_hint": price_fetch_stats["next_resume_hint"],
        "http_400_direct_fallback_count": price_fetch_stats["http_400_direct_fallback_count"],
        "http_400_direct_fallback_batches": price_fetch_stats["http_400_direct_fallback_batches"],
        "individual_fallback_worker_count": price_fetch_stats["individual_fallback_worker_count"],
        "individual_fallback_worker_downgrade_count": price_fetch_stats[
            "individual_fallback_worker_downgrade_count"
        ],
        "individual_fallback_failure_reasons": price_fetch_stats[
            "individual_fallback_failure_reasons"
        ],
        "null_batch_count": price_fetch_stats["null_batch_count"],
        "batch_size": int(price_tuning["batch_size"]),
        "batch_halving_limit": int(price_tuning["batch_halving_limit"]),
        "individual_fallback_workers": int(price_tuning["individual_fallback_workers"]),
        "max_refresh_candidates_per_run": max_refresh_candidates_per_run,
        "refresh_time_budget_seconds": refresh_time_budget_seconds,
    }


def run_warm_cache_mode(
    wishlist_appids: list[str],
    steam_id: str,
    *,
    no_cache: bool,
    min_discount: int,
    rate_limit: float,
    started_at: float,
    step_fn,
    emit_fn=print,
    run_price_cache_stage_fn=run_price_cache_stage,
) -> dict:
    step_fn("Precalentando caché de precios...")
    cache_result = run_price_cache_stage_fn(
        wishlist_appids,
        steam_id,
        no_cache=no_cache,
        min_discount=min_discount,
        rate_limit=rate_limit,
        emit_fn=emit_fn,
    )
    elapsed = time.monotonic() - started_at
    emit_fn(f"\n  {_ok(f'Warm cache listo en {elapsed:.1f}s')}")
    emit_fn(
        f"  {_dim(f'Wishlist: {len(wishlist_appids):,} juegos · Deals actuales: {len(cache_result['deals']):,}')}"
    )
    emit_fn(f"  {_dim(f'Caché objetivo: {cache_result['cache_path']}')}")
    return cache_result


# ─────────────────────────────────────────────
# FETCH DE PRECIOS (batched con fallback)
# ─────────────────────────────────────────────

BATCH_SIZE = 20
PRICE_INDIVIDUAL_FALLBACK_WORKERS = 1
PRICE_INDIVIDUAL_FALLBACK_WORKERS_MAX = 4
ENTRY_REFRESH_TTL_HOURS = 24
PRICE_FAILURE_RETRY_HOURS = 2
PRICE_TTL_JITTER_HOURS = 6
PRICE_STALE_GRACE_HOURS = 72
PRICE_MAX_STALE_REFRESH_PER_RUN = 200
PRICE_MAX_REFRESH_CANDIDATES_PER_RUN = 400
PRICE_REFRESH_TIME_BUDGET_SECONDS = 600.0


def _fetch_single(appid: str, country: str, delay: float) -> dict | None:
    """Fallback: fetch individual de un appid."""
    if _prices_module is None:
        raise RuntimeError("Prices module is not available")
    return _prices_module.fetch_single(
        appid, country, delay, get_json=_get_json, sleep_fn=time.sleep
    )


def _parse_release_year(date_str: str) -> int | None:
    """Extrae el año de una fecha de Steam (ej. 'Mar 25, 2019' → 2019)."""
    if _prices_module is None:
        raise RuntimeError("Prices module is not available")
    return _prices_module.parse_release_year(date_str)


def _process_app_entry(appid: str, data: dict) -> dict | None:
    """Extrae info de precio de la respuesta de appdetails para un appid."""
    if _prices_module is None:
        raise RuntimeError("Prices module is not available")
    return _prices_module.process_app_entry(
        appid, data, parse_release_year_fn=_parse_release_year
    )


def get_deals_from_wishlist(
    appids: list[str],
    fetched_cache: dict,
    steam_id: str,
    country: str = "mx",
    min_discount: int = 50,
    rate_limit: float = 1.5,
    *,
    emit_fn=print,
    refresh_ids=None,
    current_time_fn=time.time,
    batch_size: int = BATCH_SIZE,
    max_batch_halving: int = PRICE_BATCH_HALVING_LIMIT,
    individual_fallback_workers: int = PRICE_INDIVIDUAL_FALLBACK_WORKERS,
    stats_out: dict | None = None,
    max_refresh_candidates_per_run: int | None = None,
    refresh_time_budget_seconds: float | None = None,
) -> tuple[list[dict], int]:
    if _prices_module is None:
        raise RuntimeError("Prices module is not available")
    return _prices_module.get_deals_from_wishlist(
        appids,
        fetched_cache,
        steam_id,
        country=country,
        min_discount=min_discount,
        rate_limit=rate_limit,
        get_json=_get_json,
        sleep_fn=time.sleep,
        monotonic_fn=time.monotonic,
        save_price_cache_fn=save_price_cache,
        fetch_single_fn=_fetch_single,
        process_app_entry_fn=_process_app_entry,
        emit=emit_fn,
        warn=_warn,
        dim=_dim,
        bar_fill=BAR_FILL,
        bar_empty=BAR_EMPTY,
        color_green=C.GRN,
        color_dim=C.DIM,
        color_reset=C.RST,
        batch_size=batch_size,
        entry_ttl_hours=ENTRY_REFRESH_TTL_HOURS,
        current_time_fn=current_time_fn,
        refresh_ids=refresh_ids,
        max_batch_halving=max_batch_halving,
        individual_fallback_workers=individual_fallback_workers,
        failure_retry_hours=PRICE_FAILURE_RETRY_HOURS,
        max_refresh_candidates_per_run=max_refresh_candidates_per_run,
        refresh_time_budget_seconds=refresh_time_budget_seconds,
        stats_out=stats_out,
    )


# ─────────────────────────────────────────────
# PARSEAR HLTB CSV
# ─────────────────────────────────────────────


def parse_hltb(csv_path: Path) -> dict[str, list[dict]]:
    if _parse_hltb_impl is None:
        raise RuntimeError("HLTB module is not available")
    return _parse_hltb_impl(csv_path)


# ─────────────────────────────────────────────
# FUZZY MATCHING HLTB × DEALS
# ─────────────────────────────────────────────


def normalize(s: str) -> str:
    if _normalize_impl is None:
        raise RuntimeError("HLTB module is not available")
    return _normalize_impl(s)


def extract_numbers(s: str) -> set[str]:
    if _extract_numbers_impl is None:
        raise RuntimeError("HLTB module is not available")
    return _extract_numbers_impl(s)


def significant_words(s: str) -> set[str]:
    if _significant_words_impl is None:
        raise RuntimeError("HLTB module is not available")
    return _significant_words_impl(s)


def is_same_game(a: str, b: str) -> bool:
    if _is_same_game_impl is None:
        raise RuntimeError("HLTB module is not available")
    return _is_same_game_impl(a, b)


def find_best_match(hltb_title: str, deals: list[dict], threshold: float = 0.75):
    if _find_best_match_impl is None:
        raise RuntimeError("HLTB module is not available")
    return _find_best_match_impl(hltb_title, deals, threshold=threshold)


def cross_hltb_with_deals(
    hltb: dict[str, list[dict]],
    deals: list[dict],
    threshold: float = 0.75,
    family_appids: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    if _cross_hltb_with_deals_impl is None:
        raise RuntimeError("HLTB module is not available")
    return _cross_hltb_with_deals_impl(
        hltb,
        deals,
        threshold=threshold,
        family_appids=family_appids,
    )


# ─────────────────────────────────────────────
# FILTRO POR GÉNERO
# ─────────────────────────────────────────────


def filter_by_genres(deals: list[dict], genres: list[str]) -> list[dict]:
    if _filter_by_genres_impl is None:
        raise RuntimeError("Filters module is not available")
    return _filter_by_genres_impl(deals, genres)


def apply_filters(
    deals: list[dict],
    filters: dict,
    reviews: dict[str, dict],
    deck_compat: dict[str, int],
    hltb_hours: dict[str, float],
    previous_appids: set[str],
    comparison: dict | None = None,
) -> list[dict]:
    """Aplica filtros CLI avanzados sobre la lista de deals."""
    if _apply_filters_impl is None:
        raise RuntimeError("Filters module is not available")
    return _apply_filters_impl(
        deals,
        filters,
        reviews,
        deck_compat,
        hltb_hours,
        previous_appids,
        comparison=comparison,
    )


# ─────────────────────────────────────────────
# FETCH PARALELO (ThreadPoolExecutor)
# ─────────────────────────────────────────────

MAX_WORKERS = 16
RATE_LIMIT_INTERVAL = 0.15


def _resolve_max_workers(raw_value, default_value: int) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default_value
    return value if value >= 1 else default_value


def _resolve_alert_rise_pct(raw_value) -> float:
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    return value if value > 0 else 0.0


def _resolve_alert_global_margin_pct(raw_value) -> float:
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    return value if value >= 0 else 0.0


def _resolve_alert_score_min(raw_value) -> float:
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    return value if value >= 0 else 0.0


def _enrichment_bar(completed: int, total: int, width: int = 25) -> str:
    filled = int((completed / total) * width) if total > 0 else 0
    return f"{C.GRN}{BAR_FILL * filled}{C.DIM}{BAR_EMPTY * (width - filled)}{C.RST}"


def _fetch_parallel(
    items: list[str],
    fetch_fn,
    label: str,
    rate_limit: float = RATE_LIMIT_INTERVAL,
    max_workers: int = MAX_WORKERS,
) -> dict:
    """Execute fetch_fn(appid) in parallel with global rate limiting."""
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_parallel(
        items,
        fetch_fn,
        label,
        rate_limit=rate_limit,
        max_workers=max_workers,
        monotonic_fn=time.monotonic,
        sleep_fn=time.sleep,
        emit_progress=print,
        build_bar=_enrichment_bar,
    )


def _fetch_single_review(appid: str) -> dict | None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_single_review(appid, get_json=_get_json)


def _fetch_single_deck(appid: str) -> int | None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_single_deck(appid, get_json=_get_json)


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: REVIEWS DE STEAM
# ─────────────────────────────────────────────


def load_reviews_cache(steam_id: str) -> tuple[dict, float]:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.load_reviews_cache(REVIEWS_CACHE_FILE, steam_id)


def save_reviews_cache(steam_id: str, reviews: dict) -> None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    _enrichment_module.save_reviews_cache(REVIEWS_CACHE_FILE, steam_id, reviews)


def fetch_reviews(
    appids: list[str], cached: dict, rate_limit: float = 0.15
) -> dict[str, dict]:
    """Fetch Steam reviews in parallel. Returns merged {appid: {desc, pct, total}}."""
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_reviews(
        appids,
        cached,
        rate_limit=rate_limit,
        fetch_parallel_fn=_fetch_parallel,
        get_json=_get_json,
    )


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: COMPATIBILIDAD STEAM DECK
# ─────────────────────────────────────────────


def deck_badge(category: int) -> str:
    if _deck_badge_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _deck_badge_impl(category)


def load_deck_cache(steam_id: str) -> tuple[dict, float]:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.load_deck_cache(DECK_CACHE_FILE, steam_id)


def save_deck_cache(steam_id: str, deck: dict) -> None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    _enrichment_module.save_deck_cache(DECK_CACHE_FILE, steam_id, deck)


def fetch_deck_compat(
    appids: list[str], cached: dict, rate_limit: float = 0.15
) -> dict[str, int]:
    """Fetch Steam Deck compatibility in parallel. Returns merged {appid: category}."""
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_deck_compat(
        appids,
        cached,
        rate_limit=rate_limit,
        fetch_parallel_fn=_fetch_parallel,
        get_json=_get_json,
    )


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: PROTONDB
# ─────────────────────────────────────────────


def protondb_badge(tier: str) -> str:
    if _protondb_badge_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _protondb_badge_impl(tier)


def load_protondb_cache() -> tuple[dict, float]:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.load_protondb_cache(PROTONDB_CACHE_FILE)


def save_protondb_cache(protondb: dict) -> None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    _enrichment_module.save_protondb_cache(PROTONDB_CACHE_FILE, protondb)


def _fetch_single_protondb(appid: str) -> dict | None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_single_protondb(appid, get_json=_get_json)


def fetch_protondb(
    appids: list[str], cached: dict, rate_limit: float = 0.15
) -> dict[str, dict]:
    """Fetch ProtonDB tiers in parallel. Returns merged {appid: {tier, score, total}}."""
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_protondb(
        appids,
        cached,
        rate_limit=rate_limit,
        fetch_parallel_fn=_fetch_parallel,
        get_json=_get_json,
    )


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: ARE WE ANTI-CHEAT YET
# ─────────────────────────────────────────────


def load_anticheat_cache() -> tuple[dict, float]:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.load_anticheat_cache(ANTICHEAT_CACHE_FILE)


def save_anticheat_cache(games: dict) -> None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    _enrichment_module.save_anticheat_cache(ANTICHEAT_CACHE_FILE, games)


def fetch_anticheat_db() -> dict[str, dict]:
    """Download Are We Anti-Cheat Yet database. Returns {appid: {status, anticheats, native}}."""
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_anticheat_db(
        get_json=_get_json,
        on_error=lambda message: print(f"\n  {_warn(message)}", flush=True),
    )


def linux_badge(
    deck_cat: int,
    protondb: dict | None,
    anticheat: dict | None,
    linux_native: bool = False,
) -> str:
    """Build combined Deck/Linux badge string."""
    if _linux_badge_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _linux_badge_impl(
        deck_cat,
        protondb,
        anticheat,
        linux_native=linux_native,
        deck_badge_fn=deck_badge,
        protondb_badge_fn=protondb_badge,
    )


# ─────────────────────────────────────────────
# CACHÉ Y FETCH: STEAM TAGS (STEAMSPY)
# ─────────────────────────────────────────────


def load_tags_cache() -> tuple[dict, float]:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.load_tags_cache(TAGS_CACHE_FILE)


def save_tags_cache(tags: dict) -> None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    _enrichment_module.save_tags_cache(TAGS_CACHE_FILE, tags)


def fetch_tags(
    appids: list[str], cached: dict, rate_limit: float = 1.1
) -> dict[str, dict]:
    """Fetch tags from SteamSpy for appids not in cache."""
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_tags(
        appids,
        cached,
        rate_limit=rate_limit,
        get_json=_get_json,
        sleep_fn=time.sleep,
        monotonic_fn=time.monotonic,
        emit_progress=print,
        build_bar=_enrichment_bar,
    )


def get_top_tags(tags_data: dict, appid: str, n: int = 3) -> list[str]:
    """Get top N non-generic tags for an appid."""
    if _get_top_tags_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _get_top_tags_impl(tags_data, appid, n=n)


def group_deals_by_tag(
    deals: list[dict], tags_data: dict, min_count: int = 3
) -> list[tuple[str, list[dict]]]:
    """Group deals by their most popular tags."""
    if _group_deals_by_tag_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _group_deals_by_tag_impl(
        deals, tags_data, min_count=min_count, get_top_tags_fn=get_top_tags
    )


def players_badge(tags_entry: dict) -> str:
    """Generate compact player badge from tags_data entry."""
    if _players_badge_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _players_badge_impl(tags_entry)


# ─────────────────────────────────────────────
# ACHIEVEMENTS (GLOBAL COMPLETION DATA)
# ─────────────────────────────────────────────


def load_achievements_cache(steam_id: str) -> tuple[dict, float]:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.load_achievements_cache(ACHIEVEMENTS_CACHE_FILE, steam_id)


def save_achievements_cache(steam_id: str, achievements: dict) -> None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    _enrichment_module.save_achievements_cache(
        ACHIEVEMENTS_CACHE_FILE, steam_id, achievements
    )


def _fetch_single_achievement(appid: str) -> dict | None:
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_single_achievement(appid, get_json=_get_json)


def fetch_achievements(
    appids: list[str], cached: dict, rate_limit: float = 0.15
) -> dict[str, dict]:
    """Fetch achievement data in parallel. Returns merged {appid: {count, avg_completion}}."""
    if _enrichment_module is None:
        raise RuntimeError("Enrichment module is not available")
    return _enrichment_module.fetch_achievements(
        appids,
        cached,
        rate_limit=rate_limit,
        fetch_parallel_fn=_fetch_parallel,
        get_json=_get_json,
    )


def achievements_badge(ach: dict | None) -> str:
    """MD badge for achievements."""
    if _achievements_badge_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _achievements_badge_impl(ach)



# ─────────────────────────────────────────────
# TOP PICKS (BEST VALUE SCORE)
# ─────────────────────────────────────────────


def compute_value_score(
    discount: int,
    review_pct: int | None,
    priority: int,
    price_per_hour: float | None,
    deck_cat: int,
    release_year: int | None = None,
    metacritic_score: int | None = None,
) -> float:
    """Compute a 0-100 value score combining multiple signals."""
    if _compute_value_score_impl is None:
        raise RuntimeError("Recommendations module is not available")
    return _compute_value_score_impl(
        discount,
        review_pct,
        priority,
        price_per_hour,
        deck_cat,
        release_year=release_year,
        metacritic_score=metacritic_score,
    )


def rank_top_picks(
    deals: list[dict],
    priorities: dict[str, int],
    reviews: dict[str, dict],
    hltb_hours: dict[str, float],
    deck_compat: dict[str, int],
    n: int = 10,
    active_promo_context: dict | None = None,
) -> list[dict]:
    """Rank deals by composite value score, return top N."""
    if _rank_top_picks_impl is None:
        raise RuntimeError("Recommendations module is not available")
    return _rank_top_picks_impl(
        deals,
        priorities,
        reviews,
        hltb_hours,
        deck_compat,
        n=n,
        active_promo_context=active_promo_context,
    )


def compute_budget_picks(deals, budget_mxn, top_picks, watchlist_alerts=None):
    """Greedy budget optimizer: pick best deals that fit within budget."""
    if _compute_budget_picks_impl is None:
        raise RuntimeError("Recommendations module is not available")
    return _compute_budget_picks_impl(
        deals, budget_mxn, top_picks, watchlist_alerts=watchlist_alerts
    )


def build_recommended_collections(
    deals: list[dict],
    top_picks: list[dict] | None = None,
    *,
    max_items_per_collection: int = 4,
) -> list[dict]:
    """Build deterministic recommendation collections from existing report data."""
    if _build_recommended_collections_impl is None:
        raise RuntimeError("Recommendations module is not available")
    return _build_recommended_collections_impl(
        deals,
        top_picks=top_picks,
        max_items_per_collection=max_items_per_collection,
    )


# ─────────────────────────────────────────────
# GENERAR MARKDOWN
# ─────────────────────────────────────────────

STORE_URL = "https://store.steampowered.com/app/{appid}/"
CAPSULE_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_231x87.jpg"
HEADER_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"

MESES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def group_by_tier(games: list[dict]) -> list[tuple[str, list[dict]]]:
    if _group_by_tier_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _group_by_tier_impl(games)


def generate_md(
    deals: list[dict],
    backlog_on_sale: list[dict],
    have_on_sale: list[dict],
    vanity: str,
    owned: dict[str, str],
    wishlist_appids: list[str],
    min_discount: int,
    genres: list[str],
    hltb_used: bool = False,
    family_appids: set[str] | None = None,
    sale_name: str = "",
    priorities: dict[str, int] | None = None,
    historical_lows: dict[str, dict] | None = None,
    previous_appids: set[str] | None = None,
    reviews: dict[str, dict] | None = None,
    deck_compat: dict[str, int] | None = None,
    current_prices: dict[str, dict] | None = None,
    top_picks: list[dict] | None = None,
    comparison: dict | None = None,
    sort_field: str = "discount",
    tags_data: dict[str, dict] | None = None,
    local_trends: dict[str, dict] | None = None,
    active_bundles: dict[str, list[dict]] | None = None,
    protondb_data: dict[str, dict] | None = None,
    anticheat_data: dict[str, dict] | None = None,
    achievements_data: dict[str, dict] | None = None,
    watchlist_alerts: list[dict] | None = None,
    budget_result: dict | None = None,
    compare_data: dict | None = None,
    gift_ideas: list[dict] | None = None,
    recommended_collections: list[dict] | None = None,
    include_frontmatter: bool = False,
    active_promo_context: dict | None = None,
) -> str:
    if _generate_md_renderer is None:
        raise RuntimeError("Markdown renderer module is not available")
    if recommended_collections is None:
        recommended_collections = build_recommended_collections(deals, top_picks=top_picks)
    return _generate_md_renderer(
        deals,
        backlog_on_sale,
        have_on_sale,
        vanity,
        owned,
        wishlist_appids,
        min_discount,
        genres,
        hltb_used=hltb_used,
        family_appids=family_appids,
        sale_name=sale_name,
        priorities=priorities,
        historical_lows=historical_lows,
        previous_appids=previous_appids,
        reviews=reviews,
        deck_compat=deck_compat,
        current_prices=current_prices,
        top_picks=top_picks,
        comparison=comparison,
        sort_field=sort_field,
        tags_data=tags_data,
        local_trends=local_trends,
        active_bundles=active_bundles,
        protondb_data=protondb_data,
        anticheat_data=anticheat_data,
        achievements_data=achievements_data,
        watchlist_alerts=watchlist_alerts,
        budget_result=budget_result,
        compare_data=compare_data,
        gift_ideas=gift_ideas,
        recommended_collections=recommended_collections,
        include_frontmatter=include_frontmatter,
        active_promo_context=active_promo_context,
        group_by_tier=group_by_tier,
        filter_by_genres=filter_by_genres,
        group_deals_by_tag=group_deals_by_tag,
        linux_badge=linux_badge,
        multiplayer_badges=multiplayer_badges,
        get_top_tags=get_top_tags,
        players_badge=players_badge,
        format_trend=format_trend,
        achievements_badge=achievements_badge,
        compute_value_score=compute_value_score,
    )


# ─────────────────────────────────────────────
# GENERAR HTML INTERACTIVO
# ─────────────────────────────────────────────


def multiplayer_badges(categories: list[int]) -> str:
    """Emoji badges for multiplayer/co-op categories (for MD)."""
    if _multiplayer_badges_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _multiplayer_badges_impl(categories)


def generate_html(
    deals: list[dict],
    backlog_on_sale: list[dict],
    have_on_sale: list[dict],
    vanity: str,
    owned: dict[str, str],
    wishlist_appids: list[str],
    min_discount: int,
    genres: list[str],
    hltb_used: bool = False,
    family_appids: set[str] | None = None,
    sale_name: str = "",
    priorities: dict[str, int] | None = None,
    historical_lows: dict[str, dict] | None = None,
    previous_appids: set[str] | None = None,
    reviews: dict[str, dict] | None = None,
    deck_compat: dict[str, int] | None = None,
    current_prices: dict[str, dict] | None = None,
    top_picks: list[dict] | None = None,
    tags_data: dict[str, dict] | None = None,
    protondb_data: dict[str, dict] | None = None,
    achievements_data: dict[str, dict] | None = None,
    watchlist_alerts: list[dict] | None = None,
    budget_result: dict | None = None,
    compare_data: dict | None = None,
    gift_ideas: list[dict] | None = None,
    local_trends: dict[str, dict] | None = None,
    price_history: dict | None = None,
    profile_display_name: str | None = None,
    active_promo_context: dict | None = None,
    recommended_collections: list[dict] | None = None,
) -> str:
    if recommended_collections is None:
        recommended_collections = build_recommended_collections(deals, top_picks=top_picks)
    if _generate_html_renderer is not None:
        return _generate_html_renderer(
            deals,
            backlog_on_sale,
            have_on_sale,
            vanity,
            owned,
            wishlist_appids,
            min_discount,
            genres,
            hltb_used=hltb_used,
            family_appids=family_appids,
            sale_name=sale_name,
            priorities=priorities,
            historical_lows=historical_lows,
            previous_appids=previous_appids,
            reviews=reviews,
            deck_compat=deck_compat,
            current_prices=current_prices,
            top_picks=top_picks,
            tags_data=tags_data,
            protondb_data=protondb_data,
            achievements_data=achievements_data,
            watchlist_alerts=watchlist_alerts,
            budget_result=budget_result,
            compare_data=compare_data,
            gift_ideas=gift_ideas,
            recommended_collections=recommended_collections,
            local_trends=local_trends,
            price_history=price_history,
            profile_display_name=profile_display_name,
            active_promo_context=active_promo_context,
            group_by_tier=group_by_tier,
            group_deals_by_tag=group_deals_by_tag,
        )
    if _generate_html_fallback_renderer is None:
        raise RuntimeError("HTML fallback renderer module is not available")
    return _generate_html_fallback_renderer(
        deals,
        backlog_on_sale,
        have_on_sale,
        vanity,
        owned,
        wishlist_appids,
        min_discount,
        genres,
        hltb_used=hltb_used,
        family_appids=family_appids,
        sale_name=sale_name,
        priorities=priorities,
        historical_lows=historical_lows,
        previous_appids=previous_appids,
        reviews=reviews,
        deck_compat=deck_compat,
        current_prices=current_prices,
        top_picks=top_picks,
        tags_data=tags_data,
        protondb_data=protondb_data,
        achievements_data=achievements_data,
        watchlist_alerts=watchlist_alerts,
        budget_result=budget_result,
        compare_data=compare_data,
        gift_ideas=gift_ideas,
        recommended_collections=recommended_collections,
        local_trends=local_trends,
        price_history=price_history,
        profile_display_name=profile_display_name,
        active_promo_context=active_promo_context,
        group_by_tier=group_by_tier,
        group_deals_by_tag=group_deals_by_tag,
    )


def generate_share_html(
    deals,
    vanity,
    min_discount,
    sale_name="",
    top_picks=None,
    reviews=None,
    deck_compat=None,
    historical_lows=None,
    profile_display_name: str | None = None,
):
    """Generate a lightweight shareable HTML page with the deals list."""
    if _generate_share_html_renderer is not None:
        return _generate_share_html_renderer(
            deals,
            vanity,
            min_discount,
            sale_name=sale_name,
            top_picks=top_picks,
            reviews=reviews,
            deck_compat=deck_compat,
            historical_lows=historical_lows,
            profile_display_name=profile_display_name,
        )
    if _generate_share_html_fallback_renderer is None:
        raise RuntimeError("Share HTML fallback renderer module is not available")
    return _generate_share_html_fallback_renderer(
        deals,
        vanity,
        min_discount,
        sale_name=sale_name,
        top_picks=top_picks,
        reviews=reviews,
        deck_compat=deck_compat,
        historical_lows=historical_lows,
        profile_display_name=profile_display_name,
    )


# ─────────────────────────────────────────────
# GENERAR CSV
# ─────────────────────────────────────────────

CSV_DECK = {3: "Verified", 2: "Playable", 1: "Unsupported", 0: ""}
CSV_PROTON = {
    "native": "Native",
    "platinum": "Platinum",
    "gold": "Gold",
    "silver": "Silver",
    "bronze": "Bronze",
    "borked": "Borked",
}


def _csv_trend(trend: dict) -> str:
    if trend.get("is_first_time"):
        return "1ra vez"
    if trend.get("is_best_local") and trend.get("times_on_sale", 0) > 1:
        return "Min. local"
    if trend.get("is_first_at_price"):
        return "1ra vez a este precio"
    return f"{trend.get('times_on_sale', 0)}x, prom {trend.get('avg_fmt', '?')}"


def generate_csv(
    deals,
    priorities=None,
    reviews=None,
    deck_compat=None,
    protondb_data=None,
    anticheat_data=None,
    tags_data=None,
    hltb_hours=None,
    historical_lows=None,
    current_prices=None,
    top_picks=None,
    local_trends=None,
    achievements_data=None,
) -> str:
    if _generate_csv_renderer is None:
        raise RuntimeError("CSV renderer module is not available")
    return _generate_csv_renderer(
        deals,
        priorities=priorities,
        reviews=reviews,
        deck_compat=deck_compat,
        protondb_data=protondb_data,
        anticheat_data=anticheat_data,
        tags_data=tags_data,
        hltb_hours=hltb_hours,
        historical_lows=historical_lows,
        current_prices=current_prices,
        top_picks=top_picks,
        local_trends=local_trends,
        achievements_data=achievements_data,
        get_top_tags=get_top_tags,
        multiplayer_badges=multiplayer_badges,
    )


def generate_json(
    deals,
    backlog_on_sale,
    have_on_sale,
    vanity,
    owned,
    wishlist_appids,
    min_discount,
    genres,
    hltb_used=False,
    family_appids=None,
    sale_name="",
    priorities=None,
    historical_lows=None,
    previous_appids=None,
    reviews=None,
    deck_compat=None,
    current_prices=None,
    top_picks=None,
    comparison=None,
    sort_field="discount",
    tags_data=None,
    local_trends=None,
    active_bundles=None,
    protondb_data=None,
    anticheat_data=None,
    achievements_data=None,
    watchlist_alerts=None,
    budget_result=None,
    compare_data=None,
    gift_ideas=None,
    recommended_collections=None,
    profile_display_name: str | None = None,
    active_promo_context: dict | None = None,
) -> str:
    if _generate_json_renderer is None:
        raise RuntimeError("JSON renderer module is not available")
    if recommended_collections is None:
        recommended_collections = build_recommended_collections(deals, top_picks=top_picks)
    return _generate_json_renderer(
        deals,
        backlog_on_sale,
        have_on_sale,
        vanity,
        owned,
        wishlist_appids,
        min_discount,
        genres,
        hltb_used=hltb_used,
        family_appids=family_appids,
        sale_name=sale_name,
        priorities=priorities,
        historical_lows=historical_lows,
        previous_appids=previous_appids,
        reviews=reviews,
        deck_compat=deck_compat,
        current_prices=current_prices,
        top_picks=top_picks,
        comparison=comparison,
        sort_field=sort_field,
        tags_data=tags_data,
        local_trends=local_trends,
        active_bundles=active_bundles,
        protondb_data=protondb_data,
        anticheat_data=anticheat_data,
        achievements_data=achievements_data,
        watchlist_alerts=watchlist_alerts,
        budget_result=budget_result,
        compare_data=compare_data,
        gift_ideas=gift_ideas,
        recommended_collections=recommended_collections,
        profile_display_name=profile_display_name,
        active_promo_context=active_promo_context,
    )


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────


def _get_json(url: str, headers: dict = None) -> dict:
    return http_get_json(url, headers=headers, timeout=15)


def _post_json(url: str, body) -> dict:
    return http_post_json(url, body, timeout=30)


# ─────────────────────────────────────────────
# NOTIFICATIONS (TELEGRAM / DISCORD)
# ─────────────────────────────────────────────


def build_notification_summary(deals, comparison, top_picks, watchlist_alerts=None):
    """Build a summary dict for notifications. Returns None if nothing notable."""
    if _build_notification_summary_impl is None:
        raise RuntimeError("Notifications module is not available")
    return _build_notification_summary_impl(
        deals, comparison, top_picks, watchlist_alerts=watchlist_alerts
    )


def send_telegram(token: str, chat_id: str, summary: dict) -> bool:
    """Send notification via Telegram Bot API."""
    if _send_telegram_impl is None:
        raise RuntimeError("Notifications module is not available")
    return _send_telegram_impl(
        token,
        chat_id,
        summary,
        on_error=lambda message: print(f"  {_warn(message)}"),
    )


def send_discord(webhook_url: str, summary: dict) -> bool:
    """Send notification via Discord webhook."""
    if _send_discord_impl is None:
        raise RuntimeError("Notifications module is not available")
    return _send_discord_impl(
        webhook_url,
        summary,
        on_error=lambda message: print(f"  {_warn(message)}"),
    )


def send_notifications(filters: dict, summary: dict) -> None:
    """Send notifications via configured channels."""
    if _send_notifications_impl is None:
        raise RuntimeError("Notifications module is not available")
    _send_notifications_impl(
        filters,
        summary,
        send_telegram_fn=send_telegram,
        send_discord_fn=send_discord,
        emit=print,
        ok=_ok,
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────


def main():
    global WEB_EVENT_MODE
    sys.stdout.reconfigure(line_buffering=True)

    print(f"{C.BOLD}=== Steam Wishlist Deals Generator ==={C.RST}\n")

    (
        WEB_RUN,
        INTERACTIVE,
        KEY,
        VANITY,
        HLTB_CSV,
        OUTPUT_DIR,
        MIN_DISCOUNT,
        genres,
        no_cache,
        FAMILY_JSON,
        ITAD_KEY,
        FILTERS,
    ) = get_config()
    global MAX_WORKERS
    MAX_WORKERS = _resolve_max_workers(FILTERS.get("max_workers"), MAX_WORKERS)
    WEB_EVENT_MODE = bool(WEB_RUN)
    WARM_CACHE_ONLY = bool(FILTERS.get("warm_cache"))
    emit = print
    warm_cache_log_handle = None
    if WARM_CACHE_ONLY:
        try:
            warm_cache_log_path, warm_cache_log_handle = open_warm_cache_log_file(
                env=os.environ,
                frozen=getattr(sys, "frozen", False),
            )
            emit = build_warm_cache_emit(warm_cache_log_handle, terminal_emit=print)
            emit(f"  {_dim(f'Log warm-cache: {warm_cache_log_path}')}")
        except OSError as exc:
            print(f"  {_warn(f'No se pudo abrir log de warm-cache: {exc}')}")

    if not WEB_RUN and not INTERACTIVE:
        emit(f"  {_dim('Flujo recomendado: wizard web (python3 steam_deals_web.py).')}")
        emit(
            f"  {_dim('CLI disponible con flags/config, o modo interactivo con --interactive.')}\n"
        )
    RATE_LIMIT = 1.5
    t0 = time.monotonic()

    # Calcular total de pasos dinámicamente (+2 reviews/deck, +1 protondb/ac, +1 tags, +1 HTML, owned solo con key)
    TOTAL = (
        3
        if WARM_CACHE_ONLY
        else (
            11
            + (1 if KEY else 0)
            + (1 if FAMILY_JSON else 0)
            + (1 if HLTB_CSV else 0)
            + (1 if ITAD_KEY else 0)
            + (1 if FILTERS.get("csv") else 0)
            + (
                1
                if FILTERS.get("telegram_token") or FILTERS.get("discord_webhook")
                else 0
            )
            + (1 if FILTERS.get("compare") else 0)
        )
    )

    if not KEY:
        emit(f"  {_dim('Sin API Key — modo público (wishlist debe ser pública)')}")
    _n = [0]

    def step(msg: str):
        _n[0] += 1
        if _report_step_impl is not None:
            _report_step_impl(
                _n[0],
                TOTAL,
                msg,
                emit=emit,
                emit_event_fn=emit_event,
                bold_fn=_bold,
                color_cyan=C.CYN,
                color_reset=C.RST,
            )
            return
        emit(f"\n{C.CYN}[{_n[0]}/{TOTAL}]{C.RST} {_bold(msg)}", flush=True)
        emit_event("progress", current=_n[0], total=TOTAL, label=msg)

    # Validar rutas opcionales antes de arrancar
    if HLTB_CSV and not HLTB_CSV.exists():
        emit(f"{_err(f'HLTB CSV no encontrado: {HLTB_CSV}')}")
        HLTB_CSV = None
    if FAMILY_JSON and not FAMILY_JSON.exists():
        emit(f"{_err(f'Family JSON no encontrado: {FAMILY_JSON}')}")
        FAMILY_JSON = None

    try:
        # [1] Steam ID
        step("Resolviendo Steam ID...")
        steam_id = resolve_steam_id(KEY, VANITY)
        emit(f"  {_ok(steam_id)}")
        profile_display_name = resolve_profile_display_name(steam_id, VANITY, KEY)

        # [2] Wishlist (con prioridad)
        step("Obteniendo wishlist...")
        wishlist_appids, priorities = get_wishlist(KEY, steam_id)
        ranked = sum(1 for p in priorities.values() if p > 0)
        emit(f"  {_ok(f'{len(wishlist_appids):,} juegos ({ranked:,} con prioridad)')}")

        if WARM_CACHE_ONLY:
            run_warm_cache_mode(
                wishlist_appids,
                steam_id,
                no_cache=no_cache,
                min_discount=MIN_DISCOUNT,
                rate_limit=RATE_LIMIT,
                started_at=t0,
                step_fn=step,
                emit_fn=emit,
            )
            return
    except ValueError as exc:
        return _handle_cli_value_error(
            exc,
            VANITY,
            warm_cache=WARM_CACHE_ONLY,
            emit=emit,
            err_fn=_err,
            dim_fn=_dim,
        )
    finally:
        if WARM_CACHE_ONLY and warm_cache_log_handle is not None:
            warm_cache_log_handle.close()

        # [3] Biblioteca propia (requiere API key)
    owned: dict[str, str] = {}
    if KEY:
        step("Obteniendo biblioteca de Steam...")
        try:
            owned = get_owned_games(KEY, steam_id)
            print(f"  {_ok(f'{len(owned):,} juegos comprados')}")
        except ValueError as exc:
            print(f"  {_warn(str(exc))}")
            print(f"  {_dim('Continuando sin datos de biblioteca propia.')}")
            owned = {}

    # Compare wishlists (optional)
    compare_data = None
    gift_ideas = []
    if FILTERS.get("compare"):
        step("Comparando wishlists...")
        try:
            compare_data = compare_wishlists(KEY, steam_id, FILTERS["compare"])
            friend_set = compare_data["friend_set"]
            my_set = set(wishlist_appids)
            overlap = my_set & friend_set
            compare_data["overlap"] = overlap
            friend_label = compare_data.get("friend_name") or compare_data.get(
                "friend_vanity", "Friend"
            )
            print(
                f"  {_ok(f'{friend_label}: {len(compare_data['friend_appids']):,} juegos en wishlist')}"
            )
            print(f"  {_ok(f'{len(overlap)} en común')}")
        except Exception as e:
            print(f"  {_err(f'No se pudo comparar: {e}')}")
            compare_data = None

    # [4] Detectar oferta activa
    step("Detectando oferta activa de Steam...")
    active_promo_context = get_active_promo_context()
    sale_name = str(active_promo_context.get("sale_name", "") or "")
    if sale_name:
        print(f"  {_ok(f'{SYM_TAG}  {sale_name}')}")
    else:
        print(f"  {_dim('Sin oferta especial detectada')}")

    # Construir nombre del archivo
    today_obj = date.today()
    OUTPUT_MD = build_output_md_path(OUTPUT_DIR, sale_name, today_obj=today_obj)
    output_artifacts = build_output_artifact_paths(
        OUTPUT_MD,
        today_obj=today_obj,
        include_csv=bool(FILTERS.get("csv")),
    )
    filename = OUTPUT_MD.name
    print(f"  {_dim(f'Archivo: {OUTPUT_MD.name}')}")

    # Cargar historial de runs
    previous_context = resolve_previous_context(Path(OUTPUT_DIR), filename, steam_id)
    previous_run = previous_context["previous_run"]
    run_history = previous_context["run_history"]
    if previous_run:
        prev_date = previous_run.get("date", "?")
        prev_count = len(previous_run.get("deals", {}))
        print(f"  {_dim(f'Run anterior: {prev_date} ({prev_count} deals)')}")

    # Fallback: cargar deals del MD anterior si no hay historial
    previous_appids: set[str] = previous_context["previous_appids"]
    if previous_appids:
        print(
            f"  {_dim(f'MD anterior encontrado ({len(previous_appids)} deals) — fallback')}"
        )

    # [5] Precios (con smart cache + batching)
    step("Obteniendo precios de Steam...")
    price_stage = run_price_cache_stage(
        wishlist_appids,
        steam_id,
        no_cache=no_cache,
        min_discount=MIN_DISCOUNT,
        rate_limit=RATE_LIMIT,
    )
    deals = price_stage["deals"]

    # Comparar con runs anteriores
    comparison = compute_deal_comparison(deals, previous_run, run_history)
    comp_new = len(comparison.get("new_deals", set()))
    comp_gone = len(comparison.get("disappeared", []))
    comp_drops = sum(
        1
        for v in comparison.get("price_changes", {}).values()
        if v["direction"] == "down"
    )
    if comp_new or comp_gone or comp_drops:
        parts = []
        if comp_new:
            parts.append(f"{comp_new} nuevos")
        if comp_gone:
            parts.append(f"{comp_gone} terminaron")
        if comp_drops:
            parts.append(f"{comp_drops} bajaron")
        print(f"  {_ok(' · '.join(parts))}")

    # Guardar run actual en historial
    save_run_history(
        steam_id,
        VANITY,
        sale_name,
        MIN_DISCOUNT,
        deals,
        active_promo_context=active_promo_context,
    )

    # Historial local de precios (tendencias)
    price_history = load_price_history(steam_id)
    log_price_snapshot(price_history, deals)
    local_trends = analyze_trends(price_history, deals)
    save_price_history(price_history)
    trend_count = sum(1 for t in local_trends.values() if not t.get("is_first_time"))
    best_count = sum(1 for t in local_trends.values() if t.get("is_best_local"))
    if trend_count:
        print(
            f"  {_ok(f'{trend_count} con historial · {best_count} en mejor precio local')}"
        )

    enrichment_contract = build_generator_enrichment_contract(step)

    # [6] Reviews de Steam (solo para deals)
    deal_appids = [d["appid"] for d in deals]
    reviews_data = run_reviews_enrichment_orchestration(
        enrichment_contract,
        steam_id,
        deal_appids,
        no_cache=no_cache,
    )

    # [7] Compatibilidad Steam Deck (solo para deals)
    deck_data = run_deck_enrichment_orchestration(
        enrichment_contract,
        steam_id,
        deal_appids,
        no_cache=no_cache,
    )

    # [8] ProtonDB + Are We Anti-Cheat Yet
    protondb_data, anticheat_data = run_protondb_anticheat_enrichment_orchestration(
        enrichment_contract,
        steam_id,
        deal_appids,
        no_cache=no_cache,
    )

    # [9] Tags de Steam (via SteamSpy, solo para deals)
    tags_data = run_tags_enrichment_orchestration(
        enrichment_contract,
        steam_id,
        deal_appids,
        no_cache=no_cache,
    )

    # [10] Achievements
    achievements_data = run_achievements_enrichment_orchestration(
        enrichment_contract,
        steam_id,
        deal_appids,
        no_cache=no_cache,
    )

    # Biblioteca familiar (opcional)
    family_context = load_family_context(FAMILY_JSON, step_fn=step)
    family_renderer_kwargs = build_family_renderer_kwargs(family_context)
    itad_contract = build_generator_itad_contract(step)
    post_processing_contract = build_generator_post_processing_contract()
    engagement_contract = build_generator_engagement_contract(step)

    # HLTB
    backlog_on_sale, have_on_sale = [], []
    if HLTB_CSV:
        step("Cruzando con HLTB...")
        hltb = parse_hltb(HLTB_CSV)
        bl, cp, pl, rt = (
            len(hltb["backlog"]),
            len(hltb["completed"]),
            len(hltb["playing"]),
            len(hltb["retired"]),
        )
        print(
            f"  {_dim(f'Backlog: {bl:,} | Completados: {cp} | Playing: {pl} | Retired: {rt}')}"
        )
        backlog_on_sale, have_on_sale = cross_hltb_with_family_context(
            hltb,
            deals,
            family_context,
        )
        print(
            f"  {_ok(f'{len(backlog_on_sale)} backlog en oferta | {len(have_on_sale)} completados/retirados')}"
        )

    # IsThereAnyDeal (mínimo histórico + precios multi-tienda + bundles, opcional)
    itad_outputs = run_itad_orchestration(deal_appids, ITAD_KEY, contract=itad_contract)
    historical_lows = itad_outputs.historical_lows
    current_prices = itad_outputs.current_prices
    active_bundles = itad_outputs.active_bundles
    itad_ids = itad_outputs.itad_ids

    alert_deals = deals
    alert_global_margin_pct = _resolve_alert_global_margin_pct(
        FILTERS.get("alert_global_margin_pct")
    )
    alert_rise_pct = _resolve_alert_rise_pct(FILTERS.get("alert_rise_pct"))
    alert_score_min = _resolve_alert_score_min(FILTERS.get("alert_score_min"))

    post_processing_outputs = run_post_processing(
        deals,
        backlog_on_sale,
        have_on_sale,
        filters=FILTERS,
        priorities=priorities,
        reviews_data=reviews_data,
        deck_data=deck_data,
        previous_appids=previous_appids,
        comparison=comparison,
        contract=post_processing_contract,
        active_promo_context=active_promo_context,
    )
    hltb_hours = post_processing_outputs.hltb_hours
    deals = post_processing_outputs.deals
    top_picks = post_processing_outputs.top_picks

    smart_alerts = build_smart_alert_counts(
        deals=alert_deals,
        historical_lows=historical_lows,
        active_bundles=active_bundles,
        comparison=comparison,
        local_trends=local_trends,
        top_picks=top_picks,
        alert_global_margin_pct=alert_global_margin_pct,
        alert_rise_pct=alert_rise_pct,
        alert_score_min=alert_score_min,
    )

    engagement_outputs = run_engagement_post_run(
        deals,
        filters=FILTERS,
        top_picks=top_picks,
        compare_data=compare_data,
        owned=owned,
        comparison=comparison,
        contract=engagement_contract,
    )
    watchlist_alerts = engagement_outputs.watchlist_alerts
    budget_result = engagement_outputs.budget_result
    gift_ideas = engagement_outputs.gift_ideas
    recommended_collections = build_recommended_collections(deals, top_picks=top_picks)

    # Generar MD
    step("Generando Markdown...")
    md = generate_md(
        deals,
        backlog_on_sale,
        have_on_sale,
        VANITY,
        owned,
        wishlist_appids,
        MIN_DISCOUNT,
        genres,
        hltb_used=HLTB_CSV is not None,
        sale_name=sale_name,
        priorities=priorities,
        historical_lows=historical_lows,
        previous_appids=previous_appids,
        reviews=reviews_data,
        deck_compat=deck_data,
        current_prices=current_prices,
        top_picks=top_picks,
        comparison=comparison,
        sort_field=FILTERS.get("sort", "discount"),
        tags_data=tags_data,
        local_trends=local_trends,
        active_bundles=active_bundles,
        protondb_data=protondb_data,
        anticheat_data=anticheat_data,
        achievements_data=achievements_data,
        watchlist_alerts=watchlist_alerts,
        budget_result=budget_result,
        compare_data=compare_data,
        gift_ideas=gift_ideas,
        recommended_collections=recommended_collections,
        family_appids=family_renderer_kwargs.get("family_appids"),
        include_frontmatter=bool(FILTERS.get("md_frontmatter")),
        active_promo_context=active_promo_context,
    )

    # Generar HTML interactivo
    step("Generando HTML interactivo...")
    html = generate_html(
        deals,
        backlog_on_sale,
        have_on_sale,
        VANITY,
        owned,
        wishlist_appids,
        MIN_DISCOUNT,
        genres,
        hltb_used=HLTB_CSV is not None,
        sale_name=sale_name,
        priorities=priorities,
        historical_lows=historical_lows,
        previous_appids=previous_appids,
        reviews=reviews_data,
        deck_compat=deck_data,
        current_prices=current_prices,
        top_picks=top_picks,
        tags_data=tags_data,
        protondb_data=protondb_data,
        achievements_data=achievements_data,
        watchlist_alerts=watchlist_alerts,
        budget_result=budget_result,
        compare_data=compare_data,
        gift_ideas=gift_ideas,
        recommended_collections=recommended_collections,
        local_trends=local_trends,
        price_history=price_history,
        profile_display_name=profile_display_name,
        active_promo_context=active_promo_context,
        **family_renderer_kwargs,
    )

    # Generar HTML compartible (lightweight)
    share_html = generate_share_html(
        deals,
        VANITY,
        MIN_DISCOUNT,
        sale_name=sale_name,
        top_picks=top_picks,
        reviews=reviews_data,
        deck_compat=deck_data,
        historical_lows=historical_lows,
        profile_display_name=profile_display_name,
    )

    step("Generando JSON...")
    json_content = generate_json(
        deals,
        backlog_on_sale,
        have_on_sale,
        VANITY,
        owned,
        wishlist_appids,
        MIN_DISCOUNT,
        genres,
        hltb_used=HLTB_CSV is not None,
        sale_name=sale_name,
        priorities=priorities,
        historical_lows=historical_lows,
        previous_appids=previous_appids,
        reviews=reviews_data,
        deck_compat=deck_data,
        current_prices=current_prices,
        top_picks=top_picks,
        comparison=comparison,
        sort_field=FILTERS.get("sort", "discount"),
        tags_data=tags_data,
        local_trends=local_trends,
        active_bundles=active_bundles,
        protondb_data=protondb_data,
        anticheat_data=anticheat_data,
        achievements_data=achievements_data,
        watchlist_alerts=watchlist_alerts,
        budget_result=budget_result,
        compare_data=compare_data,
        gift_ideas=gift_ideas,
        recommended_collections=recommended_collections,
        profile_display_name=profile_display_name,
        active_promo_context=active_promo_context,
        **family_renderer_kwargs,
    )

    # Generar CSV (opcional)
    csv_content = None
    if FILTERS.get("csv"):
        step("Generando CSV...")
        csv_content = generate_csv(
            deals,
            priorities=priorities,
            reviews=reviews_data,
            deck_compat=deck_data,
            protondb_data=protondb_data,
            anticheat_data=anticheat_data,
            tags_data=tags_data,
            hltb_hours=hltb_hours,
            historical_lows=historical_lows,
            current_prices=current_prices,
            top_picks=top_picks,
            local_trends=local_trends,
            achievements_data=achievements_data,
        )

    written_artifacts = write_output_artifacts(
        output_artifacts,
        _run_output_module.OutputArtifactPayloads(
            markdown=md,
            html=html,
            share_html=share_html,
            json_content=json_content,
            csv_content=csv_content,
        ),
    )
    print(f"  {_ok(str(written_artifacts['markdown']))}")
    print(f"  {_ok(str(written_artifacts['html']))}")
    print(f"  {_ok(str(written_artifacts['share_html']))}")
    print(f"  {_ok(str(written_artifacts['json']))}")
    if "csv" in written_artifacts:
        print(f"  {_ok(str(written_artifacts['csv']))}")

    # Resumen final
    elapsed = time.monotonic() - t0
    _new_count, summary = emit_final_closeout(
        elapsed,
        deals,
        backlog_on_sale,
        previous_appids,
        top_picks,
        OUTPUT_MD,
        smart_alerts=smart_alerts,
    )


def run_scheduled():
    """Run main() in a loop if --schedule is set."""
    if _run_scheduled_impl is None:
        raise RuntimeError("Scheduler module is not available")
    _run_scheduled_impl(
        main,
        argv=sys.argv,
        now_fn=datetime.now,
        fromtimestamp_fn=datetime.fromtimestamp,
        sleep_fn=time.sleep,
        emit=print,
        style_bold=lambda text: f"{C.BOLD}{text}{C.RST}",
        style_dim=lambda text: f"{C.DIM}{text}{C.RST}",
        style_warn=lambda text: f"{C.YLW}{text}{C.RST}",
        style_err=lambda text: f"{C.RED}{text}{C.RST}",
    )


def _looks_like_placeholder_vanity(vanity: str) -> bool:
    raw = str(vanity or "").strip().rstrip("/")
    if not raw:
        return False
    normalized = raw.split("/")[-1].lower()
    return normalized in {"tu_vanity_url", "your_vanity_url"}


def _format_cli_user_error(exc: Exception, vanity: str) -> str:
    message = str(exc).strip()
    if _looks_like_placeholder_vanity(vanity):
        return (
            "No se pudo resolver el perfil porque `--vanity` sigue usando el "
            "placeholder `TU_VANITY_URL`. Reemplázalo por tu vanity real, la URL "
            "completa del perfil o tu Steam ID de 17 dígitos."
        )
    if message.startswith("No se pudo resolver el perfil") or message.startswith(
        "No se pudo resolver el vanity URL"
    ):
        return (
            f"{message}. Revisa `--vanity` y usa tu vanity real, la URL del perfil "
            "o tu Steam ID de 17 dígitos."
        )
    if message.startswith("No se pudo acceder a la wishlist"):
        return (
            f"{message} Revisa que la wishlist sea pública o intenta con la URL/Steam ID correcto."
        )
    return message


def _handle_cli_value_error(
    exc: Exception,
    vanity: str,
    *,
    warm_cache: bool,
    emit,
    err_fn,
    dim_fn,
) -> int:
    emit("")
    emit(f"  {err_fn(_format_cli_user_error(exc, vanity))}")
    if warm_cache:
        emit(
            f"  {dim_fn('Warm-cache cancelado. Corrige --vanity o permisos y vuelve a intentar.')}"
        )
    return 1


def _run_entrypoint(argv: list[str], *, main_fn, run_scheduled_fn) -> int:
    for index, arg in enumerate(argv[1:], start=1):
        if arg != "--schedule":
            continue
        if index + 1 >= len(argv):
            break
        try:
            float(argv[index + 1])
        except ValueError:
            break
        run_scheduled_fn()
        return 0
    return int(main_fn() or 0)


if __name__ == "__main__":
    raise SystemExit(
        _run_entrypoint(sys.argv, main_fn=main, run_scheduled_fn=run_scheduled)
    )
