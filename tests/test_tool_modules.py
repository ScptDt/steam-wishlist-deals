from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

import steam_deals_web
from shared.tool_modules import (
    PAYDAY2_TOOL_ID,
    STANDALONE_LINKED_NAV_MODE,
    get_tool_entrypoint,
    get_tool_module,
    public_tool_modules,
)


class ToolModulesRegistryTests(unittest.TestCase):
    def test_payday2_metadata_declares_standalone_boundary(self) -> None:
        module = get_tool_module(PAYDAY2_TOOL_ID)

        self.assertEqual(module.id, "payday2")
        self.assertEqual(module.name, "PAYDAY 2 DLC Tracker")
        self.assertEqual(module.entrypoint, "payday2_dlc_tracker.py")
        self.assertEqual(module.default_port, 8081)
        self.assertEqual(module.config_namespace, "payday2")
        self.assertEqual(module.cache_namespace, "payday2")
        self.assertEqual(module.asset_namespace, "web/payday2")
        self.assertEqual(module.nav_mode, STANDALONE_LINKED_NAV_MODE)
        self.assertIn("Standalone", module.description)

    def test_public_tool_modules_returns_registered_metadata(self) -> None:
        modules = public_tool_modules()

        self.assertEqual(tuple(module.id for module in modules), (PAYDAY2_TOOL_ID,))
        with self.assertRaises(AttributeError):
            modules[0].entrypoint = "other.py"

    def test_lookup_normalizes_ids_and_rejects_unknown_modules(self) -> None:
        self.assertEqual(
            get_tool_module(" PAYDAY2 ").entrypoint,
            "payday2_dlc_tracker.py",
        )
        self.assertEqual(
            get_tool_entrypoint(PAYDAY2_TOOL_ID),
            "payday2_dlc_tracker.py",
        )

        with self.assertRaises(KeyError):
            get_tool_module("unknown")

    def test_steam_deals_pd2_source_launch_uses_registry_entrypoint(self) -> None:
        cmd = steam_deals_web.build_pd2_command({"vanity": "wolf"}, {})

        self.assertEqual(
            steam_deals_web.PD2_ENTRYPOINT,
            get_tool_entrypoint(PAYDAY2_TOOL_ID),
        )
        self.assertEqual(Path(cmd[1]).name, "payday2_dlc_tracker.py")

    def test_steam_deals_pd2_frozen_launch_uses_registry_entrypoint(self) -> None:
        had_frozen = hasattr(sys, "frozen")
        original_frozen = getattr(sys, "frozen", None)
        try:
            setattr(sys, "frozen", True)
            cmd = steam_deals_web.build_pd2_command({"vanity": "wolf"}, {})
        finally:
            if had_frozen:
                setattr(sys, "frozen", original_frozen)
            elif hasattr(sys, "frozen"):
                delattr(sys, "frozen")

        self.assertEqual(
            cmd[:3],
            [sys.executable, "--run-script", "payday2_dlc_tracker.py"],
        )

    def test_pd2_runtime_command_keeps_secrets_out_of_argv(self) -> None:
        cmd, proc_env = steam_deals_web.build_runtime_command_and_env(
            {"vanity": "wolf", "key": "SECRET-KEY"},
            {},
            pd2=True,
        )

        self.assertIn("payday2_dlc_tracker.py", " ".join(cmd))
        self.assertNotIn("SECRET-KEY", " ".join(cmd))
        self.assertIn("SECRET-KEY", proc_env.values())


class SteamDealsPaydayBoundaryTests(unittest.TestCase):
    def test_steam_deals_web_does_not_import_payday2_runtime_modules(self) -> None:
        source_path = Path(steam_deals_web.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        forbidden_roots = {"payday2_web", "payday2_dlc_tracker"}
        forbidden_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in forbidden_roots:
                        forbidden_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".", 1)[0]
                if root in forbidden_roots:
                    forbidden_imports.append(node.module or "<relative>")

        self.assertEqual(forbidden_imports, [])


if __name__ == "__main__":
    unittest.main()
