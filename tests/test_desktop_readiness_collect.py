from __future__ import annotations

import json
import unittest

import desktop_readiness_collect


class DesktopReadinessCollectTests(unittest.TestCase):
    def test_build_safe_checks_excludes_manual_build_and_smoke_steps(self) -> None:
        checks = desktop_readiness_collect.build_safe_checks("linux")
        commands = "\n".join(check.command for check in checks)

        self.assertEqual([check.title for check in checks], [
            "Tests desktop/readiness sin red",
            "Desktop Doctor source/frozen",
        ])
        self.assertNotIn("build_desktop.py", commands)
        self.assertNotIn("--force-web-fallback", commands)
        self.assertNotIn("BG00G", commands)
        self.assertNotIn("--no-cache", commands)

    def test_dry_run_does_not_call_runner(self) -> None:
        calls: list[tuple[str, ...]] = []

        report = desktop_readiness_collect.collect_readiness(
            "linux",
            runner=lambda args: calls.append(args) or desktop_readiness_collect.CommandExecution(0),
        )

        self.assertEqual(report.mode, "dry-run")
        self.assertEqual(report.overall, "PLANNED")
        self.assertEqual(calls, [])
        self.assertTrue(all(check.status == "planned" for check in report.checks))

    def test_execute_safe_checks_uses_runner_and_summarizes_ok(self) -> None:
        calls: list[tuple[str, ...]] = []

        report = desktop_readiness_collect.collect_readiness(
            desktop_readiness_collect.current_platform(),
            execute=True,
            runner=lambda args: calls.append(args)
            or desktop_readiness_collect.CommandExecution(0, "OK\n", ""),
        )

        self.assertEqual(report.mode, "execute-safe-checks")
        self.assertEqual(report.overall, "OK")
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(check.status == "ok" for check in report.checks))

    def test_execute_safe_checks_reports_failure_without_hiding_stderr(self) -> None:
        def runner(_args: tuple[str, ...]) -> desktop_readiness_collect.CommandExecution:
            return desktop_readiness_collect.CommandExecution(1, "", "boom")

        report = desktop_readiness_collect.collect_readiness(
            desktop_readiness_collect.current_platform(), execute=True, runner=runner
        )

        self.assertEqual(report.overall, "FAIL")
        self.assertEqual(report.checks[0].status, "fail")
        self.assertEqual(report.checks[0].stderr_tail, "boom")

    def test_execute_refuses_non_current_platform(self) -> None:
        other_platform = "windows" if desktop_readiness_collect.current_platform() != "windows" else "linux"

        with self.assertRaises(ValueError):
            desktop_readiness_collect.collect_readiness(other_platform, execute=True)

    def test_main_json_dry_run_is_serializable(self) -> None:
        output: list[str] = []

        exit_code = desktop_readiness_collect.main(
            ["--platform", "linux", "--format", "json"], emit=output.append
        )
        payload = json.loads(output[0])

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["platform"], "linux")
        self.assertEqual(payload["mode"], "dry-run")
        self.assertEqual(payload["overall"], "PLANNED")
        self.assertEqual(payload["checks"][0]["status"], "planned")

    def test_main_returns_nonzero_when_runner_reports_failure(self) -> None:
        report = desktop_readiness_collect.CollectionReport(
            "linux",
            "execute-safe-checks",
            "FAIL",
            (
                desktop_readiness_collect.CollectedCheck(
                    "failing", "python -m unittest", "fail", 1, "", "boom"
                ),
            ),
            (),
        )

        self.assertEqual(desktop_readiness_collect.summarize_collected_checks(report.checks, execute=True), "FAIL")


if __name__ == "__main__":
    unittest.main()
