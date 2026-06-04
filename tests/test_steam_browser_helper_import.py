from __future__ import annotations

import unittest
from pathlib import Path

from steam_deals_access import load_steam_access_import, normalize_steam_access_import


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "steam_browser_helper_export"


def _json_keys(value) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for nested in value.values():
            keys.update(_json_keys(nested))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for nested in value:
            keys.update(_json_keys(nested))
        return keys
    return set()


class SteamBrowserHelperImportTests(unittest.TestCase):
    def test_load_steam_access_import_accepts_browser_helper_fixture_contract(self) -> None:
        # Arrange
        fixture_path = FIXTURE_DIR / "valid.json"

        # Act
        contract = load_steam_access_import(fixture_path)

        # Assert
        self.assertEqual(contract["schema"], "steam_access_import_v1")
        self.assertEqual(contract["source"], "steam_access_import")
        self.assertEqual(contract["owned_appids"], ["10", "20", "30", "40", "50"])
        self.assertEqual(contract["family_shared_appids"], ["70", "80", "90", "100"])
        self.assertEqual(contract["wishlist_appids"], ["110", "120"])
        self.assertTrue(contract["advisory_only"])
        self.assertEqual(contract["ranking_impact"], "none")
        self.assertEqual(
            contract["summary"],
            {
                "owned_count": 5,
                "family_shared_count": 4,
                "wishlist_count": 2,
                "advisory_only": True,
                "ranking_impact": "none",
            },
        )
        self.assertEqual(contract["generated_at"], "2026-06-04T12:00:00Z")

    def test_advisory_export_metadata_does_not_create_ranking_or_runtime_changes(self) -> None:
        # Arrange
        payload = {
            "schema": "steam_access_import_v1",
            "source": "steam_browser_helper_export_v1",
            "owned_appids": ["10"],
            "family_shared_appids": [],
            "wishlist_appids": ["20"],
            "advisory_only": True,
            "ranking_impact": "none",
            "score": 999,
            "ranking": ["20", "10"],
            "defaults": {"score_weight": 999},
            "cache": {"ttl": 0},
            "fetching": {"enabled": True},
        }

        # Act
        contract = normalize_steam_access_import(payload)

        # Assert
        self.assertTrue(contract["advisory_only"])
        self.assertEqual(contract["ranking_impact"], "none")
        self.assertEqual(contract["source"], "steam_browser_helper_export_v1")
        self.assertEqual(contract["owned_appids"], ["10"])
        self.assertEqual(contract["wishlist_appids"], ["20"])
        contract_keys = _json_keys(contract)
        for forbidden_behavior_key in ("score", "ranking", "defaults", "cache", "fetching"):
            with self.subTest(forbidden_behavior_key=forbidden_behavior_key):
                self.assertNotIn(forbidden_behavior_key, contract_keys)

    def test_missing_appid_collections_are_rejected_without_session_or_network_data(self) -> None:
        # Arrange
        payload = {
            "schema": "steam_access_import_v1",
            "advisory_only": True,
            "ranking_impact": "none",
            "source": "browser_helper_export_without_collections",
        }

        # Act / Assert
        with self.assertRaisesRegex(ValueError, "owned_appids.*family_shared_appids.*wishlist_appids"):
            normalize_steam_access_import(payload)


if __name__ == "__main__":
    unittest.main()
