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

"""Representations of the system's Snaps, and abstractions around managing them.

    In the `snap` module, :class:`SnapCache` creates a dict-like mapping of
    :class:`Snap` objects at instantiation. Installed snaps are fully populated,
    and available snaps are lazily-loaded upon request. This module relies on an
    installed and running `snapd` daemon to perform operations over the `snapd`
    HTTP API.

    Typical usage:
      cache = snap.SnapCache()
      juju = cache["juju"]
      juju.ensure(snap.SnapState.Latest, classic=True, channel="stable")
"""

import http.client
import json
import os
import logging
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from collections.abc import Mapping
from enum import IntEnum
from itertools import chain
from subprocess import CalledProcessError
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


class SnapAPIError(Error):
    """Raised when an HTTP API error occurs talking to the Snapd server."""

    def __init__(self, body: Dict, code: int, status: str, message: str):
        """This shouldn't be instantiated directly."""
        super().__init__(message)  # Makes str(e) return message
        self.body = body
        self.code = code
        self.status = status
        self._message = message

    def __repr__(self):
        return "APIError({!r}, {!r}, {!r}, {!r})".format(
            self.body, self.code, self.status, self._message
        )


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
    """Represents a snap package and its properties.

    :class:`Snap` exposes the following properties about a snap:
      - name: the name of the snap
      - state: a :class:`SnapState` representation of its install status
      - channel: "stable", "candidate", "beta", and "edge" are common
      - revision: a string representing the snap's revision
      - confinement: "classic" or "strict"
    """

    def __init__(
        self, name, state: SnapState, channel: str, revision: str, confinement: str
    ) -> None:
        self._name = name
        self._state = state
        self._channel = channel
        self._revision = revision
        self._confinement = confinement

    def __eq__(self, other) -> bool:
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
        """Perform a snap operation.

        Args:
          command: the snap command to execute
          optargs: an (optional) list of additional arguments to pass,
            commonly confinement or channel

        Raises:
          SnapError if there is a problem encountered
        """
        optargs = optargs if optargs is not None else []
        _cmd = ["snap", command, self._name, *optargs]
        try:
            subprocess.check_call(_cmd)
        except CalledProcessError as e:
            raise SnapError("Could not %s snap [%s]: %s", _cmd, self._name, e.output)

    def _install(self, channel: Optional[str] = "") -> None:
        """Add a snap to the system.

        Args:
          channel: the channel to install from
        """
        confinement = "--classic" if self._confinement == "classic" else ""
        channel = f'--channel="{channel}"' if channel else ""
        self._snap("install", [confinement, channel])

    def _refresh(self, channel: Optional[str] = "") -> None:
        """Refresh a snap.

        Args:
          channel: the channel to install from
        """
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
        """Ensures that a snap is in a given state.

        Args:
          state: a :class:`SnapState` to reconcile to.
          classic: an (Optional) boolean indicating whether classic confinement should be used
          channel: the channel to install from

        Raises:
          SnapError if an error is encountered
        """
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
        """Sets the snap state to a given value.

        Args:
          state: a :class:`SnapState` to reconcile the snap to.

        Raises:
          SnapError if an error is encountered
        """
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


class _UnixSocketConnection(http.client.HTTPConnection):
    """Implementation of HTTPConnection that connects to a named Unix socket."""

    def __init__(self, host, timeout=None, socket_path=None):
        if timeout is None:
            super().__init__(host)
        else:
            super().__init__(host, timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        """Override connect to use Unix socket (instead of TCP socket)."""
        if not hasattr(socket, "AF_UNIX"):
            raise NotImplementedError(
                "Unix sockets not supported on {}".format(sys.platform)
            )
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)
        if self.timeout is not None:
            self.sock.settimeout(self.timeout)


class _UnixSocketHandler(urllib.request.AbstractHTTPHandler):
    """Implementation of HTTPHandler that uses a named Unix socket."""

    def __init__(self, socket_path: str):
        super().__init__()
        self.socket_path = socket_path

    def http_open(self, req) -> http.client.HTTPResponse:
        """Override http_open to use a Unix socket connection (instead of TCP)."""
        return self.do_open(_UnixSocketConnection, req, socket_path=self.socket_path)


