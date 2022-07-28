#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
from datetime import datetime, timedelta
from subprocess import CalledProcessError, check_output

import pytest
from charms.operator_libs_linux.v1 import snap
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
    cache = snap.SnapCache()
    lxd = cache["lxd"]
    lxd.ensure(snap.SnapState.Latest, channel="latest")

    lxd.set({"ceph.external": "false", "criu.enable": "false"})

    assert lxd.get("ceph.external") == "false"
    assert lxd.get("criu.enable") == "false"

    lxd.set({"ceph.external": "true", "criu.enable": "true"})

    assert lxd.get("ceph.external") == "true"
    assert lxd.get("criu.enable") == "true"


def test_unset_key_raises_snap_error():
    cache = snap.SnapCache()
    lxd = cache["lxd"]
    lxd.ensure(snap.SnapState.Latest, channel="latest")

    # Verify that the correct exception gets raised in the case of an unset key.
    key = "keythatdoesntexist01"
    try:
        lxd.get(key)
    except snap.SnapError:
        pass
    else:
        logger.error("Getting an unset key should result in a SnapError.")

    # We can make the above work w/ abitrary config.
    lxd.set({key: "true"})
    assert lxd.get(key) == "true"


def test_snap_ensure():
    cache = snap.SnapCache()
    charmcraft = cache["charmcraft"]

    # Verify that we can run ensure multiple times in a row without delays.
    charmcraft.ensure(snap.SnapState.Latest, channel="latest/stable")
    charmcraft.ensure(snap.SnapState.Latest, channel="latest/stable")
    charmcraft.ensure(snap.SnapState.Latest, channel="latest/stable")


def test_new_snap_ensure():
    vlc = snap.SnapCache()["vlc"]
    vlc.ensure(snap.SnapState.Latest, channel="edge")


def test_snap_start():
    cache = snap.SnapCache()
    kp = cache["kube-proxy"]
    kp.ensure(snap.SnapState.Latest, classic=True, channel="latest/stable")

    assert kp.services
    kp.start()
    assert kp.services["daemon"]["active"] is not False

    with pytest.raises(snap.SnapError):
        kp.start(["foobar"])


def test_snap_stop():
    cache = snap.SnapCache()
    kp = cache["kube-proxy"]
    kp.ensure(snap.SnapState.Latest, classic=True, channel="latest/stable")

    kp.stop(["daemon"], disable=True)
    assert kp.services["daemon"]["active"] is False
    assert kp.services["daemon"]["enabled"] is False


def test_snap_logs():
    cache = snap.SnapCache()
    kp = cache["kube-proxy"]
    kp.ensure(snap.SnapState.Latest, classic=True, channel="latest/stable")

    # Terrible means of populating logs
    kp.start()
    kp.stop()
    kp.start()
    kp.stop()

    assert len(kp.logs(num_lines=15).splitlines()) == 15


def test_snap_restart():
    cache = snap.SnapCache()
    kp = cache["kube-proxy"]
    kp.ensure(snap.SnapState.Latest, classic=True, channel="latest/stable")

    try:
        kp.restart()
    except CalledProcessError as e:
        pytest.fail(e.stderr)


def test_hold_refresh():
    hold_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    snap.hold_refresh()
    result = check_output(["snap", "refresh", "--time"])
    assert f"hold: {hold_date}" in result.decode()


def test_reset_hold_refresh():
    snap.hold_refresh()
    snap.hold_refresh(0)
    result = check_output(["snap", "refresh", "--time"])
    assert "hold: " not in result.decode()
