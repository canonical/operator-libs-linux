# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

# pyright: reportPrivateUsage=false

import datetime
import io
import json
import time
import typing
import unittest
from subprocess import CalledProcessError
from typing import Any, Dict, Iterable, Optional
from unittest.mock import MagicMock, mock_open, patch

import fake_snapd as fake_snapd
from charms.operator_libs_linux.v2 import snap

patch("charms.operator_libs_linux.v2.snap._cache_init", lambda x: x).start()

lazy_load_result = r"""
{
  "type": "sync",
  "status-code": 200,
  "status": "OK",
  "result": [
    {
      "id": "jFJhGxzO7zh4xPun3oLzsYPesPvyGblh",
      "title": "curl",
      "summary": "CLI tool for transferring data with URL syntax (HTTP, HTTPS, etc)",
      "description": "A command line tool and library for transferring data with URL syntax, \nsupporting HTTP, HTTPS, FTP, FTPS, GOPHER, TFTP, SCP, SFTP, SMB, TELNET, \nDICT, LDAP, LDAPS, FILE, IMAP, SMTP, POP3, RTSP and RTMP. \ncurl offers a myriad of powerful features",
      "download-size": 6524928,
      "name": "curl",
      "publisher": {
        "id": "trElzADL6BSHUJX2R38cUoXIElh2BYRZ",
        "username": "woutervb",
        "display-name": "Wouter van Bommel",
        "validation": "unproven"
      },
      "store-url": "https://snapcraft.io/curl",
      "developer": "woutervb",
      "status": "available",
      "type": "app",
      "base": "core20",
      "version": "7.78.0",
      "channel": "stable",
      "ignore-validation": false,
      "revision": "233",
      "confinement": "strict",
      "private": false,
      "devmode": false,
      "jailmode": false,
      "contact": "https://github.com/woutervb/snap-curl",
      "license": "curl",
      "website": "https://github.com/woutervb/snap-curl",
      "channels": {
        "latest/edge": {
          "revision": "275",
          "confinement": "strict",
          "version": "7.78.0",
          "channel": "latest/edge",
          "epoch": {
            "read": [
              0
            ],
            "write": [
              0
            ]
          },
          "size": 6524928,
          "released-at": "2021-08-19T06:15:44.601272Z"
        },
        "latest/stable": {
          "revision": "233",
          "confinement": "strict",
          "version": "7.78.0",
          "channel": "latest/stable",
          "epoch": {
            "read": [
              0
            ],
            "write": [
              0
            ]
          },
          "size": 6524928,
          "released-at": "2021-07-29T23:20:37.945102Z"
        }
      },
      "tracks": [
        "latest"
      ]
    }
  ],
  "sources": [
    "store"
  ],
  "suggested-currency": "USD"
}
"""

installed_result = r"""
{
  "type": "sync",
  "status-code": 200,
  "status": "OK",
  "result": [
    {
      "id": "gcqfpVCOUvmDuYT0Dh5PjdeGypSEzNdV",
      "title": "charmcraft",
      "summary": "The charming tool",
      "description": "Charmcraft enables charm creators to build, publish, and manage charmed operators for Kubernetes, metal and virtual machines.",
      "icon": "https://dashboard.snapcraft.io/site_media/appmedia/2021/06/image-juju-256.svg.png",
      "installed-size": 55361536,
      "name": "charmcraft",
      "publisher": {
        "id": "canonical",
        "username": "canonical",
        "display-name": "Canonical",
        "validation": "verified"
      },
      "developer": "canonical",
      "status": "active",
      "type": "app",
      "base": "core20",
      "version": "1.2.1",
      "channel": "latest/stable",
      "tracking-channel": "latest/stable",
      "ignore-validation": false,
      "revision": "603",
      "confinement": "classic",
      "private": false,
      "devmode": false,
      "jailmode": false,
      "apps": [
        {
          "snap": "charmcraft",
          "name": "charmcraft"
        },
        {
          "snap": "charmcraft",
          "name": "foo_service",
          "daemon": "simple",
          "enabled": true
        }
      ],
      "contact": "",
      "license": "Apache-2.0",
      "mounted-from": "/var/lib/snapd/snaps/charmcraft_603.snap",
      "website": "https://github.com/canonical/charmcraft/",
      "media": [
        {
          "type": "icon",
          "url": "https://dashboard.snapcraft.io/site_media/appmedia/2021/06/image-juju-256.svg.png",
          "width": 256,
          "height": 256
        }
      ],
      "install-date": "2021-08-20T00:10:20.074917847Z"
    },
    {
      "id": "99T7MUlRhtI3U0QFgl5mXXESAiSwt776",
      "title": "core",
      "summary": "snapd runtime environment",
      "description": "The core runtime environment for snapd",
      "installed-size": 104210432,
      "name": "core",
      "publisher": {
        "id": "canonical",
        "username": "canonical",
        "display-name": "Canonical",
        "validation": "verified"
      },
      "developer": "canonical",
      "status": "active",
      "type": "os",
      "version": "16-2.51.3",
      "channel": "latest/stable",
      "tracking-channel": "latest/stable",
      "ignore-validation": false,
      "revision": "11420",
      "confinement": "strict",
      "private": false,
      "devmode": false,
      "jailmode": false,
      "contact": "mailto:snaps@canonical.com",
      "mounted-from": "/var/lib/snapd/snaps/core_11420.snap",
      "install-date": "2021-07-27T13:24:00.522211469Z"
    }
  ]
}
"""


