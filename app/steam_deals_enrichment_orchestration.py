from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MessageFormatters:
    ok: Callable[[str], str]
    warn: Callable[[str], str]
    dim: Callable[[str], str]


@dataclass(frozen=True)
class ProgressCallbacks:
    step: Callable[[str], None]
    emit: Callable[[str], None]


@dataclass(frozen=True)
class ScopedCacheRuntime:
    load_cache: Callable[[str], tuple[dict, float]]
    select_cache: Callable[..., Any]
    fetch_data: Callable[[list[str], dict], dict]
    save_cache: Callable[[str, dict], None]
    ttl_hours: float


@dataclass(frozen=True)
class GlobalCacheRuntime:
    load_cache: Callable[[], tuple[dict, float]]
    select_cache: Callable[..., Any]
    fetch_data: Callable[[], dict]
    save_cache: Callable[[dict], None]
    ttl_hours: float


@dataclass(frozen=True)
class EnrichmentOrchestrationContract:
    progress: ProgressCallbacks
    messages: MessageFormatters
    reviews: ScopedCacheRuntime
    deck: ScopedCacheRuntime
    protondb: ScopedCacheRuntime
    anticheat: GlobalCacheRuntime
    tags: ScopedCacheRuntime
    achievements: ScopedCacheRuntime


@dataclass(frozen=True)
class EnrichmentOutputs:
    reviews_data: dict[str, dict]
    deck_data: dict[str, int]
    protondb_data: dict[str, dict]
    anticheat_data: dict[str, dict]
    tags_data: dict[str, dict]
    achievements_data: dict[str, dict]


def build_message_formatters(*, ok, warn, dim) -> MessageFormatters:
    return MessageFormatters(ok=ok, warn=warn, dim=dim)


def build_progress_callbacks(*, step, emit) -> ProgressCallbacks:
    return ProgressCallbacks(step=step, emit=emit)


def build_scoped_cache_runtime(*, load_cache, select_cache, fetch_data, save_cache, ttl_hours: float) -> ScopedCacheRuntime:
    return ScopedCacheRuntime(
        load_cache=load_cache,
        select_cache=select_cache,
        fetch_data=fetch_data,
        save_cache=save_cache,
        ttl_hours=ttl_hours,
    )


def build_global_cache_runtime(*, load_cache, select_cache, fetch_data, save_cache, ttl_hours: float) -> GlobalCacheRuntime:
    return GlobalCacheRuntime(
        load_cache=load_cache,
        select_cache=select_cache,
        fetch_data=fetch_data,
        save_cache=save_cache,
        ttl_hours=ttl_hours,
    )


def build_enrichment_orchestration_contract(
    *,
    progress: ProgressCallbacks,
    messages: MessageFormatters,
    reviews: ScopedCacheRuntime,
    deck: ScopedCacheRuntime,
    protondb: ScopedCacheRuntime,
    anticheat: GlobalCacheRuntime,
    tags: ScopedCacheRuntime,
    achievements: ScopedCacheRuntime,
) -> EnrichmentOrchestrationContract:
    return EnrichmentOrchestrationContract(
        progress=progress,
        messages=messages,
        reviews=reviews,
        deck=deck,
        protondb=protondb,
        anticheat=anticheat,
        tags=tags,
        achievements=achievements,
    )


def empty_enrichment_outputs() -> EnrichmentOutputs:
    return EnrichmentOutputs(
        reviews_data={},
        deck_data={},
        protondb_data={},
        anticheat_data={},
        tags_data={},
        achievements_data={},
    )


def _emit_scoped_cache_status(
    policy,
    age_hours: float,
    *,
    progress: ProgressCallbacks,
    messages: MessageFormatters,
    missing_message: str,
) -> None:
    if policy.status == "valid":
        status_message = (
            missing_message.format(count=len(policy.missing_ids))
            if policy.missing_ids
            else messages.dim("todos en caché")
        )
        progress.emit(f"  {messages.ok(f'Caché válida ({age_hours:.0f}h)')} — {status_message}")
    elif policy.status == "expired":
        progress.emit(f"  {messages.warn(f'Caché expirada ({age_hours:.0f}h) — re-fetching')}")


