from __future__ import annotations

import json
import re
import urllib.request


def build_notification_summary(deals, comparison, top_picks, watchlist_alerts=None):
    """Build a summary dict for notifications. Returns None if nothing notable."""
    comparison = comparison or {}
    new_count = len(comparison.get("new_deals", set()))
    price_drops = [
        (appid, change)
        for appid, change in comparison.get("price_changes", {}).items()
        if change["direction"] == "down"
    ]
    price_drops.sort(key=lambda item: item[1]["delta_raw"])

    if new_count == 0 and not price_drops and not watchlist_alerts:
        return None

    deal_map = {deal["appid"]: deal for deal in deals}
    top_3 = [
        {
            "name": top_pick["name"],
            "discount": top_pick["discount"],
            "price": top_pick["price_final"],
            "score": top_pick["score"],
        }
        for top_pick in (top_picks or [])[:3]
    ]
    return {
        "total_deals": len(deals),
        "new_count": new_count,
        "top_3": top_3,
        "price_drops": [
            {
                "name": deal_map.get(appid, {}).get("name", appid),
                "delta": change["delta_str"],
                "prev": change["prev_price"],
            }
            for appid, change in price_drops[:5]
        ],
        "watchlist_hits": [
            {"name": alert["name"], "price": alert["price_final"], "target": alert["target_price"]}
            for alert in (watchlist_alerts or [])
        ],
    }


def _post_json_request(url: str, body: dict, timeout: int = 15) -> dict:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        return {}
    return json.loads(raw)


def _notification_error_reason(exc: Exception) -> str:
    reason = re.sub(r"[^a-z0-9_]+", "_", type(exc).__name__.lower()).strip("_")
    return reason or "error"


def _channel_result(channel: str, status: str, *, reason: str = "") -> dict:
    result = {"channel": channel, "status": status}
    if reason:
        result["reason"] = reason
    return result


def _telegram_lines(summary: dict) -> list[str]:
    lines = ["🎮 *Steam Deals Update*", f"📊 {summary['total_deals']} deals encontrados"]
    if summary["new_count"]:
        lines.append(f"🆕 {summary['new_count']} nuevos")
    if summary["top_3"]:
        lines.append("\n🏆 *Top Picks:*")
        for index, top_pick in enumerate(summary["top_3"], 1):
            lines.append(f"  {index}\\. {top_pick['name']} \\-{top_pick['discount']}% {top_pick['price']}")
    if summary["price_drops"]:
        lines.append("\n⬇️ *Bajaron de precio:*")
        for price_drop in summary["price_drops"]:
            lines.append(f"  • {price_drop['name']} \\-{price_drop['delta']}")
    if summary["watchlist_hits"]:
        lines.append("\n🎯 *Watchlist Alerts:*")
        for watchlist_hit in summary["watchlist_hits"]:
            lines.append(
                f"  • {watchlist_hit['name']} a {watchlist_hit['price']} \\(objetivo: ${watchlist_hit['target']:.0f}\\)"
            )
    return lines


def send_telegram(token: str, chat_id: str, summary: dict, *, post_json_request=_post_json_request, on_error=None) -> bool:
    """Send notification via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = {
        "chat_id": chat_id,
        "text": "\n".join(_telegram_lines(summary)),
        "parse_mode": "MarkdownV2",
    }
    try:
        response = post_json_request(url, body, timeout=15)
        return response.get("ok", False)
    except Exception as exc:
        if on_error is not None:
            on_error(f"Telegram error: {_notification_error_reason(exc)}")
        return False


def _discord_payload(summary: dict) -> dict:
    fields = [{"name": "📊 Deals", "value": f"{summary['total_deals']} encontrados", "inline": True}]
    if summary["new_count"]:
        fields.append({"name": "🆕 Nuevos", "value": str(summary["new_count"]), "inline": True})
    if summary["top_3"]:
        fields.append(
            {
                "name": "🏆 Top Picks",
                "value": "\n".join(
                    f"{index}. **{top_pick['name']}** -{top_pick['discount']}% {top_pick['price']}"
                    for index, top_pick in enumerate(summary["top_3"], 1)
                ),
            }
        )
    if summary["price_drops"]:
        fields.append(
            {
                "name": "⬇️ Bajaron",
                "value": "\n".join(f"• {price_drop['name']} -{price_drop['delta']}" for price_drop in summary["price_drops"]),
            }
        )
    if summary["watchlist_hits"]:
        fields.append(
            {
                "name": "🎯 Watchlist",
                "value": "\n".join(
                    f"• {watchlist_hit['name']} a {watchlist_hit['price']}" for watchlist_hit in summary["watchlist_hits"]
                ),
            }
        )
    return {"embeds": [{"title": "🎮 Steam Deals Update", "color": 0x66C0F4, "fields": fields}]}


def send_discord(webhook_url: str, summary: dict, *, post_json_request=_post_json_request, on_error=None) -> bool:
    """Send notification via Discord webhook."""
    try:
        post_json_request(webhook_url, _discord_payload(summary), timeout=15)
        return True
    except Exception as exc:
        if on_error is not None:
            on_error(f"Discord error: {_notification_error_reason(exc)}")
        return False


def send_notifications(
    filters: dict,
    summary: dict,
    *,
    send_telegram_fn=send_telegram,
    send_discord_fn=send_discord,
    emit=print,
    ok=None,
    warn=None,
) -> dict:
    """Send notifications via configured channels."""
    ok = ok or (lambda text: text)
    warn = warn or (lambda text: text)
    results: list[dict] = []
    if filters.get("telegram_token") and not filters.get("telegram_chat"):
        results.append(_channel_result("telegram", "skipped", reason="telegram_chat_missing"))
        emit(f"  {warn('Notificación Telegram omitida: falta telegram_chat local')}")
    elif filters.get("telegram_token") and filters.get("telegram_chat"):
        telegram_ok = send_telegram_fn(filters["telegram_token"], filters["telegram_chat"], summary)
        if telegram_ok:
            results.append(_channel_result("telegram", "sent"))
            emit(f"  {ok('Notificación Telegram enviada')}")
        else:
            results.append(_channel_result("telegram", "failed", reason="send_returned_false"))
            emit(f"  {warn('Notificación Telegram no enviada; revisa token/chat local')}")
    if filters.get("discord_webhook"):
        discord_ok = send_discord_fn(filters["discord_webhook"], summary)
        if discord_ok:
            results.append(_channel_result("discord", "sent"))
            emit(f"  {ok('Notificación Discord enviada')}")
        else:
            results.append(_channel_result("discord", "failed", reason="send_returned_false"))
            emit(f"  {warn('Notificación Discord no enviada; revisa webhook local')}")
    return {
        "schema": "steam_deals_notification_send_results_v1",
        "channels": results,
        "sent_count": sum(1 for result in results if result["status"] == "sent"),
        "failed_count": sum(1 for result in results if result["status"] == "failed"),
        "skipped_count": sum(1 for result in results if result["status"] == "skipped"),
    }
