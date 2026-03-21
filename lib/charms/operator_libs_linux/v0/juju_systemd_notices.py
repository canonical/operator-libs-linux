#!/usr/bin/python3
# Copyright 2023-2024 Canonical Ltd.
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
    Service,
    ServiceStartedEvent,
    ServiceStoppedEvent,
    SystemdNotices,
)


class ApplicationCharm(CharmBase):
    # Application charm that needs to observe the state of an internal service.

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Register services with charm. This adds the events to observe.
        self._systemd_notices = SystemdNotices(self, [Service("snap.slurm.slurmd", alias="slurmd")])
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.service_slurmd_started, self._on_slurmd_started)
        self.framework.observe(self.on.service_slurmd_stopped, self._on_slurmd_stopped)

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
        snap.slurmd.enable()

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
        snap.slurmd.stop()

    def _on_slurmd_stopped(self, _: ServiceStoppedEvent) -> None:
        self.unit.status = BlockedStatus("slurmd not running")
```
"""

__all__ = ["Service", "ServiceStartedEvent", "ServiceStoppedEvent", "SystemdNotices"]

import argparse
import asyncio
import functools
import logging
import signal
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, MessageType
from dbus_fast.errors import DBusError
from dbus_fast.message import Message
from ops.charm import CharmBase
from ops.framework import EventBase

# The unique Charmhub library identifier, never change it.
LIBID = "2bb6ecd037e64c899033113abab02e01"

# Increment this major API version when introducing breaking changes.
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version.
LIBPATCH = 2

# juju-systemd-notices charm library dependencies.
# Charm library dependencies are installed when the consuming charm is packed.
PYDEPS = ["dbus-fast>=1.90.2"]

_logger = logging.getLogger(__name__)
_juju_unit = None
_observed_services = {}
_service_states = {}
_DBUS_CHAR_MAPPINGS = {
    "_5f": "_",  # _ must be first since char mappings contain _.
    "_40": "@",
    "_2e": ".",
    "_2d": "-",
    "_5c": "\\",
}


def _systemctl(*args) -> None:
    """Control systemd by via executed `systemctl ...` commands.

    Raises:
        subprocess.CalledProcessError: Raised if systemctl command fails.
    """
    cmd = ["systemctl", *args]
    _logger.debug("systemd: Executing command %s", cmd)
    try:
        subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        _logger.error("systemctl command failed: %s", e)
        raise


_daemon_reload = functools.partial(_systemctl, "daemon-reload")
_start_service = functools.partial(_systemctl, "start")
_stop_service = functools.partial(_systemctl, "stop")
_enable_service = functools.partial(_systemctl, "enable")
_disable_service = functools.partial(_systemctl, "disable")


@dataclass
class Service:
    """Systemd service to observe.

    Args:
        name: Name of systemd service to observe on dbus.
        alias: Event name alias for service.
    """

    name: str
    alias: Optional[str] = None


class ServiceStartedEvent(EventBase):
    """Event emitted when service has started."""


class ServiceStoppedEvent(EventBase):
    """Event emitted when service has stopped."""


class SystemdNotices:
    """Observe systemd services on your machine base."""

    def __init__(self, charm: CharmBase, services: List[Union[str, Service]]) -> None:
        """Instantiate systemd notices service."""
        self._charm = charm
        self._services = [Service(s) if isinstance(s, str) else s for s in services]
        unit_name = self._charm.unit.name.replace("/", "-")
        self._service_file = Path(f"/etc/systemd/system/juju-{unit_name}-systemd-notices.service")

        _logger.debug(
            "Attaching systemd notice events to charm %s", self._charm.__class__.__name__
        )
        for s in self._services:
            event = s.alias or s.name
            self._charm.on.define_event(f"service_{event}_started", ServiceStartedEvent)
            self._charm.on.define_event(f"service_{event}_stopped", ServiceStoppedEvent)

    def subscribe(self) -> None:
        """Subscribe charmed operator to observe status of systemd services."""
        self._generate_hooks()
        self._generate_service()
        self._start()

    def stop(self) -> None:
        """Stop charmed operator from observing the status of subscribed services."""
        _stop_service(self._service_file.name)
        # Notices daemon is disabled so that the service will not restart after machine reboot.
        _disable_service(self._service_file.name)

    def _generate_hooks(self) -> None:
        """Generate legacy event hooks for observed systemd services."""
        _logger.debug("Generating systemd notice hooks for %s", self._services)
        events = [s.alias or s.name for s in self._services]
        start_hooks = [Path(f"hooks/service-{e}-started") for e in events]
        stop_hooks = [Path(f"hooks/service-{e}-stopped") for e in events]
        for hook in start_hooks + stop_hooks:
            if hook.exists():
                _logger.debug("Hook %s already exists. Skipping...", hook.name)
            else:
                hook.symlink_to(self._charm.framework.charm_dir / "dispatch")

    def _generate_service(self) -> None:
        """Generate systemd service file for notices daemon."""
        _logger.debug("Generating service file %s", self._service_file.name)
        if self._service_file.exists():
            _logger.debug("Overwriting existing service file %s", self._service_file.name)

        services = [f"{s.name}={s.alias or s.name}" for s in self._services]
        self._service_file.write_text(
            textwrap.dedent(
                f"""
                [Unit]
                Description=Juju systemd notices daemon
                After=multi-user.target

                [Service]
                Type=simple
                Restart=always
                WorkingDirectory={self._charm.framework.charm_dir}
                Environment="PYTHONPATH={self._charm.framework.charm_dir / "venv"}"
                ExecStart=/usr/bin/python3 {__file__} --unit {self._charm.unit.name} {' '.join(services)}

                [Install]
                WantedBy=multi-user.target
                """
            ).strip()
        )

        _logger.debug(
            "Service file %s written. Reloading systemd manager configuration",
            self._service_file.name,
        )

    def _start(self) -> None:
        """Start systemd notices daemon to observe subscribed services."""
        _logger.debug("Starting %s daemon", self._service_file.name)

        # Reload systemd manager configuration so that it will pick up notices daemon.
        _daemon_reload()

        # Enable notices daemon to start after machine reboots.
        _enable_service(self._service_file.name)
        _start_service(self._service_file.name)
        _logger.debug("Started %s daemon", self._service_file.name)


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
        "Received message: path: %s, interface: %s, member: %s",
        msg.path,
        msg.interface,
        msg.member,
    )
    service = _dbus_path_to_name(msg.path)
    properties = msg.body[1]
    if "ActiveState" not in properties:
        return False

    if service not in _service_states:
        _logger.debug("Dropping event for unwatched service: %s", service)
        return False

    curr_state = properties["ActiveState"].value
    prev_state = _service_states[service]
    # Drop transitioning and duplicate events
    if curr_state.endswith("ing") or curr_state == prev_state:
        _logger.debug("Dropping event - service: %s, state: %s", service, curr_state)
        return False

    _service_states[service] = curr_state
    _logger.debug("Service %s changed state to %s", service, curr_state)
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
        service = service[0:-len(".service")]  # fmt: skip

    alias = _observed_services[service]
    event_name = "started" if state == "active" else "stopped"
    hook = f"service-{alias}-{event_name}"
    cmd = ["/usr/bin/juju-exec", _juju_unit, f"hooks/{hook}"]

    _logger.debug("Invoking hook %s with command: %s", hook, " ".join(cmd))
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    if process.returncode:
        _logger.error(
            "Hook command '%s' failed with returncode %s", " ".join(cmd), process.returncode
        )
    else:
        _logger.info("Hook command '%s' succeeded.", " ".join(cmd))


async def _get_service_state(bus: MessageBus, service: str) -> str:
    """Report the current state of a service.

    Args:
        bus: The message bus to query on.
        service: The systemd service to query the state of.

    Returns:
        The state of the service. "active" or "inactive"
    """
    obj_path = _name_to_dbus_path(service)
    try:
        _logger.debug("Retrieving state for service %s at object path: %s", service, obj_path)
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
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # Loop through all the services and be sure that a new watcher is
    # started for new ones.
    _logger.info("Services to observe are %s", _observed_services)
    for service in _observed_services:
        # The .service suffix is necessary and will cause lookup failures of the
        # service unit when readying the watcher if absent from the service name.
        service = f"{service}.service"
        if service not in _service_states:
            state = await _get_service_state(bus, service)
            _logger.debug("Adding service '%s' with initial state: %s", service, state)
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

    This method is used to start the Juju systemd notices daemon when
    juju_systemd_notices.py is executed as a script, not imported as a module.

    Raises:
        argparse.ArgumentError: Raised if unit argument is absent.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("--unit", type=str)
    parser.add_argument("services", nargs="*")
    args = parser.parse_args()

    # Intentionally set as global.
    global _juju_unit
    _juju_unit = args.unit

    for s in args.services:
        service, alias = s.split("=")
        _observed_services[service] = alias

    console_handler = logging.StreamHandler()
    if args.debug:
        _logger.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)
    else:
        _logger.setLevel(logging.INFO)
        console_handler.setLevel(logging.DEBUG)

    _logger.addHandler(console_handler)
    _logger.info("Starting juju systemd notices service")
    asyncio.run(_juju_systemd_notices_daemon())


if __name__ == "__main__":  # pragma: nocover
    _main()
