from __future__ import annotations

import copy
import unittest

import payday2_web


def _dlc(appid: str, name: str) -> dict:
    return {
        "appid": appid,
        "steam_name": name,
        "price_raw": 5000,
        "orig_raw": 10000,
        "discount": 50,
    }


class Payday2BundleOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_store = copy.deepcopy(payday2_web._store)
        self.original_save_owned = payday2_web.pd2.save_owned
        self.original_load_user_config = payday2_web.pd2.load_user_config
        payday2_web.pd2.load_user_config = lambda: {}

    def tearDown(self) -> None:
        payday2_web.pd2.save_owned = self.original_save_owned
        payday2_web.pd2.load_user_config = self.original_load_user_config
        with payday2_web._store_lock:
            payday2_web._store.clear()
            payday2_web._store.update(self.original_store)

    def _load_store(
        self,
        *,
        owned: set[str],
        bundles: list[dict] | None = None,
        recommendations: dict | None = None,
    ) -> None:
        all_dlcs = {
            "10": _dlc("10", "PAYDAY 2: Valid Heist"),
            "20": _dlc("20", "PAYDAY 2: Valid Weapon Pack"),
        }
        with payday2_web._store_lock:
            payday2_web._store.update(
                {
                    "loaded": True,
                    "refreshing": False,
                    "last_refresh": None,
                    "vanity": "tester",
                    "steam_id": "steam-id",
                    "pd2_dlc_appids": ["10", "20"],
                    "all_dlcs": all_dlcs,
                    "owned": set(owned),
                    "prices": all_dlcs,
                    "sale_name": "",
                    "recommendations": recommendations if recommendations is not None else {},
                    "bundles": bundles if bundles is not None else [
                        {
                            "bundle_id": "bundle-1",
                            "name": "Mixed bundle",
                            "dlc_appids": ["10", "999", "10", "20"],
                        }
                    ],
                    "history_data": {},
                    "comparison": {},
                    "itad_lows": {},
                    "cache_status": {},
                }
            )

    def test_mark_bundle_owned_ignores_unknown_duplicate_appids(self) -> None:
        saved: list[tuple[str, list[str]]] = []
        payday2_web.pd2.save_owned = lambda steam_id, owned: saved.append(
            (steam_id, sorted(owned))
        )
        self._load_store(owned={"20"})

        result = payday2_web.mark_bundle_owned("bundle-1")
        payload = payday2_web.get_data_json()

        self.assertEqual(result["marked"], ["10"])
        self.assertEqual(saved, [("steam-id", ["10", "20"])])
        self.assertEqual(payload["ownedCount"], 2)
        self.assertEqual(payload["missingCount"], 0)
        self.assertEqual(payload["bundles"][0]["dlcAppids"], ["10", "20"])
        self.assertNotIn("999", saved[0][1])

    def test_unmark_bundle_owned_preserves_unrelated_manual_entries(self) -> None:
        saved: list[tuple[str, list[str]]] = []
        payday2_web.pd2.save_owned = lambda steam_id, owned: saved.append(
            (steam_id, sorted(owned))
        )
        self._load_store(owned={"10", "20", "999"})

        result = payday2_web.unmark_bundle_owned("bundle-1")

        self.assertEqual(result["unmarked"], ["10", "20"])
        self.assertEqual(saved, [("steam-id", ["999"])])

    def test_empty_bundle_action_does_not_persist_or_recompute(self) -> None:
        saved: list[tuple[str, list[str]]] = []
        payday2_web.pd2.save_owned = lambda steam_id, owned: saved.append(
            (steam_id, sorted(owned))
        )
        recommendations = {"sentinel": object()}
        self._load_store(
            owned={"20"},
            recommendations=recommendations,
            bundles=[
                {
                    "bundle_id": "empty-bundle",
                    "name": "Only unknown apps",
                    "dlc_appids": ["999", "888", "999"],
                }
            ],
        )

        mark_result = payday2_web.mark_bundle_owned("empty-bundle")
        unmark_result = payday2_web.unmark_bundle_owned("empty-bundle")
        payload = payday2_web.get_data_json()

        self.assertEqual(mark_result["marked"], [])
        self.assertEqual(mark_result["total_marked"], 0)
        self.assertEqual(unmark_result["unmarked"], [])
        self.assertEqual(unmark_result["total_unmarked"], 0)
        self.assertEqual(saved, [])
        self.assertIs(payday2_web._store["recommendations"], recommendations)
        self.assertEqual(payday2_web._store["owned"], {"20"})
        self.assertEqual(payload["ownedCount"], 1)
        self.assertEqual(payload["missingCount"], 1)
        self.assertEqual(payload["bundles"], [])


if __name__ == "__main__":
    unittest.main()
