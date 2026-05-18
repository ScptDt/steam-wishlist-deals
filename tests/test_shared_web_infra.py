from __future__ import annotations

import signal
import subprocess
import unittest
from unittest.mock import patch

from shared_web_infra import (
    LOCAL_CSRF_HEADER,
    create_local_session_token,
    has_valid_local_origin_or_referer,
    is_valid_local_anti_csrf_request,
    is_valid_local_token_header,
    is_valid_loopback_host,
    is_valid_loopback_host_header,
    local_anti_csrf_forbidden_payload,
    local_host_forbidden_payload,
    redact_sensitive_text,
    safe_public_error_payload,
    stop_process,
)


class _FakeProc:
    def __init__(self, *, pid: int = 123, done: bool = False, timeout: bool = False):
        self.pid = pid
        self._done = done
        self._timeout = timeout
        self.terminate_called = 0
        self.kill_called = 0
        self.wait_calls: list[float] = []

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


class LocalAntiCsrfTests(unittest.TestCase):
    def test_create_local_session_token_returns_unique_url_safe_values(self) -> None:
        with patch(
            "shared_web_infra.secrets.token_urlsafe",
            side_effect=["a" * 43, "b" * 43],
        ) as token_urlsafe:
            first = create_local_session_token()
            second = create_local_session_token()

        self.assertIsInstance(first, str)
        self.assertIsInstance(second, str)
        self.assertGreaterEqual(len(first), 32)
        self.assertRegex(first, r"^[A-Za-z0-9_-]+={0,2}$")
        self.assertNotEqual(first, second)
        token_urlsafe.assert_called_with(32)

    def test_is_valid_local_token_header_accepts_exact_expected_token(self) -> None:
        headers = {LOCAL_CSRF_HEADER: "expected-token"}

        self.assertTrue(is_valid_local_token_header(headers, "expected-token"))

    def test_is_valid_local_token_header_rejects_missing_or_invalid_token(self) -> None:
        self.assertFalse(is_valid_local_token_header({}, "expected-token"))
        self.assertFalse(
            is_valid_local_token_header(
                {LOCAL_CSRF_HEADER: "attacker-token"},
                "expected-token",
            )
        )

    def test_has_valid_local_origin_or_referer_accepts_loopback_hosts_on_server_port(self) -> None:
        server_port = 8765

        self.assertTrue(
            has_valid_local_origin_or_referer(
                {"Origin": "http://localhost:8765"},
                server_port,
            )
        )
        self.assertTrue(
            has_valid_local_origin_or_referer(
                {"Origin": "http://127.0.0.1:8765"},
                server_port,
            )
        )
        self.assertTrue(
            has_valid_local_origin_or_referer(
                {"Referer": "http://[::1]:8765/app/index.html"},
                server_port,
            )
        )

    def test_has_valid_local_origin_or_referer_rejects_external_or_wrong_port_values(self) -> None:
        self.assertFalse(
            has_valid_local_origin_or_referer(
                {"Origin": "http://evil.example:8765"},
                8765,
            )
        )
        self.assertFalse(
            has_valid_local_origin_or_referer(
                {"Referer": "http://localhost:9999/app/index.html"},
                8765,
            )
        )

    def test_absent_origin_and_referer_are_allowed_only_with_valid_token(self) -> None:
        token = "expected-token"

        self.assertTrue(
            is_valid_local_anti_csrf_request(
                {LOCAL_CSRF_HEADER: token},
                token,
                8765,
            )
        )
        self.assertFalse(
            is_valid_local_anti_csrf_request(
                {},
                token,
                8765,
            )
        )

    def test_local_anti_csrf_forbidden_payload_does_not_expose_sensitive_values(self) -> None:
        expected_token = "expected-token-SECRET"
        payload = local_anti_csrf_forbidden_payload()
        rendered = str(payload)

        self.assertEqual(payload["error"], "forbidden")
        self.assertNotIn(expected_token, rendered)
        self.assertNotIn("/home/adolfo/Documents/Deals", rendered)
        self.assertNotIn("Traceback", rendered)
        self.assertNotIn("SECRET", rendered)


