from __future__ import annotations

import base64
import json
import signal
import subprocess
import unittest
import urllib.parse
import urllib.request
import time

from steam_tools_desktop import (
    FALLBACK_REASON_MESSAGES,
    _candidate_urls,
    _config_probe_url,
    _discover_live_url,
    _fallback_url,
    _probe_steam_deals_server,
    _wait_server,
    decode_share_payload,
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
