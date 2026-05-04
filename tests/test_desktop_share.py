from __future__ import annotations

import base64
import contextlib
import io
import json
import signal
import subprocess
import sys
import unittest
import urllib.parse
import urllib.request
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from steam_tools_desktop import (
    ALLOWED_EMBEDDED_SCRIPTS,
    DesktopClipboardApi,
    FALLBACK_REASON_MESSAGES,
    _build_child_process_env,
    _candidate_urls,
    _config_probe_url,
    _discover_live_url,
    _desktop_window_url,
    _find_free_port,
    _fallback_url,
    _normalize_clipboard_text,
    _probe_steam_deals_server,
    _resolve_server_target,
    _run_embedded_script,
    _wait_server,
    copy_text_to_qt_clipboard,
    decode_share_payload,
    main as desktop_main,
    resolve_allowed_embedded_script,
    validate_embedded_script_name,
)
from shared_web_infra import stop_process


class DecodeSharePayloadTests(unittest.TestCase):
    def test_accepts_legacy_original_price_alias(self) -> None:
        raw = base64.b64encode(
            json.dumps(
                {
                    "name": "Alpha",
                    "appid": "10",
                    "price": "$10",
                    "original_price": "$20",
                    "discount": 50,
                }
            ).encode("utf-8")
        ).decode("ascii")

        payload = decode_share_payload(raw)

        self.assertEqual(payload["price_original"], "$20")

    def test_accepts_url_encoded_share_payload(self) -> None:
        raw = base64.b64encode(
            json.dumps(
                {
                    "name": "Bravo",
                    "appid": "20",
                    "price": "$15",
                    "price_original": "$30",
                    "discount": 50,
                }
            ).encode("utf-8")
        ).decode("ascii")
        encoded = urllib.parse.quote(raw)

        payload = decode_share_payload(encoded)

        self.assertEqual(payload["name"], "Bravo")
        self.assertEqual(payload["price_original"], "$30")