class LocalHostValidationTests(unittest.TestCase):
    def test_is_valid_loopback_host_accepts_loopback_hosts_on_server_port(self) -> None:
        for host in ("localhost:8765", "127.0.0.1:8765", "[::1]:8765"):
            with self.subTest(host=host):
                self.assertTrue(is_valid_loopback_host(host, 8765))

    def test_is_valid_loopback_host_rejects_missing_malformed_external_and_wrong_port(self) -> None:
        invalid_hosts = [
            None,
            "",
            "localhost",
            "localhost:9999",
            "evil.example:8765",
            "192.168.1.20:8765",
            "0.0.0.0:8765",
            "127.0.0.1:bad",
            "127.0.0.1:8765/path",
            "user@127.0.0.1:8765",
            "127.0.0.1:8765 evil.example",
        ]

        for host in invalid_hosts:
            with self.subTest(host=host):
                self.assertFalse(is_valid_loopback_host(host, 8765))

    def test_is_valid_loopback_host_header_reads_host_header(self) -> None:
        self.assertTrue(
            is_valid_loopback_host_header({"Host": "127.0.0.1:8765"}, 8765)
        )
        self.assertFalse(is_valid_loopback_host_header({}, 8765))

    def test_local_host_forbidden_payload_does_not_expose_sensitive_values(self) -> None:
        payload = local_host_forbidden_payload()
        rendered = str(payload)

        self.assertEqual(payload["error"], "forbidden_host")
        self.assertNotIn("evil.example", rendered)
        self.assertNotIn("127.0.0.1", rendered)
        self.assertNotIn("SECRET", rendered)
        self.assertNotIn("Traceback", rendered)
        self.assertNotIn("/home/adolfo/Documents/Deals", rendered)


class StopProcessTests(unittest.TestCase):
    def test_stop_process_targets_process_group_on_posix(self) -> None:
        proc = _FakeProc()
        calls: list[tuple[int, signal.Signals]] = []

        stop_process(
            proc,
            os_name="posix",
            getpgid=lambda _pid: 456,
            killpg=lambda pgid, sig: calls.append((pgid, sig)),
        )

        self.assertEqual(calls, [(456, signal.SIGTERM)])
        self.assertEqual(proc.terminate_called, 0)
        self.assertEqual(proc.kill_called, 0)

    def test_stop_process_escalates_to_sigkill_after_timeout(self) -> None:
        proc = _FakeProc(timeout=True)
        calls: list[tuple[int, signal.Signals]] = []

        stop_process(
            proc,
            os_name="posix",
            getpgid=lambda _pid: 456,
            killpg=lambda pgid, sig: calls.append((pgid, sig)),
        )

        self.assertEqual(calls, [(456, signal.SIGTERM), (456, signal.SIGKILL)])
        self.assertEqual(proc.kill_called, 0)

    def test_stop_process_noops_when_process_is_already_done(self) -> None:
        proc = _FakeProc(done=True)

        stop_process(proc, os_name="posix", getpgid=lambda _pid: 456, killpg=lambda *_a: None)

        self.assertEqual(proc.wait_calls, [])
        self.assertEqual(proc.terminate_called, 0)
        self.assertEqual(proc.kill_called, 0)

    def test_stop_process_uses_terminate_kill_wait_injected_hooks_on_windows(self) -> None:
        proc = _FakeProc()
        calls = []

        stop_process(
            proc,
            os_name="nt",
            terminate_fn=lambda: calls.append("terminate"),
            kill_fn=lambda: calls.append("kill"),
            wait_fn=lambda timeout=None: calls.append(("wait", timeout)),
        )

        self.assertEqual(calls, ["terminate", ("wait", 3.0)])

    def test_stop_process_uses_injected_kill_when_windows_wait_times_out(self) -> None:
        proc = _FakeProc(timeout=True)
        calls = []

        def fake_wait(timeout=None):
            calls.append(("wait", timeout))
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)

        stop_process(
            proc,
            os_name="nt",
            terminate_fn=lambda: calls.append("terminate"),
            kill_fn=lambda: calls.append("kill"),
            wait_fn=fake_wait,
        )

        self.assertEqual(calls, ["terminate", ("wait", 3.0), "kill"])


