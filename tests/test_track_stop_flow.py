from __future__ import annotations

import json
import threading
import unittest


class _FakeHandler:
    def __init__(self, body=None) -> None:
        self.sent = []
        self.body = body
        self.read_json_body_calls = 0

    def _send_json(self, payload, status=200):
        self.sent.append((status, payload))

    def _read_json_body(self):
        self.read_json_body_calls += 1
        return self.body


class _FakeProc:
    def __init__(self, *, done=False, scheduled=False):
        self._done = done
        self.scheduled = scheduled

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
    def test_scheduled_run_uses_running_proc_lock_and_rejects_overlap(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        # Arrange: start a scheduled run with faked subprocess/SSE plumbing.
        scheduled_body = {
            "config": {},
            "filters": {"schedule_enabled": True, "schedule_hours": "2"},
        }
        handler = _FakeHandler(body=scheduled_body)
        conflict_handler = _FakeHandler(body=scheduled_body)
        proc = _FakeProc(done=False, scheduled=True)
        started_commands = []
        running_seen_during_stream = []

        original_proc = module._running_proc
        original_lock = module._proc_lock
        original_output_dir = Handler.output_dir
        original_load_config = module.load_config
        original_save_config = module.save_config
        original_build_runtime = module.build_runtime_command_and_env
        original_start_subprocess = module.start_text_subprocess
        original_stream_process = module.stream_process_as_sse

        def fake_build_runtime_command_and_env(config, filters, *, pd2=False):
            return [
                "python",
                "steam_deals_generator.py",
                "--web-run",
                "--schedule",
                str(filters["schedule_hours"]),
            ], {}

        def fake_start_text_subprocess(command, env=None):
            started_commands.append(list(command))
            return proc

        def fake_stream_process_as_sse(_handler, stream_proc, _on_stdout_line, _on_done):
            running_seen_during_stream.append(module._running_proc)
            Handler._serve_run_sse(conflict_handler)
            stream_proc._done = True

        module._running_proc = None
        module._proc_lock = threading.Lock()
        module.load_config = lambda: {}
        module.save_config = lambda _cfg: None
        module.build_runtime_command_and_env = fake_build_runtime_command_and_env
        module.start_text_subprocess = fake_start_text_subprocess
        module.stream_process_as_sse = fake_stream_process_as_sse
        try:
            # Act: the nested run attempts to start while the scheduled proc is active.
            Handler._serve_run_sse(handler)
            running_after = module._running_proc
        finally:
            module._running_proc = original_proc
            module._proc_lock = original_lock
            Handler.output_dir = original_output_dir
            module.load_config = original_load_config
            module.save_config = original_save_config
            module.build_runtime_command_and_env = original_build_runtime
            module.start_text_subprocess = original_start_subprocess
            module.stream_process_as_sse = original_stream_process

        # Assert: the scheduled proc occupies the shared lock and overlap returns 409.
        self.assertEqual(
            started_commands,
            [["python", "steam_deals_generator.py", "--web-run", "--schedule", "2"]],
        )
        self.assertEqual(running_seen_during_stream, [proc])
        self.assertEqual(conflict_handler.sent, [(409, {"error": "Already running"})])
        self.assertEqual(conflict_handler.read_json_body_calls, 0)
        self.assertIsNone(running_after)

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

    def test_serve_stop_stops_active_scheduled_process_and_clears_lock(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        # Arrange: an active scheduled subprocess is tracked as the running proc.
        handler = _FakeHandler()
        proc = _FakeProc(done=False, scheduled=True)
        stopped_processes = []
        original_proc = module._running_proc
        original_lock = module._proc_lock
        original_stop_process = module.stop_process

        def fake_stop_process(target_proc):
            stopped_processes.append(target_proc)
            target_proc._done = True

        module._running_proc = proc
        module._proc_lock = threading.Lock()
        module.stop_process = fake_stop_process
        try:
            # Act: Detener cancels the scheduled process before it can repeat.
            Handler._serve_stop(handler)
            running_after = module._running_proc
        finally:
            module._running_proc = original_proc
            module._proc_lock = original_lock
            module.stop_process = original_stop_process

        # Assert: stop_process handled the scheduled proc and the lock was cleared.
        self.assertEqual(stopped_processes, [proc])
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

    def test_serve_stop_keeps_scheduled_process_tracked_on_stop_timeout(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        # Arrange: stop_process is invoked but the scheduled subprocess stays alive.
        handler = _FakeHandler()
        proc = _FakeProc(done=False, scheduled=True)
        stopped_processes = []
        original_proc = module._running_proc
        original_lock = module._proc_lock
        original_stop_process = module.stop_process

        def fake_stop_process(target_proc):
            stopped_processes.append(target_proc)

        module._running_proc = proc
        module._proc_lock = threading.Lock()
        module.stop_process = fake_stop_process
        try:
            # Act: Detener reports failure because the process remains active.
            Handler._serve_stop(handler)
            running_after = module._running_proc
        finally:
            module._running_proc = original_proc
            module._proc_lock = original_lock
            module.stop_process = original_stop_process

        # Assert: active scheduled proc remains tracked; no false stopped status.
        self.assertEqual(stopped_processes, [proc])
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