class SnapClient:
    """Snapd API client to talk to HTTP over UNIX sockets.

    In order to avoid shelling out and/or involving sudo in calling the snapd API,
    use a wrapper based on the Pebble Client, trimmed down to only the utility methods
    needed for talking to snapd.
    """

    def __init__(
        self,
        socket_path: str = "/run/snapd.socket",
        opener: Optional[urllib.request.OpenerDirector] = None,
        base_url: str = "http://localhost/v2/",
        timeout: float = 5.0,
    ):
        """Initialize a client instance.

        Args:
            socket_path: a path to the socket on the filesystem
            opener:
        Defaults to using a Unix socket at socket_path (which must be specified
        unless a custom opener is provided).
        """
        if opener is None:
            opener = self._get_default_opener(socket_path)
        self.opener = opener
        self.base_url = base_url
        self.timeout = timeout

    @classmethod
    def _get_default_opener(cls, socket_path):
        """Build the default opener to use for requests (HTTP over Unix socket)."""
        opener = urllib.request.OpenerDirector()
        opener.add_handler(_UnixSocketHandler(socket_path))
        opener.add_handler(urllib.request.HTTPDefaultErrorHandler())
        opener.add_handler(urllib.request.HTTPRedirectHandler())
        opener.add_handler(urllib.request.HTTPErrorProcessor())
        return opener

    def _request(
        self,
        method: str,
        path: str,
        query: Dict = None,
        body: Dict = None,
    ) -> Dict:
        """Make a JSON request to the Snapd server with the given HTTP method and path.
        If query dict is provided, it is encoded and appended as a query string
        to the URL. If body dict is provided, it is serialied as JSON and used
        as the HTTP body (with Content-Type: "application/json"). The resulting
        body is decoded from JSON.
        """
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        response = self._request_raw(method, path, query, headers, data)
        return json.loads(response.read().decode())["result"]

    def _request_raw(
        self,
        method: str,
        path: str,
        query: Dict = None,
        headers: Dict = None,
        data: bytes = None,
    ) -> http.client.HTTPResponse:
        """Make a request to the Snapd server; return the raw HTTPResponse object."""
        url = self.base_url + path
        if query:
            url = url + "?" + urllib.parse.urlencode(query)

        if headers is None:
            headers = {}
        request = urllib.request.Request(url, method=method, data=data, headers=headers)

        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            code = e.code
            status = e.reason
            message = ""
            try:
                body = json.loads(e.read().decode())["result"]
            except (IOError, ValueError, KeyError) as e2:
                # Will only happen on read error or if Pebble sends invalid JSON.
                body = {}
                message = "{} - {}".format(type(e2).__name__, e2)
            raise SnapAPIError(body, code, status, message)
        except urllib.error.URLError as e:
            raise SnapAPIError("500", "Not found", "Not found", e.reason)
        return response

    def get_installed_snaps(self) -> Dict:
        """Get information about currently installed snaps."""

        return self._request("GET", "snaps")

    def get_snap_information(self, name: str) -> Dict:
        """Query the snap server for information about single snap."""

        return self._request("GET", "find", {"name": name})[0]


class SnapCache(Mapping):
    """An abstraction to represent installed/available packages.

    When instantiated, :class:`SnapCache` iterates through the list of installed
    snaps using the `snapd` HTTP API, and a list of available snaps by reading
    the filesystem to populate the cache. Information about available snaps is lazily-loaded
    from the `snapd` API when requested.
    """

    def __init__(self):
        self._snap_client = SnapClient()
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
        installed = self._snap_client.get_installed_snaps()

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
        """Load info for snaps which are not installed if requested.

        Args:
          name: a string representing the name of the snap
        """
        info = self._snap_client.get_snap_information(name)

        return Snap(
            info["name"],
            SnapState.Available,
            info["channel"],
            info["revision"],
            info["confinement"],
        )
