#!/usr/bin/env python3
# Copyright 2023-2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Minimal charm for testing the juju_systemd_notices charm library.

FOR TESTING PURPOSES ONLY!
"""

import logging

import charms.operator_libs_linux.v1.systemd as systemd
import daemon
from charms.operator_libs_linux.v0.juju_systemd_notices import (
    ServiceStartedEvent,
    ServiceStoppedEvent,
    SystemdNotices,
)
from ops.charm import CharmBase, InstallEvent, StartEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus

logger = logging.getLogger(__name__)


class NoticesCharm(CharmBase):
    """Minimal charm for testing the juju."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._systemd_notices = SystemdNotices(self, ["test"])
        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.start: self._on_start,
            self.on.service_test_started: self._on_test_started,
            self.on.service_test_stopped: self._on_test_stopped,
            self.on.stop_service_action: self._on_stop_service_action,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, _: InstallEvent) -> None:
        """Handle install event."""
        daemon.create()
        systemd.daemon_reload()
        self._systemd_notices.subscribe()

    def _on_start(self, _: StartEvent) -> None:
        """Handle start event."""
        systemd.service_start("test")

    def _on_test_started(self, _: ServiceStartedEvent) -> None:
        """Handle service started event."""
        self.unit.status = ActiveStatus("test service running :)")

    def _on_test_stopped(self, _: ServiceStoppedEvent) -> None:
        """Handle service stopped event."""
        self.unit.status = BlockedStatus("test service not running :(")

    def _on_stop_service_action(self, _) -> None:
        """Handle stop-service action."""
        systemd.service_stop("test")


if __name__ == "__main__":  # pragma: nocover
    main(NoticesCharm)
