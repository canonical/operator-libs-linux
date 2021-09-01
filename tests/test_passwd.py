# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import subprocess

from pyfakefs.fake_filesystem_unittest import TestCase
from unittest.mock import MagicMock, patch

etc_passwd = """systemd-coredump:x:999:999:systemd Core Dumper:/:/usr/sbin/nologin
testuser:x:1000:1000::/home/testuser:/usr/bin/bash
lxd:x:998:118::/var/snap/lxd/common/lxd:/bin/false
"""

etc_group = """lxd:x:118:testuser
systemd-coredump:x:999:
testuser:x:1000:
microk8s:x:998:testuser
"""

etc_shadow = """
systemd-coredump:!!:18801::::::
rbarry::18801:0:99999:7:::
lxd:!:18801::::::
"""

patch("lib.charm.operator.v0.passwd.initialize", MagicMock(return_value="True"))
from lib.charm.operator.v0 import passwd


class TestPasswd(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.fs.create_file("/etc/passwd", contents=etc_passwd)
        self.fs.create_file("/etc/group", contents=etc_group)
        _GROUP_CACHE = passwd.GroupCache()
        _USER_CACHE = passwd.UserCache()
        _GROUP_CACHE.realize_users()

    def test_can_load_groups(self):
        g = passwd.GroupCache()

        self.assertIn("testuser", g)
        self.assertEqual(len(g), 4)

    def test_can_get_group_details(self):
        g = passwd.GroupCache()
        group = g["lxd"]

        self.assertEqual(group.name, "lxd")
        self.assertEqual(group.gid, 118)
        self.assertEqual(group.users[0].name, "testuser")

    def test_raises_error_on_group_not_found(self):
        groups = passwd.GroupCache()

        with self.assertRaises(passwd.GroupNotFoundError) as ctx:
            t = groups["nothere"]

        self.assertEqual("<lib.charm.operator.v0.passwd.GroupNotFoundError>", ctx.exception.name)
        self.assertIn("Group 'nothere' not found", ctx.exception.message)

    def test_can_load_users(self):
        u = passwd.UserCache()
        self.assertIn("systemd-coredump", u)
        self.assertEqual(len(u), 3)

    def test_can_get_user_details(self):
        users = passwd.UserCache()
        u = users["systemd-coredump"]
        self.assertEqual(u.name, "systemd-coredump")
        self.assertEqual(u.primary_group, passwd.GroupCache()["systemd-coredump"])
        self.assertEqual(u.uid, 999)
        self.assertEqual(u.shell, "/usr/sbin/nologin")
        self.assertEqual(u.homedir, "/")
        self.assertEqual(u.state, passwd.UserState.NoLogin)

    def test_raises_error_on_user_not_found(self):
        users = passwd.UserCache()

        with self.assertRaises(passwd.UserNotFoundError) as ctx:
            t = users["nothere"]

        self.assertEqual("<lib.charm.operator.v0.passwd.UserNotFoundError>", ctx.exception.name)
        self.assertIn("User 'nothere' not found", ctx.exception.message)

    @patch("lib.charm.operator.v0.passwd.subprocess.check_call")
    def test_can_ensure_user_state(self, mock_subprocess):
        mock_subprocess.return_value = 0
        users = passwd.UserCache()
        u = users["systemd-coredump"]
        u.ensure(passwd.UserState.Disabled)
        mock_subprocess.assert_called_with(["usermod", "-L", u.name])
        print(open("/etc/passwd").readlines())
        u.ensure(passwd.UserState.NoLogin)

        v = users["testuser"]
        v.ensure(passwd.UserState.NoLogin)
        mock_subprocess.assert_called_with(["usermod", "-s", "/sbin/nologin", v.name])

    @patch("lib.charm.operator.v0.passwd.subprocess.check_call")
    def test_can_add_users(self, mock_subprocess):
        mock_subprocess.return_value = 0
        groups = passwd.GroupCache()
        users = passwd.UserCache()
        g = passwd.Group("foo", 1001, [])
        groups.add(g)
        u = passwd.User("foo", 1001, g, "/home/foo", "/usr/bin/bash", passwd.UserState.Present)
        u.ensure(u.state)
        mock_subprocess.assert_called_with(
            ["useradd", "-g", 1001, "-s", "/usr/bin/bash", "-d", "/home/foo", "-u", 1001, "foo"]
        )
