from __future__ import annotations


_SUPPORTED_SMART_ALERT_CHANNELS = {"discord", "telegram"}
_SMART_ALERT_CHANNEL_LABELS = {"discord": "Discord", "telegram": "Telegram"}


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


def _preview_text(value, fallback: str = "") -> str:
    text = " ".join(str(value or "").split())
    return text or fallback


def _channel_preview_label(channels: list[str]) -> str:
    labels = [_SMART_ALERT_CHANNEL_LABELS.get(channel, channel) for channel in channels]
    return ", ".join(labels) if labels else "Sin canales soportados"


def _preview_item_line(item: dict) -> str:
    if item.get("title"):
        name = _preview_text(item.get("title"), "Bundle")
        games_count = _safe_int(item.get("games_count"), 0)
        suffix = f" · {games_count} juego(s)" if games_count else ""
        return f"  - {name}{suffix}"
    appid = _preview_text(item.get("appid") or item.get("steam_appid"))
    name = _preview_text(
        item.get("name") or item.get("steam_name"),
        f"AppID {appid}" if appid else "Juego",
    )
    reason = _preview_text(item.get("reason"))
    change_pct = _safe_float(item.get("change_pct"))
    suffix = f" · {change_pct:+.2f}%" if change_pct is not None else ""
    if reason:
        suffix += f" · {reason}"
    return f"  - {name}{suffix}"


def _preview_section_lines(section: dict) -> list[str]:
    label = _preview_text(section.get("label") or section.get("id"), "Sección")
    count = max(0, _safe_int(section.get("count"), 0))
    hidden_count = max(0, _safe_int(section.get("hidden_count"), 0))
    items = _safe_records(section.get("items"))
    lines = [f"{label}: {count} alerta(s)"]
    lines.extend(_preview_item_line(item) for item in items)
    if hidden_count:
        lines.append(f"  … {hidden_count} más ocultas por cap")
    return lines


def build_smart_alert_channel_preview(
    digest: dict | None,
    *,
    requested_channels=None,
    user_opt_in: bool = False,
    digest_reviewed: bool = False,
    allow_high_volume: bool = False,
) -> dict:
    """Build a reviewable channel message preview without sending it."""
    readiness = decide_smart_alert_channel_readiness(
        digest,
        requested_channels=requested_channels,
        user_opt_in=user_opt_in,
        digest_reviewed=digest_reviewed,
        allow_high_volume=allow_high_volume,
    )
    anti_spam = (
        readiness.get("anti_spam", {})
        if isinstance(readiness.get("anti_spam"), dict)
        else {}
    )
    sections = (
        digest.get("sections")
        if isinstance(digest, dict) and isinstance(digest.get("sections"), list)
        else []
    )
    hidden_count = max(0, _safe_int(anti_spam.get("total_hidden_count"), 0))
    lines = [
        "Alertas inteligentes — preview de digest",
        f"Canales solicitados: {_channel_preview_label(readiness.get('requested_channels', []))}",
        (
            f"Volumen: {_preview_text(anti_spam.get('volume_level'), 'unknown')} · "
            f"visibles {max(0, _safe_int(anti_spam.get('visible_items_count'), 0))} · "
            f"ocultas {hidden_count}"
        ),
        "Preview only: no envía Telegram/Discord, no notifica por juego y no cambia score/ranking/defaults.",
    ]
    if readiness.get("channel_ready"):
        lines.append("Estado: listo para revisión de un slice futuro; send_ready permanece false.")
    else:
        blockers = readiness.get("blockers") if isinstance(readiness.get("blockers"), list) else []
        lines.append(f"Estado: bloqueado ({', '.join(blockers) if blockers else 'sin alertas aptas'}).")
    if sections:
        for section in sections:
            if isinstance(section, dict):
                lines.extend(_preview_section_lines(section))
    else:
        lines.append("Sin secciones de alertas para previsualizar.")
    return {
        "schema": "smart_alert_channel_preview_v1",
        "preview_only": True,
        "send_ready": False,
        "external_send_enabled": False,
        "channels": [],
        "requested_channels": readiness.get("requested_channels", []),
        "channel_ready": readiness.get("channel_ready") is True,
        "status": readiness.get("status", "blocked"),
        "readiness": readiness,
        "anti_spam": anti_spam,
        "total_count": readiness.get("total_count", 0),
        "hidden_count": hidden_count,
        "title": "Alertas inteligentes — preview de digest",
        "lines": lines,
        "message": "\n".join(lines),
    }


