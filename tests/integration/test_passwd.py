#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging

from charms.operator_libs_linux.v0 import passwd
from helpers import lines_in_file

logger = logging.getLogger(__name__)


def test_add_user():
    # First check the user we're creating doesn't exist
    assert passwd.user_exists("test-user-0") is None

    u = passwd.add_user(username="test-user-0")

    expected_passwd_line = "{}:x:{}:{}::{}:{}".format(
        u.pw_name, u.pw_uid, u.pw_gid, u.pw_dir, u.pw_shell
    )
    expected_group_line = "{}:x:{}:".format(u.pw_name, u.pw_gid)

    assert passwd.user_exists("test-user-0") is not None
    assert expected_group_line in lines_in_file("/etc/group")
    assert expected_passwd_line in lines_in_file("/etc/passwd")
    # clean up
    passwd.remove_user("test-user-0")


def test_remove_user():
    u = passwd.add_user(username="test-user-0")
    assert passwd.user_exists("test-user-0") is not None

    passwd.remove_user("test-user-0")

    expected_passwd_line = "{}:x:{}:{}::{}:{}".format(
        u.pw_name, u.pw_uid, u.pw_gid, u.pw_dir, u.pw_shell
    )
    expected_group_line = "{}:x:{}:".format(u.pw_name, u.pw_gid)

    assert passwd.user_exists("test-user-0") is None
    assert expected_group_line not in lines_in_file("/etc/group")
    assert expected_passwd_line not in lines_in_file("/etc/passwd")


def test_add_user_with_params():
    u = passwd.add_user(username="test-user-1", shell="/bin/bash", primary_group="admin")
    expected = "{}:x:{}:{}::{}:{}".format(u.pw_name, u.pw_uid, u.pw_gid, u.pw_dir, u.pw_shell)

    assert expected in lines_in_file("/etc/passwd")

    passwd.remove_user("test-user-1")


def test_add_group():
    assert passwd.group_exists("test-group") is None

    g = passwd.add_group(group_name="test-group")

    expected = "{}:x:{}:".format(g.gr_name, g.gr_gid)

    assert passwd.group_exists("test-group") is not None
    assert expected in lines_in_file("/etc/group")

    passwd.remove_group("test-group")


def test_remove_group():
    g = passwd.add_group(group_name="test-group")
    assert passwd.group_exists("test-group") is not None

    expected = "{}:x:{}:".format(g.gr_name, g.gr_gid)
    assert expected in lines_in_file("/etc/group")

    passwd.remove_group("test-group")
    assert passwd.group_exists("test-group") is None
    assert expected not in lines_in_file("/etc/group")


def test_add_group_with_gid():
    assert passwd.group_exists("test-group") is None

    passwd.add_group(group_name="test-group", gid=1099)

    expected = "test-group:x:1099:"

    assert passwd.group_exists("test-group") is not None
    assert expected in lines_in_file("/etc/group")

    passwd.remove_group("test-group")
