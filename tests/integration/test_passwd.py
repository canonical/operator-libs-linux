#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
import subprocess

from charms.operator_libs_linux.v0 import passwd
from helpers import lines_in_file

logger = logging.getLogger(__name__)


def test_add_user():
    # First check the user we're creating doesn't exist
    expected_passwd_line = "test-user-0:x:1001:1001::/home/test-user-0:/bin/sh"
    expected_group_line = "test-user-0:x:1001:"
    assert expected_group_line not in lines_in_file("/etc/group")
    assert expected_passwd_line not in lines_in_file("/etc/passwd")

    passwd.add_user(name="test-user-0")

    assert expected_group_line in lines_in_file("/etc/group")
    assert expected_passwd_line in lines_in_file("/etc/passwd")
    # clean up
    subprocess.check_output(["userdel", "test-user-0"])


# TODO: Enable this test once the feature is implemented
# def test_remove_user():
#     p = passwd.Passwd()
#     user = passwd.User(name="test-user-0", state=passwd.UserState.Present)
#     p.add_user(user)

#     expected_passwd_line = "test-user-0:x:1001:1001::/home/test-user-0:/bin/sh"
#     expected_group_line = "test-user-0:x:1001:"
#     assert expected_group_line in lines_in_file("/etc/group")
#     assert expected_passwd_line in lines_in_file("/etc/passwd")

#     passwd.Passwd.remove_user("test-user-0")
#     assert expected_group_line not in lines_in_file("/etc/group")
#     assert expected_passwd_line not in lines_in_file("/etc/passwd")


def test_add_user_with_params():
    p = passwd.Passwd()
    user = passwd.User(
        name="test-user-1", state=passwd.UserState.Present, shell="/bin/bash", group="admin"
    )
    p.add_user(user)

    expected = "test-user-1:x:1001:116::/home/test-user-1:/bin/bash"
    assert expected in lines_in_file("/etc/passwd")
    # clean up.
    # TODO: user the remove user function once implemented.
    subprocess.check_output(["userdel", "test-user-1"])


def test_add_group():
    passwd.Group(name="test-group", users=[]).add()
    expected = "test-group:x:1001:"
    assert expected in lines_in_file("/etc/group")
    # clean up
    subprocess.check_output(["groupdel", "test-group"])


def test_remove_group():
    group = passwd.Group(name="test-group", users=[])
    group.add()
    expected = "test-group:x:1001:"
    assert expected in lines_in_file("/etc/group")

    group.remove()
    assert expected not in lines_in_file("/etc/group")


def test_add_group_with_gid():
    group = passwd.Group(name="test-group-1099", users=[], gid=1099)
    group.add()
    expected = "test-group-1099:x:1099:"
    assert expected in lines_in_file("/etc/group")
    group.remove()
