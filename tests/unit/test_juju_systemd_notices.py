#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for juju systemd notices charm library."""

import argparse
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from charms.operator_libs_linux.v0.juju_systemd_notices import (
    ServiceStartedEvent,
    ServiceStoppedEvent,
    SystemdNotices,
    _async_load_services,
    _dbus_path_to_name,
    _get_service_state,
    _juju_systemd_notices_daemon,
    _main,
    _name_to_dbus_path,
    _send_juju_notification,
    _systemd_unit_changed,
)
from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, ErrorType
from dbus_fast.errors import DBusError
from ops.charm import CharmBase, InstallEvent, StopEvent
from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Harness


class MockNoticesCharm(CharmBase):
    """Mock charm to use in unit tests for testing notices daemon."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._systemd_notices = SystemdNotices(self, ["foobar"])
        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.stop: self._on_stop,
            self.on.service_foobar_started: self._on_foobar_started,
            self.on.service_foobar_stopped: self._on_foobar_stopped,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, _: InstallEvent) -> None:
        """Subscribe to foobar service to watch for events."""
        self._systemd_notices.subscribe()

    def _on_stop(self, _: StopEvent) -> None:
        """Stop watching foobar service as machine is removed."""
        self._systemd_notices.stop()

    def _on_foobar_started(self, _: ServiceStartedEvent) -> None:
        """Set status to active after systemctl marks service as active."""
        self.unit.status = ActiveStatus("foobar running :)")

    def _on_foobar_stopped(self, _: ServiceStoppedEvent) -> None:
        """Set status to blocked after systemctl marks service as inactive."""
        self.unit.status = BlockedStatus("foobar not running :(")


class TestJujuSystemdNoticesCharmAPI(unittest.TestCase):
    """Test public API meant to be used within charms."""

    def setUp(self) -> None:
        self.harness = Harness(MockNoticesCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.symlink_to")
    @patch("subprocess.check_output")
    @patch("pathlib.Path.exists")
    def test_subscribe(self, mock_exists, mock_subp, *_) -> None:
        # Scenario 1 - Subscribe success but no pre-existing service file.
        mock_exists.return_value = False
        self.harness.charm.on.install.emit()

        # Scenario 2 - Subscribe success and pre-existing service file.
        mock_exists.return_value = True
        self.harness.charm.on.install.emit()

        # Scenario 3 - Subscribe success but systemctl fails to start notices daemon.
        mock_subp.side_effect = subprocess.CalledProcessError(1, "systemctl start foobar")
        with self.assertRaises(subprocess.CalledProcessError):
            self.harness.charm.on.install.emit()

    @patch("subprocess.check_output")
    def test_stop(self, *_) -> None:
        """Test that notices service is successfully disabled.

        Note:
            For test to pass, the mock _on_stop must successfully complete.
        """
        self.harness.charm.on.stop.emit()

    def test_service_started(self) -> None:
        """Test that service_{name}_started is properly attached to charm."""
        self.harness.charm.on.service_foobar_started.emit()
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("foobar running :)"))

    def test_service_stopped(self) -> None:
        """Test that service_{name}_stopped is properly attached to charm."""
        self.harness.charm.on.service_foobar_stopped.emit()
        self.assertEqual(self.harness.charm.unit.status, BlockedStatus("foobar not running :("))


class TestJujuSystemdNoticesDaemon(unittest.IsolatedAsyncioTestCase):
    """Test asynchronous bits of the Juju systemd notices daemon."""

    def test_name_to_dbus_path(self) -> None:
        dbus_path = _name_to_dbus_path("\\foobar@ubuntu.juju_systemd-notices")
        self.assertEqual(
            dbus_path,
            "/org/freedesktop/systemd1/unit/_5cfoobar_40ubuntu_2ejuju_5fsystemd_2dnotices",
        )

    def test_dbus_path_to_name(self) -> None:
        name = _dbus_path_to_name(
            "/org/freedesktop/systemd1/unit/_5cfoobar_40ubuntu_2ejuju_5fsystemd_2dnotices"
        )
        self.assertEqual(name, "\\foobar@ubuntu.juju_systemd-notices")

    @patch("charms.operator_libs_linux.v0.juju_systemd_notices._send_juju_notification")
    @patch("dbus_fast.signature.Variant")
    @patch("dbus_fast.message.Message")
    async def test_systemd_unit_changed(self, mock_message, mock_variant, *_) -> None:
        mock_message.path = "/org/freedesktop/systemd1/unit/foobar"
        mock_message.interface = "foobar"
        mock_message.member = "unit"

        # Scenario 1 - ActiveStatus not in properties.
        mock_message.body = ["", {"Baz": ""}]
        self.assertFalse(_systemd_unit_changed(mock_message))

        # Scenario 2 - Service name not in _service_states.
        mock_message.body = ["", {"ActiveState": ""}]
        with patch("charms.operator_libs_linux.v0.juju_systemd_notices._service_states", {}):
            self.assertFalse(_systemd_unit_changed(mock_message))

        # Scenario 3 - Service state ends with -ing.
        mock_variant.value = "activating"
        mock_message.body = ["", {"ActiveState": mock_variant}]
        with patch(
            "charms.operator_libs_linux.v0.juju_systemd_notices._service_states",
            {"foobar": "inactive"},
        ):
            self.assertFalse(_systemd_unit_changed(mock_message))

        # Scenario 4 - Current state matches previous state.
        mock_variant.value = "inactive"
        mock_message.body = ["", {"ActiveState": mock_variant}]
        with patch(
            "charms.operator_libs_linux.v0.juju_systemd_notices._service_states",
            {"foobar": "inactive"},
        ):
            self.assertFalse(_systemd_unit_changed(mock_message))

        # Scenario 5 - Desired outcome (result of _systemd_unit_changed is True).
        mock_variant.value = "active"
        mock_message.body = ["", {"ActiveState": mock_variant}]
        with patch(
            "charms.operator_libs_linux.v0.juju_systemd_notices._service_states",
            {"foobar": "inactive"},
        ):
            self.assertTrue(_systemd_unit_changed(mock_message))

    @patch("charms.operator_libs_linux.v0.juju_systemd_notices._juju_unit", "foobar/0")
    @patch("asyncio.create_subprocess_exec")
    async def test_send_juju_notification(self, mock_subp, *_) -> None:
        # Scenario 1 - .service in service name and notification succeeds.
        mock_p = AsyncMock()
        mock_p.wait.return_value = None
        mock_p.returncode = 0
        mock_subp.return_value = mock_p
        await _send_juju_notification("foobar.service", "active")

        # Scenario 2 - No .service in name and state is stopped but notification fails.
        mock_p = AsyncMock()
        mock_p.wait.return_value = None
        mock_p.returncode = 1
        mock_subp.return_value = mock_p
        await _send_juju_notification("foobar", "inactive")

    async def test_get_service_state(self) -> None:
        # Scenario 1 - Succeed getting the state of the current service.
        #   Note: Requires dbus to be installed on your test host
        #   and the test host to have a running cron service through systemd.
        with patch("dbus_fast.signature.Variant") as mock_variant:
            mock_variant.value = "active"
            sysbus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            state = await _get_service_state(sysbus, "cron.service")
            self.assertEqual(state, "active")

        # Scenario 2 - DBusError is encountered when getting the state of a service.
        mock_sysbus = AsyncMock()
        mock_sysbus.introspect = AsyncMock(
            side_effect=DBusError(ErrorType.TIMEOUT, "Timeout waiting DBus")
        )
        state = await _get_service_state(mock_sysbus, "foobar")
        self.assertEqual(state, "unknown")

    @patch("charms.operator_libs_linux.v0.juju_systemd_notices._get_service_state")
    @patch("pathlib.Path.iterdir")
    @patch("pathlib.Path.exists")
    async def test_async_load_services(self, mock_exists, mock_iterdir, mock_state) -> None:
        # Scenario 1 - Hooks dir does not exist.
        mock_exists.return_value = False
        self.assertIsNone(await _async_load_services())

        # Scenario 2 - There are no services to watch.
        mock_exists.return_value = True
        mock_iterdir.return_value = []
        self.assertIsNone(await _async_load_services())

        # Scenario 3 - Desired outcome (services are subscribed to for watching).
        mock_exists.return_value = True
        mock_iterdir.return_value = [
            Path("service-foobar-started"),
            Path("service-foobar-stopped"),
            Path("dispatch"),  # Ensure that unmatched hooks are ignored/not registered.
        ]
        mock_state.return_value = "active"
        self.assertIsNone(await _async_load_services())

    @patch("pathlib.Path.exists", return_value=False)
    @patch("asyncio.Event.wait")
    async def test_juju_systemd_notices_daemon(self, *_) -> None:
        # Desired outcome is that _juju_systemd_notices does not fail to start.
        await _juju_systemd_notices_daemon()

    @patch("charms.operator_libs_linux.v0.juju_systemd_notices._juju_systemd_notices_daemon")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main(self, mocked_args, *_) -> None:
        # Scenario 1 - Desired outcome (juju-systemd-notices daemon starts successfully)
        #   and debug is set to True.
        mocked_args.return_value = argparse.Namespace(debug=True, unit="foobar/0")
        _main()

        # Scenario 2 - Desired outcome (juju-systemd-notices daemon starts successfully)
        #   and debug is set to False
        mocked_args.return_value = argparse.Namespace(debug=False, unit="foobar/0")
        _main()

        # Scenario 3 - Debug flag is passed to script but no unit name.
        mocked_args.side_effect = argparse.ArgumentError(argument=None, message="Unit missing")
        with self.assertRaises(argparse.ArgumentError):
            _main()