class PublicErrorRedactionTests(unittest.TestCase):
    def test_redact_sensitive_text_removes_secrets_paths_and_tracebacks(self) -> None:
        raw = (
            "Traceback (most recent call last): key=STEAMSECRET123 "
            "token=123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabc "
            "https://discord.com/api/webhooks/123/secret "
            "/home/adolfo/Documents/Deals/private.txt /usr/bin/python3 "
            "/etc/hosts /srv/app/config.json /private/tmp/app.log _MEIPASS"
        )

        redacted = redact_sensitive_text(raw, extra_values=["STEAMSECRET123"])

        self.assertNotIn("Traceback", redacted)
        self.assertNotIn("STEAMSECRET123", redacted)
        self.assertNotIn("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabc", redacted)
        self.assertNotIn("discord.com/api/webhooks", redacted)
        self.assertNotIn("/home/adolfo", redacted)
        self.assertNotIn("/usr/bin/python3", redacted)
        self.assertNotIn("/etc/hosts", redacted)
        self.assertNotIn("/srv/app/config.json", redacted)
        self.assertNotIn("/private/tmp/app.log", redacted)
        self.assertNotIn("_MEIPASS", redacted)
        self.assertIn("[redactado]", redacted)
        self.assertIn("[ruta]", redacted)

    def test_redact_sensitive_text_tolerates_unavailable_cwd(self) -> None:
        with patch(
            "shared_web_infra.Path.cwd",
            side_effect=FileNotFoundError("cwd no longer exists"),
        ):
            redacted = redact_sensitive_text(
                "Traceback at /tmp/private key=STEAMSECRET123",
                extra_values=["STEAMSECRET123"],
            )

        self.assertNotIn("Traceback", redacted)
        self.assertNotIn("/tmp/private", redacted)
        self.assertNotIn("STEAMSECRET123", redacted)
        self.assertIn("[ruta]", redacted)
        self.assertIn("[redactado]", redacted)

    def test_redact_sensitive_text_preserves_safe_progress_metrics(self) -> None:
        raw = (
            "Progreso 7 /10 juegos (70%); deals /reviews /cache: 12 /34 /56; "
            "historial/cache 8/10; mejor precio local 4/5"
        )

        redacted = redact_sensitive_text(raw)

        self.assertIn("7 /10 juegos", redacted)
        self.assertIn("70%", redacted)
        self.assertIn("deals /reviews /cache: 12 /34 /56", redacted)
        self.assertIn("historial/cache 8/10", redacted)
        self.assertIn("mejor precio local 4/5", redacted)
        self.assertNotIn("[ruta]", redacted)

    def test_redact_sensitive_text_still_redacts_paths_near_metrics(self) -> None:
        raw = (
            "Cache 12 /34 listo; ruta /cache/private.txt; "
            "ruta simple /cache; otra ruta /123/private; home /home/example-user/private.txt"
        )

        redacted = redact_sensitive_text(raw)

        self.assertIn("12 /34 listo", redacted)
        self.assertNotIn("/cache/private.txt", redacted)
        self.assertNotIn("ruta simple /cache", redacted)
        self.assertNotIn("/123/private", redacted)
        self.assertNotIn("/home/example-user", redacted)
        self.assertIn("[ruta]", redacted)

    def test_safe_public_error_payload_sanitizes_exception_detail(self) -> None:
        payload = safe_public_error_payload(
            "boom",
            "No se pudo completar.",
            exc=RuntimeError("falló en /tmp/private con webhook=https://discord.com/api/webhooks/1/abc"),
        )

        self.assertEqual(payload["error"], "boom")
        self.assertEqual(payload["message"], "No se pudo completar.")
        self.assertNotIn("/tmp/private", payload["detail"])
        self.assertNotIn("discord.com/api/webhooks", payload["detail"])
