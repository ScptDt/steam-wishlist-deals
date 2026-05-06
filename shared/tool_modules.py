from __future__ import annotations

from dataclasses import dataclass


PAYDAY2_TOOL_ID = "payday2"
STANDALONE_LINKED_NAV_MODE = "standalone_linked"


@dataclass(frozen=True)
class ToolModule:
    id: str
    name: str
    description: str
    entrypoint: str
    default_port: int
    config_namespace: str
    cache_namespace: str
    asset_namespace: str
    nav_mode: str


_TOOL_MODULES = (
    ToolModule(
        id=PAYDAY2_TOOL_ID,
        name="PAYDAY 2 DLC Tracker",
        description="Standalone PAYDAY 2 DLC ownership and purchase planner.",
        entrypoint="payday2_dlc_tracker.py",
        default_port=8081,
        config_namespace="payday2",
        cache_namespace="payday2",
        asset_namespace="web/payday2",
        nav_mode=STANDALONE_LINKED_NAV_MODE,
    ),
)

_TOOL_MODULES_BY_ID = {module.id: module for module in _TOOL_MODULES}


def public_tool_modules() -> tuple[ToolModule, ...]:
    return _TOOL_MODULES


def get_tool_module(module_id: str) -> ToolModule:
    normalized_id = str(module_id or "").strip().lower()
    try:
        return _TOOL_MODULES_BY_ID[normalized_id]
    except KeyError as exc:
        raise KeyError(f"unknown tool module: {normalized_id or '<empty>'}") from exc


def get_tool_entrypoint(module_id: str) -> str:
    return get_tool_module(module_id).entrypoint
