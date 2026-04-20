from __future__ import annotations

import signal
import subprocess
import unittest

from shared_web_infra import stop_process


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
