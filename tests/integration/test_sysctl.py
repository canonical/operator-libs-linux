#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


from pathlib import Path
from subprocess import check_output

from charms.operator_libs_linux.v0 import sysctl

EXPECTED_MERGED_RESULT = """# This config file was produced by sysctl lib v0.2
#
# This file represents the output of the sysctl lib, which can combine multiple
# configurations into a single file like.
# test1
net.ipv4.tcp_max_syn_backlog=4096
# test2
net.ipv4.tcp_window_scaling=2
"""


def test_configure():
    cfg = sysctl.Config("test1")
    cfg.configure({"net.ipv4.tcp_max_syn_backlog": "4096"})

    result = check_output(["sysctl", "net.ipv4.tcp_max_syn_backlog"])

    test_file = Path("/etc/sysctl.d/90-juju-test1")
    merged_file = Path("/etc/sysctl.d/95-juju-sysctl.conf")
    assert "net.ipv4.tcp_max_syn_backlog = 4096" in result.decode()
    assert test_file.exists()
    assert merged_file.exists()


def test_multiple_configure():
    # file from previous test still exists, so we only need to create a new one.
    cfg_2 = sysctl.Config("test2")
    cfg_2.configure({"net.ipv4.tcp_window_scaling": "2"})

    test_file_2 = Path("/etc/sysctl.d/90-juju-test2")
    merged_file = Path("/etc/sysctl.d/95-juju-sysctl.conf")
    result = check_output(
        ["sysctl", "net.ipv4.tcp_max_syn_backlog", "net.ipv4.tcp_window_scaling"]
    )
    assert (
        "net.ipv4.tcp_max_syn_backlog = 4096\nnet.ipv4.tcp_window_scaling = 2\n" in result.decode()
    )
    assert test_file_2.exists()

    with open(merged_file, "r") as f:
        assert f.read() == EXPECTED_MERGED_RESULT


def test_remove():
    cfg = sysctl.Config("test")
    cfg.remove()

    test_file = Path("/etc/sysctl.d/90-juju-test")
    assert not test_file.exists()
