# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import grp
import pwd
from unittest.mock import patch

from charms.operator_libs_linux.v0 import passwd
from pyfakefs.fake_filesystem_unittest import TestCase

pwd_getpw_return = [
    pwd.struct_passwd(
        (
            "systemd-coredump",
            "x",
            "999",
            "999",
            "systemd Core Dumper",
            "/",
            "/usr/sbin/nologin",
        )
    ),
    pwd.struct_passwd(
        (
            "testuser",
            "x",
            "1000",
            "1000",
            "",
            "/home/testuser",
            "/usr/bin/bash",
        )
    ),
    pwd.struct_passwd(
        (
            "lxd",
            "x",
            "998",
            "118",
            "",
            "/var/snap/lxd/common/lxd",
            "/bin/false",
        )
    ),
]

grp_getgr_return = [
    grp.struct_group(("lxd", "x", "118", ["testuser"])),
    grp.struct_group(("systemd-coredump", "x", "999", [])),
    grp.struct_group(("testuser", "x", "1000", [])),
    grp.struct_group(("microk8s", "x", "998", ["testuser"])),
]

etc_passwd = """systemd-coredump:x:999:999:systemd Core Dumper:/:/usr/sbin/nologin
testuser:x:1000:1000::/home/testuser:/usr/bin/bash
lxd:x:998:118::/var/snap/lxd/common/lxd:/bin/false
"""

etc_shadow = """
systemd-coredump:!!:18801::::::
rbarry::18801:0:99999:7:::
lxd:!:18801::::::
"""


class TestPasswd(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.fs.create_file("/etc/passwd", contents=etc_passwd)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_can_load_groups(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()
        self.assertIn("testuser", p.groups)
        self.assertEqual(len(p.groups), 4)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_lookup_group_by_gid(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()
        lxd_group = passwd.Passwd.lookup_group(118)
        self.assertEqual(p.groups["lxd"], lxd_group)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_lookup_group_by_name(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()
        lxd_group = passwd.Passwd.lookup_group("lxd")
        self.assertEqual(p.groups["lxd"], lxd_group)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_lookup_group_raises_type_error(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        invalid = [False, passwd.Group("foo", []), 37.55]
        for x in invalid:
            with self.assertRaises(TypeError):
                passwd.Passwd.lookup_group(x)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_can_get_group_details(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()
        group = p.groups["lxd"]

        self.assertEqual(group.name, "lxd")
        self.assertEqual(group.gid, 118)
        self.assertEqual(group.users[0].name, "testuser")

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_raises_error_on_group_not_found(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()

        with self.assertRaises(passwd.GroupNotFoundError) as ctx:
            p.groups["nothere"]

        self.assertEqual(
            "<charms.operator_libs_linux.v0.passwd.GroupNotFoundError>", ctx.exception.name
        )
        self.assertIn("Group 'nothere' not found", ctx.exception.message)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_can_load_users(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()
        self.assertIn("systemd-coredump", p.users)
        self.assertEqual(len(p.users), 3)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_can_get_user_details(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()
        u = p.users["systemd-coredump"]
        self.assertEqual(u.name, "systemd-coredump")
        self.assertEqual(u.primary_group, p.groups["systemd-coredump"])
        self.assertEqual(u.uid, 999)
        self.assertEqual(u.shell, "/usr/sbin/nologin")
        self.assertEqual(u.homedir, "/")
        self.assertEqual(u.state, passwd.UserState.NoLogin)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_lookup_user_by_uid(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()
        lxd_user = passwd.Passwd.lookup_user(998)
        self.assertEqual(p.users["lxd"], lxd_user)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_lookup_user_by_name(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()
        lxd_user = passwd.Passwd.lookup_user("lxd")
        self.assertEqual(p.users["lxd"], lxd_user)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_lookup_user_raises_type_error(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        invalid = [False, passwd.Group("foo", []), 37.55]
        for x in invalid:
            with self.assertRaises(TypeError):
                passwd.Passwd.lookup_user(x)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    def test_raises_error_on_user_not_found(self, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        p = passwd.Passwd()

        with self.assertRaises(passwd.UserNotFoundError) as ctx:
            p.users["nothere"]

        self.assertEqual(
            "<charms.operator_libs_linux.v0.passwd.UserNotFoundError>", ctx.exception.name
        )
        self.assertIn("User 'nothere' not found", ctx.exception.message)

    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    @patch("charms.operator_libs_linux.v0.passwd.subprocess.check_call")
    def test_can_ensure_user_state(self, mock_subprocess, mock_grp, mock_pw):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        mock_subprocess.return_value = 0
        p = passwd.Passwd()

        u = p.users["systemd-coredump"]
        u.ensure_state(passwd.UserState.Disabled)
        mock_subprocess.assert_called_with(["usermod", "-L", u.name])
        print(open("/etc/passwd").readlines())
        u.ensure_state(passwd.UserState.NoLogin)

        v = p.users["testuser"]
        v.ensure_state(passwd.UserState.NoLogin)
        mock_subprocess.assert_called_with(["usermod", "-s", "/sbin/nologin", v.name])

    @patch("pwd.getpwuid")
    @patch("pwd.getpwall")
    @patch("grp.getgrall")
    @patch("charms.operator_libs_linux.v0.passwd.subprocess.check_call")
    def test_can_add_users_and_groups(self, mock_subprocess, mock_grp, mock_pw, mock_getuid):
        mock_grp.return_value = grp_getgr_return
        mock_pw.return_value = pwd_getpw_return
        mock_getuid.side_effect = KeyError
        mock_subprocess.return_value = 0
        p = passwd.Passwd()

        g = passwd.Group("foo", [], gid=1001)
        p.add_group(g)
        mock_subprocess.assert_called_with(["groupadd", "-g", 1001, "foo"])
        u = passwd.User(
            "foo",
            passwd.UserState.Present,
            uid=1001,
            group=g,
            homedir="/home/foo",
            shell="/usr/bin/bash",
        )
        u.ensure_state(u.state)
        mock_subprocess.assert_called_with(
            [
                "useradd",
                "-g",
                "1001",
                "-s",
                "/usr/bin/bash",
                "-d",
                "/home/foo",
                "-u",
                "1001",
                "foo",
            ]
        )
