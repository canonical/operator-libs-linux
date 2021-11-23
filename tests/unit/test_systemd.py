# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import MagicMock, call, patch

from charms.operator_libs_linux.v0 import systemd


def with_mock_subp(func):
    """Decorator that sets up a Popen mock.

    Any function that uses this decorator should take a function as an argument. When
    called wtih a series of return codes, that function will mock out subprocess.Popen,
    and set it to return those error codes, in order.

    The function returns the mock Popen object, so that routines such as
    assert_called_with can be called upon it, along with the return from
    systemd.popen_kwargs, for convenience when composing call objects.

    """

    @patch("charms.operator_libs_linux.v0.systemd.subprocess")
    def make_mocks_and_run(cls, mock_subp):
        def make_mock_popen(returncodes: list[int], lines: list[str] = None, stdout: str = None):
            lines = lines if lines is not None else ("", "")

            mock_subp.PIPE = mock_subp.STDOUT = stdout or ""

            side_effects = []

            for code in returncodes:
                mock_proc = MagicMock()
                mock_proc.wait.return_value = None
                mock_proc.stdout.readline.side_effect = lines
                mock_proc.returncode = code
                side_effects.append(mock_proc)

            mock_popen = mock_subp.Popen
            mock_popen.side_effect = tuple(side_effects)

            return mock_popen, systemd.popen_kwargs()

        func(cls, make_mock_popen)

    return make_mocks_and_run


class TestSystemD(unittest.TestCase):
    @with_mock_subp
    def test_service(self, make_mock):
        mockp, kw = make_mock([0, 1])

        success = systemd.service("is-active", "mysql")
        mockp.assert_called_with(["systemctl", "is-active", "mysql"], **kw)
        self.assertTrue(success)

        success = systemd.service("is-active", "mysql")
        mockp.assert_called_with(["systemctl", "is-active", "mysql"], **kw)
        self.assertFalse(success)

    @with_mock_subp
    def test_service_running(self, make_mock):
        mockp, kw = make_mock([0, 1])

        is_running = systemd.service_running("mysql")
        mockp.assert_called_with(["systemctl", "is-active", "mysql", "--quiet"], **kw)
        self.assertTrue(is_running)

        is_running = systemd.service_running("mysql")
        mockp.assert_called_with(["systemctl", "is-active", "mysql", "--quiet"], **kw)
        self.assertFalse(is_running)

    @with_mock_subp
    def test_service_start(self, make_mock):
        mockp, kw = make_mock([0, 1])

        started = systemd.service_start("mysql")
        mockp.assert_called_with(["systemctl", "start", "mysql"], **kw)
        self.assertTrue(started)

        started = systemd.service_start("mysql")
        mockp.assert_called_with(["systemctl", "start", "mysql"], **kw)
        self.assertFalse(started)

    @with_mock_subp
    def test_service_stop(self, make_mock):
        mockp, kw = make_mock([0, 1])

        stopped = systemd.service_stop("mysql")
        mockp.assert_called_with(["systemctl", "stop", "mysql"], **kw)
        self.assertTrue(stopped)

        stopped = systemd.service_stop("mysql")
        mockp.assert_called_with(["systemctl", "stop", "mysql"], **kw)
        self.assertFalse(stopped)

    @with_mock_subp
    def test_service_restart(self, make_mock):
        mockp, kw = make_mock([0, 1])

        restarted = systemd.service_restart("mysql")
        mockp.assert_called_with(["systemctl", "restart", "mysql"], **kw)
        self.assertTrue(restarted)

        restarted = systemd.service_restart("mysql")
        mockp.assert_called_with(["systemctl", "restart", "mysql"], **kw)
        self.assertFalse(restarted)

    @with_mock_subp
    def test_service_reload(self, make_mock):
        # We reload succesfully.
        mockp, kw = make_mock([0])
        reloaded = systemd.service_reload("mysql")
        mockp.assert_called_with(["systemctl", "reload", "mysql"], **kw)
        self.assertTrue(reloaded)

        # We can't reload, so we restart
        mockp, kw = make_mock([1, 0])
        reloaded = systemd.service_reload("mysql", restart_on_failure=True)
        mockp.assert_has_calls(
            [
                call(["systemctl", "reload", "mysql"], **kw),
                call(["systemctl", "restart", "mysql"], **kw),
            ]
        )
        self.assertTrue(reloaded)

        # We should only restart if requested.
        mockp, kw = make_mock([1, 0])
        reloaded = systemd.service_reload("mysql")
        mockp.assert_called_with(["systemctl", "reload", "mysql"], **kw)
        self.assertFalse(reloaded)

        # ... and if we fail at both, we should fail.
        mockp, kw = make_mock([1, 1])
        reloaded = systemd.service_reload("mysql", restart_on_failure=True)
        mockp.assert_has_calls(
            [
                call(["systemctl", "reload", "mysql"], **kw),
                call(["systemctl", "restart", "mysql"], **kw),
            ]
        )
        self.assertFalse(reloaded)

    @with_mock_subp
    def test_service_pause(self, make_mock):
        # Test pause
        mockp, kw = make_mock([0, 0, 1])

        paused = systemd.service_pause("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "disable", "mysql", "--now"], **kw),
                call(["systemctl", "mask", "mysql"], **kw),
                call(["systemctl", "is-active", "mysql", "--quiet"], **kw),
            ]
        )
        self.assertTrue(paused)

        # Could not stop service!
        mockp, kw = make_mock([0, 0, 0])
        paused = systemd.service_pause("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "disable", "mysql", "--now"], **kw),
                call(["systemctl", "mask", "mysql"], **kw),
                call(["systemctl", "is-active", "mysql", "--quiet"], **kw),
            ]
        )
        self.assertFalse(paused)

        # Failures in disable and mask aren't handled.
        mockp, kw = make_mock([1, 1, 1])
        paused = systemd.service_pause("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "disable", "mysql", "--now"], **kw),
                call(["systemctl", "mask", "mysql"], **kw),
                call(["systemctl", "is-active", "mysql", "--quiet"], **kw),
            ]
        )
        self.assertTrue(paused)

    @with_mock_subp
    def test_service_resume(self, make_mock):

        # Service is already running
        mockp, kw = make_mock([0, 0, 0])
        resumed = systemd.service_resume("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"], **kw),
                call(["systemctl", "enable", "mysql", "--now"], **kw),
                call(["systemctl", "is-active", "mysql", "--quiet"], **kw),
            ]
        )
        self.assertTrue(resumed)

        # Service was stopped
        mockp, kw = make_mock([0, 0, 0])
        resumed = systemd.service_resume("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"], **kw),
                call(["systemctl", "enable", "mysql", "--now"], **kw),
                call(["systemctl", "is-active", "mysql", "--quiet"], **kw),
            ]
        )
        self.assertTrue(resumed)

        # Could not start service!
        mockp, kw = make_mock([0, 0, 1])
        resumed = systemd.service_resume("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"], **kw),
                call(["systemctl", "enable", "mysql", "--now"], **kw),
                call(["systemctl", "is-active", "mysql", "--quiet"], **kw),
            ]
        )
        self.assertFalse(resumed)

        # Failures in unmask and enable aren't handled.
        mockp, kw = make_mock([1, 1, 0])

        resumed = systemd.service_resume("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"], **kw),
                call(["systemctl", "enable", "mysql", "--now"], **kw),
                call(["systemctl", "is-active", "mysql", "--quiet"], **kw),
            ]
        )
        self.assertTrue(resumed)