def _valid_preview_channels(preview: dict) -> list[str]:
    channels = preview.get("requested_channels")
    if not isinstance(channels, list):
        return []
    return [str(channel).strip() for channel in channels if str(channel or "").strip()]


def build_smart_alert_fake_delivery_plan(preview: dict | None) -> dict:
    """Plan a fake channel delivery without touching external transports."""
    result = {
        "schema": "smart_alert_fake_delivery_plan_v1",
        "transport": "fake",
        "preview_only": True,
        "dry_run": True,
        "fake_delivery": True,
        "send_ready": False,
        "external_send_enabled": False,
        "channels": [],
        "requested_channels": [],
        "delivery_mode": "grouped_digest",
        "per_game_notifications": False,
        "send_performed": False,
        "status": "blocked",
        "blockers": [],
        "planned_deliveries": [],
        "anti_spam": {
            "volume_level": "unknown",
            "visible_items_count": 0,
            "total_hidden_count": 0,
            "max_items_per_section": 0,
            "per_game_notifications": False,
            "grouped_digest": False,
        },
        "message": "",
    }
    if not isinstance(preview, dict):
        result["blockers"] = ["invalid_preview"]
        return result

    readiness = preview.get("readiness") if isinstance(preview.get("readiness"), dict) else {}
    anti_spam = preview.get("anti_spam") if isinstance(preview.get("anti_spam"), dict) else {}
    requested_channels = _valid_preview_channels(preview)
    blockers: list[str] = []

    if preview.get("schema") != "smart_alert_channel_preview_v1":
        blockers.append("invalid_preview")
    if preview.get("preview_only") is not True:
        blockers.append("preview_only_required")
    if preview.get("send_ready") is not False:
        blockers.append("send_ready_must_remain_false")
    if preview.get("external_send_enabled") is not False:
        blockers.append("external_send_must_remain_disabled")
    if preview.get("channels") not in ([], None):
        blockers.append("preview_channels_must_stay_empty")
    if not requested_channels:
        blockers.append("channel_opt_in_required")
    if preview.get("channel_ready") is not True:
        readiness_blockers = readiness.get("blockers") if isinstance(readiness.get("blockers"), list) else []
        blockers.extend(str(blocker) for blocker in readiness_blockers if str(blocker or "").strip())
        if not readiness_blockers:
            blockers.append("channel_readiness_blocked")
    if anti_spam.get("per_game_notifications") is True:
        blockers.append("per_game_notifications_forbidden")

    unique_blockers = list(dict.fromkeys(blockers))
    ready = not unique_blockers
    planned_deliveries = [
        {
            "channel": channel,
            "transport": "fake",
            "delivery_mode": "grouped_digest",
            "would_send_digest": ready,
            "send_performed": False,
            "per_game_notifications": False,
            "message_preview_available": bool(preview.get("message")),
        }
        for channel in requested_channels
    ]

    result.update(
        {
            "requested_channels": requested_channels,
            "status": "ready_for_fake_delivery" if ready else "blocked",
            "blockers": unique_blockers,
            "planned_deliveries": planned_deliveries,
            "anti_spam": {
                "volume_level": str(anti_spam.get("volume_level") or "unknown"),
                "visible_items_count": max(0, _safe_int(anti_spam.get("visible_items_count"), 0)),
                "total_hidden_count": max(0, _safe_int(anti_spam.get("total_hidden_count"), 0)),
                "max_items_per_section": max(0, _safe_int(anti_spam.get("max_items_per_section"), 0)),
                "per_game_notifications": anti_spam.get("per_game_notifications") is True,
                "grouped_digest": anti_spam.get("grouped_digest") is True,
            },
            "message": str(preview.get("message") or "") if ready else "",
        }
    )
    return result


