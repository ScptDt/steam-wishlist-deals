from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class EngagementMessageFormatters:
    ok: Callable[[str], str]
    dim: Callable[[str], str]


@dataclass(frozen=True)
class EngagementCallbacks:
    step: Callable[[str], None]
    emit: Callable[[str], None]


@dataclass(frozen=True)
class EngagementRuntime:
    load_watchlist: Callable[[], list[dict]]
    check_watchlist_alerts: Callable[[list[dict], list[dict]], list[dict]]
    compute_budget_picks: Callable[..., dict]
    build_gift_ideas: Callable[..., list[dict]]
    build_notification_summary: Callable[..., dict | None]
    send_notifications: Callable[[dict, dict], dict]


@dataclass(frozen=True)
class EngagementContract:
    messages: EngagementMessageFormatters
    callbacks: EngagementCallbacks
    runtime: EngagementRuntime


@dataclass(frozen=True)
class EngagementOutputs:
    watchlist: list[dict]
    watchlist_alerts: list[dict]
    budget_result: dict | None
    gift_ideas: list[dict]
    notification_summary: dict | None


def build_message_formatters(*, ok, dim) -> EngagementMessageFormatters:
    return EngagementMessageFormatters(ok=ok, dim=dim)


def build_callbacks(*, step, emit) -> EngagementCallbacks:
    return EngagementCallbacks(step=step, emit=emit)


def build_runtime(
    *,
    load_watchlist,
    check_watchlist_alerts,
    compute_budget_picks,
    build_gift_ideas,
    build_notification_summary,
    send_notifications,
) -> EngagementRuntime:
    return EngagementRuntime(
        load_watchlist=load_watchlist,
        check_watchlist_alerts=check_watchlist_alerts,
        compute_budget_picks=compute_budget_picks,
        build_gift_ideas=build_gift_ideas,
        build_notification_summary=build_notification_summary,
        send_notifications=send_notifications,
    )


def build_engagement_contract(*, messages, callbacks, runtime) -> EngagementContract:
    return EngagementContract(
        messages=messages,
        callbacks=callbacks,
        runtime=runtime,
    )


def empty_engagement_outputs() -> EngagementOutputs:
    return EngagementOutputs(
        watchlist=[],
        watchlist_alerts=[],
        budget_result=None,
        gift_ideas=[],
        notification_summary=None,
    )


def gift_idea_context_from_compare(compare_data: dict | None) -> dict:
    if not isinstance(compare_data, dict):
        return {}
    context: dict = {}
    if compare_data.get("overlap") is not None:
        context["overlap_appids"] = compare_data.get("overlap")
    friend_activity = compare_data.get("friend_activity_games")
    if friend_activity is None:
        friend_activity = compare_data.get("friend_activity")
    if friend_activity is not None:
        context["friend_activity_games"] = friend_activity
    return context


def run_engagement_post_run(
    deals: list[dict],
    *,
    filters: dict,
    top_picks: list[dict],
    compare_data: dict | None,
    owned: dict[str, str],
    comparison: dict | None,
    contract: EngagementContract,
    sym_target: str,
    sym_budget: str,
    sym_gift: str,
) -> EngagementOutputs:
    watchlist = contract.runtime.load_watchlist()
    watchlist_alerts: list[dict] = []
    if watchlist:
        watchlist_alerts = contract.runtime.check_watchlist_alerts(deals, watchlist)
        if watchlist_alerts:
            contract.callbacks.emit(
                f"  {contract.messages.ok(f'{sym_target} {len(watchlist_alerts)} watchlist alerts!')}"
            )
            for alert in watchlist_alerts:
                contract.callbacks.emit(
                    f"    {alert['name']} — {alert['price_final']} (objetivo: ${alert['target_price']:.0f})"
                )

    budget_result = None
    if filters.get("budget"):
        budget_result = contract.runtime.compute_budget_picks(
            deals,
            filters["budget"],
            top_picks,
            watchlist_alerts,
        )
        contract.callbacks.emit(
            f"  {contract.messages.ok(f'{sym_budget} Budget ${filters['budget']:.0f}: {budget_result['games_count']} juegos, ${budget_result['total_spent']:.0f} gastados')}"
        )

    gift_ideas: list[dict] = []
    if compare_data:
        gift_ideas = contract.runtime.build_gift_ideas(
            compare_data["friend_set"],
            deals,
            owned,
            **gift_idea_context_from_compare(compare_data),
        )
        if gift_ideas:
            contract.callbacks.emit(
                f"  {contract.messages.ok(f'{sym_gift} {len(gift_ideas)} gift ideas en oferta')}"
            )

    notification_summary = None
    if filters.get("telegram_token") or filters.get("discord_webhook"):
        contract.callbacks.step("Enviando notificaciones...")
        notification_summary = contract.runtime.build_notification_summary(
            deals,
            comparison,
            top_picks,
            watchlist_alerts,
        )
        if notification_summary:
            contract.runtime.send_notifications(filters, notification_summary)
        else:
            contract.callbacks.emit(
                f"  {contract.messages.dim('Sin cambios notables — no se envió notificación')}"
            )

    return EngagementOutputs(
        watchlist=watchlist,
        watchlist_alerts=watchlist_alerts,
        budget_result=budget_result,
        gift_ideas=gift_ideas,
        notification_summary=notification_summary,
    )
