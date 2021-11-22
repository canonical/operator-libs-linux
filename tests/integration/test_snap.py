#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging

from charms.operator_libs_linux.v0 import snap
from helpers import get_command_path

logger = logging.getLogger(__name__)


def test_snap_install():
    # Try by initialising the cache first, then using ensure
    try:
        cache = snap.SnapCache()
        juju = cache["juju"]
        if not juju.present:
            juju.ensure(snap.SnapState.Latest, classic="True", channel="stable")
    except snap.SnapError as e:
        logger.error("An exception occurred when installing Juju. Reason: {}".format(e.message))

    assert get_command_path("juju") == "/snap/bin/juju"


def test_snap_install_bare():
    snap.add(["charmcraft"], state=snap.SnapState.Latest, classic=True, channel="candidate")
    assert get_command_path("charmcraft") == "/snap/bin/charmcraft"


def test_snap_remove():
    # First ensure that charmcraft is installed (it might be if this is run after the install test)
    cache = snap.SnapCache()
    charmcraft = cache["charmcraft"]
    if not charmcraft.present:
        charmcraft.ensure(snap.SnapState.Latest, classic="True", channel="candidate")

    assert get_command_path("charmcraft") == "/snap/bin/charmcraft"

    snap.remove("charmcraft")
    assert get_command_path("charmcraft") == ""


def test_snap_refresh():
    cache = snap.SnapCache()
    lxd = cache["lxd"]
    lxd.ensure(snap.SnapState.Latest, classic=False, channel="latest/candidate", cohort="+")


def test_snap_set():
    lxd = snap.ensure(["lxd"], snap.SnapState.Latest, channel="latest/stable")

    assert lxd.get("ceph.external") == "false"
    assert lxd.get("criu.enable") == "false"

    lxd.set({"ceph.external": "true", "criu.enable": "true"})

    assert lxd.get("ceph.external") == "true"
    assert lxd.get("criu.enable") == "true"
