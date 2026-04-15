from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FamilyContext:
    family_appids: set[str]


def empty_family_context() -> FamilyContext:
    return FamilyContext(family_appids=set())


def load_family_context(
    family_json: Path | None,
    *,
    load_family_games_fn,
    step_fn,
    emit_fn,
    ok_fn,
) -> FamilyContext:
    if family_json is None:
        return empty_family_context()

    step_fn("Cargando biblioteca familiar...")
    family_appids = load_family_games_fn(family_json)
    emit_fn(f"  {ok_fn(f'{len(family_appids):,} juegos en la familia')}")
    return FamilyContext(family_appids=family_appids)


def cross_hltb_with_family_context(
    hltb: dict[str, list[dict]],
    deals: list[dict],
    family_context: FamilyContext,
    *,
    cross_hltb_with_deals_fn,
) -> tuple[list[dict], list[dict]]:
    return cross_hltb_with_deals_fn(
        hltb,
        deals,
        family_appids=family_context.family_appids,
    )


def build_family_renderer_kwargs(family_context: FamilyContext) -> dict[str, set[str]]:
    return {"family_appids": set(family_context.family_appids)}
