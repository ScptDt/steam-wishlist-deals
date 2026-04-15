#!/usr/bin/env python3
"""
Steam Wishlist Deals Generator
Genera un MD con los deals de tu wishlist cruzados con tu HLTB.

Uso:
    python3 steam_deals_generator.py --vanity BG00G
    python3 steam_deals_generator.py --vanity https://steamcommunity.com/id/BG00G/
    python3 steam_deals_generator.py --key TU_KEY --vanity BG00G --discount 60
    python3 steam_deals_generator.py --genre roguelike --genre indie
    python3 steam_deals_generator.py --no-cache        # re-fetch aunque haya caché
    python3 steam_deals_generator.py --family-json ~/familia.json
    python3 steam_deals_generator.py --itad-key TU_ITAD_KEY  # precio mínimo histórico

La Steam API Key es opcional. Sin key: funciona con endpoints públicos (wishlist
debe ser pública). Con key: además muestra juegos propios para limpiar la wishlist.

Config guardada en ~/.config/steam_deals.json tras el primer run interactivo.
"""

import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path
from shared.io_utils import http_get_json, http_post_json, load_json_file, write_json_file

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
    from renderers.share_html_renderer import (
        generate_share_html as _generate_share_html_renderer,
    )
except Exception:
    _generate_share_html_renderer = None


try:
    from renderers.csv_renderer import generate_csv as _generate_csv_renderer
except Exception:
    _generate_csv_renderer = None


try:
    from steam_deals_recommendations import (
        build_gift_ideas as _build_gift_ideas_impl,
        compute_budget_picks as _compute_budget_picks_impl,
        compute_value_score as _compute_value_score_impl,
        rank_top_picks as _rank_top_picks_impl,
    )
except Exception:
    _build_gift_ideas_impl = None
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
        get_active_sale as _get_active_sale_impl,
        get_owned_games as _get_owned_games_impl,
        get_wishlist as _get_wishlist_impl,
        load_family_games as _load_family_games_impl,
        resolve_steam_id as _resolve_steam_id_impl,
    )
except Exception:
    _compare_wishlists_impl = None
    _get_active_sale_impl = None
    _get_owned_games_impl = None
    _get_wishlist_impl = None
    _load_family_games_impl = None
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
    RST  = _RuntimeAnsiColors.RST if _RuntimeAnsiColors else "\033[0m"
    BOLD = _RuntimeAnsiColors.BOLD if _RuntimeAnsiColors else "\033[1m"
    DIM  = _RuntimeAnsiColors.DIM if _RuntimeAnsiColors else "\033[2m"
    GRN  = _RuntimeAnsiColors.GRN if _RuntimeAnsiColors else "\033[32m"
    YLW  = _RuntimeAnsiColors.YLW if _RuntimeAnsiColors else "\033[33m"
    RED  = _RuntimeAnsiColors.RED if _RuntimeAnsiColors else "\033[31m"
    CYN  = _RuntimeAnsiColors.CYN if _RuntimeAnsiColors else "\033[36m"

def _safe_symbol(unicode_symbol: str, fallback: str) -> str:
    if _safe_symbol_impl is not None:
        return _safe_symbol_impl(unicode_symbol, fallback, stdout_encoding=(sys.stdout.encoding or "utf-8"))
    enc = (sys.stdout.encoding or "utf-8")
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
        _emit_event_impl(event_type, web_event_mode=WEB_EVENT_MODE, emit=print, event_prefix=EVENT_PREFIX, **payload)
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
    url = f"https://steamcommunity.com/id/{vanity}/?xml=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read().decode("utf-8")

