from __future__ import annotations

import json
import unittest

import desktop_readiness_plan


class DesktopReadinessPlanTests(unittest.TestCase):
    def test_normalize_platform_accepts_common_aliases(self) -> None:
        self.assertEqual(desktop_readiness_plan.normalize_platform("linux2"), "linux")
        self.assertEqual(desktop_readiness_plan.normalize_platform("win32"), "windows")
        self.assertEqual(desktop_readiness_plan.normalize_platform("darwin"), "macos")
        self.assertEqual(desktop_readiness_plan.normalize_platform("all"), "all")

    def test_normalize_platform_rejects_unknown_platform(self) -> None:
        with self.assertRaises(ValueError):
            desktop_readiness_plan.normalize_platform("solaris")

    def test_macos_plan_keeps_native_host_blocker_visible(self) -> None:
        plan = desktop_readiness_plan.build_readiness_plan("macos")

        blockers = "\n".join(plan.blockers)
        commands = "\n".join(step.command for step in plan.steps)

        self.assertIn("host macOS nativo", blockers)
        self.assertIn("open dist/SteamToolsDesktop.app", commands)
        self.assertNotIn("BG00G", commands)
        self.assertNotIn("--no-cache", commands)

    def test_windows_plan_marks_build_and_smoke_as_manual(self) -> None:
        plan = desktop_readiness_plan.build_readiness_plan("windows")

        build_steps = [step for step in plan.steps if step.phase == "build"]
        smoke_steps = [step for step in plan.steps if step.phase == "smoke"]

        self.assertEqual(len(build_steps), 1)
        self.assertTrue(build_steps[0].requires_approval)
        self.assertTrue(build_steps[0].manual)
        self.assertTrue(all(step.manual for step in smoke_steps))
        self.assertIn("WebView2", "\n".join(plan.prerequisites))

    def test_render_plan_states_that_it_does_not_execute_steps(self) -> None:
        rendered = desktop_readiness_plan.render_plan(
            desktop_readiness_plan.build_readiness_plan("linux")
        )

        self.assertIn("solo imprime el plan; no ejecuta pasos", rendered)
        self.assertIn("tests.test_desktop_doctor", rendered)
        self.assertIn("BROWSER=/bin/false", rendered)

    def test_all_plans_returns_each_supported_platform_once(self) -> None:
        plans = desktop_readiness_plan.build_all_readiness_plans()

        self.assertEqual(
            [plan.platform for plan in plans],
            ["linux", "windows", "macos"],
        )

    def test_json_cli_output_is_serializable_and_does_not_run_commands(self) -> None:
        output: list[str] = []

        exit_code = desktop_readiness_plan.main(
            ["--platform", "windows", "--format", "json"], emit=output.append
        )
        payload = json.loads(output[0])

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload[0]["platform"], "windows")
        self.assertEqual(payload[0]["steps"][0]["phase"], "checks")
        self.assertTrue(any(step["manual"] for step in payload[0]["steps"]))


if __name__ == "__main__":
    unittest.main()