class DesktopLauncherFallbackTests(unittest.TestCase):
    def test_fallback_url_includes_reason_query_when_present(self) -> None:
        self.assertEqual(
            _fallback_url("window-timeout"),
            "http://127.0.0.1:8080?desktop_fallback=1&reason=window-timeout",
        )

    def test_fallback_url_uses_discovered_base_url_when_provided(self) -> None:
        self.assertEqual(
            _fallback_url(
                "window-timeout", base_url="http://127.0.0.1:8087"
            ),
            "http://127.0.0.1:8087?desktop_fallback=1&reason=window-timeout",
        )

    def test_desktop_window_url_marks_native_mode_without_affecting_fallback(self) -> None:
        self.assertEqual(
            _desktop_window_url("http://127.0.0.1:8087?foo=bar"),
            "http://127.0.0.1:8087?foo=bar&desktop_native=1",
        )

    def test_config_probe_url_targets_api_config(self) -> None:
        self.assertEqual(
            _config_probe_url("http://127.0.0.1:8087"),
            "http://127.0.0.1:8087/api/config",
        )

    def test_candidate_urls_cover_desktop_port_window(self) -> None:
        self.assertEqual(
            _candidate_urls(8080)[:3],
            [
                "http://127.0.0.1:8080",
                "http://127.0.0.1:8081",
                "http://127.0.0.1:8082",
            ],
        )

    def test_build_child_process_env_sets_pyinstaller_reset_only_for_frozen(
        self,
    ) -> None:
        self.assertEqual(
            _build_child_process_env(frozen=False, base_env={"A": "1"}),
            {"A": "1"},
        )
        self.assertEqual(
            _build_child_process_env(
                frozen=True,
                base_env={"A": "1", "HOME": "/home/tester"},
            ),
            {
                "A": "1",
                "HOME": "/home/tester",
                "PYINSTALLER_RESET_ENVIRONMENT": "1",
                "STEAM_DEALS_CACHE_DIR": "/home/tester/.cache/steam_deals",
                "STEAM_DEALS_LOG_DIR": "/home/tester/.cache/steam_deals/logs",
                "STEAM_DEALS_OUTPUT_DIR": "/home/tester/SteamTools/output",
            },
        )

    def test_find_free_port_returns_first_bindable_port(self) -> None:
        class _FakeSocket:
            attempts = []

            def __init__(self, *_args):
                self.port = None

            def bind(self, address):
                _FakeSocket.attempts.append(address)
                self.port = address[1]
                if self.port in (8080, 8081):
                    raise OSError("busy")

            def close(self):
                return None

        result = _find_free_port(8080, socket_factory=_FakeSocket)

        self.assertEqual(result, 8082)
        self.assertEqual(
            _FakeSocket.attempts,
            [
                ("127.0.0.1", 8080),
                ("127.0.0.1", 8081),
                ("127.0.0.1", 8082),
            ],
        )

    def test_probe_steam_deals_server_uses_api_config_healthcheck(self) -> None:
        class _FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        calls = []

        def fake_urlopen(url, timeout=0):
            calls.append((url, timeout))
            return _FakeResponse()

        result = _probe_steam_deals_server(
            "http://127.0.0.1:8087", urlopen_fn=fake_urlopen
        )

        self.assertEqual(result, True)
        self.assertEqual(
            calls,
            [("http://127.0.0.1:8087/api/config", 1.5)],
        )

    def test_fallback_reason_messages_keep_known_launcher_reasons(self) -> None:
        self.assertIn("missing-webview", FALLBACK_REASON_MESSAGES)
        self.assertIn("window-timeout", FALLBACK_REASON_MESSAGES)
        self.assertIn("window-error", FALLBACK_REASON_MESSAGES)

    def test_wait_server_returns_false_after_timeout_when_endpoint_never_responds(
        self,
    ) -> None:
        calls = []

        def fake_urlopen(_url, timeout=0):
            calls.append(timeout)
            raise RuntimeError("down")

        original_urlopen = urllib.request.urlopen
        original_sleep = time.sleep
        try:
            urllib.request.urlopen = fake_urlopen
            time.sleep = lambda _delay: None
            result = _wait_server("http://127.0.0.1:8080", timeout=0.0)
        finally:
            urllib.request.urlopen = original_urlopen
            time.sleep = original_sleep

        self.assertEqual(result, False)
        self.assertEqual(calls, [])

    def test_discover_live_url_returns_first_matching_port_in_scan_window(self) -> None:
        checked = []

        class _FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_urlopen(url, timeout=0):
            checked.append(url)
            if url == "http://127.0.0.1:8083/api/config":
                return _FakeResponse()
            raise RuntimeError("down")

        result = _discover_live_url(
            8080,
            timeout=0.3,
            urlopen_fn=fake_urlopen,
            sleep_fn=lambda _delay: None,
        )

        self.assertEqual(result, "http://127.0.0.1:8083")
        self.assertIn("http://127.0.0.1:8083/api/config", checked)

    def test_resolve_server_target_uses_launch_port_as_discovery_base_when_spawning(
        self,
    ) -> None:
        result = _resolve_server_target(
            8080,
            discover_live_url_fn=lambda _port, timeout=0.0: None,
            find_free_port_fn=lambda _port: 8084,
        )

        self.assertEqual(
            result,
            {
                "reuse_existing": False,
                "active_url": "http://127.0.0.1:8084",
                "launch_port": 8084,
                "discover_start_port": 8084,
            },
        )

    def test_resolve_server_target_reuses_existing_server_when_available(self) -> None:
        result = _resolve_server_target(
            8080,
            discover_live_url_fn=lambda _port, timeout=0.0: "http://127.0.0.1:8080",
            find_free_port_fn=lambda _port: 8084,
        )

        self.assertEqual(
            result,
            {
                "reuse_existing": True,
                "active_url": "http://127.0.0.1:8080",
                "launch_port": None,
                "discover_start_port": 8080,
            },
        )


