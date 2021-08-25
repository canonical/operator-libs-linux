# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Representations of the system's Snaps."""

import json
import os
import logging
import subprocess

from collections.abc import Mapping
from enum import IntEnum
from itertools import chain
from subprocess import check_output, CalledProcessError
from typing import Dict, Iterable, List, Optional


logger = logging.getLogger(__name__)


class Error(Exception):
    """Base class of most errors raised by this library."""

    def __repr__(self):
        return "<{}.{} {}>".format(
            type(self).__module__, type(self).__name__, self.args
        )

    @property
    def name(self):
        """Return a string representation of the model plus class."""
        return "<{}.{}>".format(type(self).__module__, type(self).__name__)

    @property
    def message(self):
        """Return the message passed as an argument."""
        return self.args[0]


class StateBase(IntEnum):
    Present = 1
    Absent = 2


class SnapError(Error):
    """Raised when there's an error installing or removing a snap"""


class SnapStateBase(IntEnum):
    """A parent class to combine IntEnums, since Python does not otherwise allow this."""

    Latest = 3
    Available = 4


SnapState = IntEnum(
    "SnapState", [(i.name, i.value) for i in chain(StateBase, SnapStateBase)]
)


class Snap(object):
    """Represents a snap package."""

    def __init__(
        self, name, state: SnapState, channel: str, revision: str, confinement: str
    ) -> None:
        self._name = name
        self._state = state
        self._channel = channel
        self._revision = revision
        self._confinement = confinement

    def __eq__(self, other):
        """Equality for comparison."""
        return (
            isinstance(other, self.__class__)
            and (
                self._name,
                self._revision,
            )
            == (other._name, other._revision)
        )

    def __hash__(self):
        """A basic hash so this class can be used in Mappings and dicts."""
        return hash((self._name, self._revision))

    def __repr__(self):
        """A representation of the snap."""
        return "<{}.{}: {}>".format(
            self.__module__, self.__class__.__name__, self.__dict__
        )

    def __str__(self):
        """A human-readable representation of the snap"""
        return "<{}: {}-{}.{} -- {}>".format(
            self.__class__.__name__,
            self._name,
            self._revision,
            self._channel,
            str(self._state),
        )

    def _snap(self, command: str, optargs: Optional[List[str]] = None) -> None:
        optargs = optargs if optargs is not None else []
        """Wrap snap management commands"""
        _cmd = ["snap", command, self._name, *optargs]
        try:
            subprocess.check_call(_cmd)
        except CalledProcessError as e:
            raise SnapError("Could not %s snap [%s]: %s", _cmd, self._name, e.output)

    def _install(self, channel: Optional[str] = "") -> None:
        """Add a snap to the system"""
        confinement = "--classic" if self._confinement == "classic" else ""
        channel = f'--channel="{channel}"' if channel else ""
        self._snap("install", [confinement, channel])

    def _refresh(self, channel: Optional[str] = "") -> None:
        """Refresh a snap"""
        channel = f"--{channel}" if channel else self._channel
        self._snap("refresh", [channel])

    def _remove(self) -> None:
        """Removes a snap from the system."""
        return self._snap("remove")

    @property
    def name(self) -> str:
        """Returns the name of the snap"""
        return self._name

    def ensure(
        self,
        state: SnapState,
        classic: Optional[bool] = False,
        channel: Optional[str] = "",
    ):
        """Ensures that a snap is in a given state."""
        self._confinement = (
            "classic" if classic or self._confinement == "classic" else ""
        )
        if self._state is not state:
            if state not in (SnapState.Present, SnapState.Latest):
                self._remove()
            else:
                self._install(channel)
            self._state = state

    @property
    def present(self) -> bool:
        """Returns whether or not a snap is present."""
        return self._state is SnapState.Present

    @property
    def latest(self) -> bool:
        """Returns whether the snap is the most recent version."""
        return self._state is SnapState.Latest

    @property
    def state(self) -> SnapState:
        """Returns the current snap state."""
        return self._state

    @state.setter
    def state(self, state: SnapState) -> None:
        """Sets the snap state to a given value."""
        if self._state is not state:
            self.ensure(state)
        self._state = state

    @property
    def revision(self) -> str:
        """Returns the revision for a snap."""
        return self._revision

    @property
    def channel(self) -> str:
        """Returns the channel for a snap."""
        return self._channel

    @property
    def confinement(self) -> str:
        """Returns the confinement for a snap."""
        return self._confinement


class SnapCache(Mapping):
    """An abstraction to represent installed/available packages."""

    def __init__(self):
        self._snap_map = {}
        self._load_available_snaps()
        self._load_installed_snaps()

    def __contains__(self, key: str) -> bool:
        return key in self._snap_map

    def __len__(self) -> int:
        return len(self._snap_map)

    def __iter__(self) -> Iterable["Snap"]:
        return iter(self._snap_map.values())

    def __getitem__(self, snap_name: str) -> Snap:
        """Return either the installed version or latest version for a given snap."""
        snap = self._snap_map[snap_name]

        if snap is None:
            self._snap_map[snap_name] = self._load_info(snap_name)
            return self._snap_map[snap_name]

        return self._snap_map[snap_name]

    @staticmethod
    def _curl_cmd(endpoint: str) -> Dict:
        """A wrapper to talk to the snap daemon. To avoid additional imports which can
        speak HTTP over UNIX sockets, shell out to `curl` instead."""

        if not os.path.isfile("/run/snapd.socket"):
            raise SnapError("snapd is not running. /run/snapd.socket cannot be found!")

        cmd = [
            "sudo",
            "curl",
            "-sS",
            "--unix-socket",
            "/run/snapd.socket",
            f"http://localhost/v2/{endpoint}",
        ]
        output = json.loads(check_output(cmd, universal_newlines=True))["result"]

        return output

    def _load_available_snaps(self) -> None:
        """Load the list of available snaps from disk. Leave them empty and lazily load later if asked for."""
        if not os.path.isfile("/var/cache/snapd/names"):
            logger.warning(
                "The snap cache has not been populated or is not in the default location"
            )
            return

        with open("/var/cache/snapd/names", "r") as f:
            for line in f:
                if line.strip():
                    self._snap_map[line.strip()] = None

    def _load_installed_snaps(self) -> None:
        """Load the installed snaps into the dict."""
        installed = self._curl_cmd("snaps")

        for i in installed:
            snap = Snap(
                i["name"],
                SnapState.Latest,
                i["channel"],
                i["revision"],
                i["confinement"],
            )
            self._snap_map[snap.name] = snap

    def _load_info(self, name) -> Snap:
        """Load info for snaps which are not installed if requested."""
        info = self._curl_cmd(f"find?name={name}")[0]

        return Snap(
            info["name"],
            SnapState.Available,
            info["channel"],
            info["revision"],
            info["confinement"],
        )
