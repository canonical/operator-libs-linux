# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import subprocess
import unittest
from typing import List
from unittest.mock import MagicMock, call, patch

from charms.operator_libs_linux.v1 import systemd


def with_mock_subp(func):
    """Set up a `subprocess.run(...)` mock.

    Any function that uses this decorator should take a function as an argument. When
    called with a series of return codes, that function will mock out `subprocess.run(...)`,
    and set it to return those error codes, in order.

    The function returns the mock `subprocess.run(...)` object, so that routines such as
    assert_called_with can be called upon it.
    """

    @patch("charms.operator_libs_linux.v1.systemd.subprocess.run")
    def make_mocks_and_run(cls, mock_subp):
        def make_mock_run(returncodes: List[int], check: bool = False):
            side_effects = []
            for code in returncodes:
                if code != 0 and check:
                    side_effects.append(subprocess.CalledProcessError(code, "systemctl fail"))
                else:
                    mock_proc = MagicMock()
                    mock_proc.returncode = code
                    mock_proc.stdout = subprocess.PIPE,
                    mock_proc.stderr = subprocess.STDOUT,
                    mock_proc.check = check
                    side_effects.append(mock_proc)

            mock_subp.side_effect = tuple(side_effects)

            return mock_subp, {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "bufsize": 1,
                "encoding": "utf-8",
                "check": check,
            }

        func(cls, make_mock_run)

    return make_mocks_and_run


