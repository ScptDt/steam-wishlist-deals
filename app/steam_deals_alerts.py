from __future__ import annotations


_SUPPORTED_SMART_ALERT_CHANNELS = {"discord", "telegram"}


def _safe_float(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _safe_records(records) -> list[dict]:
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def _appid(record: dict) -> str:
    return str(record.get("appid") or record.get("steam_appid") or "").strip()


def _deal_indexes(deals: list[dict] | None, top_picks: list[dict] | None) -> tuple[dict[str, dict], dict[str, dict]]:
    deal_by_appid = {
        _appid(deal): deal
        for deal in _safe_records(deals)
        if _appid(deal)
    }
    pick_by_appid = {
        _appid(pick): pick
        for pick in _safe_records(top_picks)
        if _appid(pick)
    }
    return deal_by_appid, pick_by_appid


def _game_name(appid: str, deal_by_appid: dict[str, dict], pick_by_appid: dict[str, dict]) -> str:
    source = deal_by_appid.get(appid) or pick_by_appid.get(appid) or {}
    return str(source.get("name") or source.get("steam_name") or f"AppID {appid}").strip()


def _cap_section_items(items: list[dict], limit: int) -> tuple[list[dict], int]:
    safe_limit = max(0, _safe_int(limit, 0))
    if safe_limit == 0:
        return [], len(items)
    return items[:safe_limit], max(0, len(items) - safe_limit)


def _section(section_id: str, label: str, count: int, items: list[dict], *, max_items: int, extra: dict | None = None) -> dict:
    visible_items, hidden_count = _cap_section_items(items, max_items)
    payload = {
        "id": section_id,
        "label": label,
        "count": count,
        "items": visible_items,
        "hidden_count": max(hidden_count, max(0, count - len(visible_items))),
    }
    if extra:
        payload.update(extra)
    return payload


def _digest_volume_level(total_count: int, hidden_count: int) -> str:
    if total_count >= 12 or hidden_count >= 6:
        return "high"
    if total_count >= 4 or hidden_count > 0:
        return "medium"
    return "low"


def _anti_spam_summary(sections: list[dict], *, total_count: int, max_items: int) -> dict:
    total_hidden_count = sum(_safe_int(section.get("hidden_count"), 0) for section in sections)
    visible_items_count = sum(len(section.get("items", [])) for section in sections)
    return {
        "grouped_digest": True,
        "per_game_notifications": False,
        "max_items_per_section": max_items,
        "visible_items_count": visible_items_count,
        "total_hidden_count": total_hidden_count,
        "volume_level": _digest_volume_level(total_count, total_hidden_count),
    }


def _normalized_channel_names(channels) -> tuple[list[str], int]:
    if not isinstance(channels, (list, tuple, set)):
        return [], 0
    normalized: list[str] = []
    unsupported_count = 0
    for channel in channels:
        name = str(channel or "").strip().lower()
        if not name:
            continue
        if name not in _SUPPORTED_SMART_ALERT_CHANNELS:
            unsupported_count += 1
            continue
        if name not in normalized:
            normalized.append(name)
    return normalized, unsupported_count


def decide_smart_alert_channel_readiness(
    digest: dict | None,
    *,
    requested_channels=None,
    user_opt_in: bool = False,
    digest_reviewed: bool = False,
    allow_high_volume: bool = False,
) -> dict:
    """Classify future channel readiness without enabling external sends."""
    channels, unsupported_count = _normalized_channel_names(requested_channels)
    result = {
        "schema": "smart_alert_channel_readiness_v1",
        "channel_ready": False,
        "send_ready": False,
        "external_send_enabled": False,
        "channels": [],
        "requested_channels": channels,
        "unsupported_channels_count": unsupported_count,
        "status": "blocked",
        "reason_codes": [],
        "blockers": [],
        "anti_spam": {
            "volume_level": "unknown",
            "visible_items_count": 0,
            "total_hidden_count": 0,
            "max_items_per_section": 0,
            "per_game_notifications": False,
            "grouped_digest": False,
        },
    }
    if not isinstance(digest, dict):
        result["blockers"].append("invalid_digest")
        return result

    anti_spam = digest.get("anti_spam") if isinstance(digest.get("anti_spam"), dict) else {}
    notification_policy = (
        digest.get("notification_policy")
        if isinstance(digest.get("notification_policy"), dict)
        else {}
    )
    sections = digest.get("sections") if isinstance(digest.get("sections"), list) else []
    total_count = max(0, _safe_int(digest.get("total_count"), 0))
    volume_level = str(anti_spam.get("volume_level") or "unknown").strip() or "unknown"
    result["anti_spam"] = {
        "volume_level": volume_level,
        "visible_items_count": max(0, _safe_int(anti_spam.get("visible_items_count"), 0)),
        "total_hidden_count": max(0, _safe_int(anti_spam.get("total_hidden_count"), 0)),
        "max_items_per_section": max(0, _safe_int(anti_spam.get("max_items_per_section"), 0)),
        "per_game_notifications": anti_spam.get("per_game_notifications") is True,
        "grouped_digest": anti_spam.get("grouped_digest") is True,
    }
    result["total_count"] = total_count

    blockers: list[str] = []
    reasons: list[str] = ["preview_only_no_external_send"]
    if digest.get("mode") != "preview" or digest.get("dry_run") is not True:
        blockers.append("preview_digest_required")
    if digest.get("send_ready") is not False:
        blockers.append("send_ready_must_remain_false")
    if notification_policy.get("external_send_enabled") is not False:
        blockers.append("external_send_must_remain_disabled")
    if notification_policy.get("channels") not in ([], None):
        blockers.append("digest_channels_must_stay_empty")
    if not result["anti_spam"]["grouped_digest"]:
        blockers.append("grouped_digest_required")
    if result["anti_spam"]["per_game_notifications"]:
        blockers.append("per_game_notifications_forbidden")
    if total_count <= 0 or not sections:
        blockers.append("no_alerts_to_send")
    if not channels:
        blockers.append("channel_opt_in_required")
    if unsupported_count:
        reasons.append("unsupported_channels_ignored")
    if not user_opt_in:
        blockers.append("user_channel_opt_in_required")
    if not digest_reviewed:
        blockers.append("digest_review_required")
    if volume_level == "high" and not allow_high_volume:
        blockers.append("high_volume_requires_explicit_approval")
    elif volume_level in {"low", "medium", "high"}:
        reasons.append(f"{volume_level}_volume_digest")
    if result["anti_spam"]["total_hidden_count"] > 0:
        reasons.append("hidden_items_must_be_disclosed")

    result["blockers"] = blockers
    result["reason_codes"] = reasons
    result["channel_ready"] = not blockers
    if result["channel_ready"]:
        result["status"] = "ready_for_future_channel_slice"
    elif blockers == ["high_volume_requires_explicit_approval"]:
        result["status"] = "needs_high_volume_review"
    else:
        result["status"] = "blocked"
    return result


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


def _global_historical_low_items(
    deals: list[dict],
    historical_lows: dict[str, dict],
    *,
    alert_global_margin_pct: float,
    qualifying_appids: set[str] | None,
) -> list[dict]:
    items: list[dict] = []
    deal_by_appid = {str(deal.get("appid")): deal for deal in deals if isinstance(deal, dict) and deal.get("appid")}
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
        current_price = price_raw / 100.0
        if current_price <= low_with_margin:
            items.append(
                {
                    "appid": appid,
                    "name": str(deal.get("name") or deal.get("steam_name") or f"AppID {appid}"),
                    "current_price": current_price,
                    "historical_low": low_price,
                    "reason": "cerca del mínimo histórico global",
                }
            )
    return sorted(items, key=lambda item: (item["current_price"], item["name"]))


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


def _price_rise_items(
    comparison: dict | None,
    *,
    alert_rise_pct: float,
    qualifying_appids: set[str] | None,
    deal_by_appid: dict[str, dict],
    pick_by_appid: dict[str, dict],
) -> list[dict]:
    changes = (comparison or {}).get("price_changes", {})
    if not isinstance(changes, dict):
        return []
    items: list[dict] = []
    for appid, change in changes.items():
        appid = str(appid)
        if not _is_in_scope(appid, qualifying_appids) or not isinstance(change, dict):
            continue
        if change.get("direction") != "up":
            continue
        change_pct = _safe_float(change.get("change_pct"))
        if change_pct is None or change_pct < alert_rise_pct:
            continue
        items.append(
            {
                "appid": appid,
                "name": _game_name(appid, deal_by_appid, pick_by_appid),
                "change_pct": change_pct,
                "reason": "subió frente al run anterior",
            }
        )
    return sorted(items, key=lambda item: (-item["change_pct"], item["name"]))


def _count_best_local(local_trends: dict[str, dict], qualifying_appids: set[str] | None) -> int:
    return sum(
        1
        for appid, trend in local_trends.items()
        if _is_in_scope(str(appid), qualifying_appids)
        and isinstance(trend, dict)
        and trend.get("is_best_local")
        and not trend.get("is_first_time")
    )


def _best_local_items(
    local_trends: dict[str, dict],
    qualifying_appids: set[str] | None,
    *,
    deal_by_appid: dict[str, dict],
    pick_by_appid: dict[str, dict],
) -> list[dict]:
    items: list[dict] = []
    for appid, trend in local_trends.items():
        appid = str(appid)
        if not _is_in_scope(appid, qualifying_appids):
            continue
        if not isinstance(trend, dict) or not trend.get("is_best_local") or trend.get("is_first_time"):
            continue
        items.append(
            {
                "appid": appid,
                "name": _game_name(appid, deal_by_appid, pick_by_appid),
                "reason": "mejor precio local registrado",
            }
        )
    return sorted(items, key=lambda item: item["name"])


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


def _active_bundle_items(active_bundles: dict[str, list[dict]], qualifying_appids: set[str] | None) -> list[dict]:
    by_title: dict[str, set[str]] = {}
    for appid, bundles in active_bundles.items():
        appid = str(appid)
        if not _is_in_scope(appid, qualifying_appids):
            continue
        for title in _bundle_titles(bundles):
            by_title.setdefault(title, set()).add(appid)
    return [
        {
            "title": title,
            "appids": sorted(appids),
            "games_count": len(appids),
            "reason": "bundle activo detectado",
        }
        for title, appids in sorted(by_title.items())
    ]


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


def build_smart_alert_digest(
    *,
    deals: list[dict] | None,
    historical_lows: dict[str, dict] | None,
    active_bundles: dict[str, list[dict]] | None,
    comparison: dict | None,
    local_trends: dict[str, dict] | None,
    top_picks: list[dict] | None = None,
    alert_global_margin_pct: float = 0.0,
    alert_rise_pct: float = 0.0,
    alert_score_min: float = 0.0,
    max_items_per_section: int = 3,
) -> dict:
    """Build a local Smart Alerts preview digest without enabling external sends."""
    safe_deals = _safe_records(deals)
    safe_historical_lows = historical_lows or {}
    safe_active_bundles = active_bundles or {}
    safe_local_trends = local_trends or {}
    safe_top_picks = _safe_records(top_picks)
    qualifying_appids = _qualifying_appids(safe_top_picks, alert_score_min)
    counts = build_smart_alert_counts(
        deals=safe_deals,
        historical_lows=safe_historical_lows,
        active_bundles=safe_active_bundles,
        comparison=comparison,
        local_trends=safe_local_trends,
        top_picks=safe_top_picks,
        alert_global_margin_pct=alert_global_margin_pct,
        alert_rise_pct=alert_rise_pct,
        alert_score_min=alert_score_min,
    )
    deal_by_appid, pick_by_appid = _deal_indexes(safe_deals, safe_top_picks)
    max_items = max(0, _safe_int(max_items_per_section, 3))
    section_specs = [
        (
            "best_local",
            "Mejor precio local",
            counts["best_local_count"],
            _best_local_items(
                safe_local_trends,
                qualifying_appids,
                deal_by_appid=deal_by_appid,
                pick_by_appid=pick_by_appid,
            ),
            {},
        ),
        (
            "price_up",
            "Subidas vs run anterior",
            counts["price_up_count"],
            _price_rise_items(
                comparison,
                alert_rise_pct=alert_rise_pct,
                qualifying_appids=qualifying_appids,
                deal_by_appid=deal_by_appid,
                pick_by_appid=pick_by_appid,
            ),
            {},
        ),
        (
            "global_historical_low",
            "Mínimos históricos globales",
            counts["global_historical_low_count"],
            _global_historical_low_items(
                safe_deals,
                safe_historical_lows,
                alert_global_margin_pct=alert_global_margin_pct,
                qualifying_appids=qualifying_appids,
            ),
            {},
        ),
        (
            "active_bundles",
            "Bundles activos",
            counts["active_bundles_count"],
            _active_bundle_items(safe_active_bundles, qualifying_appids),
            {"games_count": counts["active_bundle_games_count"]},
        ),
    ]
    sections = [
        _section(section_id, label, count, items, max_items=max_items, extra=extra)
        for section_id, label, count, items, extra in section_specs
        if count > 0
    ]
    total_count = (
        counts["best_local_count"]
        + counts["price_up_count"]
        + counts["global_historical_low_count"]
        + counts["active_bundles_count"]
    )
    return {
        "mode": "preview",
        "dry_run": True,
        "preview_only": True,
        "send_ready": False,
        "counts": counts,
        "total_count": total_count,
        "sections": sections,
        "anti_spam": _anti_spam_summary(
            sections,
            total_count=total_count,
            max_items=max_items,
        ),
        "notification_policy": {
            "external_send_enabled": False,
            "requires_digest_review": True,
            "channels": [],
        },
        "notes": [
            "Preview local: no envía Telegram/Discord.",
            "No habilita notificaciones por juego hasta calibrar volumen real.",
        ],
    }
