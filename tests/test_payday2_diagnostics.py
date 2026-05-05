from __future__ import annotations

import unittest

import payday2_dlc_tracker as pd2


def base_response(appids: list[str]) -> dict:
    return {pd2.PD2_APPID: {"success": True, "data": {"dlc": appids}}}


def app_response(appid: str, *, name: str = "", success: bool = True) -> dict:
    data = {"name": name, "type": "dlc"} if success else {}
    return {appid: {"success": success, "data": data}}


class Payday2DlcDiagnosticTests(unittest.TestCase):
    def test_config_accepts_diagnose_dlc_flag(self) -> None:
        cfg = pd2.get_config(
            argv=["--diagnose-dlc", "123456"],
            load_user_config_fn=lambda: {},
        )

        self.assertEqual(cfg["diagnose_dlc"], "123456")

    def test_diagnostic_reports_listed_dlc_when_live_and_cache_have_appid(self) -> None:
        diagnostic = pd2.build_expected_dlc_diagnostic(
            "101",
            base_appdetails=base_response(["101"]),
            candidate_appdetails=app_response("101", name="PAYDAY 2: Diamond Heist"),
            dlc_list_cache={"appids": ["101"]},
            mapping_cache={"names": {"101": "PAYDAY 2: Diamond Heist"}},
            prices_cache={"prices": {"101": {"price_fmt": "Mex$ 39.00"}}},
        )

        self.assertEqual(diagnostic["status"], "listed_in_base_dlc")
        self.assertTrue(diagnostic["in_live_base_dlc"])
        self.assertTrue(diagnostic["in_cache_catalog"])

    def test_diagnostic_reports_stale_cache_when_live_lists_missing_cache_appid(self) -> None:
        diagnostic = pd2.build_expected_dlc_diagnostic(
            "202",
            base_appdetails=base_response(["202"]),
            candidate_appdetails=app_response("202", name="PAYDAY 2: New Heist"),
            dlc_list_cache={"appids": ["101"]},
        )

        self.assertEqual(diagnostic["status"], "cache_stale")
        self.assertIn("--no-cache", diagnostic["action"])

    def test_diagnostic_reports_valid_app_not_linked_to_base(self) -> None:
        diagnostic = pd2.build_expected_dlc_diagnostic(
            "303",
            base_appdetails=base_response(["101"]),
            candidate_appdetails=app_response("303", name="PAYDAY 2: Standalone Item"),
            dlc_list_cache={"appids": ["101"]},
        )

        self.assertEqual(diagnostic["status"], "valid_app_not_linked_to_base")
        self.assertFalse(diagnostic["in_live_base_dlc"])

    def test_diagnostic_reports_bundle_candidate_without_hardcoding_dlc(self) -> None:
        diagnostic = pd2.build_expected_dlc_diagnostic(
            "https://store.steampowered.com/bundle/9999/PAYDAY_2_Bundle/",
            base_appdetails=base_response(["101"]),
        )

        self.assertEqual(diagnostic["status"], "package_or_bundle_candidate")
        self.assertIsNone(diagnostic["candidate_appid"])

    def test_diagnostic_reports_not_found_for_unknown_appid(self) -> None:
        diagnostic = pd2.build_expected_dlc_diagnostic(
            "404",
            base_appdetails=base_response(["101"]),
            candidate_appdetails=app_response("404", success=False),
        )

        self.assertEqual(diagnostic["status"], "not_found_or_unreleased")

    def test_diagnostic_reports_name_mismatch_for_unsafe_name_match(self) -> None:
        diagnostic = pd2.build_expected_dlc_diagnostic(
            "Expected Heist",
            base_appdetails=base_response(["505"]),
            candidate_appdetails=app_response("505", name="PAYDAY 2: Different Soundtrack"),
            dlc_list_cache={"appids": ["505"]},
            mapping_cache={"names": {"505": "PAYDAY 2: Expected Heist"}},
        )

        self.assertEqual(diagnostic["status"], "name_mismatch")

    def test_diagnose_expected_dlc_uses_fake_steam_and_cache_without_saving(self) -> None:
        calls: list[str] = []

        def fake_get_json(url: str, headers=None) -> dict:
            calls.append(url)
            if f"appids={pd2.PD2_APPID}" in url:
                return base_response(["606"])
            if "appids=606" in url:
                return app_response("606", name="PAYDAY 2: Dragon Heist")
            raise AssertionError(f"unexpected URL: {url}")

        def fake_load_cache(path):
            if path == pd2.DLC_LIST_CACHE:
                return {"appids": ["606"]}, 1.0
            if path == pd2.DLC_MAPPING_CACHE:
                return {"names": {"606": "PAYDAY 2: Dragon Heist"}}, 1.0
            if path == pd2.PRICES_CACHE:
                return {"prices": {"606": {"price_fmt": "Mex$ 10.00"}}}, 1.0
            return {}, float("inf")

        diagnostic = pd2.diagnose_expected_dlc(
            "Dragon Heist",
            get_json_fn=fake_get_json,
            load_cache_fn=fake_load_cache,
        )

        self.assertEqual(diagnostic["status"], "listed_in_base_dlc")
        self.assertEqual(diagnostic["candidate_appid"], "606")
        self.assertEqual(len(calls), 2)

    def test_formatted_report_is_actionable_and_safe(self) -> None:
        diagnostic = pd2.build_expected_dlc_diagnostic(
            "707",
            base_appdetails=base_response(["707"]),
            candidate_appdetails=app_response("707", name="PAYDAY 2: Safe House"),
            dlc_list_cache={"appids": []},
        )

        report = pd2.format_dlc_diagnostic_report(diagnostic)

        self.assertIn("Clasificación: cache_stale", report)
        self.assertIn("data.dlc", report)
        self.assertIn("Acción sugerida", report)
        self.assertNotIn("Traceback", report)


if __name__ == "__main__":
    unittest.main()