class TestSystemD(unittest.TestCase):
    @with_mock_subp
    def test_service(self, make_mock):
        mockp, kw = make_mock([0])

        success = systemd._systemctl("is-active", "mysql")
        mockp.assert_called_with(["systemctl", "is-active", "mysql"], **kw)
        self.assertEqual(success, 0)

        mockp, kw = make_mock([1], check=True)

        self.assertRaises(systemd.SystemdError, systemd._systemctl, "is-active", "mysql", check=True)
        mockp.assert_called_with(["systemctl", "is-active", "mysql"], **kw)

    @with_mock_subp
    def test_service_running(self, make_mock):
        mockp, kw = make_mock([0, 3])

        is_running = systemd.service_running("mysql")
        mockp.assert_called_with(["systemctl", "--quiet", "is-active", "mysql"], **kw)
        self.assertTrue(is_running)

        is_running = systemd.service_running("mysql")
        mockp.assert_called_with(["systemctl", "--quiet", "is-active", "mysql"], **kw)
        self.assertFalse(is_running)

    @with_mock_subp
    def test_service_failed(self, make_mock):
        mockp, kw = make_mock([0, 1])

        is_failed = systemd.service_failed("mysql")
        mockp.assert_called_with(["systemctl", "--quiet", "is-failed", "mysql"], **kw)
        self.assertTrue(is_failed)

        is_failed = systemd.service_failed("mysql")
        mockp.assert_called_with(["systemctl", "--quiet", "is-failed", "mysql", ], **kw)
        self.assertFalse(is_failed)

    @with_mock_subp
    def test_service_start(self, make_mock):
        mockp, kw = make_mock([0, 1], check=True)

        systemd.service_start("mysql")
        mockp.assert_called_with(["systemctl", "start", "mysql"], **kw)

        self.assertRaises(systemd.SystemdError, systemd.service_start, "mysql")
        mockp.assert_called_with(["systemctl", "start", "mysql"], **kw)

    @with_mock_subp
    def test_service_stop(self, make_mock):
        mockp, kw = make_mock([0, 1], check=True)

        systemd.service_stop("mysql")
        mockp.assert_called_with(["systemctl", "stop", "mysql"], **kw)

        self.assertRaises(systemd.SystemdError, systemd.service_stop, "mysql")
        mockp.assert_called_with(["systemctl", "stop", "mysql"], **kw)

    @with_mock_subp
    def test_service_restart(self, make_mock):
        mockp, kw = make_mock([0, 1], check=True)

        systemd.service_restart("mysql")
        mockp.assert_called_with(["systemctl", "restart", "mysql"], **kw)

        self.assertRaises(systemd.SystemdError, systemd.service_restart, "mysql")
        mockp.assert_called_with(["systemctl", "restart", "mysql"], **kw)

    @with_mock_subp
    def test_service_enable(self, make_mock):
        mockp, kw = make_mock([0, 1], check=True)

        systemd.service_enable("slurmd")
        mockp.assert_called_with(["systemctl", "enable", "slurmd"], **kw)

        self.assertRaises(systemd.SystemdError, systemd.service_enable, "slurmd")
        mockp.assert_called_with(["systemctl", "enable", "slurmd"], **kw)

    @with_mock_subp
    def test_service_disable(self, make_mock):
        mockp, kw = make_mock([0, 1], check=True)

        systemd.service_disable("slurmd")
        mockp.assert_called_with(["systemctl", "disable", "slurmd"], **kw)

        self.assertRaises(systemd.SystemdError, systemd.service_disable, "slurmd")
        mockp.assert_called_with(["systemctl", "disable", "slurmd"], **kw)

    @with_mock_subp
    def test_service_reload(self, make_mock):
        # We reload successfully.
        mockp, kw = make_mock([0], check=True)
        systemd.service_reload("mysql")
        mockp.assert_called_with(["systemctl", "reload", "mysql"], **kw)

        # We can't reload, so we restart
        mockp, kw = make_mock([1, 0], check=True)
        systemd.service_reload("mysql", restart_on_failure=True)
        mockp.assert_has_calls(
            [
                call(["systemctl", "reload", "mysql"], **kw),
                call(["systemctl", "restart", "mysql"], **kw),
            ]
        )

        # We should only restart if requested.
        mockp, kw = make_mock([1, 0], check=True)
        self.assertRaises(systemd.SystemdError, systemd.service_reload, "mysql")
        mockp.assert_called_with(["systemctl", "reload", "mysql"], **kw)

        # ... and if we fail at both, we should fail.
        mockp, kw = make_mock([1, 1], check=True)
        self.assertRaises(
            systemd.SystemdError, systemd.service_reload, "mysql", restart_on_failure=True
        )
        mockp.assert_has_calls(
            [
                call(["systemctl", "reload", "mysql"], **kw),
                call(["systemctl", "restart", "mysql"], **kw),
            ]
        )

    @with_mock_subp
    def test_service_pause(self, make_mock):
        # Test pause
        mockp, kw = make_mock([0, 0, 3])

        systemd.service_pause("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "disable", "--now", "mysql"], **kw),
                call(["systemctl", "mask", "mysql"], **kw),
                call(["systemctl", "--quiet", "is-active", "mysql"], **kw),
            ]
        )

        # Could not stop service!
        mockp, kw = make_mock([0, 0, 0])
        self.assertRaises(systemd.SystemdError, systemd.service_pause, "mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "disable", "--now", "mysql"], **kw),
                call(["systemctl", "mask", "mysql"], **kw),
                call(["systemctl", "--quiet", "is-active", "mysql"], **kw),
            ]
        )

    @with_mock_subp
    def test_service_resume(self, make_mock):
        # Service is already running
        mockp, kw = make_mock([0, 0, 0])
        systemd.service_resume("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"], **kw),
                call(["systemctl", "enable", "--now", "mysql"], **kw),
                call(["systemctl", "--quiet", "is-active", "mysql"], **kw),
            ]
        )

        # Service was stopped
        mockp, kw = make_mock([0, 0, 0])
        systemd.service_resume("mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"], **kw),
                call(["systemctl", "enable", "--now", "mysql"], **kw),
                call(["systemctl", "--quiet", "is-active", "mysql"], **kw),
            ]
        )

        # Could not start service!
        mockp, kw = make_mock([0, 0, 3])
        self.assertRaises(systemd.SystemdError, systemd.service_resume, "mysql")
        mockp.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"], **kw),
                call(["systemctl", "enable", "--now", "mysql"], **kw),
                call(["systemctl", "--quiet", "is-active", "mysql"], **kw),
            ]
        )

    @with_mock_subp
    def test_daemon_reload(self, make_mock):
        mockp, kw = make_mock([0, 1], check=True)

        systemd.daemon_reload()
        mockp.assert_called_with(["systemctl", "daemon-reload"], **kw)

        # Failed to reload systemd configuration.
        self.assertRaises(systemd.SystemdError, systemd.daemon_reload)
        mockp.assert_called_with(["systemctl", "daemon-reload"], **kw)
