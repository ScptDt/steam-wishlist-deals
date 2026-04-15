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
    send_notifications: Callable[[dict, dict], None]


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