def resolve_steam_id(api_key: str | None, vanity: str) -> str:
    """Convierte vanity URL, link de perfil, o Steam ID numérico a Steam ID."""
    if _resolve_steam_id_impl is None:
        raise RuntimeError("Steam adapter module is not available")
    return _resolve_steam_id_impl(
        api_key,
        vanity,
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


def build_itad_runtime(*, lookup_games_fn, get_store_lows_fn, get_current_prices_fn, get_active_bundles_fn):
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


def empty_itad_outputs():
    if _itad_orchestration_module is None:
        raise RuntimeError("ITAD orchestration module is not available")
    return _itad_orchestration_module.empty_itad_outputs()


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


def empty_post_processing_outputs():
    if _post_processing_module is None:
        raise RuntimeError("Post-processing module is not available")
    return _post_processing_module.empty_post_processing_outputs()


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


def empty_engagement_outputs():
    if _engagement_post_run_module is None:
        raise RuntimeError("Engagement post-run module is not available")
    return _engagement_post_run_module.empty_engagement_outputs()


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
    steam_id: str, vanity: str, sale_name: str, min_discount: int, deals: list[dict]
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


def build_output_md_path(output_dir: str | Path, sale_name: str, *, today_obj: date | None = None) -> Path:
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.build_output_md_path(output_dir, sale_name, today_obj=today_obj)


def resolve_previous_context(output_dir: str | Path, current_filename: str, steam_id: str) -> dict:
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


def build_share_output_path(output_dir: str | Path, *, today_obj: date | None = None) -> Path:
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


def build_final_summary(elapsed: float, deals: list[dict], backlog_on_sale: list[dict], previous_appids: set[str], top_picks: list[dict] | None, output_md: Path) -> tuple[int, str]:
    if _run_output_module is None:
        raise RuntimeError("Run-output module is not available")
    return _run_output_module.build_final_summary(elapsed, deals, backlog_on_sale, previous_appids, top_picks, output_md)


def emit_final_closeout(
    elapsed: float,
    deals: list[dict],
    backlog_on_sale: list[dict],
    previous_appids: set[str],
    top_picks: list[dict] | None,
    output_md: Path,
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
CACHE_DIR = PROJECT_DIR / ".cache" / "steam_deals"
CACHE_FILE = CACHE_DIR / "prices_cache.json"
CACHE_MAX_HOURS = 24
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
):
    if _cache_policy_module is None:
        raise RuntimeError("Cache policy module is not available")
    return _cache_policy_module.select_scoped_cache(
        target_ids,
        cached,
        cache_age,
        no_cache=no_cache,
        ttl_hours=ttl_hours,
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


def build_scoped_enrichment_runtime(*, load_cache_fn, select_cache_fn, fetch_data_fn, save_cache_fn, ttl_hours: float):
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.build_scoped_cache_runtime(
        load_cache=load_cache_fn,
        select_cache=select_cache_fn,
        fetch_data=fetch_data_fn,
        save_cache=save_cache_fn,
        ttl_hours=ttl_hours,
    )


def build_global_enrichment_runtime(*, load_cache_fn, select_cache_fn, fetch_data_fn, save_cache_fn, ttl_hours: float):
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


def empty_enrichment_outputs():
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.empty_enrichment_outputs()


def build_generator_enrichment_contract(step_fn):
    progress = build_enrichment_progress_callbacks(step_fn=step_fn, emit_fn=print)
    messages = build_enrichment_message_formatters(ok_fn=_ok, warn_fn=_warn, dim_fn=_dim)
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


def run_reviews_enrichment_orchestration(contract, steam_id: str, deal_appids: list[str], *, no_cache: bool) -> dict[str, dict]:
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.run_reviews_orchestration(
        steam_id,
        deal_appids,
        no_cache=no_cache,
        contract=contract,
    )


def run_deck_enrichment_orchestration(contract, steam_id: str, deal_appids: list[str], *, no_cache: bool) -> dict[str, int]:
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.run_deck_orchestration(
        steam_id,
        deal_appids,
        no_cache=no_cache,
        contract=contract,
    )


def run_protondb_anticheat_enrichment_orchestration(contract, steam_id: str, deal_appids: list[str], *, no_cache: bool) -> tuple[dict[str, dict], dict[str, dict]]:
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.run_protondb_anticheat_orchestration(
        steam_id,
        deal_appids,
        no_cache=no_cache,
        contract=contract,
    )


def run_tags_enrichment_orchestration(contract, steam_id: str, deal_appids: list[str], *, no_cache: bool) -> dict[str, dict]:
    if _enrichment_orchestration_module is None:
        raise RuntimeError("Enrichment orchestration module is not available")
    return _enrichment_orchestration_module.run_tags_orchestration(
        steam_id,
        deal_appids,
        no_cache=no_cache,
        contract=contract,
    )


def run_achievements_enrichment_orchestration(contract, steam_id: str, deal_appids: list[str], *, no_cache: bool) -> dict[str, dict]:
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


# ─────────────────────────────────────────────
# FETCH DE PRECIOS (batched con fallback)
# ─────────────────────────────────────────────

BATCH_SIZE = 20


def _fetch_single(appid: str, country: str, delay: float) -> dict | None:
    """Fallback: fetch individual de un appid."""
    if _prices_module is None:
        raise RuntimeError("Prices module is not available")
    return _prices_module.fetch_single(appid, country, delay, get_json=_get_json, sleep_fn=time.sleep)


def _parse_release_year(date_str: str) -> int | None:
    """Extrae el año de una fecha de Steam (ej. 'Mar 25, 2019' → 2019)."""
    if _prices_module is None:
        raise RuntimeError("Prices module is not available")
    return _prices_module.parse_release_year(date_str)


def _process_app_entry(appid: str, data: dict) -> dict | None:
    """Extrae info de precio de la respuesta de appdetails para un appid."""
    if _prices_module is None:
        raise RuntimeError("Prices module is not available")
    return _prices_module.process_app_entry(appid, data, parse_release_year_fn=_parse_release_year)


def get_deals_from_wishlist(
    appids: list[str],
    fetched_cache: dict,
    steam_id: str,
    country: str = "mx",
    min_discount: int = 50,
    rate_limit: float = 1.5,
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
        emit=print,
        warn=_warn,
        dim=_dim,
        bar_fill=BAR_FILL,
        bar_empty=BAR_EMPTY,
        color_green=C.GRN,
        color_dim=C.DIM,
        color_reset=C.RST,
        batch_size=BATCH_SIZE,
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

MAX_WORKERS = 8
RATE_LIMIT_INTERVAL = 0.15


def _enrichment_bar(completed: int, total: int, width: int = 25) -> str:
    filled = int((completed / total) * width) if total > 0 else 0
    return f"{C.GRN}{BAR_FILL * filled}{C.DIM}{BAR_EMPTY * (width - filled)}{C.RST}"


def _fetch_parallel(items: list[str], fetch_fn, label: str,
                    rate_limit: float = RATE_LIMIT_INTERVAL, max_workers: int = MAX_WORKERS) -> dict:
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
    return _enrichment_module.fetch_reviews(appids, cached, rate_limit=rate_limit, fetch_parallel_fn=_fetch_parallel, get_json=_get_json)


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
    return _enrichment_module.fetch_deck_compat(appids, cached, rate_limit=rate_limit, fetch_parallel_fn=_fetch_parallel, get_json=_get_json)


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
    return _enrichment_module.fetch_protondb(appids, cached, rate_limit=rate_limit, fetch_parallel_fn=_fetch_parallel, get_json=_get_json)


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


def linux_badge(deck_cat: int, protondb: dict | None, anticheat: dict | None, linux_native: bool = False) -> str:
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
    return _group_deals_by_tag_impl(deals, tags_data, min_count=min_count, get_top_tags_fn=get_top_tags)


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
    _enrichment_module.save_achievements_cache(ACHIEVEMENTS_CACHE_FILE, steam_id, achievements)


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
    return _enrichment_module.fetch_achievements(appids, cached, rate_limit=rate_limit, fetch_parallel_fn=_fetch_parallel, get_json=_get_json)


def achievements_badge(ach: dict | None) -> str:
    """MD badge for achievements."""
    if _achievements_badge_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _achievements_badge_impl(ach)


def _html_achievements_badge(ach: dict | None) -> str:
    if not ach:
        return '<span class="review-na">\u2014</span>'
    return f'<span class="badge ach-badge" title="Avg global completion: {ach["avg_completion"]:.1f}%">\U0001f3c6 {ach["count"]}</span>'


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
) -> list[dict]:
    """Rank deals by composite value score, return top N."""
    if _rank_top_picks_impl is None:
        raise RuntimeError("Recommendations module is not available")
    return _rank_top_picks_impl(deals, priorities, reviews, hltb_hours, deck_compat, n=n)


def compute_budget_picks(deals, budget_mxn, top_picks, watchlist_alerts=None):
    """Greedy budget optimizer: pick best deals that fit within budget."""
    if _compute_budget_picks_impl is None:
        raise RuntimeError("Recommendations module is not available")
    return _compute_budget_picks_impl(deals, budget_mxn, top_picks, watchlist_alerts=watchlist_alerts)


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
) -> str:
    if _generate_md_renderer is None:
        raise RuntimeError("Markdown renderer module is not available")
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


def _html_esc(text: str) -> str:
    return _renderer_html_escape(text)


def _html_link(name: str, appid: str) -> str:
    return f'<a href="{STORE_URL.format(appid=appid)}" target="_blank">{_html_esc(name)}</a>'


def _html_deck_badge(category: int) -> str:
    labels = {
        3: ("Verified", "verified"),
        2: ("Playable", "playable"),
        1: ("Unsupported", "unsupported"),
    }
    if category not in labels:
        return '<span class="badge deck-unknown">\u2014</span>'
    text, cls = labels[category]
    return f'<span class="badge deck-{cls}">{text}</span>'


def _html_review_badge(review: dict | None) -> str:
    if not review:
        return '<span class="review-na">\u2014</span>'
    pct = review["pct"]
    cls = "review-good" if pct >= 80 else "review-mixed" if pct >= 60 else "review-bad"
    return f'<span class="{cls}" title="{review["total"]:,} reviews">{_html_esc(review["desc"])} ({pct}%)</span>'


def _html_prio_badge(priority: int) -> str:
    if priority == 0:
        return ""
    cls = "prio-top" if priority <= 10 else "prio-mid" if priority <= 50 else ""
    if not cls:
        return ""
    return f' <span class="{cls}">#{priority}</span>'


def _html_metacritic_badge(score: int | None) -> str:
    if score is None:
        return '<span class="review-na">\u2014</span>'
    cls = "mc-good" if score >= 75 else "mc-mixed" if score >= 50 else "mc-bad"
    return f'<span class="badge {cls}">{score}</span>'


def multiplayer_badges(categories: list[int]) -> str:
    """Emoji badges for multiplayer/co-op categories (for MD)."""
    if _multiplayer_badges_impl is None:
        raise RuntimeError("Presentation module is not available")
    return _multiplayer_badges_impl(categories)


def _html_multiplayer_badges(categories: list[int]) -> str:
    cats = set(categories)
    parts = []
    if cats & {9, 38, 39}:
        parts.append('<span class="badge mp-coop">Co-op</span>')
    if cats & {36, 37}:
        parts.append('<span class="badge mp-pvp">PvP</span>')
    if not parts and 1 in cats:
        parts.append('<span class="badge mp-multi">Multi</span>')
    if not parts and 2 in cats:
        parts.append('<span class="badge mp-single">Single</span>')
    return " ".join(parts) if parts else '<span class="review-na">\u2014</span>'


def _build_sparkline_svg(
    snapshots: list[dict], width: int = 80, height: int = 24
) -> str:
    """Build an inline SVG sparkline from price snapshots."""
    if len(snapshots) < 2:
        return ""
    prices = [s["price_raw"] / 100 for s in snapshots]
    mn, mx = min(prices), max(prices)
    rng = mx - mn if mx != mn else 1
    n = len(prices)
    points = []
    for i, p in enumerate(prices):
        x = round(i / (n - 1) * width, 1)
        y = round(height - (p - mn) / rng * (height - 2) - 1, 1)
        points.append(f"{x},{y}")
    polyline = " ".join(points)
    last_price = prices[-1]
    color = (
        "#6cc644"
        if last_price <= mn
        else "#f0b232"
        if last_price <= mn + rng * 0.3
        else "#c7d5e0"
    )
    # Dot on current price
    lx, ly = points[-1].split(",")
    return (
        f'<svg width="{width}" height="{height}" style="vertical-align:middle" title="Historial: ${mn:.0f}-${mx:.0f}">'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="{lx}" cy="{ly}" r="2" fill="{color}"/></svg>'
    )


def _html_price_raw(price_str: str) -> float:
    m = re.search(r"[\d,.]+", price_str.replace(",", ""))
    return float(m.group()) if m else 0.0


_HTML_CSS = """
:root {
  --bg-primary: #1b2838; --bg-secondary: #2a475e; --bg-card: #16202d;
  --bg-hover: #1a3a5c; --text-primary: #c7d5e0; --text-secondary: #8f98a0;
  --accent-blue: #66c0f4; --accent-green: #6cc644; --accent-yellow: #f0b232;
  --accent-red: #c7322e; --gold: #d4a84b; --border: #2a475e;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg-primary); color: var(--text-primary); line-height: 1.5; padding: 1rem; max-width: 1400px; margin: 0 auto; }
a { color: var(--accent-blue); text-decoration: none; }
a:hover { text-decoration: underline; }
.stats-bar { background: var(--bg-secondary); border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; }
.stats-bar h1 { font-size: 1.4rem; margin-bottom: .3rem; }
.stats-meta { color: var(--text-secondary); font-size: .85rem; margin-bottom: .6rem; }
.sale-badge { color: var(--accent-yellow); font-weight: bold; }
.stats-pills { display: flex; flex-wrap: wrap; gap: .4rem; }
.pill { background: var(--bg-primary); border: 1px solid var(--border); border-radius: 12px; padding: .15rem .6rem; font-size: .8rem; }
.pill-accent { background: var(--accent-blue); color: #000; border-color: var(--accent-blue); font-weight: 600; }
.pill-new { background: var(--accent-green); color: #000; border-color: var(--accent-green); }
.top-picks { margin-bottom: 1.5rem; }
.top-picks h2 { font-size: 1.2rem; margin-bottom: .3rem; }
.section-desc { color: var(--text-secondary); font-size: .8rem; margin-bottom: .8rem; }
.picks-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: .6rem; }
a.pick-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 0; position: relative; overflow: hidden; display: flex; flex-direction: column; text-decoration: none; color: inherit; cursor: pointer; transition: border-color .2s, transform .1s; }
a.pick-card:hover { border-color: var(--accent-blue); transform: translateY(-2px); text-decoration: none; }
.pick-img { width: 100%; aspect-ratio: 460/215; object-fit: cover; display: block; }
.pick-body { padding: .5rem .7rem .7rem; flex: 1; }
.pick-card:hover { border-color: var(--accent-blue); }
.rank-gold { border-color: var(--gold); }
.rank-silver { border-color: #aaa; }
.rank-bronze { border-color: #cd7f32; }
.pick-rank { position: absolute; top: .3rem; right: .5rem; font-size: .75rem; color: var(--text-secondary); font-weight: bold; }
.pick-score { font-size: 1.5rem; font-weight: bold; color: var(--accent-blue); }
.pick-name { font-size: .85rem; margin: .3rem 0; }
.pick-details { font-size: .8rem; }
.pick-discount { color: var(--accent-green); font-weight: bold; margin-right: .5rem; }
.pick-price { color: var(--text-secondary); }
.pick-meta { font-size: .75rem; color: var(--text-secondary); margin-top: .3rem; }
.filter-panel { background: var(--bg-secondary); border-radius: 8px; padding: .8rem 1.2rem; margin-bottom: 1.5rem; }
.filter-panel summary { cursor: pointer; font-weight: bold; font-size: 1rem; }
.filter-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem; margin-top: .8rem; }
.filter-group label { display: block; font-size: .8rem; color: var(--text-secondary); margin-bottom: .2rem; }
.filter-group input[type=text], .filter-group select { width: 100%; padding: .3rem .5rem; background: var(--bg-primary); color: var(--text-primary); border: 1px solid var(--border); border-radius: 4px; font-size: .85rem; }
.filter-group input[type=range] { width: 100%; }
.filter-group output { color: var(--accent-blue); font-weight: 600; }
.btn-reset { background: var(--bg-primary); color: var(--text-primary); border: 1px solid var(--border); border-radius: 4px; padding: .3rem .8rem; cursor: pointer; font-size: .85rem; }
.btn-reset:hover { border-color: var(--accent-blue); }
.tier-section { margin-bottom: 1rem; }
.tier-section summary { cursor: pointer; }
.tier-header { font-size: 1.1rem; font-weight: bold; padding: .5rem 0; }
.tier-count { font-weight: normal; color: var(--text-secondary); }
.table-wrap { overflow-x: auto; }
.deals-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.deals-table th { background: var(--bg-secondary); padding: .4rem .5rem; text-align: left; cursor: pointer; white-space: nowrap; user-select: none; border-bottom: 2px solid var(--border); }
.deals-table th:hover { color: var(--accent-blue); }
.sort-arrow { font-size: .65rem; color: var(--text-secondary); margin-left: .2rem; }
.deals-table td { padding: .35rem .5rem; border-bottom: 1px solid var(--border); }
.deals-table tbody tr:hover { background: var(--bg-hover); }
.game-cell { display: flex; align-items: center; gap: .5rem; }
.game-thumb { width: 120px; height: 45px; object-fit: cover; border-radius: 3px; flex-shrink: 0; transition: transform .2s ease; position: relative; z-index: 1; }
.game-thumb:hover { transform: scale(2.5); z-index: 100; box-shadow: 0 4px 16px rgba(0,0,0,.6); border-radius: 4px; }
.badge { display: inline-block; padding: .1rem .4rem; border-radius: 3px; font-size: .75rem; font-weight: 600; }
.deck-verified { background: #1a3d1a; color: var(--accent-green); }
.deck-playable { background: #3d3a1a; color: var(--accent-yellow); }
.deck-unsupported { background: #3d1a1a; color: var(--accent-red); }
.new-badge { background: var(--accent-green); color: #000; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .6; } }
.review-good { color: var(--accent-green); }
.review-mixed { color: var(--accent-yellow); }
.review-bad { color: var(--accent-red); }
.review-na { color: var(--text-secondary); }
.prio-top { background: var(--gold); color: #000; padding: .05rem .3rem; border-radius: 3px; font-size: .7rem; font-weight: bold; }
.prio-mid { color: var(--text-secondary); font-size: .75rem; }
.mc-good { background: #1a3d1a; color: var(--accent-green); }
.mc-mixed { background: #3d3a1a; color: var(--accent-yellow); }
.mc-bad { background: #3d1a1a; color: var(--accent-red); }
.mp-coop { background: #1a3d3d; color: #6cc6c6; }
.mp-pvp { background: #3d1a1a; color: #c66c6c; }
.mp-multi { background: #2a2a3d; color: #8f98c0; }
.mp-single { background: #2a2a3d; color: #8f98c0; }
.ach-badge { background: #3d3a1a; color: var(--accent-yellow); }
.wl-card { display: flex; align-items: center; gap: .6rem; background: var(--bg-card); border: 2px solid var(--accent-green); border-radius: 6px; padding: .6rem; }
.wl-info { flex: 1; }
@media (max-width: 1023px) { .picks-grid { grid-template-columns: repeat(3, 1fr); } .filter-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 767px) { .picks-grid { grid-template-columns: repeat(2, 1fr); } .filter-grid { grid-template-columns: 1fr; } .deals-table { font-size: .75rem; } .game-thumb { width: 80px; height: 30px; } }
.dashboard { background: var(--bg-secondary); border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; }
.dashboard summary { cursor: pointer; font-weight: bold; font-size: 1.1rem; }
.dash-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-top: .8rem; }
.dash-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: .8rem; }
.dash-card h3 { font-size: .9rem; margin-bottom: .5rem; }
.hbar-row { display: flex; align-items: center; gap: .4rem; margin-bottom: .3rem; }
.hbar-label { width: 4.5rem; font-size: .75rem; color: var(--text-secondary); text-align: right; flex-shrink: 0; }
.hbar-track { flex: 1; background: var(--bg-primary); border-radius: 3px; height: 1.1rem; overflow: hidden; }
.hbar-fill { height: 100%; border-radius: 3px; display: flex; align-items: center; padding-left: .3rem; font-size: .65rem; font-weight: 600; color: #000; }
.hbar-value { font-size: .75rem; color: var(--text-secondary); width: 2.5rem; text-align: right; flex-shrink: 0; }
.stacked-bar { display: flex; height: 1.5rem; border-radius: 4px; overflow: hidden; margin-bottom: .4rem; }
.stacked-seg { display: flex; align-items: center; justify-content: center; font-size: .6rem; font-weight: 600; color: #000; }
.stacked-legend { display: flex; flex-wrap: wrap; gap: .4rem; }
.legend-item { display: flex; align-items: center; gap: .2rem; font-size: .7rem; color: var(--text-secondary); }
.legend-dot { width: .5rem; height: .5rem; border-radius: 50%; }
.fin-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: .5rem; }
.fin-item { text-align: center; padding: .4rem; }
.fin-value { font-size: 1.2rem; font-weight: bold; color: var(--accent-blue); }
.fin-savings { color: var(--accent-green); }
.fin-label { font-size: .7rem; color: var(--text-secondary); margin-top: .2rem; }
@media (max-width: 1023px) { .dash-grid { grid-template-columns: 1fr; } .fin-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 767px) { .fin-grid { grid-template-columns: repeat(2, 1fr); } }
.pick-card { position: relative; }
.share-btn-mini { position: absolute; top: .4rem; right: .4rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: 4px; padding: .3rem .5rem; cursor: pointer; font-size: .9rem; opacity: 0.6; transition: opacity .2s; }
.share-btn-mini:hover { opacity: 1; background: var(--accent-blue); }
.share-modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center; }
.share-modal.active { display: flex; }
.share-modal-content { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; max-width: 420px; width: 90%; }
.share-modal h3 { color: var(--accent-blue); margin-bottom: 1rem; font-size: 1.1rem; }
.share-game-info { background: var(--bg-primary); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
.share-game-name { font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem; }
.share-game-price { color: var(--accent-green); font-size: 1.2rem; font-weight: 700; }
.share-game-price span { text-decoration: line-through; color: var(--text-secondary); font-weight: 400; font-size: 0.9rem; }
.share-game-minhist { font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.3rem; }
.share-game-minhist span { color: var(--accent-yellow); }
.share-actions { display: flex; flex-direction: column; gap: 0.6rem; }
.share-btn { padding: 0.6rem 1rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer; text-align: center; }
.share-btn-copy-app { background: var(--accent-blue); color: #000; border: none; }
.share-btn-copy-app:hover { background: #4db8e8; }
.share-btn-copy-steam { background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border); }
.share-btn-copy-steam:hover { border-color: var(--accent-blue); }
.share-btn-open { background: var(--bg-primary); color: var(--text-secondary); border: 1px solid var(--border); }
.share-close { margin-top: 0.8rem; text-align: center; color: var(--text-secondary); font-size: 0.85rem; cursor: pointer; }
.share-close:hover { color: var(--text-primary); }
"""

_HTML_JS = """
const sortState = {};
function sortTable(tableId, colIdx, dataType) {
  const table = document.getElementById(tableId);
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const key = tableId + '-' + colIdx;
  sortState[key] = sortState[key] === 'asc' ? 'desc' : 'asc';
  const dir = sortState[key] === 'asc' ? 1 : -1;
  table.querySelectorAll('th .sort-arrow').forEach(s => s.textContent = '\\u25b2\\u25bc');
  const th = table.querySelectorAll('th')[colIdx];
  if (th) th.querySelector('.sort-arrow').textContent = dir === 1 ? '\\u25b2' : '\\u25bc';
  function parseVal(row) {
    const text = row.children[colIdx] ? row.children[colIdx].textContent.trim() : '';
    if (dataType === 'num' || dataType === 'price') return parseFloat(text.replace(/[^0-9.\\-]/g, '')) || 0;
    return text.toLowerCase();
  }
  rows.sort((a, b) => { const va = parseVal(a), vb = parseVal(b); return (typeof va === 'number' ? va - vb : va.localeCompare(vb)) * dir; });
  rows.forEach(r => tbody.appendChild(r));
}
function applyFilters() {
  const discMin = parseInt(document.getElementById('f-discount').value);
  const priceMax = parseInt(document.getElementById('f-price-max').value);
  const deck = document.getElementById('f-deck').value;
  const revMin = parseInt(document.getElementById('f-reviews').value);
  const search = document.getElementById('f-search').value.toLowerCase();
  const newOnly = document.getElementById('f-new-only').checked;
  let totalV = 0, totalD = 0, totalP = 0;
  document.querySelectorAll('.deals-table tbody tr').forEach(row => {
    const d = row.dataset;
    let show = true;
    if (parseInt(d.discount) < discMin) show = false;
    if (priceMax < 2000 && parseFloat(d.price) > priceMax) show = false;
    if (deck !== 'all' && d.deck !== deck) show = false;
    const rv = parseInt(d.review);
    if (rv >= 0 && rv < revMin) show = false;
    if (search && !d.name.includes(search)) show = false;
    if (newOnly && d.new !== '1') show = false;
    row.style.display = show ? '' : 'none';
    if (show) { totalV++; totalD += parseInt(d.discount); totalP += parseFloat(d.price); }
  });
  const sd = document.getElementById('stat-deals'); if (sd) sd.textContent = totalV.toLocaleString() + ' deals visibles';
  if (totalV > 0) {
    const sa = document.getElementById('stat-avg-disc'); if (sa) sa.textContent = 'Promedio: -' + Math.round(totalD / totalV) + '%';
    const sp = document.getElementById('stat-avg-price'); if (sp) sp.textContent = 'Precio medio: $' + Math.round(totalP / totalV);
  }
  document.querySelectorAll('.tier-section').forEach(s => {
    const t = s.querySelector('.deals-table');
    if (t) { const v = t.querySelectorAll('tbody tr:not([style*=\"display: none\"])').length; const c = s.querySelector('.visible-count'); if (c) c.textContent = v; }
  });
}
function resetFilters() {
  document.getElementById('f-search').value = '';
  document.getElementById('f-discount').value = 50;
  document.getElementById('f-price-max').value = 2000;
  document.getElementById('f-deck').value = 'all';
  document.getElementById('f-reviews').value = 0;
  document.getElementById('f-new-only').checked = false;
  document.querySelectorAll('.filter-group output').forEach(o => { if (o.id === 'f-disc-val') o.textContent = '50%'; else if (o.id === 'f-price-val') o.textContent = 'Sin limite'; else if (o.id === 'f-rev-val') o.textContent = '0%'; });
  applyFilters();
}
document.addEventListener('DOMContentLoaded', applyFilters);
function copyForSheets() {
  const rows = [];
  document.querySelectorAll('.deals-table').forEach(table => {
    if (!rows.length) {
      const ths = Array.from(table.querySelectorAll('th')).map(th => th.textContent.replace(/[▲▼]/g,'').trim());
      rows.push(ths.join('\\t'));
    }
    table.querySelectorAll('tbody tr').forEach(tr => {
      if (tr.style.display === 'none') return;
      const cells = Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim().replace(/\\t/g,' '));
      rows.push(cells.join('\\t'));
    });
  });
  const tsv = rows.join('\\n');
  navigator.clipboard.writeText(tsv).then(() => {
    const btn = document.querySelector('[onclick*=copyForSheets]');
    const orig = btn.innerHTML;
    btn.innerHTML = '&#9989; Copiado!';
    setTimeout(() => btn.innerHTML = orig, 2000);
  }).catch(() => alert('No se pudo copiar al clipboard'));
}
// Share Modal
let currentShareData = null;
let currentSteamUrl = '';
function openShareModal(game) {
  currentShareData = game;
  currentSteamUrl = 'https://store.steampowered.com/app/' + game.appid + '/';
  document.getElementById('share-name').textContent = game.name || '';
  document.getElementById('share-price').innerHTML = (game.price_original && game.price ? '<span>$' + game.price_original + ' </span>' : '') + (game.price || '') + (game.discount ? ' (' + game.discount + '% OFF)' : '');
  document.getElementById('share-minhist').innerHTML = game.min_hist ? 'Minimo historico: <span>$' + game.min_hist + '</span>' : '';
  document.getElementById('share-modal').classList.add('active');
}
function closeShareModal() {
  document.getElementById('share-modal').classList.remove('active');
  currentShareData = null;
}
function copyShareLink() {
  if (!currentShareData) return;
  const encoded = btoa(JSON.stringify(currentShareData));
  const shareUrl = 'steamtools://share?data=' + encoded;
  navigator.clipboard.writeText(shareUrl).then(() => {
    const btn = document.getElementById('btn-copy-app');
    btn.textContent = 'Copiado!';
    setTimeout(() => btn.textContent = 'Copiar link steamtools://', 2000);
  });
}
function copySteamLink() {
  if (!currentSteamUrl) return;
  navigator.clipboard.writeText(currentSteamUrl).then(() => {
    const btn = document.querySelector('.share-btn-copy-steam');
    btn.textContent = 'Copiado!';
    setTimeout(() => btn.textContent = 'Copiar link de Steam', 2000);
  });
}
function openInSteam() {
  if (currentSteamUrl) window.open(currentSteamUrl, '_blank');
}
"""


def _build_dashboard_html(deals, reviews, deck_compat_data, tags_data, protondb_data):
    """Build statistics dashboard HTML section."""
    if not deals:
        return ""
    total = len(deals)

    # Financial summary
    total_orig = sum(_html_price_raw(d.get("price_original", "")) for d in deals)
    total_final = sum(_html_price_raw(d["price_final"]) for d in deals)
    total_savings = total_orig - total_final
    avg_disc = sum(d["discount"] for d in deals) / total
    prices = sorted(_html_price_raw(d["price_final"]) for d in deals)
    median_price = prices[len(prices) // 2] if prices else 0

    fin_html = f"""<div class="dash-card" style="grid-column:1/-1">
  <h3>&#128176; Resumen Financiero</h3>
  <div class="fin-grid">
    <div class="fin-item"><div class="fin-value">${total_orig:,.0f}</div><div class="fin-label">Precio original</div></div>
    <div class="fin-item"><div class="fin-value">${total_final:,.0f}</div><div class="fin-label">En oferta</div></div>
    <div class="fin-item"><div class="fin-value fin-savings">${total_savings:,.0f}</div><div class="fin-label">Ahorro total</div></div>
    <div class="fin-item"><div class="fin-value">-{avg_disc:.0f}%</div><div class="fin-label">Descuento promedio</div></div>
    <div class="fin-item"><div class="fin-value">${median_price:.0f}</div><div class="fin-label">Precio mediana</div></div>
  </div>
</div>"""

    # Discount distribution bars
    tier_colors = {
        "90%+": "#6cc644",
        "80–89%": "#4eaa5a",
        "70–79%": "#f0b232",
        "60–69%": "#e89030",
        "50–59%": "#c7322e",
    }
    tiers = group_by_tier(deals)
    max_t = max((len(ds) for _, ds in tiers), default=1) or 1
    bars_html = ""
    for name, ds in tiers:
        pct = len(ds) / max_t * 100
        color = tier_colors.get(name, "#66c0f4")
        bars_html += f'<div class="hbar-row"><span class="hbar-label">{name}</span><div class="hbar-track"><div class="hbar-fill" style="width:{pct}%;background:{color}">{len(ds)}</div></div><span class="hbar-value">{len(ds)}</span></div>\n'
    disc_html = f'<div class="dash-card"><h3>&#128200; Descuentos</h3>{bars_html}</div>'

    # Deck + ProtonDB stacked bars
    dk_counts = {3: 0, 2: 0, 1: 0, 0: 0}
    for d in deals:
        dk_counts[deck_compat_data.get(d["appid"], 0)] = (
            dk_counts.get(deck_compat_data.get(d["appid"], 0), 0) + 1
        )
    dk_colors = {
        3: ("#6cc644", "Verified"),
        2: ("#f0b232", "Playable"),
        1: ("#c7322e", "Unsupported"),
        0: ("#555", "Unknown"),
    }
    dk_segs = ""
    dk_legend = ""
    for cat in (3, 2, 1, 0):
        if dk_counts[cat] > 0:
            pct = dk_counts[cat] / total * 100
            color, label = dk_colors[cat]
            dk_segs += f'<div class="stacked-seg" style="width:{pct}%;background:{color}">{dk_counts[cat] if pct > 5 else ""}</div>'
            dk_legend += f'<span class="legend-item"><span class="legend-dot" style="background:{color}"></span>{label} ({dk_counts[cat]})</span>'

    pdb_counts = {}
    for d in deals:
        pdb = (protondb_data or {}).get(d["appid"])
        if pdb:
            t = pdb.get("tier", "")
            pdb_counts[t] = pdb_counts.get(t, 0) + 1
    pdb_colors = {
        "native": "#6cc644",
        "platinum": "#b4c7dc",
        "gold": "#d4a84b",
        "silver": "#a8a8a8",
        "bronze": "#cd7f32",
        "borked": "#c7322e",
    }
    pdb_segs = ""
    pdb_legend = ""
    for t in ("native", "platinum", "gold", "silver", "bronze", "borked"):
        c = pdb_counts.get(t, 0)
        if c > 0:
            pct = c / total * 100
            pdb_segs += f'<div class="stacked-seg" style="width:{pct}%;background:{pdb_colors[t]}">{c if pct > 5 else ""}</div>'
            pdb_legend += f'<span class="legend-item"><span class="legend-dot" style="background:{pdb_colors[t]}"></span>{t.title()} ({c})</span>'

    compat_html = f"""<div class="dash-card"><h3>&#127918; Deck / ProtonDB</h3>
  <div style="margin-bottom:.6rem"><div style="font-size:.75rem;color:var(--text-secondary);margin-bottom:.2rem">Steam Deck</div><div class="stacked-bar">{dk_segs}</div><div class="stacked-legend">{dk_legend}</div></div>
  <div><div style="font-size:.75rem;color:var(--text-secondary);margin-bottom:.2rem">ProtonDB</div><div class="stacked-bar">{pdb_segs}</div><div class="stacked-legend">{pdb_legend}</div></div>
</div>"""

    # Top tags bars
    tags_html = ""
    if tags_data:
        tag_groups = group_deals_by_tag(deals, tags_data)
        if tag_groups:
            max_tg = len(tag_groups[0][1]) if tag_groups else 1
            tg_bars = ""
            for tname, tdeals in tag_groups[:8]:
                pct = len(tdeals) / max_tg * 100
                tg_bars += f'<div class="hbar-row"><span class="hbar-label">{_html_esc(tname)}</span><div class="hbar-track"><div class="hbar-fill" style="width:{pct}%;background:var(--accent-blue)">{len(tdeals)}</div></div><span class="hbar-value">{len(tdeals)}</span></div>\n'
            tags_html = (
                f'<div class="dash-card"><h3>&#127991; Top Tags</h3>{tg_bars}</div>'
            )

    return f"""<details open class="dashboard">
  <summary>&#128202; Dashboard</summary>
  <div class="dash-grid">
    {fin_html}
    {disc_html}
    {compat_html}
    {tags_html}
  </div>
</details>"""


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
) -> str:
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
            local_trends=local_trends,
            price_history=price_history,
            group_by_tier=group_by_tier,
            group_deals_by_tag=group_deals_by_tag,
        )
    today_obj = date.today()
    today = f"{today_obj.day} de {MESES[today_obj.month]} de {today_obj.year}"
    priorities = priorities or {}
    historical_lows = historical_lows or {}
    previous_appids = previous_appids or set()
    reviews = reviews or {}
    deck_compat_data = deck_compat or {}
    current_prices = current_prices or {}
    top_picks = top_picks or []
    achievements_data = achievements_data or {}
    watchlist_alerts = watchlist_alerts or []
    local_trends = local_trends or {}
    price_history_games = (price_history or {}).get("games", {})
    has_itad = bool(historical_lows)
    has_best = bool(current_prices)
    has_ach = bool(achievements_data)
    has_sparklines = bool(price_history_games)

    # Stats
    total_deals = len(deals)
    avg_disc = sum(d["discount"] for d in deals) / total_deals if total_deals else 0
    avg_price = (
        sum(_html_price_raw(d["price_final"]) for d in deals) / total_deals
        if total_deals
        else 0
    )
    verified = sum(1 for d in deals if deck_compat_data.get(d["appid"]) == 3)
    new_count = (
        sum(1 for d in deals if previous_appids and d["appid"] not in previous_appids)
        if previous_appids
        else 0
    )

    parts = []

    # ── Stats bar ──
    sale_html = (
        f'Evento: <span class="sale-badge">&#127991; {_html_esc(sale_name)}</span> | '
        if sale_name
        else ""
    )
    pills = [
        f'<span class="pill">{len(wishlist_appids):,} en wishlist</span>',
        f'<span class="pill pill-accent" id="stat-deals">{total_deals:,} deals (&ge;{min_discount}%)</span>',
        f'<span class="pill" id="stat-avg-disc">Promedio: -{avg_disc:.0f}%</span>',
        f'<span class="pill" id="stat-avg-price">Precio medio: ${avg_price:.0f}</span>',
        f'<span class="pill">{verified} Deck Verified</span>',
    ]
    if new_count:
        pills.append(f'<span class="pill pill-new">{new_count} nuevos</span>')
    parts.append(f"""<header class="stats-bar">
  <h1>Steam Deals &mdash; {_html_esc(vanity)}</h1>
  <div class="stats-meta">{sale_html}{today} | Precios en MXN</div>
  <div class="stats-pills">{"".join(pills)}</div>
</header>""")

    # ── Dashboard ──
    parts.append(
        _build_dashboard_html(
            deals, reviews, deck_compat_data, tags_data or {}, protondb_data or {}
        )
    )

    # ── Top Picks ──
    if top_picks:
        cards = []
        for idx, tp in enumerate(top_picks, 1):
            rank_cls = (
                "rank-gold"
                if idx == 1
                else "rank-silver"
                if idx == 2
                else "rank-bronze"
                if idx == 3
                else ""
            )
            rev_html = _html_review_badge(tp.get("review"))
            dk_html = _html_deck_badge(tp.get("deck", 0))
            mc_html = _html_metacritic_badge(tp.get("metacritic_score"))
            mp_html = _html_multiplayer_badges(tp.get("categories", []))
            prio_html = _html_prio_badge(tp.get("priority", 0))
            header_img = HEADER_URL.format(appid=tp["appid"])
            store_url = STORE_URL.format(appid=tp["appid"])
            min_hist = historical_lows.get(tp["appid"])
            min_hist_str = f"${min_hist['price']:.0f}" if min_hist else ""
            tp_data = f'{{"name":"{_html_esc(tp["name"])}","appid":"{tp["appid"]}","price":"{_html_esc(tp["price_final"])}","price_original":"{_html_esc(tp.get("price_original", ""))}","discount":{tp["discount"]},"min_hist":"{min_hist_str}"}}'
            cards.append(f'''<div class="pick-card {rank_cls}">
  <a href="{store_url}" target="_blank" style="display:block">
    <img class="pick-img" src="{header_img}" alt="" loading="lazy" onerror="this.style.display='none'">
    <div class="pick-body">
      <div class="pick-rank">#{idx}</div>
      <div class="pick-score">{tp["score"]}</div>
      <div class="pick-name">{_html_esc(tp["name"])}{prio_html}</div>
      <div class="pick-details"><span class="pick-discount">-{tp["discount"]}%</span><span class="pick-price">{_html_esc(tp["price_final"])}</span></div>
      <div class="pick-meta">{rev_html} &middot; {mc_html} &middot; {dk_html} &middot; {mp_html}</div>
    </div>
  </a>
  <button class="share-btn-mini" onclick="openShareModal({tp_data})" title="Compartir">&#128279;</button>
</div>''')
        parts.append(f"""<section class="top-picks">
  <h2>&#127942; Top {len(top_picks)} Picks</h2>
  <p class="section-desc">Ranking: reviews (26%) + descuento (22%) + prioridad (18%) + $/hora HLTB (14%) + Deck (10%) + Metacritic (5%) + edad (5%).</p>
  <div class="picks-grid">{"".join(cards)}</div>
</section>""")

    # ── Watchlist Alerts ──
    if watchlist_alerts:
        wl_rows = []
        for wa in watchlist_alerts:
            savings = wa["target_price"] - (wa.get("price_raw", 0) / 100)
            savings_html = (
                f'<span style="color:var(--accent-green)">+${savings:.0f}</span>'
                if savings > 0
                else ""
            )
            capsule = CAPSULE_URL.format(appid=wa["appid"])
            wl_rows.append(f'''<div class="wl-card">
  <img src="{capsule}" alt="" loading="lazy" style="width:120px;height:45px;border-radius:4px;object-fit:cover" onerror="this.style.display='none'">
  <div class="wl-info">
    <div><strong>{_html_link(wa["name"], wa["appid"])}</strong></div>
    <div style="font-size:.85rem">{_html_esc(wa["price_final"])} <span style="color:var(--text-secondary)">(objetivo: ${wa["target_price"]:.0f})</span> {savings_html}</div>
    <div style="font-size:.8rem"><span class="pick-discount">-{wa["discount"]}%</span></div>
  </div>
</div>''')
        parts.append(f"""<section class="top-picks" style="margin-bottom:1.5rem">
  <h2>&#127919; Watchlist Alerts</h2>
  <p class="section-desc">{len(watchlist_alerts)} juegos alcanzaron tu precio objetivo</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.6rem">{"".join(wl_rows)}</div>
</section>""")

    # ── Budget Mode ──
    if budget_result:
        b = budget_result
        pct_used = b["total_spent"] / b["budget"] * 100 if b["budget"] > 0 else 0
        budget_rows = ""
        for idx, pick in enumerate(b["selected"], 1):
            capsule = CAPSULE_URL.format(appid=pick["appid"])
            budget_rows += f'''<tr>
  <td>{idx}</td><td>{pick.get("score", "—")}</td><td>-{pick["discount"]}%</td>
  <td>{_html_esc(pick["price_final"])}</td>
  <td><div class="game-cell"><img class="game-thumb" src="{capsule}" alt="" loading="lazy" onerror="this.style.display='none'"><span>{_html_link(pick["name"], pick["appid"])}</span></div></td>
</tr>'''
        parts.append(f"""<section style="margin-bottom:1.5rem">
  <h2>&#128176; Budget Mode &mdash; ${b["budget"]:.0f} MXN</h2>
  <p class="section-desc">Con ${b["budget"]:.0f} MXN puedes comprar {b["games_count"]} juegos &middot; Ahorro: ${b["total_savings"]:.0f} &middot; Restante: ${b["remaining"]:.0f}</p>
  <div style="background:var(--bg-secondary);border-radius:6px;height:24px;margin-bottom:.8rem;overflow:hidden;position:relative">
    <div style="height:100%;width:{pct_used:.0f}%;background:linear-gradient(90deg,var(--accent-blue),#4b9cd3);border-radius:6px"></div>
    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:600;color:var(--text-primary)">${b["total_spent"]:.0f} / ${b["budget"]:.0f} ({pct_used:.0f}%)</div>
  </div>
  <div class="table-wrap"><table class="deals-table"><thead><tr><th>#</th><th>Score</th><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>{budget_rows}</tbody></table></div>
</section>""")

    # ── Wishlist Comparison ──
    if compare_data:
        friend = compare_data.get("friend_vanity", "?")
        overlap = compare_data.get("overlap", set())
        overlap_deals = [d for d in deals if d["appid"] in overlap]
        comp_html = f"""<section style="margin-bottom:1.5rem">
  <h2>&#128101; Wishlist Comparison &mdash; {_html_esc(friend)}</h2>
  <p class="section-desc">{len(overlap)} juegos en com&uacute;n"""
        if overlap_deals:
            comp_html += f" &middot; {len(overlap_deals)} en oferta"
        comp_html += "</p>"
        if overlap_deals:
            ol_rows = ""
            for d in sorted(overlap_deals, key=lambda x: -x["discount"])[:20]:
                capsule = CAPSULE_URL.format(appid=d["appid"])
                ol_rows += f'<tr><td>-{d["discount"]}%</td><td>{_html_esc(d["price_final"])}</td><td><div class="game-cell"><img class="game-thumb" src="{capsule}" alt="" loading="lazy" onerror="this.style.display=\'none\'"><span>{_html_link(d["name"], d["appid"])}</span></div></td></tr>'
            comp_html += f'<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">En com&uacute;n y en oferta</h3><div class="table-wrap"><table class="deals-table"><thead><tr><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>{ol_rows}</tbody></table></div>'
        gift_ideas_list = gift_ideas or []
        if gift_ideas_list:
            gi_rows = ""
            for g in gift_ideas_list[:20]:
                capsule = CAPSULE_URL.format(appid=g["appid"])
                gi_rows += f'<tr><td>-{g["discount"]}%</td><td>{_html_esc(g["price_final"])}</td><td><div class="game-cell"><img class="game-thumb" src="{capsule}" alt="" loading="lazy" onerror="this.style.display=\'none\'"><span>{_html_link(g["name"], g["appid"])}</span></div></td></tr>'
            comp_html += f'<h3 style="font-size:.95rem;margin:.8rem 0 .4rem">&#127873; Gift Ideas para {_html_esc(friend)}</h3><div class="table-wrap"><table class="deals-table"><thead><tr><th>%</th><th>Precio</th><th>Juego</th></tr></thead><tbody>{gi_rows}</tbody></table></div>'
        comp_html += "</section>"
        parts.append(comp_html)

    # ── Filters ──
    parts.append(f'''<details open class="filter-panel">
  <summary>&#128269; Filtros</summary>
  <div class="filter-grid">
    <div class="filter-group"><label>Buscar juego</label><input type="text" id="f-search" placeholder="Nombre..." oninput="applyFilters()"></div>
    <div class="filter-group"><label>Descuento min: <output id="f-disc-val">{min_discount}%</output></label><input type="range" id="f-discount" min="50" max="100" value="{min_discount}" oninput="document.getElementById('f-disc-val').textContent=this.value+'%';applyFilters()"></div>
    <div class="filter-group"><label>Precio max: <output id="f-price-val">Sin limite</output></label><input type="range" id="f-price-max" min="0" max="2000" value="2000" step="10" oninput="document.getElementById('f-price-val').textContent=this.value>=2000?'Sin limite':'$'+this.value;applyFilters()"></div>
    <div class="filter-group"><label>Steam Deck</label><select id="f-deck" onchange="applyFilters()"><option value="all">Todos</option><option value="3">Verified</option><option value="2">Playable</option><option value="1">Unsupported</option></select></div>
    <div class="filter-group"><label>Reviews min: <output id="f-rev-val">0%</output></label><input type="range" id="f-reviews" min="0" max="100" value="0" oninput="document.getElementById('f-rev-val').textContent=this.value+'%';applyFilters()"></div>
    <div class="filter-group"><label><input type="checkbox" id="f-new-only" onchange="applyFilters()"> Solo nuevos</label></div>
    <div class="filter-group"><button onclick="resetFilters()" class="btn-reset">Limpiar filtros</button> <button onclick="copyForSheets()" class="btn-reset" title="Copiar datos visibles como TSV para pegar en Google Sheets/Excel">&#128203; Copiar para Sheets</button></div>
  </div>
</details>''')

    # ── Tier tables ──
    for tier_name, tier_deals in group_by_tier(deals):
        tier_deals.sort(
            key=lambda d: (
                priorities.get(d["appid"], 0) == 0,
                priorities.get(d["appid"], 9999),
            )
        )
        tid = re.sub(r"[^a-z0-9]", "", tier_name.lower())

        # Headers
        cols = [
            ("", "text"),
            ("%", "num"),
            ("Precio", "price"),
            ("Era", "price"),
            ("Reviews", "num"),
            ("MC", "num"),
            ("Deck", "text"),
            ("Modo", "text"),
        ]
        if has_ach:
            cols.append(("Logros", "num"))
        if has_sparklines:
            cols.append(("Trend", "text"))
        if has_itad:
            cols.append(("Min. hist.", "price"))
        if has_best:
            cols.append(("Mejor precio", "price"))
        cols.append(("Juego", "text"))

        ths = "".join(
            f"<th onclick=\"sortTable('t-{tid}',{i},'{ct}')\">{_html_esc(h)} <span class=\"sort-arrow\">&#9650;&#9660;</span></th>"
            for i, (h, ct) in enumerate(cols)
        )

        rows = []
        for d in tier_deals:
            appid = d["appid"]
            is_new = bool(previous_appids and appid not in previous_appids)
            new_html = '<span class="badge new-badge">NUEVO</span>' if is_new else ""
            rev = reviews.get(appid)
            rev_pct = rev["pct"] if rev else -1
            dk = deck_compat_data.get(appid, 0)
            prio = priorities.get(appid, 0)
            price_num = _html_price_raw(d["price_final"])

            mc = d.get("metacritic_score")
            mp_cats = d.get("categories", [])
            cells = [
                f"<td>{new_html}</td>",
                f"<td>-{d['discount']}%</td>",
                f"<td>{_html_esc(d['price_final'])}</td>",
                f"<td>{_html_esc(d['price_original'])}</td>",
                f"<td>{_html_review_badge(rev)}</td>",
                f"<td>{_html_metacritic_badge(mc)}</td>",
                f"<td>{_html_deck_badge(dk)}</td>",
                f"<td>{_html_multiplayer_badges(mp_cats)}</td>",
            ]
            if has_ach:
                ach = achievements_data.get(appid)
                cells.append(f"<td>{_html_achievements_badge(ach)}</td>")
            if has_sparklines:
                game_hist = price_history_games.get(appid, {})
                snaps = game_hist.get("snapshots", [])
                spark = _build_sparkline_svg(snaps) if len(snaps) >= 2 else "\u2014"
                cells.append(f"<td>{spark}</td>")
            if has_itad:
                low = historical_lows.get(appid)
                if low:
                    low_txt = f"${low['price']:.0f} ({low['date']})"
                    cells.append(f"<td>{_html_esc(low_txt)}</td>")
                else:
                    cells.append("<td>\u2014</td>")
            if has_best:
                bp = current_prices.get(appid)
                if bp:
                    bp_html = f'${bp["price"]:.0f} en <a href="{bp["url"]}" target="_blank">{_html_esc(bp["store"])}</a>'
                    cells.append(f"<td>{bp_html}</td>")
                else:
                    cells.append("<td>\u2014</td>")
            capsule_img = CAPSULE_URL.format(appid=appid)
            desc_attr = (
                f' title="{_html_esc(d.get("description", ""))}"'
                if d.get("description")
                else ""
            )
            min_hist = historical_lows.get(appid)
            min_hist_str = f"${min_hist['price']:.0f}" if min_hist else ""
            game_data = f'{{"name":"{_html_esc(d["name"])}","appid":"{appid}","price":"{_html_esc(d["price_final"])}","price_original":"{_html_esc(d["price_original"])}","discount":{d["discount"]},"min_hist":"{min_hist_str}"}}'
            name_html = (
                f'<div class="game-cell">'
                f'<img class="game-thumb" src="{capsule_img}" alt="" loading="lazy" onerror="this.style.display=\'none\'">'
                f"<span{desc_attr}>{_html_link(d['name'], appid)}{_html_prio_badge(prio)}</span>"
                f'<button class="share-btn-mini" onclick="openShareModal({game_data})" title="Compartir" style="margin-left:.4rem;position:relative;top:-1px">&#128279;</button>'
                f"</div>"
            )
            cells.append(f"<td>{name_html}</td>")

            data_attrs = f'data-discount="{d["discount"]}" data-price="{price_num}" data-deck="{dk}" data-review="{rev_pct}" data-name="{_html_esc(d["name"].lower())}" data-new="{"1" if is_new else "0"}"'
            rows.append(f"<tr {data_attrs}>{''.join(cells)}</tr>")

        parts.append(f"""<details open class="tier-section">
  <summary class="tier-header">{_html_esc(tier_name)} de Descuento <span class="tier-count">(<span class="visible-count">{len(tier_deals)}</span> juegos)</span></summary>
  <div class="table-wrap"><table class="deals-table" id="t-{tid}"><thead><tr>{ths}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
</details>""")

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Steam Deals &mdash; {_html_esc(vanity)}</title><style>{_HTML_CSS}</style></head>
<body>
{"".join(parts)}
<script>{_HTML_JS}</script>
</body>
</html>"""


# ─────────────────────────────────────────────
# GENERAR CSV
# ─────────────────────────────────────────────

def generate_share_html(deals, vanity, min_discount, sale_name="", top_picks=None, reviews=None, deck_compat=None):
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
        )
    reviews = reviews or {}
    deck_compat = deck_compat or {}
    top_picks = top_picks or []
    today = date.today().strftime("%Y-%m-%d")
    title = f"Steam Deals — {vanity}"
    rows = ""
    for d in deals:
        appid = d["appid"]
        rev = reviews.get(appid)
        rev_str = f"{rev['desc']} ({rev['pct']}%)" if rev else ""
        dk = deck_compat.get(appid, 0)
        dk_str = {3: "Verified", 2: "Playable"}.get(dk, "")
        capsule = CAPSULE_URL.format(appid=appid)
        store = STORE_URL.format(appid=appid)
        rows += f'<tr><td>-{d["discount"]}%</td><td>{_html_esc(d["price_final"])}</td><td>{rev_str}</td><td>{dk_str}</td><td><div style="display:flex;align-items:center;gap:.4rem"><img src="{capsule}" style="width:80px;height:30px;object-fit:cover;border-radius:3px" loading="lazy" onerror="this.style.display=\'none\'"><a href="{store}" target="_blank">{_html_esc(d["name"])}</a></div></td></tr>\n'

    picks_html = ""
    if top_picks:
        pick_cards = ""
        for idx, tp in enumerate(top_picks[:5], 1):
            header = HEADER_URL.format(appid=tp["appid"])
            store = STORE_URL.format(appid=tp["appid"])
            pick_cards += f'<a href="{store}" target="_blank" style="text-decoration:none;color:inherit;background:#16202d;border:1px solid #2a475e;border-radius:6px;overflow:hidden;display:flex;flex-direction:column"><img src="{header}" style="width:100%;aspect-ratio:460/215;object-fit:cover" loading="lazy"><div style="padding:.4rem .6rem"><div style="font-size:1.2rem;font-weight:bold;color:#66c0f4">{tp["score"]}</div><div style="font-size:.8rem;margin:.2rem 0">{_html_esc(tp["name"])}</div><div style="font-size:.8rem"><span style="color:#6cc644">-{tp["discount"]}%</span> {_html_esc(tp["price_final"])}</div></div></a>'
        picks_html = f'<h2 style="margin:1rem 0 .5rem">Top Picks</h2><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.5rem">{pick_cards}</div>'

    sale_line = f" — {_html_esc(sale_name)}" if sale_name else ""
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{_html_esc(title)}</title>
<style>{{*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:system-ui,sans-serif;background:#1b2838;color:#c7d5e0;padding:1rem;max-width:1000px;margin:0 auto}}a{{color:#66c0f4;text-decoration:none}}a:hover{{text-decoration:underline}}h1{{font-size:1.3rem;margin-bottom:.3rem}}table{{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:.5rem}}th{{background:#2a475e;padding:.4rem .5rem;text-align:left;border-bottom:2px solid #2a475e}}td{{padding:.35rem .5rem;border-bottom:1px solid #2a475e}}tr:hover{{background:#1a3a5c}}.meta{{color:#8f98a0;font-size:.85rem;margin-bottom:1rem}}.share-modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;align-items:center;justify-content:center}}.share-modal.active{{display:flex}}.share-modal-content{{background:#16202d;border:1px solid #2a475e;border-radius:12px;padding:1.5rem;max-width:420px;width:90%}}.share-modal h3{{color:#66c0f4;margin-bottom:1rem;font-size:1.1rem}}.share-game-info{{background:#1b2838;border-radius:8px;padding:1rem;margin-bottom:1rem}}.share-game-name{{font-weight:600;font-size:1rem;margin-bottom:.5rem}}.share-game-price{{color:#6cc644;font-size:1.2rem;font-weight:700}}.share-game-price span{{text-decoration:line-through;color:#8f98a0;font-weight:400;font-size:.9rem}}.share-game-minhist{{font-size:.8rem;color:#8f98a0;margin-top:.3rem}}.share-game-minhist span{{color:#f0b232}}.share-actions{{display:flex;flex-direction:column;gap:.6rem}}.share-btn{{padding:.6rem 1rem;border-radius:6px;font-size:.85rem;font-weight:600;cursor:pointer;text-align:center}}.share-btn-copy-app{{background:#66c0f4;color:#000;border:none}}.share-btn-copy-app:hover{{background:#4db8e8}}.share-btn-copy-steam{{background:#2a475e;color:#c7d5e0;border:1px solid #2a475e}}.share-btn-copy-steam:hover{{border-color:#66c0f4}}.share-btn-open{{background:#1b2838;color:#8f98a0;border:1px solid #2a475e}}.share-close{{margin-top:.8rem;text-align:center;color:#8f98a0;font-size:.85rem;cursor:pointer}}.share-close:hover{{color:#c7d5e0}}</style>
</head><body>
<h1>&#127918; {_html_esc(title)}{sale_line}</h1>
<div class="meta">{today} | {len(deals)} deals (&ge;{min_discount}%) | Precios en MXN</div>
{picks_html}
<h2 style="margin:1rem 0 .5rem">Todos los Deals</h2>
<table><thead><tr><th>%</th><th>Precio</th><th>Reviews</th><th>Deck</th><th>Juego</th></tr></thead><tbody>{rows}</tbody></table>
<div style="margin-top:1.5rem;text-align:center;color:#8f98a0;font-size:.75rem">Generado con Steam Deals Generator</div>

<!-- Share Modal -->
<div class="share-modal" id="share-modal">
  <div class="share-modal-content">
    <h3>Compartir Deal</h3>
    <div class="share-game-info">
      <div class="share-game-name" id="share-name"></div>
      <div class="share-game-price" id="share-price"></div>
      <div class="share-game-minhist" id="share-minhist"></div>
    </div>
    <div class="share-actions">
      <button class="share-btn share-btn-copy-app" id="btn-copy-app" onclick="copyShareLink()">Copiar link steamtools://</button>
      <button class="share-btn share-btn-copy-steam" onclick="copySteamLink()">Copiar link de Steam</button>
      <button class="share-btn share-btn-open" onclick="openInSteam()">Abrir en Steam</button>
    </div>
    <div class="share-close" onclick="closeShareModal()">Cerrar</div>
  </div>
</div>
<script>let currentShareData=null,currentSteamUrl='';function openShareModal(game){{currentShareData=game;currentSteamUrl='https://store.steampowered.com/app/'+game.appid+'/';document.getElementById('share-name').textContent=game.name||'';document.getElementById('share-price').innerHTML=(game.price_original&&game.price?'<span>$'+game.price_original+' </span>':'')+(game.price||'')+(game.discount?' ('+game.discount+'% OFF)':'');document.getElementById('share-minhist').innerHTML=game.min_hist?'Minimo historico: <span>$'+game.min_hist+'</span>':'';document.getElementById('share-modal').classList.add('active')}}function closeShareModal(){{document.getElementById('share-modal').classList.remove('active');currentShareData=null}}function copyShareLink(){{if(!currentShareData)return;const encoded=btoa(JSON.stringify(currentShareData));const shareUrl='steamtools://share?data='+encoded;navigator.clipboard.writeText(shareUrl).then(()=>{{const btn=document.getElementById('btn-copy-app');btn.textContent='Copiado!';setTimeout(()=>btn.textContent='Copiar link steamtools://',2000)}})}}function copySteamLink(){{if(!currentSteamUrl)return;navigator.clipboard.writeText(currentSteamUrl).then(()=>{{const btn=document.querySelector('.share-btn-copy-steam');btn.textContent='Copiado!';setTimeout(()=>btn.textContent='Copiar link de Steam',2000)}})}}function openInSteam(){{if(currentSteamUrl)window.open(currentSteamUrl,'_blank')}}</script>
</body></html>"""


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
    return _build_notification_summary_impl(deals, comparison, top_picks, watchlist_alerts=watchlist_alerts)


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
    WEB_EVENT_MODE = bool(WEB_RUN)
    if not WEB_RUN and not INTERACTIVE:
        print(
            f"  {_dim('Flujo recomendado: wizard web (python3 steam_deals_web.py).')}"
        )
        print(
            f"  {_dim('CLI disponible con flags/config, o modo interactivo con --interactive.')}\n"
        )
    RATE_LIMIT = 1.5
    t0 = time.monotonic()

    # Calcular total de pasos dinámicamente (+2 reviews/deck, +1 protondb/ac, +1 tags, +1 HTML, owned solo con key)
    TOTAL = (
        11
        + (1 if KEY else 0)
        + (1 if FAMILY_JSON else 0)
        + (1 if HLTB_CSV else 0)
        + (1 if ITAD_KEY else 0)
        + (1 if FILTERS.get("csv") else 0)
        + (1 if FILTERS.get("telegram_token") or FILTERS.get("discord_webhook") else 0)
        + (1 if FILTERS.get("compare") else 0)
    )

    if not KEY:
        print(f"  {_dim('Sin API Key — modo público (wishlist debe ser pública)')}")
    _n = [0]

    def step(msg: str):
        _n[0] += 1
        if _report_step_impl is not None:
            _report_step_impl(
                _n[0],
                TOTAL,
                msg,
                emit=print,
                emit_event_fn=emit_event,
                bold_fn=_bold,
                color_cyan=C.CYN,
                color_reset=C.RST,
            )
            return
        print(f"\n{C.CYN}[{_n[0]}/{TOTAL}]{C.RST} {_bold(msg)}", flush=True)
        emit_event("progress", current=_n[0], total=TOTAL, label=msg)

    # Validar rutas opcionales antes de arrancar
    if HLTB_CSV and not HLTB_CSV.exists():
        print(f"{_err(f'HLTB CSV no encontrado: {HLTB_CSV}')}")
        HLTB_CSV = None
    if FAMILY_JSON and not FAMILY_JSON.exists():
        print(f"{_err(f'Family JSON no encontrado: {FAMILY_JSON}')}")
        FAMILY_JSON = None

    # [1] Steam ID
    step("Resolviendo Steam ID...")
    steam_id = resolve_steam_id(KEY, VANITY)
    print(f"  {_ok(steam_id)}")

    # [2] Wishlist (con prioridad)
    step("Obteniendo wishlist...")
    wishlist_appids, priorities = get_wishlist(KEY, steam_id)
    ranked = sum(1 for p in priorities.values() if p > 0)
    print(f"  {_ok(f'{len(wishlist_appids):,} juegos ({ranked:,} con prioridad)')}")

    # [3] Biblioteca propia (requiere API key)
    owned: dict[str, str] = {}
    if KEY:
        step("Obteniendo biblioteca de Steam...")
        owned = get_owned_games(KEY, steam_id)
        print(f"  {_ok(f'{len(owned):,} juegos comprados')}")

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
            print(
                f"  {_ok(f'Friend: {len(compare_data['friend_appids']):,} juegos en wishlist')}"
            )
            print(f"  {_ok(f'{len(overlap)} en común')}")
        except Exception as e:
            print(f"  {_err(f'No se pudo comparar: {e}')}")
            compare_data = None

    # [4] Detectar oferta activa
    step("Detectando oferta activa de Steam...")
    sale_name = get_active_sale()
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
        print(f"  {_dim(f'MD anterior encontrado ({len(previous_appids)} deals) — fallback')}")

    # [5] Precios (con smart cache + batching)
    step("Obteniendo precios de Steam...")
    fetched_cache, cache_age = load_price_cache(steam_id)

    price_cache_policy = select_scoped_cache(
        wishlist_appids,
        fetched_cache,
        cache_age,
        no_cache=no_cache,
        ttl_hours=CACHE_MAX_HOURS,
    )
    fetched_cache = price_cache_policy.cache

    if price_cache_policy.status == "bypass":
        clear_cache_files(
            [
                REVIEWS_CACHE_FILE,
                DECK_CACHE_FILE,
                TAGS_CACHE_FILE,
                PROTONDB_CACHE_FILE,
                ANTICHEAT_CACHE_FILE,
                ACHIEVEMENTS_CACHE_FILE,
            ]
        )
        print(f"  {_warn('--no-cache: ignorando caché existente')}")
    elif price_cache_policy.status == "valid":
        new_appids = price_cache_policy.missing_ids
        status_msg = (
            f"{len(new_appids)} nuevos por fetchear"
            if new_appids
            else _dim("sin nuevos, skip fetch")
        )
        print(f"  {_ok(f'Caché válida ({cache_age:.1f}h)')} — {status_msg}")
    elif price_cache_policy.status == "expired":
        print(f"  {_warn(f'Caché expirada ({cache_age:.0f}h) — re-fetching todo')}")
    else:
        print(f"  {_dim('Sin caché — fetch completo')}")

    try:
        deals, n_fetched = get_deals_from_wishlist(
            wishlist_appids,
            fetched_cache,
            steam_id,
            country="mx",
            min_discount=MIN_DISCOUNT,
            rate_limit=RATE_LIMIT,
        )
    except KeyboardInterrupt:
        print(f"\n  {_warn('Interrumpido — guardando caché parcial...')}")
        save_price_cache(steam_id, fetched_cache)
        print(
            f"  {_ok('Caché guardada. Ejecuta de nuevo para continuar donde quedó.')}"
        )
        sys.exit(1)

    if n_fetched > 0:
        save_price_cache(steam_id, fetched_cache)
        print(
            f"  {_ok(f'{len(deals):,} deals (≥{MIN_DISCOUNT}%) — caché actualizada')}"
        )
    else:
        print(f"  {_ok(f'{len(deals):,} deals (≥{MIN_DISCOUNT}%) — desde caché')}")

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
    save_run_history(steam_id, VANITY, sale_name, MIN_DISCOUNT, deals)

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
    )
    hltb_hours = post_processing_outputs.hltb_hours
    deals = post_processing_outputs.deals
    top_picks = post_processing_outputs.top_picks

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
        **family_renderer_kwargs,
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
        local_trends=local_trends,
        price_history=price_history,
        **family_renderer_kwargs,
    )

    # Generar HTML compartible (lightweight)
    share_html = generate_share_html(deals, VANITY, MIN_DISCOUNT, sale_name=sale_name,
                                      top_picks=top_picks, reviews=reviews_data, deck_compat=deck_data)

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
            csv_content=csv_content,
        ),
    )
    print(f"  {_ok(str(written_artifacts['markdown']))}")
    print(f"  {_ok(str(written_artifacts['html']))}")
    print(f"  {_ok(str(written_artifacts['share_html']))}")
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


if __name__ == "__main__":
    run_scheduled()
