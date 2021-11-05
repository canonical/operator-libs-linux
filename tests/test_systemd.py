# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

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