class DesktopClipboardApiTests(unittest.TestCase):
    def test_normalize_clipboard_text_rejects_empty_log(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _normalize_clipboard_text("   ")

        self.assertEqual(str(ctx.exception), "No hay contenido de log para copiar.")

    def test_copy_text_to_qt_clipboard_uses_qapplication_clipboard(self) -> None:
        copied = []

        class _FakeClipboard:
            def setText(self, text):
                copied.append(text)

        class _FakeApp:
            def clipboard(self):
                return _FakeClipboard()

        class _FakeQApplication:
            @staticmethod
            def instance():
                return _FakeApp()

        backend = copy_text_to_qt_clipboard(
            "hello log",
            qapplication_cls=_FakeQApplication,
        )

        self.assertEqual(backend, "qt")
        self.assertEqual(copied, ["hello log"])

    def test_copy_text_to_qt_clipboard_rejects_missing_qapplication(self) -> None:
        class _FakeQApplication:
            @staticmethod
            def instance():
                return None

        with self.assertRaises(RuntimeError) as ctx:
            copy_text_to_qt_clipboard("hello", qapplication_cls=_FakeQApplication)

        self.assertEqual(str(ctx.exception), "Clipboard nativo Qt no inicializado.")

    def test_desktop_clipboard_api_returns_safe_success_payload(self) -> None:
        calls = []
        api = DesktopClipboardApi(copy_text_fn=lambda text: calls.append(text) or "qt")

        result = api.copy_text_to_clipboard("hello log")

        self.assertEqual(result, {"status": "copied", "backend": "qt"})
        self.assertEqual(calls, ["hello log"])

    def test_desktop_clipboard_api_hides_backend_error_details(self) -> None:
        def failing_copy(_text):
            raise RuntimeError("internal path /tmp/secret-clipboard")

        api = DesktopClipboardApi(copy_text_fn=failing_copy)

        with self.assertRaises(RuntimeError) as ctx:
            api.copy_text_to_clipboard("hello log")

        message = str(ctx.exception)
        self.assertEqual(
            message,
            "Clipboard nativo no disponible. Usa Descargar log (.txt).",
        )
        self.assertNotIn("/tmp/secret-clipboard", message)


class DesktopEmbeddedScriptAllowlistTests(unittest.TestCase):
    def test_allowed_embedded_scripts_are_exact_expected_names(self) -> None:
        self.assertEqual(
            ALLOWED_EMBEDDED_SCRIPTS,
            {"steam_deals_generator.py", "payday2_dlc_tracker.py"},
        )

    def test_validate_embedded_script_name_accepts_allowed_names(self) -> None:
        self.assertEqual(
            validate_embedded_script_name("steam_deals_generator.py"),
            "steam_deals_generator.py",
        )
        self.assertEqual(
            validate_embedded_script_name("payday2_dlc_tracker.py"),
            "payday2_dlc_tracker.py",
        )

    def test_validate_embedded_script_name_rejects_unsafe_names(self) -> None:
        unsafe_names = [
            "",
            "../steam_deals_generator.py",
            "nested/steam_deals_generator.py",
            "nested\\steam_deals_generator.py",
            "/tmp/steam_deals_generator.py",
            "C:\\temp\\steam_deals_generator.py",
            "steam_deals_generator.py:alt",
            "unknown.py",
        ]

        for raw_name in unsafe_names:
            with self.subTest(raw_name=raw_name):
                with self.assertRaises(ValueError) as ctx:
                    validate_embedded_script_name(raw_name)
                self.assertEqual(str(ctx.exception), "Script embebido no permitido.")
                self.assertNotIn("/", str(ctx.exception))
                self.assertNotIn("\\", str(ctx.exception))

    def test_resolve_allowed_embedded_script_stays_inside_base(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            script = base / "steam_deals_generator.py"
            script.write_text("print('ok')", encoding="utf-8")

            resolved = resolve_allowed_embedded_script(
                "steam_deals_generator.py",
                base_dir=base,
            )

        self.assertEqual(resolved, script.resolve())

    def test_resolve_allowed_embedded_script_rejects_missing_allowed_script_safely(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(RuntimeError) as ctx:
                resolve_allowed_embedded_script(
                    "steam_deals_generator.py",
                    base_dir=Path(temp_dir),
                )

        self.assertEqual(
            str(ctx.exception),
            "Script embebido permitido no disponible.",
        )
        self.assertNotIn(temp_dir, str(ctx.exception))

    def test_run_embedded_script_preserves_passthrough_args_and_restores_argv(self) -> None:
        original_argv = ["desktop", "--run-script"]
        calls = []

        def fake_run_path(path, run_name=None):
            calls.append((path, run_name, list(sys.argv)))

        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            script = base / "payday2_dlc_tracker.py"
            script.write_text("print('ok')", encoding="utf-8")
            previous_argv = sys.argv[:]
            try:
                sys.argv = original_argv[:]
                _run_embedded_script(
                    "payday2_dlc_tracker.py",
                    ["--vanity", "wolf"],
                    base_dir=base,
                    run_path_fn=fake_run_path,
                )
                restored = list(sys.argv)
            finally:
                sys.argv = previous_argv

        self.assertEqual(
            calls,
            [
                (
                    str(script.resolve()),
                    "__main__",
                    [str(script.resolve()), "--vanity", "wolf"],
                )
            ],
        )
        self.assertEqual(restored, original_argv)

    def test_run_embedded_script_rejects_unknown_before_runpy(self) -> None:
        calls = []

        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                _run_embedded_script(
                    "unknown.py",
                    [],
                    base_dir=Path(temp_dir),
                    run_path_fn=lambda *_args, **_kwargs: calls.append("run"),
                )

        self.assertEqual(calls, [])

    def test_main_reports_run_script_validation_errors_without_traceback(self) -> None:
        previous_argv = sys.argv[:]
        stderr = io.StringIO()
        try:
            sys.argv = ["desktop", "--run-script", "../steam_deals_generator.py"]
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    desktop_main()
        finally:
            sys.argv = previous_argv

        output = stderr.getvalue()
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("Script embebido no permitido.", output)
        self.assertNotIn("Traceback", output)
        self.assertNotIn("/home/", output)
        self.assertNotIn("Documents", output)


class DesktopCleanShutdownContractTests(unittest.TestCase):
    class _FakeProc:
        def __init__(self, *, done=False, timeout=False):
            self.pid = 123
            self._done = done
            self._timeout = timeout
            self.terminate_called = 0
            self.kill_called = 0
            self.wait_calls = []

        def poll(self):
            return 0 if self._done else None

        def terminate(self):
            self.terminate_called += 1

        def kill(self):
            self.kill_called += 1

        def wait(self, timeout=None):
            self.wait_calls.append(timeout)
            if self._timeout:
                raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
            return 0

    def test_stop_process_terminates_then_kills_when_timeout_expires(self) -> None:
        proc = self._FakeProc(timeout=True)
        calls = []

        stop_process(
            proc,
            os_name="posix",
            getpgid=lambda _pid: 456,
            killpg=lambda pgid, sig: calls.append((pgid, sig)),
        )

        self.assertEqual(calls, [(456, signal.SIGTERM), (456, signal.SIGKILL)])

    def test_stop_process_noops_when_proc_already_done(self) -> None:
        proc = self._FakeProc(done=True)

        stop_process(proc, os_name="posix", getpgid=lambda _pid: 456, killpg=lambda *_args: None)

        self.assertEqual(proc.wait_calls, [])
        self.assertEqual(proc.terminate_called, 0)
        self.assertEqual(proc.kill_called, 0)
