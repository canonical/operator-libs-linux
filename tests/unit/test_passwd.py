# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest import TestCase
from unittest.mock import MagicMock, patch

from charms.operator_libs_linux.v0 import passwd


class TestPasswd(TestCase):
    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrnam")
    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_adds_a_user_if_it_doesnt_exist(self, check_output, getpwnam, getgrnam):
        username = "johndoe"
        password = "eodnhoj"
        shell = "/bin/bash"
        existing_user_pwnam = KeyError("user not found")
        new_user_pwnam = "some user pwnam"

        getpwnam.side_effect = [existing_user_pwnam, new_user_pwnam]

        result = passwd.add_user(username, password=password)

        self.assertEqual(result, new_user_pwnam)
        check_output.assert_called_with(
            [
                "useradd",
                "--create-home",
                "--shell",
                shell,
                "--password",
                password,
                "-g",
                username,
                username,
            ],
            stderr=-2,
        )
        getpwnam.assert_called_with(username)

    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_doesnt_add_user_if_it_already_exists(self, check_output, getpwnam):
        username = "johndoe"
        password = "eodnhoj"
        existing_user_pwnam = "some user pwnam"

        getpwnam.return_value = existing_user_pwnam

        result = passwd.add_user(username, password=password)

        self.assertEqual(result, existing_user_pwnam)
        self.assertFalse(check_output.called)
        getpwnam.assert_called_with(username)

    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrnam")
    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_adds_a_user_with_different_shell(self, check_output, getpwnam, getgrnam):
        username = "johndoe"
        password = "eodnhoj"
        shell = "/bin/zsh"
        existing_user_pwnam = KeyError("user not found")
        new_user_pwnam = "some user pwnam"

        getpwnam.side_effect = [existing_user_pwnam, new_user_pwnam]
        getgrnam.side_effect = KeyError("group not found")

        result = passwd.add_user(username, password=password, shell=shell)

        self.assertEqual(result, new_user_pwnam)
        check_output.assert_called_with(
            ["useradd", "--create-home", "--shell", shell, "--password", password, username],
            stderr=-2,
        )
        getpwnam.assert_called_with(username)

    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrnam")
    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_add_user_with_groups(self, check_output, getpwnam, getgrnam):
        username = "johndoe"
        password = "eodnhoj"
        shell = "/bin/bash"
        existing_user_pwnam = KeyError("user not found")
        new_user_pwnam = "some user pwnam"

        getpwnam.side_effect = [existing_user_pwnam, new_user_pwnam]

        result = passwd.add_user(
            username,
            password=password,
            primary_group="foo",
            secondary_groups=[
                "bar",
                "qux",
            ],
        )

        self.assertEqual(result, new_user_pwnam)
        check_output.assert_called_with(
            [
                "useradd",
                "--create-home",
                "--shell",
                shell,
                "--password",
                password,
                "-g",
                "foo",
                "-G",
                "bar,qux",
                username,
            ],
            stderr=-2,
        )
        getpwnam.assert_called_with(username)
        assert not getgrnam.called

    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_adds_a_systemuser(self, check_output, getpwnam):
        username = "johndoe"
        existing_user_pwnam = KeyError("user not found")
        new_user_pwnam = "some user pwnam"

        getpwnam.side_effect = [existing_user_pwnam, new_user_pwnam]

        result = passwd.add_user(username, system_user=True)

        self.assertEqual(result, new_user_pwnam)
        check_output.assert_called_with(["useradd", "--system", username], stderr=-2)
        getpwnam.assert_called_with(username)

    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_adds_a_systemuser_with_home_dir(self, check_output, getpwnam):
        username = "johndoe"
        existing_user_pwnam = KeyError("user not found")
        new_user_pwnam = "some user pwnam"

        getpwnam.side_effect = [existing_user_pwnam, new_user_pwnam]

        result = passwd.add_user(username, system_user=True, home_dir="/var/lib/johndoe")

        self.assertEqual(result, new_user_pwnam)
        check_output.assert_called_with(
            ["useradd", "--home", "/var/lib/johndoe", "--system", username], stderr=-2
        )
        getpwnam.assert_called_with(username)

    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwnam")
    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwuid")
    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_add_user_uid(self, check_output, getgrnam, getpwuid, getpwnam):
        user_name = "james"
        user_id = 1111
        uid_key_error = KeyError("user not found")
        getpwuid.side_effect = uid_key_error
        passwd.add_user(user_name, uid=user_id)

        check_output.assert_called_with(
            ["useradd", "--uid", str(user_id), "--system", "-g", user_name, user_name], stderr=-2
        )
        getpwnam.assert_called_with(user_name)
        getpwuid.assert_called_with(user_id)

    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrnam")
    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrgid")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_add_group_gid(self, check_output, getgrgid, getgrnam):
        group_name = "darkhorse"
        group_id = 1005
        existing_group_gid = KeyError("group not found")
        new_group_gid = 1006
        getgrgid.side_effect = [existing_group_gid, new_group_gid]

        passwd.add_group(group_name, gid=group_id)
        check_output.assert_called_with(
            ["addgroup", "--gid", str(group_id), "--group", group_name], stderr=-2
        )
        getgrgid.assert_called_with(group_id)
        getgrnam.assert_called_with(group_name)

    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwnam")
    def test_user_exists_true(self, getpwnam):
        getpwnam.side_effect = "pw info"
        self.assertTrue(passwd.user_exists("bob"))

    @patch("charms.operator_libs_linux.v0.passwd.pwd.getpwnam")
    def test_user_exists_false(self, getpwnam):
        getpwnam.side_effect = KeyError("user not found")
        self.assertFalse(passwd.user_exists("bob"))

    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrnam")
    @patch("charms.operator_libs_linux.v0.passwd.group_exists")
    @patch("charms.operator_libs_linux.v0.passwd.user_exists")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_adds_a_user_to_a_group(self, check_output, user_exists, group_exists, getgrnam):
        user_exists.return_value = True
        group_exists.return_value = True
        username = "foo"
        group = "bar"
        passwd.add_user_to_group(username, group)
        check_output.assert_called_with(["gpasswd", "-a", username, group], stderr=-2)

    @patch("charms.operator_libs_linux.v0.passwd.group_exists")
    @patch("charms.operator_libs_linux.v0.passwd.user_exists")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_adds_a_user_to_a_group_user_missing(self, check_output, user_exists, group_exists):
        user_exists.return_value = False
        group_exists.return_value = True
        username = "foo"
        group = "bar"
        with self.assertRaises(ValueError):
            passwd.add_user_to_group(username, group)
        check_output.assert_not_called()

    @patch("charms.operator_libs_linux.v0.passwd.group_exists")
    @patch("charms.operator_libs_linux.v0.passwd.user_exists")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_adds_a_user_to_a_group_group_missing(self, check_output, user_exists, group_exists):
        user_exists.return_value = True
        group_exists.return_value = False
        username = "foo"
        group = "bar"
        with self.assertRaises(ValueError):
            passwd.add_user_to_group(username, group)
        check_output.assert_not_called()

    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_add_a_group_if_it_doesnt_exist(self, check_output, getgrnam):
        group_name = "testgroup"
        existing_group_grnam = KeyError("group not found")
        new_group_grnam = "some group grnam"

        getgrnam.side_effect = [existing_group_grnam, new_group_grnam]
        result = passwd.add_group(group_name)

        self.assertEqual(result, new_group_grnam)
        check_output.assert_called_with(["addgroup", "--group", group_name], stderr=-2)
        getgrnam.assert_called_with(group_name)

    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_doesnt_add_group_if_it_already_exists(self, check_output, getgrnam):
        group_name = "testgroup"
        existing_group_grnam = "some group grnam"

        getgrnam.return_value = existing_group_grnam
        result = passwd.add_group(group_name)

        self.assertEqual(result, existing_group_grnam)
        self.assertFalse(check_output.called)
        getgrnam.assert_called_with(group_name)

    @patch("charms.operator_libs_linux.v0.passwd.grp.getgrnam")
    @patch("charms.operator_libs_linux.v0.passwd.check_output")
    def test_add_a_system_group(self, check_output, getgrnam):
        group_name = "testgroup"
        existing_group_grnam = KeyError("group not found")
        new_group_grnam = "some group grnam"

        getgrnam.side_effect = [existing_group_grnam, new_group_grnam]
        result = passwd.add_group(group_name, system_group=True)

        self.assertEqual(result, new_group_grnam)
        check_output.assert_called_with(["addgroup", "--system", group_name], stderr=-2)
        getgrnam.assert_called_with(group_name)
