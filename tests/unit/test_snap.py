# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import datetime
import json
import unittest
from subprocess import CalledProcessError
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
    @patch("builtins.open", new_callable=mock_open, read_data="foo\nbar\n")
    @patch("os.path.isfile")
    def test_can_load_snap_cache(self, mock_exists, m):
        m.return_value.__iter__ = lambda self: self
        m.return_value.__next__ = lambda self: next(iter(self.readline, ""))
        mock_exists.return_value = True
        s = SnapCacheTester()
        s._load_available_snaps()
        self.assertIn("foo", s._snap_map)
        self.assertEqual(len(s._snap_map), 2)

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
        self.assertEqual("<charms.operator_libs_linux.v2.snap.SnapAPIError>", ctx.exception.name)
        self.assertIn("snapd is not running", ctx.exception.message)

    def test_can_compare_snap_equality(self):
        foo1 = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")
        foo2 = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")
        self.assertEqual(foo1, foo2)

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_can_run_snap_commands(self, mock_subprocess):
        mock_subprocess.return_value = 0
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")
        self.assertEqual(foo.present, True)

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

        foo.ensure(snap.SnapState.Latest, revision=123)
        mock_subprocess.assert_called_with(
            ["snap", "install", "foo", "--classic", '--revision="123"'], universal_newlines=True
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_can_run_snap_commands_devmode(self, mock_check_output):
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
    def test_snap_snap_connect_raises_snap_error(self, mock_subprocess: MagicMock):
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
    def test_can_run_bare_changes(self, mock_subprocess):
        mock_subprocess.return_value = 0
        foo = snap.add("curl", classic=True, channel="latest")
        mock_subprocess.assert_called_with(
            ["snap", "install", "curl", "--classic", '--channel="latest"'],
            universal_newlines=True,
        )
        self.assertTrue(foo.present)

        bar = snap.remove("curl")
        mock_subprocess.assert_called_with(["snap", "remove", "curl"], universal_newlines=True)
        self.assertFalse(bar.present)

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
    def test_raises_snap_not_found_error(self, mock_subprocess):
        def raise_error(cmd, **kwargs):
            # If we can't find the snap, we should raise a CalledProcessError.
            #
            # We do it artificially so that this test works on systems w/out snapd installed.
            raise CalledProcessError(None, cmd)

        mock_subprocess.side_effect = raise_error
        with self.assertRaises(snap.SnapError) as ctx:
            snap.add("nothere")
        self.assertEqual("<charms.operator_libs_linux.v2.snap.SnapError>", ctx.exception.name)
        self.assertIn("Failed to install or refresh snap(s): nothere", ctx.exception.message)

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_snap_set_typed(self, mock_subprocess):
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")

        config = {"n": 42, "s": "string", "d": {"nested": True}}

        foo.set(config, typed=True)
        mock_subprocess.assert_called_with(
            ["snap", "set", "foo", "-t", "n=42", 's="string"', 'd={"nested": true}'],
            universal_newlines=True,
        )

    @patch("charms.operator_libs_linux.v2.snap.subprocess.check_output")
    def test_snap_set_untyped(self, mock_subprocess):
        foo = snap.Snap("foo", snap.SnapState.Present, "stable", "1", "classic")

        config = {"n": 42, "s": "string", "d": {"nested": True}}

        foo.set(config, typed=False)
        mock_subprocess.assert_called_with(
            ["snap", "set", "foo", "n=42", "s=string", "d={'nested': True}"],
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
