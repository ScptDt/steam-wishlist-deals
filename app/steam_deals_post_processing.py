from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PostProcessingMessageFormatters:
    ok: Callable[[str], str]


@dataclass(frozen=True)
class PostProcessingCallbacks:
    emit: Callable[[str], None]


@dataclass(frozen=True)
class PostProcessingRuntime:
    apply_filters: Callable[..., list[dict]]
    rank_top_picks: Callable[..., list[dict]]


@dataclass(frozen=True)
class PostProcessingContract:
    messages: PostProcessingMessageFormatters
    callbacks: PostProcessingCallbacks
    runtime: PostProcessingRuntime


@dataclass(frozen=True)
class PostProcessingOutputs:
    hltb_hours: dict[str, float]
    deals: list[dict]
    top_picks: list[dict]


def build_message_formatters(*, ok) -> PostProcessingMessageFormatters:
    return PostProcessingMessageFormatters(ok=ok)


def build_callbacks(*, emit) -> PostProcessingCallbacks:
    return PostProcessingCallbacks(emit=emit)


def build_runtime(*, apply_filters, rank_top_picks) -> PostProcessingRuntime:
    return PostProcessingRuntime(
        apply_filters=apply_filters,
        rank_top_picks=rank_top_picks,
    )


def build_post_processing_contract(*, messages, callbacks, runtime) -> PostProcessingContract:
    return PostProcessingContract(
        messages=messages,
        callbacks=callbacks,
        runtime=runtime,
    )


def empty_post_processing_outputs() -> PostProcessingOutputs:
    return PostProcessingOutputs(
        hltb_hours={},
        deals=[],
        top_picks=[],
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
    contract: PostProcessingContract,
) -> PostProcessingOutputs:
    hltb_hours: dict[str, float] = {}
    for entry in backlog_on_sale + have_on_sale:
        if entry.get("hours"):
            hltb_hours[entry["appid"]] = entry["hours"]

    original_count = len(deals)
    filtered_deals = contract.runtime.apply_filters(
        deals,
        filters,
        reviews_data,
        deck_data,
        hltb_hours,
        previous_appids,
        comparison,
    )
    if len(filtered_deals) < original_count:
        contract.callbacks.emit(
            f"  {contract.messages.ok(f'Filtros aplicados: {original_count} → {len(filtered_deals)} deals')}"
        )

    top_picks = contract.runtime.rank_top_picks(
        filtered_deals,
        priorities,
        reviews_data,
        hltb_hours,
        deck_data,
        n=filters.get("top", 10),
    )

    return PostProcessingOutputs(
        hltb_hours=hltb_hours,
        deals=filtered_deals,
        top_picks=top_picks,
    )