def run_reviews_orchestration(
    steam_id: str,
    deal_appids: list[str],
    *,
    no_cache: bool,
    contract: EnrichmentOrchestrationContract,
) -> dict[str, dict]:
    contract.progress.step("Obteniendo reviews de Steam...")
    reviews_cache, reviews_age = contract.reviews.load_cache(steam_id)
    reviews_cache_policy = contract.reviews.select_cache(
        deal_appids,
        reviews_cache,
        reviews_age,
        no_cache=no_cache,
        ttl_hours=contract.reviews.ttl_hours,
    )
    _emit_scoped_cache_status(
        reviews_cache_policy,
        reviews_age,
        progress=contract.progress,
        messages=contract.messages,
        missing_message="{count} nuevos por fetchear",
    )
    reviews_data = contract.reviews.fetch_data(deal_appids, reviews_cache_policy.cache)
    contract.reviews.save_cache(steam_id, reviews_data)
    reviewed = sum(1 for appid in deal_appids if appid in reviews_data)
    contract.progress.emit(f"  {contract.messages.ok(f'{reviewed}/{len(deal_appids)} deals con reviews')}")
    return reviews_data


def run_deck_orchestration(
    steam_id: str,
    deal_appids: list[str],
    *,
    no_cache: bool,
    contract: EnrichmentOrchestrationContract,
) -> dict[str, int]:
    contract.progress.step("Obteniendo compatibilidad Steam Deck...")
    deck_cache, deck_age = contract.deck.load_cache(steam_id)
    deck_cache_policy = contract.deck.select_cache(
        deal_appids,
        deck_cache,
        deck_age,
        no_cache=no_cache,
        ttl_hours=contract.deck.ttl_hours,
    )
    _emit_scoped_cache_status(
        deck_cache_policy,
        deck_age,
        progress=contract.progress,
        messages=contract.messages,
        missing_message="{count} nuevos por fetchear",
    )
    deck_data = contract.deck.fetch_data(deal_appids, deck_cache_policy.cache)
    contract.deck.save_cache(steam_id, deck_data)
    verified = sum(1 for appid in deal_appids if deck_data.get(appid) == 3)
    playable = sum(1 for appid in deal_appids if deck_data.get(appid) == 2)
    contract.progress.emit(f"  {contract.messages.ok(f'{verified} Verified · {playable} Playable')}")
    return deck_data


