from __future__ import annotations

import os
import sys
import unittest

import desktop_doctor
from steam_deals_paths import CACHE_DIR_ENV_VAR, LOG_DIR_ENV_VAR


class DesktopDoctorFrozenRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._had_frozen = hasattr(sys, "frozen")
        self._original_frozen = getattr(sys, "frozen", None)
        self._had_meipass = hasattr(sys, "_MEIPASS")
        self._original_meipass = getattr(sys, "_MEIPASS", None)
        self._original_module_available = desktop_doctor.module_available
        self._original_cache_override = os.environ.get(CACHE_DIR_ENV_VAR)
        self._original_logs_override = os.environ.get(LOG_DIR_ENV_VAR)
        setattr(sys, "frozen", True)
        setattr(sys, "_MEIPASS", "/tmp/_MEI123")

    def tearDown(self) -> None:
        desktop_doctor.module_available = self._original_module_available
        self._restore_sys_attr("frozen", self._had_frozen, self._original_frozen)
        self._restore_sys_attr("_MEIPASS", self._had_meipass, self._original_meipass)
        self._restore_env(CACHE_DIR_ENV_VAR, self._original_cache_override)
        self._restore_env(LOG_DIR_ENV_VAR, self._original_logs_override)

    @staticmethod
    def _restore_sys_attr(name: str, existed: bool, value) -> None:
        if existed:
            setattr(sys, name, value)
        elif hasattr(sys, name):
            delattr(sys, name)

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_frozen_runtime_downgrades_source_only_dependency_checks(self) -> None:
        desktop_doctor.module_available = lambda _module_name: False

        checks = [
            desktop_doctor.check_python_environment(),
            desktop_doctor.check_pywebview_stack(),
            desktop_doctor.check_pyinstaller_tool(),
            desktop_doctor.check_build_configuration(),
            desktop_doctor.check_artifact_presence(),
        ]

        self.assertEqual({check.status for check in checks}, {"ok"})

    def test_frozen_doctor_includes_runtime_and_storage_checks(self) -> None:
        desktop_doctor.module_available = lambda _module_name: False

        checks = desktop_doctor.get_desktop_doctor_checks()
        status_by_title = {check.title: check.status for check in checks}

        self.assertEqual(status_by_title["Runtime frozen"], "ok")
        self.assertEqual(status_by_title["Cache/logs persistentes"], "ok")
        self.assertEqual(status_by_title["Entorno Python"], "ok")
        self.assertEqual(status_by_title["pywebview"], "ok")
        self.assertEqual(status_by_title["PyInstaller"], "ok")

    def test_frozen_storage_check_fails_when_override_points_inside_meipass(self) -> None:
        os.environ[CACHE_DIR_ENV_VAR] = "/tmp/_MEI123/cache"
        os.environ.pop(LOG_DIR_ENV_VAR, None)

        check = desktop_doctor.check_frozen_runtime_storage()

        self.assertIsNotNone(check)
        self.assertEqual(check.status, "fail")
        self.assertEqual(check.title, "Cache/logs persistentes")


class DesktopDoctorDependencyCommandTests(unittest.TestCase):
    def test_desktop_dependency_install_action_uses_constraints(self) -> None:
        command = desktop_doctor.build_desktop_dependency_install_command("python")
        action = desktop_doctor.get_desktop_dependency_install_action()

        self.assertEqual(command[:5], ("python", "-m", "pip", "install", "-r"))
        self.assertIn("-c", command)
        self.assertIn(str(desktop_doctor.DESKTOP_CONSTRAINTS_FILE), command)
        self.assertIn("constraints/desktop.txt", action)


if __name__ == "__main__":
    unittest.main()
