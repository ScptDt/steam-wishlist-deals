from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ItadMessageFormatters:
    ok: Callable[[str], str]
    dim: Callable[[str], str]


@dataclass(frozen=True)
class ItadProgressCallbacks:
    step: Callable[[str], None]
    emit: Callable[[str], None]


@dataclass(frozen=True)
class ItadRuntime:
    lookup_games: Callable[[list[str], str], dict[str, str]]
    get_store_lows: Callable[..., dict[str, dict]]
    get_current_prices: Callable[..., dict[str, dict]]
    get_active_bundles: Callable[..., dict[str, list[dict]]]


@dataclass(frozen=True)
class ItadOrchestrationContract:
    progress: ItadProgressCallbacks
    messages: ItadMessageFormatters
    runtime: ItadRuntime


@dataclass(frozen=True)
class ItadOutputs:
    itad_ids: dict[str, str]
    historical_lows: dict[str, dict]
    current_prices: dict[str, dict]
    active_bundles: dict[str, list[dict]]


def build_message_formatters(*, ok, dim) -> ItadMessageFormatters:
    return ItadMessageFormatters(ok=ok, dim=dim)


def build_progress_callbacks(*, step, emit) -> ItadProgressCallbacks:
    return ItadProgressCallbacks(step=step, emit=emit)


def build_itad_runtime(*, lookup_games, get_store_lows, get_current_prices, get_active_bundles) -> ItadRuntime:
    return ItadRuntime(
        lookup_games=lookup_games,
        get_store_lows=get_store_lows,
        get_current_prices=get_current_prices,
        get_active_bundles=get_active_bundles,
    )


def build_itad_orchestration_contract(*, progress, messages, runtime) -> ItadOrchestrationContract:
    return ItadOrchestrationContract(
        progress=progress,
        messages=messages,
        runtime=runtime,
    )


def empty_itad_outputs() -> ItadOutputs:
    return ItadOutputs(
        itad_ids={},
        historical_lows={},
        current_prices={},
        active_bundles={},
    )


def run_itad_orchestration(
    deal_appids: list[str],
    itad_key: str | None,
    *,
    contract: ItadOrchestrationContract,
) -> ItadOutputs:
    if not itad_key:
        return empty_itad_outputs()

    contract.progress.step("Obteniendo datos de IsThereAnyDeal...")
    itad_ids = contract.runtime.lookup_games(deal_appids, itad_key)
    contract.progress.emit(
        f"  {contract.messages.ok(f'{len(itad_ids):,}/{len(deal_appids):,} juegos encontrados en ITAD')}"
    )

    if not itad_ids:
        return ItadOutputs(
            itad_ids=itad_ids,
            historical_lows={},
            current_prices={},
            active_bundles={},
        )

    historical_lows = contract.runtime.get_store_lows(itad_ids, itad_key, country="MX")
    contract.progress.emit(
        f"  {contract.messages.ok(f'{len(historical_lows):,} mínimos históricos obtenidos')}"
    )

    current_prices = contract.runtime.get_current_prices(itad_ids, itad_key, country="MX")
    if current_prices:
        contract.progress.emit(
            f"  {contract.messages.ok(f'{len(current_prices):,} juegos más baratos en otra tienda')}"
        )
    else:
        contract.progress.emit(f"  {contract.messages.dim('Steam es el mejor precio en todos los deals')}")

    active_bundles = contract.runtime.get_active_bundles(itad_ids, itad_key)
    if active_bundles:
        bundle_names = {bundle["title"] for bundles in active_bundles.values() for bundle in bundles}
        contract.progress.emit(
            f"  {contract.messages.ok(f'{len(active_bundles)} juegos en {len(bundle_names)} bundle(s)')}"
        )
    else:
        contract.progress.emit(f"  {contract.messages.dim('Ningún juego en bundles activos')}")

    return ItadOutputs(
        itad_ids=itad_ids,
        historical_lows=historical_lows,
        current_prices=current_prices,
        active_bundles=active_bundles,
    )