def _safe_planned_deliveries(plan: dict) -> list[dict]:
    deliveries = plan.get("planned_deliveries")
    if not isinstance(deliveries, list):
        return []
    return [delivery for delivery in deliveries if isinstance(delivery, dict)]


def execute_smart_alert_fake_delivery_plan(plan: dict | None, *, fake_send_fn=None) -> dict:
    """Execute a fake Smart Alerts delivery plan through an injected fake sender only."""
    result = {
        "schema": "smart_alert_fake_delivery_result_v1",
        "transport": "fake",
        "preview_only": True,
        "dry_run": True,
        "fake_delivery": True,
        "send_ready": False,
        "external_send_enabled": False,
        "channels": [],
        "send_performed": False,
        "fake_send_performed": False,
        "status": "blocked",
        "blockers": [],
        "attempts": [],
    }
    if not isinstance(plan, dict):
        result["blockers"] = ["invalid_fake_delivery_plan"]
        return result

    deliveries = _safe_planned_deliveries(plan)
    blockers: list[str] = []
    if plan.get("schema") != "smart_alert_fake_delivery_plan_v1":
        blockers.append("invalid_fake_delivery_plan")
    if plan.get("transport") != "fake" or plan.get("fake_delivery") is not True:
        blockers.append("fake_transport_required")
    if plan.get("preview_only") is not True or plan.get("dry_run") is not True:
        blockers.append("dry_run_preview_required")
    if plan.get("send_ready") is not False:
        blockers.append("send_ready_must_remain_false")
    if plan.get("external_send_enabled") is not False:
        blockers.append("external_send_must_remain_disabled")
    if plan.get("channels") not in ([], None):
        blockers.append("plan_channels_must_stay_empty")
    if plan.get("per_game_notifications") is True:
        blockers.append("per_game_notifications_forbidden")
    plan_blockers = plan.get("blockers") if isinstance(plan.get("blockers"), list) else []
    blockers.extend(str(blocker) for blocker in plan_blockers if str(blocker or "").strip())
    if plan.get("status") != "ready_for_fake_delivery":
        blockers.append("fake_delivery_plan_not_ready")
    if not deliveries:
        blockers.append("no_planned_deliveries")
    if not callable(fake_send_fn):
        blockers.append("fake_sender_required")

    unique_blockers = list(dict.fromkeys(blockers))
    if unique_blockers:
        result["blockers"] = unique_blockers
        return result

    message = str(plan.get("message") or "")
    attempts: list[dict] = []
    for delivery in deliveries:
        channel = str(delivery.get("channel") or "").strip()
        payload = {
            "channel": channel,
            "message": message,
            "delivery": dict(delivery),
            "transport": "fake",
            "preview_only": True,
            "dry_run": True,
        }
        try:
            response = fake_send_fn(payload)
            ok = bool(response.get("ok")) if isinstance(response, dict) and "ok" in response else bool(response)
            attempts.append(
                {
                    "channel": channel,
                    "ok": ok,
                    "fake_send_performed": True,
                    "send_performed": False,
                }
            )
        except Exception as exc:
            attempts.append(
                {
                    "channel": channel,
                    "ok": False,
                    "fake_send_performed": True,
                    "send_performed": False,
                    "error": str(exc),
                }
            )

    result["attempts"] = attempts
    result["fake_send_performed"] = bool(attempts)
    result["status"] = "fake_delivery_completed" if attempts and all(attempt.get("ok") for attempt in attempts) else "fake_delivery_failed"
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
