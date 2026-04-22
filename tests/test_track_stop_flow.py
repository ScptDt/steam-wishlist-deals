from __future__ import annotations

import json
import threading
import unittest


class _FakeHandler:
    def __init__(self) -> None:
        self.sent = []

    def _send_json(self, payload, status=200):
        self.sent.append((status, payload))


class _FakeProc:
    def __init__(self, *, done=False):
        self._done = done

    def poll(self):
        return 0 if self._done else None


class _FakeStdout:
    def __init__(self, lines):
        self._lines = list(lines)

    def __iter__(self):
        return iter(self._lines)


class _FakeSseProc:
    def __init__(self, *, returncode=0, lines=None):
        self.returncode = returncode
        self.stdout = _FakeStdout(lines or [])
        self.wait_called = 0

    def wait(self):
        self.wait_called += 1
        return self.returncode


class TrackStopFlowTests(unittest.TestCase):
    def test_serve_stop_returns_not_running_when_no_process_exists(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        handler = _FakeHandler()
        original_proc = module._running_proc
        original_lock = module._proc_lock
        module._running_proc = None
        module._proc_lock = threading.Lock()
        try:
          Handler._serve_stop(handler)
        finally:
          module._running_proc = original_proc
          module._proc_lock = original_lock

        self.assertEqual(
            handler.sent,
            [
                (
                    200,
                    {
                        "status": "not_running",
                        "message": "No había una ejecución activa para detener.",
                    },
                )
            ],
        )

    def test_serve_stop_clears_stale_finished_process(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        handler = _FakeHandler()
        original_proc = module._running_proc
        original_lock = module._proc_lock
        module._running_proc = _FakeProc(done=True)
        module._proc_lock = threading.Lock()
        try:
          Handler._serve_stop(handler)
          running_after = module._running_proc
        finally:
          module._running_proc = original_proc
          module._proc_lock = original_lock

        self.assertIsNone(running_after)
        self.assertEqual(
            handler.sent,
            [
                (
                    200,
                    {
                        "status": "not_running",
                        "message": "La ejecución ya había terminado.",
                    },
                )
            ],
        )

    def test_serve_stop_returns_stopped_for_active_process(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        handler = _FakeHandler()
        proc = _FakeProc(done=False)
        original_proc = module._running_proc
        original_lock = module._proc_lock
        original_stop_process = module.stop_process

        def fake_stop_process(target_proc):
            target_proc._done = True

        module._running_proc = proc
        module._proc_lock = threading.Lock()
        module.stop_process = fake_stop_process
        try:
          Handler._serve_stop(handler)
          running_after = module._running_proc
        finally:
          module._running_proc = original_proc
          module._proc_lock = original_lock
          module.stop_process = original_stop_process

        self.assertIsNone(running_after)
        self.assertEqual(
            handler.sent,
            [
                (
                    200,
                    {
                        "status": "stopped",
                        "message": "La ejecución se detuvo correctamente.",
                    },
                )
            ],
        )

    def test_serve_stop_returns_stop_timeout_if_proc_remains_active(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        handler = _FakeHandler()
        proc = _FakeProc(done=False)
        original_proc = module._running_proc
        original_lock = module._proc_lock
        original_stop_process = module.stop_process

        module._running_proc = proc
        module._proc_lock = threading.Lock()
        module.stop_process = lambda _proc: None
        try:
          Handler._serve_stop(handler)
          running_after = module._running_proc
        finally:
          module._running_proc = original_proc
          module._proc_lock = original_lock
          module.stop_process = original_stop_process

        self.assertIs(running_after, proc)
        self.assertEqual(
            handler.sent,
            [
                (
                    500,
                    {
                        "status": "stop_timeout",
                        "message": "Se intentó detener la ejecución, pero el proceso sigue activo.",
                    },
                )
            ],
        )

    def test_sse_done_callback_clears_running_proc_and_emits_done(self) -> None:
        import steam_deals_web as module

        proc = _FakeSseProc(returncode=0)
        original_proc = module._running_proc
        original_lock = module._proc_lock
        module._running_proc = proc
        module._proc_lock = threading.Lock()

        events = []

        def emit_sse(payload):
            events.append(payload)
            return True

        def clear_running_proc():
            with module._proc_lock:
                module._running_proc = None

        def handle_process_done(done_proc, emit_sse_fn):
            clear_running_proc()
            emit_sse_fn(
                {
                    "type": "done",
                    "exit_code": done_proc.returncode,
                    "files": ["/tmp/out/report.html"],
                }
            )

        try:
          handle_process_done(proc, emit_sse)
          running_after = module._running_proc
        finally:
          module._running_proc = original_proc
          module._proc_lock = original_lock

        self.assertIsNone(running_after)
        self.assertEqual(
            events,
            [
                {
                    "type": "done",
                    "exit_code": 0,
                    "files": ["/tmp/out/report.html"],
                }
            ],
        )
