from __future__ import annotations


def _safe_float(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _qualifying_appids(top_picks: list[dict], alert_score_min: float) -> set[str] | None:
    if alert_score_min <= 0:
        return None
    qualifying: set[str] = set()
    for pick in top_picks:
        if not isinstance(pick, dict) or not pick.get("appid"):
            continue
        score = _safe_float(pick.get("score"))
        if score is not None and score >= alert_score_min:
            qualifying.add(str(pick["appid"]))
    return qualifying


def _is_in_scope(appid: str, qualifying_appids: set[str] | None) -> bool:
    return qualifying_appids is None or appid in qualifying_appids


def _count_global_historical_lows(
    deals: list[dict],
    historical_lows: dict[str, dict],
    *,
    alert_global_margin_pct: float,
    qualifying_appids: set[str] | None,
) -> int:
    deal_by_appid = {str(deal.get("appid")): deal for deal in deals if deal.get("appid")}
    count = 0
    for appid, low in historical_lows.items():
        appid = str(appid)
        if not _is_in_scope(appid, qualifying_appids):
            continue
        deal = deal_by_appid.get(appid)
        if not deal or not isinstance(low, dict):
            continue
        price_raw = _safe_float(deal.get("price_raw"))
        low_price = _safe_float(low.get("price"))
        if not price_raw or low_price is None:
            continue
        low_with_margin = low_price * (1.0 + (alert_global_margin_pct / 100.0))
        if (price_raw / 100.0) <= low_with_margin:
            count += 1
    return count


def _count_price_rises(
    comparison: dict | None,
    *,
    alert_rise_pct: float,
    qualifying_appids: set[str] | None,
) -> int:
    changes = (comparison or {}).get("price_changes", {})
    count = 0
    for appid, change in changes.items():
        appid = str(appid)
        if not _is_in_scope(appid, qualifying_appids):
            continue
        if not isinstance(change, dict):
            continue
        if change.get("direction") != "up":
            continue
        change_pct = _safe_float(change.get("change_pct"))
        if change_pct is not None and change_pct >= alert_rise_pct:
            count += 1
    return count


def _count_best_local(local_trends: dict[str, dict], qualifying_appids: set[str] | None) -> int:
    return sum(
        1
        for appid, trend in local_trends.items()
        if _is_in_scope(str(appid), qualifying_appids)
        and isinstance(trend, dict)
        and trend.get("is_best_local")
        and not trend.get("is_first_time")
    )


def _bundle_titles(bundles) -> list[str]:
    if not isinstance(bundles, list):
        return []
    return [
        str(bundle.get("title"))
        for bundle in bundles
        if isinstance(bundle, dict) and bundle.get("title")
    ]


def _count_active_bundles(
    active_bundles: dict[str, list[dict]], qualifying_appids: set[str] | None
) -> tuple[int, int]:
    bundle_names = {
        title
        for appid, bundles in active_bundles.items()
        if _is_in_scope(str(appid), qualifying_appids)
        for title in _bundle_titles(bundles)
    }
    bundle_games_count = sum(
        1
        for appid, bundles in active_bundles.items()
        if _is_in_scope(str(appid), qualifying_appids) and _bundle_titles(bundles)
    )
    return len(bundle_names), bundle_games_count


def build_smart_alert_counts(
    *,
    deals: list[dict],
    historical_lows: dict[str, dict] | None,
    active_bundles: dict[str, list[dict]] | None,
    comparison: dict | None,
    local_trends: dict[str, dict] | None,
    top_picks: list[dict] | None = None,
    alert_global_margin_pct: float = 0.0,
    alert_rise_pct: float = 0.0,
    alert_score_min: float = 0.0,
) -> dict[str, int]:
    qualifying_appids = _qualifying_appids(top_picks or [], alert_score_min)
    safe_historical_lows = historical_lows or {}
    safe_active_bundles = active_bundles or {}
    safe_local_trends = local_trends or {}
    active_bundles_count, active_bundle_games_count = _count_active_bundles(
        safe_active_bundles, qualifying_appids
    )
    return {
        "best_local_count": _count_best_local(safe_local_trends, qualifying_appids),
        "price_up_count": _count_price_rises(
            comparison,
            alert_rise_pct=alert_rise_pct,
            qualifying_appids=qualifying_appids,
        ),
        "global_historical_low_count": _count_global_historical_lows(
            deals,
            safe_historical_lows,
            alert_global_margin_pct=alert_global_margin_pct,
            qualifying_appids=qualifying_appids,
        ),
        "active_bundles_count": active_bundles_count,
        "active_bundle_games_count": active_bundle_games_count,
    }
