#!/usr/bin/python3
# Copyright 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Library for utilizing systemd to observe and emit notices when services change state.

This library provides both the public API for observing systemd services from within
charmed operators, and utilities for running a minimal juju-systemd-notices daemon that watches
observed services running on the machine. The juju-systemd-notices daemon watches observed
services using DBus; it observes messages received on the DBus message bus and evaluates the
contents of the messages to determine if a service state-change event must be emitted.

## How to use within a charmed operator (machine only)

Here is an example of subscribing a charmed operator to observe the state of an internal
systemd service and handle events based on the current emitted state:

```python
from charms.operator_libs_linux.v0.juju_systemd_notices import (
    ServiceStartedEvent,
    ServiceStoppedEvent,
    SystemdNotices,
)


class ApplicationCharm(CharmBase):
    # Application charm that needs to observe the state of an internal service.

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Register services with charm. This adds the events to observe.
        self._systemd_notices = SystemdNotices(self, ["slurmd"])
        event_handler_bindings = {
            self.on.install: self._on_install,
            self.on.stop: self._on_stop,
            self.on.service_slurmd_started: self._on_slurmd_started,
            self.on.service_slurmd_stopped: self._on_slurmd_stopped,
        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, _: InstallEvent) -> None:
        # Subscribe the charmed operator to the services on the machine.
        # .subscribe() configures the notices hooks and starts the juju-systemd-notices daemon.
        # The juju-systemd-notices daemon is per unit. This means that the unit name will be
        # meshed into the service name. E.g. juju-systemd-notices becomes
        # juju-{unit_name}-{unit_number}-systemd-notices.
        self._systemd_notices.subscribe()

    def _on_start(self, _: StartEvent) -> None:
        # This will trigger the juju-systemd-notices daemon to
        # emit a `service-slurmd-started` event.
        systemd.service_start("slurmd")

    def _on_stop(self, _: StopEvent) -> None:
        # To stop the juju-systemd-notices service running in the background.
        # .stop() also disables the juju-systemd-notices so that it does not
        # start back up if the underlying machine is rebooted.
        self._systemd_notices.stop()

    def _on_slurmd_started(self, _: ServiceStartedEvent) -> None:
        self.unit.status = ActiveStatus()
        time.sleep(60)

        # This will trigger the juju-systemd-notices daemon to
        # emit a `service-slurmd-stopped` event.
        systemd.service_stop("slurmd")

    def _on_slurmd_stopped(self, _: ServiceStoppedEvent) -> None:
        self.unit.status = BlockedStatus("slurmd not running")
```
"""

__all__ = ["ServiceStartedEvent", "ServiceStoppedEvent", "SystemdNotices"]

import argparse
import asyncio
import functools
import logging
import re
import signal
import subprocess
import sys
import textwrap
from pathlib import Path
from types import MappingProxyType
from typing import List, Union

from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, MessageType
from dbus_fast.errors import DBusError
from dbus_fast.message import Message
from ops.charm import CharmBase
from ops.framework import EventBase

LIBID = "HPCTEAMUSEONLY"
LIBAPI = 0
LIBPATCH = 1
PYDEPS = ["dbus-fast>=1.90.2"]

_logger = logging.getLogger(__name__)
_juju_unit = None
_service_states = {}
_service_hook_regex_filter = re.compile(r"service-(?P<service>[\w\\:-]*)-(?:started|stopped)")
_DBUS_CHAR_MAPPINGS = MappingProxyType(
    {
        "_5f": "_",
        "_40": "@",
        "_2e": ".",
        "_2d": "-",
        "_5c": "\\",
    }
)


def _systemctl(*args) -> None:
    """Control systemd by via executed `systemctl ...` commands.

    Raises:
        subprocess.CalledProcessError: Raised if systemctl command fails.
    """
    cmd = ["systemctl", *args]
    _logger.debug(f"systemd: Executing command {cmd}")
    try:
        subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        _logger.error(f"systemctl command failed: {e}")
        raise


_daemon_reload = functools.partial(_systemctl, "daemon-reload")
_daemon_reload.__doc__ = "Reload systemd manager configuration."
_start_service = functools.partial(_systemctl, "start")
_start_service.__doc__ = "Start systemd service unit."
_stop_service = functools.partial(_systemctl, "stop")
_stop_service.__doc__ = "Stop systemd service unit."
_enable_service = functools.partial(_systemctl, "enable")
_enable_service.__doc__ = "Enable systemd service."
_disable_service = functools.partial(_systemctl, "disable")
_disable_service.__doc__ = "Disable systemd service."


class ServiceStartedEvent(EventBase):
    """Event emitted when service has started."""


class ServiceStoppedEvent(EventBase):
    """Event emitted when service has stopped."""


class SystemdNotices:
    """Observe systemd services on your machine base."""

    def __init__(self, charm: CharmBase, services: Union[str, List[str]]) -> None:
        """Instantiate systemd notices service."""
        self._charm = charm
        self._services = [services] if isinstance(services, str) else services
        unit_name = self._charm.unit.name.replace("/", "-")
        self._service_file = Path(f"/etc/systemd/system/juju-{unit_name}-systemd-notices.service")

        _logger.debug(f"Attaching systemd notice events to charm {self._charm.__class__.__name__}")
        for service in self._services:
            self._charm.on.define_event(f"service_{service}_started", ServiceStartedEvent)
            self._charm.on.define_event(f"service_{service}_stopped", ServiceStoppedEvent)

    def subscribe(self) -> None:
        """Subscribe charmed operator to observe status of systemd services."""
        _logger.debug(f"Generating systemd notice hooks for {self._services}")
        for service in self._services:
            Path(f"hooks/service-{service}-started").symlink_to(f"{Path.cwd()}/dispatch")
            Path(f"hooks/service-{service}-stopped").symlink_to(f"{Path.cwd()}/dispatch")

        _logger.debug(f"Starting {self._service_file.name} daemon")
        if self._service_file.exists():
            _logger.debug(f"Overwriting existing service file {self._service_file.name}")
        self._service_file.write_text(
            textwrap.dedent(
                f"""
                [Unit]
                Description=Juju systemd notices daemon
                After=multi-user.target

                [Service]
                Type=simple
                Restart=always
                WorkingDirectory={Path.cwd()}
                Environment="PYTHONPATH={Path.cwd() / "venv"}"
                ExecStart=/usr/bin/python3 {__file__} {self._charm.unit.name}

                [Install]
                WantedBy=multi-user.target
                """
            ).strip()
        )
        _logger.debug(f"Service file {self._service_file.name} written. Reloading systemd")
        _daemon_reload()
        # Notices daemon is enabled so that the service will start even after machine reboot.
        # This functionality is needed in the event that a charm is rebooted to apply updates.
        _enable_service(self._service_file.name)
        _start_service(self._service_file.name)
        _logger.debug(f"Started {self._service_file.name} daemon")

    def stop(self) -> None:
        """Stop charmed operator from observing the status of subscribed services."""
        _stop_service(self._service_file.name)
        # Notices daemon is disabled so that the service will not restart after machine reboot.
        _disable_service(self._service_file.name)


def _name_to_dbus_path(name: str) -> str:
    """Convert the specified name into an org.freedesktop.systemd1.Unit path handle.

    Args:
        name: The name of the service.

    Returns:
        String containing the DBus path.
    """
    # DBUS Object names may only contain ASCII chars [A-Z][a-z][0-9]_
    # It's basically urlencoded but instead of a %, it uses a _
    path = name
    for key, value in _DBUS_CHAR_MAPPINGS.items():
        path = path.replace(value, key)

    return f"/org/freedesktop/systemd1/unit/{path}"


def _dbus_path_to_name(path: str) -> str:
    """Convert the specified DBus path handle to a service name.

    Args:
        path: The DBus path to convert to service name.

    Returns:
        String containing the service name.
    """
    # DBUS Object names may only contain ASCII chars [A-Z][a-z][0-9]_
    name = Path(path).name
    for key, value in _DBUS_CHAR_MAPPINGS.items():
        name = name.replace(key, value)

    return name


def _systemd_unit_changed(msg: Message) -> bool:
    """Send Juju notification if systemd unit state changes on the DBus bus.

    Invoked when a PropertiesChanged event occurs on an org.freedesktop.systemd1.Unit
    object across the dbus. These events are sent whenever a unit changes state, including
    starting and stopping.

    Args:
        msg: The message to process in the callback.

    Returns:
        True if the event is processed. False if otherwise.
    """
    _logger.debug(
        f"Received message: path: {msg.path}, interface: {msg.interface}, member: {msg.member}"
    )
    service = _dbus_path_to_name(msg.path)
    properties = msg.body[1]
    if "ActiveState" not in properties:
        return False

    global _service_states
    if service not in _service_states:
        _logger.debug(f"Dropping event for unwatched service: {service}")
        return False

    curr_state = properties["ActiveState"].value
    prev_state = _service_states[service]
    # Drop transitioning and duplicate events
    if curr_state.endswith("ing") or curr_state == prev_state:
        _logger.debug(f"Dropping event - service: {service}, state: {curr_state}")
        return False

    _service_states[service] = curr_state
    _logger.debug(f"Service {service} changed state to {curr_state}")
    # Run the hook in a separate thread so the dbus notifications aren't
    # blocked from being received.
    asyncio.create_task(_send_juju_notification(service, curr_state))
    return True


async def _send_juju_notification(service: str, state: str) -> None:
    """Invoke a Juju hook to notify an operator that a service state has changed.

    Args:
        service: The name of the service which has changed state.
        state: The state of the service.
    """
    if service.endswith(".service"):
        service = service[0 : -len(".service")]
    if state == "active":
        event_name = "started"
    else:
        event_name = "stopped"
    hook = f"service-{service}-{event_name}"
    cmd = ["/usr/bin/juju-exec", _juju_unit, f"hooks/{hook}"]

    _logger.debug(f"Invoking hook {hook} with command: {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
    )
    await process.wait()
    if process.returncode:
        _logger.error(
            f"Hook command '{' '.join(cmd)}' failed with returncode {process.returncode}"
        )
    else:
        _logger.info(f"Hook command '{' '.join(cmd)}' succeeded.")


async def _get_state(bus: MessageBus, service: str) -> str:
    """Report the current state of a service.

    Args:
        bus: The message bus to query on.
        service: The systemd service to query the state of.

    Returns:
        The state of the service. "active" or "inactive"
    """
    obj_path = _name_to_dbus_path(service)
    try:
        _logger.debug(f"Retrieving state for service {service} at object path: {obj_path}")
        introspection = await bus.introspect("org.freedesktop.systemd1", obj_path)
        proxy = bus.get_proxy_object("org.freedesktop.systemd1", obj_path, introspection)
        properties = proxy.get_interface("org.freedesktop.DBus.Properties")
        state = await properties.call_get("org.freedesktop.systemd1.Unit", "ActiveState")  # noqa
        return state.value
    except DBusError:
        # This will be thrown if the unit specified does not currently exist,
        # which happens if the application needs to install the service, etc.
        return "unknown"


async def _async_load_services() -> None:
    """Load names of services to observe from legacy Juju hooks.

    Parses the hook names found in the charm hooks directory and determines
    if this is one of the services that the charm is interested in observing.
    The hooks will match one of the following names:

      - service-{service_name}-started
      - service-{service_name}-stopped

    Any other hooks are ignored and not loaded into the set of services
    that should be watched. Upon finding a service hook it's current ActiveState
    will be queried from systemd to determine it's initial state.
    """
    global _juju_unit
    hooks_dir = Path.cwd() / "hooks"
    _logger.info(f"Loading services from hooks in {hooks_dir}")

    if not hooks_dir.exists():
        _logger.warning(f"Hooks dir {hooks_dir} does not exist.")
        return

    watched_services = []
    # Get service-{service}-(started|stopped) hooks defined by the charm.
    for hook in filter(lambda p: _service_hook_regex_filter.match(p.name), hooks_dir.iterdir()):
        match = _service_hook_regex_filter.match(hook.name)
        watched_services.append(match.group("service"))

    _logger.info(f"Services from hooks are {watched_services}")
    if not watched_services:
        return

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # Loop through all the services and be sure that a new watcher is
    # started for new ones.
    for service in watched_services:
        # The .service suffix is necessary and will cause lookup failures of the
        # service unit when readying the watcher if absent from the service name.
        service = f"{service}.service"
        if service not in _service_states:
            state = await _get_state(bus, service)
            _logger.debug(f"Adding service '{service}' with initial state: {state}")
            _service_states[service] = state


def _load_services(loop: asyncio.AbstractEventLoop) -> None:  # pragma: no cover
    """Load services synchronously using _async_load_services.

    This is a synchronous form of the _load_services method. This is called from a
    signal handler which cannot take coroutines, thus this method will schedule a
    task to run in the current running loop.

    Args:
        loop: Asynchronous event loop from main thread.
    """
    loop.call_soon(_async_load_services)


async def _juju_systemd_notices_daemon() -> None:
    """Start Juju systemd notices daemon.

    This start call will set up the notices service to listen for events.
    It connects to the system message bus and registers for signals/events on the
    org.freedesktop.systemd1.Unit object looking for any PropertyChanged events.
    This method additionally sets up signal handlers for various signals to either
    terminate the process or reload the configuration from the hooks directory.
    """
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    # The event loop must be early bound to the lambda, otherwise the event loop
    # will not exist within the lambda when the SIGHUP signal is received
    # by the running notices daemon.
    loop.add_signal_handler(  # pragma: no branch
        signal.SIGHUP, lambda loop=loop: _load_services(loop)
    )

    sysbus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    await _async_load_services()

    reply = await sysbus.call(
        Message(
            destination="org.freedesktop.DBus",
            path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus",
            member="AddMatch",
            signature="s",
            body=[
                "path_namespace='/org/freedesktop/systemd1/unit',type='signal',"
                "interface='org.freedesktop.DBus.Properties'"
            ],
            serial=sysbus.next_serial(),
        )
    )
    assert reply.message_type == MessageType.METHOD_RETURN
    sysbus.add_message_handler(_systemd_unit_changed)
    await stop_event.wait()


def _main():
    """Invoke the Juju systemd notices daemon.

    Note:
        This method is used to start the Juju systemd notices daemon when
        juju_systemd_notices.py is executed as a script, not imported as a module.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("unit", type=str)
    args = parser.parse_args()

    console_handler = logging.StreamHandler()
    if args.debug:
        _logger.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)
    else:
        _logger.setLevel(logging.INFO)
        console_handler.setLevel(logging.DEBUG)
    _logger.addHandler(console_handler)

    # Intentionally set as global.
    global _juju_unit
    _juju_unit = args.unit
    if not _juju_unit:
        parser.print_usage()
        sys.exit(2)

    _logger.info("Starting juju systemd notices service")
    asyncio.run(_juju_systemd_notices_daemon())


if __name__ == "__main__":  # pragma: nocover
    _main()
