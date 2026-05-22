from __future__ import annotations

import argparse
import sys
from pathlib import Path

from steam_deals_paths import resolve_reports_output_dir
from shared_web_infra import resolve_config_secret
from shared.io_utils import load_json_file as _default_load_json_file
from shared.io_utils import write_json_file as _default_write_json_file


CONFIG_FILE = Path.home() / ".config" / "steam_deals.json"


def load_user_config(
    config_file: Path = CONFIG_FILE, *, load_json_file=_default_load_json_file
) -> dict:
    return load_json_file(config_file, {})


def save_user_config(
    config_file: Path, cfg: dict, *, write_json_file=_default_write_json_file
) -> None:
    write_json_file(config_file, cfg, ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Steam Wishlist Deals Generator")
    parser.add_argument("--web-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Habilita prompts en terminal para configurar valores faltantes",
    )
    parser.add_argument(
        "--key", help="Steam API Key (opcional, habilita sección de juegos propios)"
    )
    parser.add_argument(
        "--vanity", help="Vanity URL, Steam ID, o link de perfil de Steam"
    )
    parser.add_argument("--hltb", help="Ruta al CSV de HLTB")
    parser.add_argument("--output", help="Directorio de salida para reportes")
    parser.add_argument("--discount", type=int, help="Descuento mínimo %%")
    parser.add_argument(
        "--genre",
        nargs="*",
        metavar="GENRE",
        help="Géneros de interés (ej. --genre roguelike --genre indie)",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Re-fetch aunque haya caché válida"
    )
    parser.add_argument(
        "--free-weekend-live",
        action="store_true",
        help="Opt-in: consultar Store JSON para Free Weekend con caché separado",
    )
    parser.add_argument(
        "--warm-cache",
        action="store_true",
        help="Precalienta caché de precios y sale sin generar reportes",
    )
    parser.add_argument(
        "--family-json",
        nargs="?",
        const="",
        default=None,
        help="Ruta al JSON de biblioteca familiar. Sin valor = omitir",
    )
    parser.add_argument(
        "--wishlist-external-matches-json",
        help="Ruta al JSON local de matches externos para wishlist hygiene",
    )
    parser.add_argument(
        "--itad-key", help="IsThereAnyDeal API Key (para mínimo histórico)"
    )
    parser.add_argument(
        "--itad-external-offers-cache",
        help="Ruta a caché JSON local ITAD para external_offers (sin red live)",
    )
    parser.add_argument(
        "--itad-refresh-external-offers-cache",
        action="store_true",
        help="Opt-in: refresca en vivo la caché local ITAD external_offers",
    )
    parser.add_argument(
        "--max-price", type=float, metavar="N", help="Solo deals bajo N MXN"
    )
    parser.add_argument(
        "--deck-only", action="store_true", help="Solo Deck Verified o Playable"
    )
    parser.add_argument(
        "--deck-verified", action="store_true", help="Solo Deck Verified"
    )
    parser.add_argument(
        "--min-reviews",
        type=int,
        metavar="N",
        help="Solo juegos con >= N%% reviews positivas",
    )
    parser.add_argument(
        "--min-review-count",
        type=int,
        metavar="N",
        help="Solo juegos con >= N reviews totales",
    )
    parser.add_argument(
        "--max-hours", type=float, metavar="N", help="Solo juegos con HLTB <= N horas"
    )
    parser.add_argument(
        "--top", type=int, metavar="N", default=10, help="Top N picks (default: 10)"
    )
    parser.add_argument(
        "--sort",
        choices=["discount", "price", "reviews", "priority", "score"],
        default="discount",
        help="Ordenar tiers por campo",
    )
    parser.add_argument(
        "--new-only", action="store_true", help="Solo deals nuevos vs run anterior"
    )
    parser.add_argument(
        "--csv", action="store_true", help="Generar CSV para Excel/Sheets"
    )
    parser.add_argument(
        "--watchlist",
        nargs="*",
        metavar="CMD",
        help="Watchlist: add APPID PRECIO / remove APPID / list",
    )
    parser.add_argument(
        "--budget",
        type=float,
        metavar="MXN",
        help="Presupuesto en MXN — recomendación óptima de compras",
    )
    parser.add_argument(
        "--compare",
        metavar="VANITY2",
        help="Comparar tu wishlist con otro perfil de Steam",
    )
    parser.add_argument(
        "--telegram-token", help="Telegram Bot API token para notificaciones"
    )
    parser.add_argument("--telegram-chat", help="Telegram chat ID para notificaciones")
    parser.add_argument(
        "--discord-webhook", help="Discord webhook URL para notificaciones"
    )
    parser.add_argument(
        "--schedule",
        type=float,
        metavar="HOURS",
        help="Ejecutar automáticamente cada N horas (ej: --schedule 6)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        metavar="N",
        help="Workers de fetch paralelo para enrichment (default: 16)",
    )
    parser.add_argument(
        "--md-frontmatter",
        action="store_true",
        help="Incluir frontmatter YAML en Markdown (Obsidian/Notion)",
    )
    parser.add_argument(
        "--alert-rise-pct",
        type=float,
        metavar="PCT",
        help="Umbral de subida %% para alertas inteligentes (ej: 10 para >=10%%)",
    )
    parser.add_argument(
        "--alert-global-margin-pct",
        type=float,
        metavar="PCT",
        help="Margen %% sobre mínimo global para alertas (ej: 3 para <= mínimo+3%%)",
    )
    parser.add_argument(
        "--alert-score-min",
        type=float,
        metavar="SCORE",
        help="Score mínimo para priorizar alertas inteligentes (ej: 75)",
    )
    return parser


def _has_local_cache(script_path: Path) -> bool:
    local_cache_dir = script_path.parent / ".cache" / "steam_deals"
    return local_cache_dir.exists() and any(local_cache_dir.iterdir())


def _can_prompt(args, stdin, script_path: Path) -> bool:
    stdin_obj = stdin if stdin is not None else sys.stdin
    is_tty = bool(stdin_obj and hasattr(stdin_obj, "isatty") and stdin_obj.isatty())
    return bool(
        not args.web_run
        and is_tty
        and (args.interactive or not _has_local_cache(script_path))
    )


def _ask(input_fn, prompt: str, default=None, *, can_prompt: bool) -> str:
    if not can_prompt:
        return default or ""
    suffix = f" [{default}]" if default else ""
    try:
        return input_fn(f"  {prompt}{suffix}: ").strip()
    except EOFError:
        return default or ""


def _from_arg_cfg_or_ask(
    arg_val,
    cfg: dict,
    cfg_key: str,
    prompt: str,
    default,
    *,
    can_prompt: bool,
    interactive_keys: list[str],
    input_fn,
) -> str:
    if arg_val is not None:
        return arg_val
    if cfg.get(cfg_key) is not None:
        return cfg[cfg_key]
    if can_prompt:
        interactive_keys.append(cfg_key)
    raw = _ask(input_fn, prompt, default, can_prompt=can_prompt)
    return raw or default or ""


def _resolve_hltb(
    args, cfg: dict, *, can_prompt: bool, interactive_keys: list[str], input_fn
):
    if args.hltb:
        return Path(args.hltb).expanduser()
    if cfg.get("hltb"):
        return Path(cfg["hltb"]).expanduser()
    if can_prompt:
        interactive_keys.append("hltb")
    raw = _ask(
        input_fn, "Ruta al CSV de HLTB (Enter para omitir)", can_prompt=can_prompt
    )
    return Path(raw).expanduser() if raw else None


def _resolve_output_dir(
    args,
    cfg: dict,
    script_path: Path,
    *,
    can_prompt: bool,
    interactive_keys: list[str],
    input_fn,
) -> Path:
    if args.output:
        return Path(args.output).expanduser()
    if cfg.get("output_dir"):
        return Path(cfg["output_dir"]).expanduser()
    if can_prompt:
        interactive_keys.append("output_dir")
    default_output_dir = (
        resolve_reports_output_dir(script_path.parent, frozen=True)
        if getattr(sys, "frozen", False)
        else script_path.parent
    )
    raw = _ask(
        input_fn,
        "Directorio de salida para reportes",
        str(default_output_dir),
        can_prompt=can_prompt,
    )
    return Path(raw or default_output_dir).expanduser()


def _resolve_discount(
    args, cfg: dict, *, can_prompt: bool, interactive_keys: list[str], input_fn
) -> int:
    if args.discount is not None:
        return args.discount
    if cfg.get("discount") is not None:
        return cfg["discount"]
    if can_prompt:
        interactive_keys.append("discount")
    raw = _ask(input_fn, "Descuento mínimo %", "50", can_prompt=can_prompt)
    return int(raw) if raw else 50


def _resolve_genres(
    args, cfg: dict, *, can_prompt: bool, interactive_keys: list[str], input_fn
) -> list[str]:
    if args.genre is not None:
        return [genre.strip().lower() for genre in args.genre if genre.strip()]
    if cfg.get("genres") is not None:
        return cfg["genres"]
    if can_prompt:
        interactive_keys.append("genres")
    raw = _ask(
        input_fn,
        "Géneros de interés (coma-separados, Enter para omitir)",
        can_prompt=can_prompt,
    )
    return [genre.strip().lower() for genre in raw.split(",") if genre.strip()]


def _resolve_family_json(args, cfg: dict):
    if args.family_json is not None:
        return Path(args.family_json).expanduser() if args.family_json else None
    if cfg.get("family_json"):
        return Path(cfg["family_json"]).expanduser()
    return None


def _build_filters(args, cfg: dict, *, environ=None) -> dict:
    max_workers = (
        args.max_workers if args.max_workers is not None else cfg.get("max_workers")
    )
    itad_external_offers_cache = (
        args.itad_external_offers_cache or cfg.get("itad_external_offers_cache")
    )
    alert_rise_pct = (
        args.alert_rise_pct
        if args.alert_rise_pct is not None
        else cfg.get("alert_rise_pct")
    )
    alert_global_margin_pct = (
        args.alert_global_margin_pct
        if args.alert_global_margin_pct is not None
        else cfg.get("alert_global_margin_pct")
    )
    alert_score_min = (
        args.alert_score_min
        if args.alert_score_min is not None
        else cfg.get("alert_score_min")
    )
    return {
        "max_price": args.max_price,
        "deck_only": args.deck_only,
        "deck_verified": args.deck_verified,
        "min_reviews": args.min_reviews,
        "min_review_count": args.min_review_count,
        "max_hours": args.max_hours,
        "top": args.top,
        "sort": args.sort,
        "new_only": args.new_only,
        "csv": args.csv,
        "warm_cache": args.warm_cache,
        "free_weekend_live": bool(args.free_weekend_live or cfg.get("free_weekend_live")),
        "wishlist_external_matches_json": Path(args.wishlist_external_matches_json).expanduser()
        if args.wishlist_external_matches_json
        else None,
        "itad_external_offers_cache": Path(itad_external_offers_cache).expanduser()
        if itad_external_offers_cache
        else None,
        "itad_refresh_external_offers_cache": bool(args.itad_refresh_external_offers_cache),
        "budget": args.budget,
        "compare": args.compare,
        "telegram_token": resolve_config_secret(
            args.telegram_token,
            cfg,
            "telegram_token",
            environ=environ,
        ),
        "telegram_chat": args.telegram_chat or cfg.get("telegram_chat"),
        "discord_webhook": resolve_config_secret(
            args.discord_webhook,
            cfg,
            "discord_webhook",
            environ=environ,
        ),
        "schedule": args.schedule,
        "max_workers": max_workers,
        "md_frontmatter": bool(args.md_frontmatter),
        "alert_rise_pct": alert_rise_pct,
        "alert_global_margin_pct": alert_global_margin_pct,
        "alert_score_min": alert_score_min,
    }


def get_config(
    *,
    script_path: Path,
    load_user_config_fn=load_user_config,
    save_user_config_fn=None,
    handle_watchlist_command_fn=None,
    input_fn=input,
    stdin=None,
    exit_fn=None,
    argv=None,
    environ=None,
):
    if save_user_config_fn is None:
        save_user_config_fn = lambda cfg: save_user_config(CONFIG_FILE, cfg)
    args = build_parser().parse_args(argv)
    if args.watchlist is not None:
        if handle_watchlist_command_fn is not None:
            handle_watchlist_command_fn(args.watchlist)
        if exit_fn is None:
            raise SystemExit(0)
        exit_fn(0)
        return None

    cfg = load_user_config_fn()
    can_prompt = _can_prompt(args, stdin, script_path)
    interactive_keys: list[str] = []
    key = resolve_config_secret(args.key, cfg, "key", environ=environ) or None
    vanity = (
        _from_arg_cfg_or_ask(
            args.vanity,
            cfg,
            "vanity",
            "Vanity URL, Steam ID, o link de perfil",
            "gaben",
            can_prompt=can_prompt,
            interactive_keys=interactive_keys,
            input_fn=input_fn,
        )
        or "gaben"
    )
    hltb = _resolve_hltb(
        args,
        cfg,
        can_prompt=can_prompt,
        interactive_keys=interactive_keys,
        input_fn=input_fn,
    )
    output_dir = _resolve_output_dir(
        args,
        cfg,
        script_path,
        can_prompt=can_prompt,
        interactive_keys=interactive_keys,
        input_fn=input_fn,
    )
    discount = _resolve_discount(
        args,
        cfg,
        can_prompt=can_prompt,
        interactive_keys=interactive_keys,
        input_fn=input_fn,
    )
    genres = _resolve_genres(
        args,
        cfg,
        can_prompt=can_prompt,
        interactive_keys=interactive_keys,
        input_fn=input_fn,
    )
    family_json = _resolve_family_json(args, cfg)
    itad_key = resolve_config_secret(args.itad_key, cfg, "itad_key", environ=environ) or None
    no_cache = args.no_cache

    if can_prompt and interactive_keys:
        raw = (
            input_fn("\n  ¿Guardar como configuración por defecto? [s/N]: ")
            .strip()
            .lower()
        )
        if raw == "s":
            save_user_config_fn(
                {
                    **cfg,
                    "key": key,
                    "vanity": vanity,
                    "hltb": str(hltb) if hltb else None,
                    "output_dir": str(output_dir),
                    "discount": discount,
                    "genres": genres,
                    "family_json": str(family_json) if family_json else None,
                    "itad_key": itad_key,
                    "max_workers": args.max_workers
                    if args.max_workers is not None
                    else cfg.get("max_workers"),
                }
            )

    return (
        args.web_run,
        args.interactive,
        key,
        vanity,
        hltb,
        output_dir,
        discount,
        genres,
        no_cache,
        family_json,
        itad_key,
        _build_filters(args, cfg, environ=environ),
    )