class SnapCacheTester(snap.SnapCache):
    def __init__(self):
        # Fake out __init__ so we can test methods individually
        self._snap_map = {}
        self._snap_client = MagicMock()


class TestSnapCache(unittest.TestCase):
    @patch.object(snap.SnapCache, "snapd_installed", new=False)
    def test_error_on_not_snapd_installed(self):
        with self.assertRaises(snap.SnapError):
            snap.SnapCache()

    @patch(
        "charms.operator_libs_linux.v2.snap.subprocess.check_output",
        return_value=0,
    )
    @patch.object(snap, "SnapCache", new=SnapCacheTester)
    def test_new_snap_cache_on_first_decorated(self, _mock_check_output: MagicMock):
        """Test that the snap cache is created when a decorated function is called.

        add, remove and ensure are decorated with cache_init, which initialises a new cache
        when these functions are called if there isn't one yet
        """

        class CachePlaceholder:
            cache = None

            def __getitem__(self, name: str) -> snap.Snap:
                return self.cache[name]  # pyright: ignore

        with patch.object(snap, "_Cache", new=CachePlaceholder()):
            self.assertIsNone(snap._Cache.cache)
            snap.add(snap_names="curl")
            self.assertIsInstance(snap._Cache.cache, snap.SnapCache)

        with patch.object(snap, "_Cache", new=CachePlaceholder()):
            self.assertIsNone(snap._Cache.cache)
            snap.remove(snap_names="curl")
            self.assertIsInstance(snap._Cache.cache, snap.SnapCache)

        with patch.object(snap, "_Cache", new=CachePlaceholder()):
            self.assertIsNone(snap._Cache.cache)
            snap.ensure(snap_names="curl", state="latest")
            self.assertIsInstance(snap._Cache.cache, snap.SnapCache)

    @patch("builtins.open", new_callable=mock_open, read_data="foo\nbar\n  \n")
    @patch("os.path.isfile")
    def test_can_load_snap_cache(self, mock_exists, m):
        m.return_value.__iter__ = lambda self: self
        m.return_value.__next__ = lambda self: next(iter(self.readline, ""))
        mock_exists.return_value = True
        s = SnapCacheTester()
        s._load_available_snaps()
        self.assertIn("foo", s._snap_map)
        self.assertEqual(len(s._snap_map), 2)

    @patch("os.path.isfile", return_value=False)
    def test_no_load_if_catalog_not_populated(self, mock_isfile: MagicMock):
        s = SnapCacheTester()
        s._load_available_snaps()
        self.assertFalse(s._snap_map)  # pyright: ignore[reportUnknownMemberType]

    @patch("builtins.open", new_callable=mock_open, read_data="curl\n")
    @patch("os.path.isfile")
    def test_can_lazy_load_snap_info(self, mock_exists, m):
        m.return_value.__iter__ = lambda self: self
        m.return_value.__next__ = lambda self: next(iter(self.readline, ""))
        mock_exists.return_value = True
        s = SnapCacheTester()
        s._snap_client.get_snap_information.return_value = json.loads(lazy_load_result)["result"][
            0
        ]
        s._load_available_snaps()
        self.assertIn("curl", s._snap_map)

        result = s["curl"]
        self.assertEqual(result.name, "curl")
        self.assertEqual(result.state, snap.SnapState.Available)
        self.assertEqual(result.channel, "stable")
        self.assertEqual(result.confinement, "strict")
        self.assertEqual(result.revision, "233")

    @patch("os.path.isfile")
    def test_can_load_installed_snap_info(self, mock_exists):
        mock_exists.return_value = True
        s = SnapCacheTester()
        s._snap_client.get_installed_snaps.return_value = json.loads(installed_result)["result"]

        s._load_installed_snaps()

        self.assertEqual(len(s), 2)
        self.assertIn("charmcraft", s)
        self.assertEqual(list(s), [s["charmcraft"], s["core"]])  # test SnapCache.__iter__

        self.assertEqual(s["charmcraft"].name, "charmcraft")
        self.assertEqual(s["charmcraft"].state, snap.SnapState.Latest)
        self.assertEqual(s["charmcraft"].channel, "latest/stable")
        self.assertEqual(s["charmcraft"].confinement, "classic")
        self.assertEqual(s["charmcraft"].revision, "603")

    @patch("os.path.isfile")
    def test_raises_error_if_snap_not_running(self, mock_exists):
        mock_exists.return_value = False
        s = SnapCacheTester()
        s._snap_client.get_installed_snaps.side_effect = snap.SnapAPIError(
            {}, 400, "error", "snapd is not running"
        )
        with self.assertRaises(snap.SnapAPIError) as ctx:
            s._load_installed_snaps()
        repr(ctx.exception)  # ensure custom __repr__ doesn't error
        self.assertEqual("<charms.operator_libs_linux.v2.snap.SnapAPIError>", ctx.exception.name)
        self.assertIn("snapd is not running", ctx.exception.message)

    def test_can_compare_snap_equality(self):
        foo1 = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")
        foo2 = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")
        self.assertEqual(foo1, foo2)

    def test_snap_magic_methods(self):
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")
        self.assertEqual(hash(foo), hash((foo._name, foo._revision)))
        str(foo)  # ensure custom __str__ doesn't error
        repr(foo)  # ensure custom __repr__ doesn't error

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_can_run_snap_commands(self, mock_subprocess: MagicMock):
        mock_subprocess.return_value = 0
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")
        self.assertEqual(foo.present, True)
        foo.state = snap.SnapState.Present
        mock_subprocess.assert_not_called()

        foo.ensure(snap.SnapState.Absent)
        mock_subprocess.assert_called_with(["snap", "remove", "foo"], universal_newlines=True)

        foo.ensure(snap.SnapState.Latest, classic=True, channel="latest/edge")

        mock_subprocess.assert_called_with(
            [
                "snap",
                "install",
                "foo",
                "--classic",
                '--channel="latest/edge"',
            ],
            universal_newlines=True,
        )
        self.assertEqual(foo.latest, True)

        foo.state = snap.SnapState.Absent
        mock_subprocess.assert_called_with(["snap", "remove", "foo"], universal_newlines=True)

        foo.ensure(snap.SnapState.Latest, revision="123")
        mock_subprocess.assert_called_with(
            ["snap", "install", "foo", "--classic", '--revision="123"'], universal_newlines=True
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_refresh_revision_devmode_cohort_args(self, mock_subprocess: MagicMock):
        """Test that ensure and _refresh succeed and call the correct snap commands."""
        foo = snap.Snap(
            name="foo",
            state=snap.SnapState.Present,
            channel="stable",
            revision="1",
            confinement="devmode",
            apps=None,
            cohort="A",
        )
        foo.ensure(snap.SnapState.Latest, revision="2", devmode=True)
        mock_subprocess.assert_called_with(
            [
                "snap",
                "refresh",
                "foo",
                '--revision="2"',
                "--devmode",
                '--cohort="A"',
            ],
            universal_newlines=True,
        )

        foo._refresh(leave_cohort=True)
        mock_subprocess.assert_called_with(
            [
                "snap",
                "refresh",
                "foo",
                "--leave-cohort",
            ],
            universal_newlines=True,
        )
        self.assertEqual(foo._cohort, "")

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_no_subprocess_when_not_installed(self, mock_subprocess: MagicMock):
        """Don't call out to snap when ensuring an uninstalled state when not installed."""
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")
        not_installed_states = (snap.SnapState.Absent, snap.SnapState.Available)
        for _state in not_installed_states:
            foo._state = _state
            for state in not_installed_states:
                foo.ensure(state)
                mock_subprocess.assert_not_called()

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_can_run_snap_commands_devmode(self, mock_check_output: MagicMock):
        mock_check_output.return_value = 0
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "devmode")
        self.assertEqual(foo.present, True)

        foo.ensure(snap.SnapState.Absent)
        mock_check_output.assert_called_with(["snap", "remove", "foo"], universal_newlines=True)

        foo.ensure(snap.SnapState.Latest, devmode=True, channel="latest/edge")

        mock_check_output.assert_called_with(
            [
                "snap",
                "install",
                "foo",
                "--devmode",
                '--channel="latest/edge"',
            ],
            universal_newlines=True,
        )
        self.assertEqual(foo.latest, True)

        foo.state = snap.SnapState.Absent
        mock_check_output.assert_called_with(["snap", "remove", "foo"], universal_newlines=True)

        foo.ensure(snap.SnapState.Latest, revision=123)
        mock_check_output.assert_called_with(
            ["snap", "install", "foo", "--devmode", '--revision="123"'], universal_newlines=True
        )

        with self.assertRaises(ValueError):  # devmode and classic are mutually exclusive
            foo.ensure(snap.SnapState.Latest, devmode=True, classic=True)

    @patch("charms.operator_libs_linux.v2.snap.subprocess.run")
    def test_can_run_snap_daemon_commands(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock()
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")

        foo.start(["bar", "baz"], enable=True)
        mock_subprocess.assert_called_with(
            ["snap", "start", "--enable", "foo.bar", "foo.baz"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

        foo.stop(["bar"])
        mock_subprocess.assert_called_with(
            ["snap", "stop", "foo.bar"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

        foo.stop()
        mock_subprocess.assert_called_with(
            ["snap", "stop", "foo"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

        foo.logs()
        mock_subprocess.assert_called_with(
            ["snap", "logs", "-n=10", "foo"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

        foo.logs(services=["bar", "baz"], num_lines=None)
        mock_subprocess.assert_called_with(
            ["snap", "logs", "foo.bar", "foo.baz"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

        foo.restart()
        mock_subprocess.assert_called_with(
            ["snap", "restart", "foo"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

        foo.restart(["bar", "baz"], reload=True)
        mock_subprocess.assert_called_with(
            ["snap", "restart", "--reload", "foo.bar", "foo.baz"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

    @patch(
        "charms.operator_libs_linux.v2.snap.subprocess.run",
        side_effect=CalledProcessError(returncode=1, cmd=""),
    )
    def test_snap_daemon_commands_raise_snap_error(self, mock_subprocess: MagicMock):
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")
        with self.assertRaises(snap.SnapError):
            foo.start(["bad", "arguments"], enable=True)

    @patch("charms.operator_libs_linux.v2.snap.subprocess.run")
    def test_snap_connect(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock()
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")

        foo.connect(plug="bar", slot="baz")
        mock_subprocess.assert_called_with(
            ["snap", "connect", "foo:bar", "baz"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

        foo.connect(plug="bar")
        mock_subprocess.assert_called_with(
            ["snap", "connect", "foo:bar"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

        foo.connect(plug="bar", service="baz", slot="boo")
        mock_subprocess.assert_called_with(
            ["snap", "connect", "foo:bar", "baz:boo"],
            universal_newlines=True,
            check=True,
            capture_output=True,
        )

    @patch(
        "charms.operator_libs_linux.v2.snap.subprocess.run",
        side_effect=CalledProcessError(returncode=1, cmd=""),
    )
    def test_snap_connect_raises_snap_error(self, mock_subprocess: MagicMock):
        """Ensure that a SnapError is raised when Snap.connect is called with bad arguments."""
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")
        with self.assertRaises(snap.SnapError):
            foo.connect(plug="bad", slot="argument")

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_snap_hold_timedelta(self, mock_subprocess):
        mock_subprocess.return_value = 0
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")

        foo.hold(duration=datetime.timedelta(hours=72))
        mock_subprocess.assert_called_with(
            [
                "snap",
                "refresh",
                "foo",
                "--hold=259200s",
            ],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_snap_hold_forever(self, mock_subprocess):
        mock_subprocess.return_value = 0
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")

        foo.hold()
        mock_subprocess.assert_called_with(
            [
                "snap",
                "refresh",
                "foo",
                "--hold=forever",
            ],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_snap_unhold(self, mock_subprocess):
        mock_subprocess.return_value = 0
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")

        foo.unhold()
        mock_subprocess.assert_called_with(
            [
                "snap",
                "refresh",
                "foo",
                "--unhold",
            ],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.SnapClient.get_installed_snap_apps")
    def test_apps_property(self, patched):
        s = SnapCacheTester()
        s._snap_client.get_installed_snaps.return_value = json.loads(installed_result)["result"]
        s._load_installed_snaps()

        patched.return_value = json.loads(installed_result)["result"][0]["apps"]
        self.assertEqual(len(s["charmcraft"].apps), 2)
        self.assertIn({"snap": "charmcraft", "name": "charmcraft"}, s["charmcraft"].apps)

    @patch("charms.operator_libs_linux.v2.snap.SnapClient.get_installed_snap_apps")
    def test_services_property(self, patched):
        s = SnapCacheTester()
        s._snap_client.get_installed_snaps.return_value = json.loads(installed_result)["result"]
        s._load_installed_snaps()

        patched.return_value = json.loads(installed_result)["result"][0]["apps"]
        self.assertEqual(len(s["charmcraft"].services), 1)
        self.assertDictEqual(
            s["charmcraft"].services,
            {
                "foo_service": {
                    "daemon": "simple",
                    "enabled": True,
                    "active": False,
                    "daemon_scope": None,
                    "activators": [],
                }
            },
        )


class TestSocketClient(unittest.TestCase):
    def test_socket_not_found(self):
        client = snap.SnapClient(socket_path="/does/not/exist")
        with self.assertRaises(snap.SnapAPIError) as ctx:
            client.get_installed_snaps()
        self.assertIsInstance(ctx.exception, snap.SnapAPIError)

    def test_fake_socket(self):
        shutdown, socket_path = fake_snapd.start_server()

        try:
            client = snap.SnapClient(socket_path)
            with self.assertRaises(snap.SnapAPIError) as ctx:
                client.get_installed_snaps()
            self.assertIsInstance(ctx.exception, snap.SnapAPIError)
        finally:
            shutdown()

    @patch("builtins.hasattr", return_value=False)
    def test_not_implemented_raised_when_missing_socket_af_unix(self, _: MagicMock):
        """Assert NotImplementedError raised when missing socket.AF_UNIX."""
        s = snap._UnixSocketConnection("localhost")
        with self.assertRaises(NotImplementedError):
            s.connect()  # hasattr(socket, "AF_UNIX") == False

    def test_request_bad_body_raises_snapapierror(self):
        """Assert SnapAPIError raised on SnapClient._request with bad body."""
        shutdown, socket_path = fake_snapd.start_server()
        try:
            client = snap.SnapClient(socket_path)
            body = {"bad": "body"}
            with patch.object(
                client,
                "_request_raw",
                side_effect=client._request_raw,  # pyright: ignore[reportUnknownMemberType]
            ) as mock_raw:
                with self.assertRaises(snap.SnapAPIError):
                    client._request(  # pyright: ignore[reportUnknownMemberType]
                        "GET", "snaps", body=body
                    )
                mock_raw.assert_called_with(
                    "GET",  # method
                    "snaps",  # path
                    None,  # query
                    {"Accept": "application/json", "Content-Type": "application/json"},  # headers
                    json.dumps(body).encode("utf-8"),  # body
                )
        finally:
            shutdown()

    def test_request_raw_missing_headers_raises_snapapierror(self):
        """Assert SnapAPIError raised on SnapClient._request_raw when missing headers."""
        shutdown, socket_path = fake_snapd.start_server()
        try:
            client = snap.SnapClient(socket_path)
            with patch.object(
                snap.urllib.request, "Request", side_effect=snap.urllib.request.Request
            ) as mock_request:
                with self.assertRaises(snap.SnapAPIError):
                    client._request_raw("GET", "snaps")  # pyright: ignore[reportUnknownMemberType]
            self.assertEqual(mock_request.call_args.kwargs["headers"], {})
        finally:
            shutdown()

    def test_request_raw_bad_response_raises_snapapierror(self):
        """Assert SnapAPIError raised on SnapClient._request_raw when receiving a bad response."""
        shutdown, socket_path = fake_snapd.start_server()
        try:
            client = snap.SnapClient(socket_path)
            with patch.object(snap.json, "loads", return_value={}):
                with self.assertRaises(snap.SnapAPIError) as ctx:
                    client._request_raw("GET", "snaps")  # pyright: ignore[reportUnknownMemberType]
            # the return_value was correctly patched in
            self.assertEqual(ctx.exception.body, {})  # pyright: ignore[reportUnknownMemberType]
            # response is bad because it's missing expected keys
            self.assertEqual(ctx.exception.message, "KeyError - 'result'")
        finally:
            shutdown()

    def test_wait_changes(self):
        change_finished = False

        def _request_raw(
            method: str,
            path: str,
            query: Dict = None,
            headers: Dict = None,
            data: bytes = None,
        ) -> typing.IO[bytes]:
            nonlocal change_finished
            if method == "PUT" and path == "snaps/test/conf":
                return io.BytesIO(
                    json.dumps(
                        {
                            "type": "async",
                            "status-code": 202,
                            "status": "Accepted",
                            "result": None,
                            "change": "97",
                        }
                    ).encode("utf-8")
                )
            if method == "GET" and path == "changes/97" and not change_finished:
                change_finished = True
                return io.BytesIO(
                    json.dumps(
                        {
                            "type": "sync",
                            "status-code": 200,
                            "status": "OK",
                            "result": {
                                "id": "97",
                                "kind": "configure-snap",
                                "summary": 'Change configuration of "test" snap',
                                "status": "Doing",
                                "tasks": [
                                    {
                                        "id": "1029",
                                        "kind": "run-hook",
                                        "summary": 'Run configure hook of "test" snap',
                                        "status": "Doing",
                                        "progress": {"label": "", "done": 1, "total": 1},
                                        "spawn-time": "2024-11-28T20:02:47.498399651+00:00",
                                        "data": {"affected-snaps": ["test"]},
                                    }
                                ],
                                "ready": False,
                                "spawn-time": "2024-11-28T20:02:47.49842583+00:00",
                            },
                        }
                    ).encode("utf-8")
                )
            if method == "GET" and path == "changes/97" and change_finished:
                return io.BytesIO(
                    json.dumps(
                        {
                            "type": "sync",
                            "status-code": 200,
                            "status": "OK",
                            "result": {
                                "id": "98",
                                "kind": "configure-snap",
                                "summary": 'Change configuration of "test" snap',
                                "status": "Done",
                                "tasks": [
                                    {
                                        "id": "1030",
                                        "kind": "run-hook",
                                        "summary": 'Run configure hook of "test" snap',
                                        "status": "Done",
                                        "progress": {"label": "", "done": 1, "total": 1},
                                        "spawn-time": "2024-11-28T20:06:41.415929854+00:00",
                                        "ready-time": "2024-11-28T20:06:41.797437537+00:00",
                                        "data": {"affected-snaps": ["test"]},
                                    }
                                ],
                                "ready": True,
                                "spawn-time": "2024-11-28T20:06:41.415955681+00:00",
                                "ready-time": "2024-11-28T20:06:41.797440022+00:00",
                            },
                        }
                    ).encode("utf-8")
                )
            raise RuntimeError("unknown request")

        client = snap.SnapClient()
        with patch.object(client, "_request_raw", _request_raw), patch.object(time, "sleep"):
            client._put_snap_conf("test", {"foo": "bar"})

    def test_wait_failed(self):
        def _request_raw(
            method: str,
            path: str,
            query: Dict = None,
            headers: Dict = None,
            data: bytes = None,
        ) -> typing.IO[bytes]:
            if method == "PUT" and path == "snaps/test/conf":
                return io.BytesIO(
                    json.dumps(
                        {
                            "type": "async",
                            "status-code": 202,
                            "status": "Accepted",
                            "result": None,
                            "change": "97",
                        }
                    ).encode("utf-8")
                )
            if method == "GET" and path == "changes/97":
                return io.BytesIO(
                    json.dumps(
                        {
                            "type": "sync",
                            "status-code": 200,
                            "status": "OK",
                            "result": {
                                "id": "97",
                                "kind": "configure-snap",
                                "summary": 'Change configuration of "test" snap',
                                "status": "Error",
                                "ready": False,
                                "spawn-time": "2024-11-28T20:02:47.49842583+00:00",
                            },
                        }
                    ).encode("utf-8")
                )
            raise RuntimeError("unknown request")

        client = snap.SnapClient()
        with patch.object(client, "_request_raw", _request_raw), patch.object(time, "sleep"):
            with self.assertRaises(snap.SnapError):
                client._put_snap_conf("test", {"foo": "bar"})


class TestSnapBareMethods(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="curl\n")
    @patch("os.path.isfile")
    def setUp(self, mock_exists, m):
        m.return_value.__iter__ = lambda self: self
        m.return_value.__next__ = lambda self: next(iter(self.readline, ""))
        mock_exists.return_value = True
        snap._Cache.cache = SnapCacheTester()
        snap._Cache.cache._snap_client.get_installed_snaps.return_value = json.loads(
            installed_result
        )["result"]
        snap._Cache.cache._snap_client.get_snap_information.return_value = json.loads(
            lazy_load_result
        )["result"][0]
        snap._Cache.cache._load_installed_snaps()
        snap._Cache.cache._load_available_snaps()

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_can_run_bare_changes(self, mock_subprocess: MagicMock):
        mock_subprocess.return_value = 0
        foo = snap.add("curl", classic=True, channel="latest")
        mock_subprocess.assert_called_with(
            ["snap", "install", "curl", "--classic", '--channel="latest"'],
            universal_newlines=True,
        )
        self.assertTrue(foo.present)
        snap.add("curl", state="latest")  # cover string conversion path
        mock_subprocess.assert_called_with(
            ["snap", "refresh", "curl", '--channel="latest"'],
            universal_newlines=True,
        )
        with self.assertRaises(TypeError):  # cover error path
            snap.add(snap_names=[])

        bar = snap.remove("curl")
        mock_subprocess.assert_called_with(["snap", "remove", "curl"], universal_newlines=True)
        self.assertFalse(bar.present)
        with self.assertRaises(TypeError):  # cover error path
            snap.remove(snap_names=[])

        baz = snap.add("curl", classic=True, revision=123)
        mock_subprocess.assert_called_with(
            ["snap", "install", "curl", "--classic", '--revision="123"'], universal_newlines=True
        )
        self.assertTrue(baz.present)

    @patch("charms.operator_libs_linux.v2.snap.subprocess")
    def test_cohort(self, mock_subprocess):
        mock_subprocess.check_output = MagicMock()

        snap.add("curl", channel="latest", cohort="+")
        mock_subprocess.check_output.assert_called_with(
            [
                "snap",
                "install",
                "curl",
                '--channel="latest"',
                '--cohort="+"',
            ],
            universal_newlines=True,
        )

        snap.ensure("curl", "latest", classic=True, channel="latest/beta", cohort="+")
        mock_subprocess.check_output.assert_called_with(
            [
                "snap",
                "refresh",
                "curl",
                '--channel="latest/beta"',
                '--cohort="+"',
            ],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_revision_doesnt_refresh(self, mock_check_output):
        snap.add("curl", revision="233", cohort="+")
        mock_check_output.assert_called_with(
            [
                "snap",
                "install",
                "curl",
                '--revision="233"',
                '--cohort="+"',
            ],
            universal_newlines=True,
        )

        mock_check_output.reset_mock()
        # Ensure that calling refresh with the same revision doesn't subprocess out.
        snap.ensure("curl", "latest", classic=True, revision="233", cohort="+")
        mock_check_output.assert_not_called()

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_can_ensure_states(self, mock_subprocess):
        mock_subprocess.return_value = 0
        foo = snap.ensure("curl", "latest", classic=True, channel="latest/test")
        mock_subprocess.assert_called_with(
            ["snap", "install", "curl", "--classic", '--channel="latest/test"'],
            universal_newlines=True,
        )
        self.assertTrue(foo.present)

        bar = snap.ensure("curl", "absent")
        mock_subprocess.assert_called_with(["snap", "remove", "curl"], universal_newlines=True)
        self.assertFalse(bar.present)

        baz = snap.ensure("curl", "present", classic=True, revision=123)
        mock_subprocess.assert_called_with(
            ["snap", "install", "curl", "--classic", '--revision="123"'],
            universal_newlines=True,
        )
        self.assertTrue(baz.present)

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_raises_snap_error_on_failed_subprocess(self, mock_subprocess: MagicMock):
        def raise_error(cmd, **kwargs):
            # If we can't find the snap, we should raise a CalledProcessError.
            #
            # We do it artificially so that this test works on systems w/out snapd installed.
            raise CalledProcessError(None, cmd)

        mock_subprocess.side_effect = raise_error
        with self.assertRaises(snap.SnapError) as ctx:
            snap.add("nothere")
        repr(ctx.exception)  # ensure custom __repr__ doesn't error

    def test_raises_snap_error_on_snap_not_found(self):
        """A cache failure will also ultimately result in a SnapError."""

        class NotFoundCache:
            cache = None

            def __getitem__(self, name: str) -> snap.Snap:
                raise snap.SnapNotFoundError()

        with patch.object(snap, "_Cache", new=NotFoundCache()):
            with self.assertRaises(snap.SnapError) as ctx:
                snap.add("nothere")
        repr(ctx.exception)  # ensure custom __repr__ doesn't error
        self.assertEqual("<charms.operator_libs_linux.v2.snap.SnapError>", ctx.exception.name)
        self.assertIn("Failed to install or refresh snap(s): nothere", ctx.exception.message)

    def test_snap_get(self):
        """Test the multiple different ways of calling the Snap.get function.

        Valid ways:
            ("key", typed=False) -> returns a string
            ("key", typed=True) -> returns value parsed from json
            (None, typed=True) -> returns parsed json for all keys
            ("", typed=True) -> returns parsed json for all keys

        An invalid key will raise an error if typed=False, but return None if typed=True.
        """

        def fake_snap(command: str, optargs: Optional[Iterable[str]] = None) -> str:
            """Snap._snap would normally call subprocess.check_output(["snap", ...], ...).

            Here we only handle the "get" commands generated by Snap.get:
                ["snap", "get", "-d"] -- equivalent to (None, typed=True)
                ["snap", "get", "key"] -- equivalent to ("key", typed=False)
                ["snap", "get", "-d" "key"] -- equivalent to ("key", typed=True)

            Values are returned from the local keys_and_values dict instead of calling out to snap.
            """
            assert command == "get"
            assert optargs is not None
            optargs = list(optargs)
            if optargs == ["-d"]:
                return json.dumps(keys_and_values)
            if len(optargs) == 1:  # [<some-key>]
                key = optargs[0]
                if key in keys_and_values:
                    return str(keys_and_values[key])
                raise snap.SnapError()
            if len(optargs) == 2 and optargs[0] == "-d":  # ["-d", <some-key>]
                key = optargs[1]
                if key in keys_and_values:
                    return json.dumps({key: keys_and_values[key]})
                return json.dumps({})
            raise snap.SnapError("Bad arguments:", command, optargs)

        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")
        foo._snap = MagicMock(side_effect=fake_snap)
        keys_and_values: Dict[str, Any] = {
            "key_w_string_value": "string",
            "key_w_float_value": 4.2,
            "key_w_int_value": 13,
            "key_w_json_value": {"key1": "string", "key2": 4.2, "key3": 13},
        }
        for key, value in keys_and_values.items():
            self.assertEqual(foo.get(key, typed=True), value)
            self.assertEqual(foo.get(key, typed=False), str(value))
            self.assertEqual(foo.get(key), str(value))
        self.assertEqual(foo.get(None, typed=True), keys_and_values)
        self.assertEqual(foo.get("", typed=True), keys_and_values)
        self.assertIs(foo.get("missing_key", typed=True), None)
        with self.assertRaises(snap.SnapError):
            foo.get("missing_key", typed=False)
        with self.assertRaises(TypeError):
            foo.get(None, typed=False)  # pyright: ignore[reportCallIssue, reportArgumentType]
        with self.assertRaises(TypeError):
            foo.get(None)  # pyright: ignore[reportArgumentType]

    @patch("charms.operator_libs_linux.v2.snap.SnapClient._put_snap_conf")
    def test_snap_set_typed(self, put_snap_conf):
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")

        config = {"n": 42, "s": "string", "d": {"nested": True}}

        foo.set(config, typed=True)
        put_snap_conf.assert_called_with("foo", {"n": 42, "s": "string", "d": {"nested": True}})

    @patch("charms.operator_libs_linux.v2.snap.SnapClient._put_snap_conf")
    def test_snap_set_untyped(self, put_snap_conf):
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")

        config = {"n": 42, "s": "string", "d": {"nested": True}}

        foo.set(config, typed=False)
        put_snap_conf.assert_called_with(
            "foo", {"n": "42", "s": "string", "d": "{'nested': True}"}
        )

    @patch(
        "charms.operator_libs_linux.v2.snap.subprocess.check_output",
        side_effect=lambda *args, **kwargs: "",  # pyright: ignore[reportUnknownLambdaType]
    )
    def test_snap_unset(self, mock_subprocess: MagicMock):
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")
        key: str = "test_key"
        self.assertEqual(foo.unset(key), "")  # pyright: ignore[reportUnknownMemberType]
        mock_subprocess.assert_called_with(
            ["snap", "unset", "foo", key],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_call")
    def test_system_set(self, mock_subprocess):
        snap._system_set("refresh.hold", "foobar")
        mock_subprocess.assert_called_with(
            ["snap", "set", "system", "refresh.hold=foobar"],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_call")
    def test_system_set_fail(self, mock_subprocess):
        mock_subprocess.side_effect = CalledProcessError(1, "foobar")
        with self.assertRaises(snap.SnapError):
            snap._system_set("refresh.hold", "foobar")

    def test_hold_refresh_invalid_too_high(self):
        with self.assertRaises(ValueError):
            snap.hold_refresh(days=120)

    def test_hold_refresh_invalid_non_int(self):
        with self.assertRaises(TypeError):
            snap.hold_refresh(days="foobar")

    def test_hold_refresh_invalid_non_bool(self):
        with self.assertRaises(TypeError):
            snap.hold_refresh(forever="foobar")

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_call")
    def test_hold_refresh_reset(self, mock_subprocess):
        snap.hold_refresh(days=0)
        mock_subprocess.assert_called_with(
            ["snap", "set", "system", "refresh.hold="],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_call")
    def test_hold_refresh_forever(self, mock_subprocess):
        snap.hold_refresh(forever=True)

        mock_subprocess.assert_called_with(
            ["snap", "set", "system", "refresh.hold=forever"],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.datetime")
    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_call")
    def test_hold_refresh_valid_days(self, mock_subprocess, mock_datetime):
        # A little too closely-tied to the internals of hold_refresh(), but at least
        # the test runs whatever your local time zone is.
        mock_datetime.now.return_value.astimezone.return_value = datetime.datetime(
            1970, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
        )

        snap.hold_refresh(days=90)

        mock_subprocess.assert_called_with(
            ["snap", "set", "system", "refresh.hold=1970-04-01T00:00:00+00:00"],
            universal_newlines=True,
        )

    def test_ansi_filter(self):
        assert (
            snap.ansi_filter.sub("", "\x1b[0m\x1b[?25h\x1b[Khello-world-gtk") == "hello-world-gtk"
        )
        assert snap.ansi_filter.sub("", "\x1b[0m\x1b[?25h\x1b[Kpypi-server") == "pypi-server"
        assert snap.ansi_filter.sub("", "\x1b[0m\x1b[?25h\x1b[Kparca") == "parca"

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_install_local(self, mock_subprocess):
        mock_subprocess.return_value = "curl XXX installed"
        snap.install_local("./curl.snap")
        mock_subprocess.assert_called_with(
            ["snap", "install", "./curl.snap"],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_install_local_args(self, mock_subprocess):
        mock_subprocess.return_value = "curl XXX installed"
        for kwargs, cmd_args in [
            ({"classic": True}, ["--classic"]),
            ({"devmode": True}, ["--devmode"]),
            ({"dangerous": True}, ["--dangerous"]),
            ({"classic": True, "dangerous": True}, ["--classic", "--dangerous"]),
        ]:
            snap.install_local("./curl.snap", **kwargs)
            mock_subprocess.assert_called_with(
                ["snap", "install", "./curl.snap"] + cmd_args,
                universal_newlines=True,
            )
            mock_subprocess.reset_mock()

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_install_local_snap_api_error(self, mock_subprocess: MagicMock):
        """install_local raises a SnapError if cache access raises a SnapAPIError."""

        class APIErrorCache:
            def __getitem__(self, key):
                raise snap.SnapAPIError(body={}, code=123, status="status", message="message")

        mock_subprocess.return_value = "curl XXX installed"
        with patch.object(snap, "SnapCache", new=APIErrorCache):
            with self.assertRaises(snap.SnapError) as ctx:
                snap.install_local("./curl.snap")
        self.assertEqual(ctx.exception.message, "Failed to find snap curl in Snap cache")

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_install_local_called_process_error(self, mock_subprocess: MagicMock):
        """install_local raises a SnapError if the subprocess raises a CalledProcessError."""
        mock_subprocess.side_effect = CalledProcessError(
            returncode=1, cmd="cmd", output="dummy-output"
        )
        with self.assertRaises(snap.SnapError) as ctx:
            snap.install_local("./curl.snap")
        self.assertEqual(ctx.exception.message, "Could not install snap ./curl.snap: dummy-output")

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_alias(self, mock_subprocess):
        mock_subprocess.return_value = ""
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")
        foo.alias("bar", "baz")
        mock_subprocess.assert_called_once_with(
            ["snap", "alias", "foo.bar", "baz"],
            universal_newlines=True,
        )
        mock_subprocess.reset_mock()

        foo.alias("bar")
        mock_subprocess.assert_called_once_with(
            ["snap", "alias", "foo.bar", "bar"],
            universal_newlines=True,
        )
        mock_subprocess.reset_mock()

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_alias_raises_snap_error(self, mock_subprocess):
        mock_subprocess.side_effect = CalledProcessError(
            returncode=1, cmd=["snap", "alias", "foo.bar", "baz"]
        )
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")
        with self.assertRaises(snap.SnapError):
            foo.alias("bar", "baz")
        mock_subprocess.assert_called_once_with(
            ["snap", "alias", "foo.bar", "baz"],
            universal_newlines=True,
        )
        mock_subprocess.reset_mock()

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_held(self, mock_subprocess: MagicMock):
        foo = snap.Snap("foo", snap.SnapState.Latest, "stable", "1", "classic")
        mock_subprocess.return_value = {}
        self.assertEqual(foo.held, False)
        mock_subprocess.return_value = {"hold:": "key isn't checked"}
        self.assertEqual(foo.held, True)
