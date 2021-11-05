# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import call, patch

from charms.operator_libs_linux.v0 import systemd


@patch("charms.operator_libs_linux.v0.systemd.subprocess")
class TestSnapCache(unittest.TestCase):
    def test_service(self, mock_subp):
        mock_subp.call.return_value = 0
        success = systemd.service("is-active", "mysql")
        mock_subp.call.assert_called_with(["systemctl", "is-active", "mysql"])
        self.assertTrue(success)

        mock_subp.call.return_value = 1
        success = systemd.service("is-active", "mysql")
        mock_subp.call.assert_called_with(["systemctl", "is-active", "mysql"])
        self.assertFalse(success)

    def test_service_running(self, mock_subp):
        mock_subp.call.return_value = 0
        is_running = systemd.service_running("mysql")
        mock_subp.call.assert_called_with(["systemctl", "is-active", "mysql"])
        self.assertTrue(is_running)

        mock_subp.call.return_value = 1
        is_running = systemd.service_running("mysql")
        mock_subp.call.assert_called_with(["systemctl", "is-active", "mysql"])
        self.assertFalse(is_running)

    def test_service_start(self, mock_subp):
        mock_subp.call.return_value = 0
        started = systemd.service_start("mysql")
        mock_subp.call.assert_called_with(["systemctl", "start", "mysql"])
        self.assertTrue(started)

        mock_subp.call.return_value = 1
        started = systemd.service_start("mysql")
        mock_subp.call.assert_called_with(["systemctl", "start", "mysql"])
        self.assertFalse(started)

    def test_service_stop(self, mock_subp):
        mock_subp.call.return_value = 0
        stopped = systemd.service_stop("mysql")
        mock_subp.call.assert_called_with(["systemctl", "stop", "mysql"])
        self.assertTrue(stopped)

        mock_subp.call.return_value = 1
        stopped = systemd.service_stop("mysql")
        mock_subp.call.assert_called_with(["systemctl", "stop", "mysql"])
        self.assertFalse(stopped)

    def test_service_restart(self, mock_subp):
        mock_subp.call.return_value = 0
        restarted = systemd.service_restart("mysql")
        mock_subp.call.assert_called_with(["systemctl", "restart", "mysql"])
        self.assertTrue(restarted)

        mock_subp.call.return_value = 1
        restarted = systemd.service_restart("mysql")
        mock_subp.call.assert_called_with(["systemctl", "restart", "mysql"])
        self.assertFalse(restarted)

    def test_service_reload(self, mock_subp):
        # We reload succesfully.
        mock_subp.call.return_value = 0
        reloaded = systemd.service_reload("mysql")
        mock_subp.call.assert_called_with(["systemctl", "reload", "mysql"])
        self.assertTrue(reloaded)

        # We can't reload, so we restart
        mock_subp.call.side_effect = (1, 0)
        reloaded = systemd.service_reload("mysql", restart_on_failure=True)
        mock_subp.call.assert_has_calls(
            [call(["systemctl", "reload", "mysql"]), call(["systemctl", "restart", "mysql"])]
        )
        self.assertTrue(reloaded)

        # We should only restart if requested.
        mock_subp.call.side_effect = (1, 0)
        reloaded = systemd.service_reload("mysql")
        mock_subp.call.assert_called_with(["systemctl", "reload", "mysql"])
        self.assertFalse(reloaded)

        # ... and if we fail at both, we should fail.
        mock_subp.call.side_effect = (1, 1)
        reloaded = systemd.service_reload("mysql", restart_on_failure=True)
        mock_subp.call.assert_has_calls(
            [call(["systemctl", "reload", "mysql"]), call(["systemctl", "restart", "mysql"])]
        )
        self.assertFalse(reloaded)

    def test_service_pause(self, mock_subp):
        # Service is running, so we stop and disable it.
        mock_subp.call.side_effect = (0, 0, 0, 0)
        paused = systemd.service_pause("mysql")
        mock_subp.call.assert_has_calls(
            [
                call(["systemctl", "is-active", "mysql"]),
                call(["systemctl", "stop", "mysql"]),
                call(["systemctl", "disable", "mysql"]),
                call(["systemctl", "mask", "mysql"]),
            ]
        )
        self.assertTrue(paused)

        # Service is not running.
        mock_subp.call.side_effect = (1, 0, 0)
        paused = systemd.service_pause("mysql")
        mock_subp.call.assert_has_calls(
            [
                call(["systemctl", "is-active", "mysql"]),
                call(["systemctl", "disable", "mysql"]),
                call(["systemctl", "mask", "mysql"]),
            ]
        )
        self.assertTrue(paused)

        # Could not stop service!
        mock_subp.call.side_effect = (0, 1, 0, 0)
        paused = systemd.service_pause("mysql")
        mock_subp.call.assert_has_calls(
            [
                call(["systemctl", "is-active", "mysql"]),
                call(["systemctl", "stop", "mysql"]),
                call(["systemctl", "disable", "mysql"]),
                call(["systemctl", "mask", "mysql"]),
            ]
        )
        self.assertFalse(paused)

        # Failures in disable and mask aren't handled.
        # TODO: might want to log a warning in that case.
        mock_subp.call.side_effect = (0, 0, 1, 1)
        paused = systemd.service_pause("mysql")
        mock_subp.call.assert_has_calls(
            [
                call(["systemctl", "is-active", "mysql"]),
                call(["systemctl", "stop", "mysql"]),
                call(["systemctl", "disable", "mysql"]),
                call(["systemctl", "mask", "mysql"]),
            ]
        )
        self.assertTrue(paused)

    def test_service_resume(self, mock_subp):
        # Service is already running
        mock_subp.call.side_effect = (0, 0, 0)
        resumed = systemd.service_resume("mysql")
        mock_subp.call.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"]),
                call(["systemctl", "enable", "mysql"]),
                call(["systemctl", "is-active", "mysql"]),
            ]
        )
        self.assertTrue(resumed)

        # Service was stopped
        mock_subp.call.side_effect = (0, 0, 1, 0)
        resumed = systemd.service_resume("mysql")
        mock_subp.call.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"]),
                call(["systemctl", "enable", "mysql"]),
                call(["systemctl", "is-active", "mysql"]),
                call(["systemctl", "start", "mysql"]),
            ]
        )
        self.assertTrue(resumed)

        # Could not start service!
        mock_subp.call.side_effect = (0, 0, 1, 1)
        resumed = systemd.service_resume("mysql")
        mock_subp.call.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"]),
                call(["systemctl", "enable", "mysql"]),
                call(["systemctl", "is-active", "mysql"]),
                call(["systemctl", "start", "mysql"]),
            ]
        )
        self.assertFalse(resumed)

        # Failures in unmask and enable aren't handled.
        # TODO: might want to log a warning.
        mock_subp.call.side_effect = (1, 1, 1, 0)
        resumed = systemd.service_resume("mysql")
        mock_subp.call.assert_has_calls(
            [
                call(["systemctl", "unmask", "mysql"]),
                call(["systemctl", "enable", "mysql"]),
                call(["systemctl", "is-active", "mysql"]),
                call(["systemctl", "start", "mysql"]),
            ]
        )
        self.assertTrue(resumed)