def run_protondb_anticheat_orchestration(
    steam_id: str,
    deal_appids: list[str],
    *,
    no_cache: bool,
    contract: EnrichmentOrchestrationContract,
) -> tuple[dict[str, dict], dict[str, dict]]:
    del steam_id
    contract.progress.step("Obteniendo datos Linux (ProtonDB + Anti-Cheat)...")

    protondb_cache, protondb_age = contract.protondb.load_cache("")
    protondb_cache_policy = contract.protondb.select_cache(
        deal_appids,
        protondb_cache,
        protondb_age,
        no_cache=no_cache,
        ttl_hours=contract.protondb.ttl_hours,
    )
    if protondb_cache_policy.status == "valid":
        if protondb_cache_policy.missing_ids:
            contract.progress.emit(
                f"  {contract.messages.ok(f'ProtonDB caché válida ({protondb_age:.0f}h)')} — {len(protondb_cache_policy.missing_ids)} nuevos"
            )
        else:
            contract.progress.emit(
                f"  {contract.messages.ok(f'ProtonDB caché válida ({protondb_age:.0f}h)')}"
            )
    protondb_data = contract.protondb.fetch_data(deal_appids, protondb_cache_policy.cache)
    contract.protondb.save_cache("", protondb_data)
    pdb_count = sum(1 for appid in deal_appids if appid in protondb_data)
    platinum = sum(
        1
        for appid in deal_appids
        if protondb_data.get(appid, {}).get("tier") in ("platinum", "native")
    )
    contract.progress.emit(
        f"  {contract.messages.ok(f'ProtonDB: {pdb_count}/{len(deal_appids)} · {platinum} Platinum/Native')}"
    )

    anticheat_cache, anticheat_age = contract.anticheat.load_cache()
    anticheat_cache_policy = contract.anticheat.select_cache(
        anticheat_cache,
        anticheat_age,
        no_cache=no_cache,
        ttl_hours=contract.anticheat.ttl_hours,
    )
    if anticheat_cache_policy.status != "valid":
        anticheat_data = contract.anticheat.fetch_data()
        if anticheat_data:
            contract.anticheat.save_cache(anticheat_data)
            contract.progress.emit(
                f"  {contract.messages.ok(f'Anti-Cheat DB: {len(anticheat_data)} juegos cargados')}"
            )
    else:
        anticheat_data = anticheat_cache_policy.cache
        contract.progress.emit(
            f"  {contract.messages.ok(f'Anti-Cheat DB desde caché ({anticheat_age:.0f}h)')}"
        )
    ac_issues = sum(
        1
        for appid in deal_appids
        if anticheat_data.get(appid, {}).get("status") in ("Denied", "Broken")
    )
    if ac_issues:
        contract.progress.emit(
            f"  {contract.messages.warn(f'{ac_issues} deals con problemas de anti-cheat en Linux')}"
        )

    return protondb_data, anticheat_data


def run_tags_orchestration(
    steam_id: str,
    deal_appids: list[str],
    *,
    no_cache: bool,
    contract: EnrichmentOrchestrationContract,
) -> dict[str, dict]:
    del steam_id
    contract.progress.step("Obteniendo tags de Steam...")
    tags_cache, tags_age = contract.tags.load_cache("")
    tags_cache_policy = contract.tags.select_cache(
        deal_appids,
        tags_cache,
        tags_age,
        no_cache=no_cache,
        ttl_hours=contract.tags.ttl_hours,
    )
    _emit_scoped_cache_status(
        tags_cache_policy,
        tags_age,
        progress=contract.progress,
        messages=contract.messages,
        missing_message="{count} nuevos",
    )
    tags_data = contract.tags.fetch_data(deal_appids, tags_cache_policy.cache)
    contract.tags.save_cache("", tags_data)
    tagged = sum(1 for appid in deal_appids if appid in tags_data and tags_data[appid])
    contract.progress.emit(f"  {contract.messages.ok(f'{tagged}/{len(deal_appids)} deals con tags')}")
    return tags_data


def run_achievements_orchestration(
    steam_id: str,
    deal_appids: list[str],
    *,
    no_cache: bool,
    contract: EnrichmentOrchestrationContract,
) -> dict[str, dict]:
    contract.progress.step("Obteniendo achievements...")
    ach_cache, ach_age = contract.achievements.load_cache(steam_id)
    ach_cache_policy = contract.achievements.select_cache(
        deal_appids,
        ach_cache,
        ach_age,
        no_cache=no_cache,
        ttl_hours=contract.achievements.ttl_hours,
    )
    _emit_scoped_cache_status(
        ach_cache_policy,
        ach_age,
        progress=contract.progress,
        messages=contract.messages,
        missing_message="{count} nuevos por fetchear",
    )
    achievements_data = contract.achievements.fetch_data(deal_appids, ach_cache_policy.cache)
    contract.achievements.save_cache(steam_id, achievements_data)
    ach_count = sum(1 for appid in deal_appids if appid in achievements_data)
    contract.progress.emit(
        f"  {contract.messages.ok(f'{ach_count}/{len(deal_appids)} deals con achievements')}"
    )
    return achievements_data
