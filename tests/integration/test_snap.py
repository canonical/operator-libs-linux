#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
import re
import time
from datetime import datetime, timedelta
from subprocess import CalledProcessError, check_output, run

import pytest
from charms.operator_libs_linux.v2 import snap
from helpers import get_command_path

logger = logging.getLogger(__name__)


def test_snap_install():
    # Try by initialising the cache first, then using ensure
    try:
        cache = snap.SnapCache()
        juju = cache["juju"]
        if not juju.present:
            juju.ensure(snap.SnapState.Latest, channel="stable")
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
    hello_world = cache["hello-world"]
    if not hello_world.present:
        hello_world.ensure(snap.SnapState.Latest, channel="latest/stable")

    cache = snap.SnapCache()
    hello_world = cache["hello-world"]
    assert hello_world.channel == "latest/stable"
    hello_world.ensure(snap.SnapState.Latest, channel="latest/candidate")
    # Refresh cache
    cache = snap.SnapCache()
    hello_world = cache["hello-world"]
    assert hello_world.channel == "latest/candidate"


def test_snap_set_and_get_with_typed():
    cache = snap.SnapCache()
    lxd = cache["lxd"]
    try:
        lxd.ensure(snap.SnapState.Latest, channel="latest")
    except snap.SnapError:
        time.sleep(60)
        lxd.ensure(snap.SnapState.Latest, channel="latest")
    configs = {
        "true": True,
        "false": False,
        "null": None,
        "integer": 1,
        "float": 2.0,
        "list": [1, 2.0, True, False, None],
        "dict": {
            "true": True,
            "false": False,
            "null": None,
            "integer": 1,
            "float": 2.0,
            "list": [1, 2.0, True, False, None],
        },
        "criu.enable": "true",
        "ceph.external": "false",
    }

    lxd.set(configs, typed=True)

    assert lxd.get("true", typed=True)
    assert not lxd.get("false", typed=True)
    with pytest.raises(snap.SnapError):
        lxd.get("null", typed=True)
    assert lxd.get("integer", typed=True) == 1
    assert lxd.get("float", typed=True) == 2.0
    assert lxd.get("list", typed=True) == [1, 2.0, True, False, None]

    # Note that `"null": None` will be missing here because `key=null` will not
    # be set (because it means unset in snap). However, `key=[null]` will be
    # okay, and that's why `None` exists in "list".
    assert lxd.get("dict", typed=True) == {
        "true": True,
        "false": False,
        "integer": 1,
        "float": 2.0,
        "list": [1, 2.0, True, False, None],
    }

    assert lxd.get("dict.true", typed=True)
    assert not lxd.get("dict.false", typed=True)
    with pytest.raises(snap.SnapError):
        lxd.get("dict.null", typed=True)
    assert lxd.get("dict.integer", typed=True) == 1
    assert lxd.get("dict.float", typed=True) == 2.0
    assert lxd.get("dict.list", typed=True) == [1, 2.0, True, False, None]

    assert lxd.get("criu.enable", typed=True) == "true"
    assert lxd.get("ceph.external", typed=True) == "false"
    assert lxd.get(None, typed=True) == {
        "true": True,
        "false": False,
        "integer": 1,
        "float": 2.0,
        "list": [1, 2.0, True, False, None],
        "dict": {
            "true": True,
            "false": False,
            "integer": 1,
            "float": 2.0,
            "list": [1, 2.0, True, False, None],
        },
        "criu": {"enable": "true"},
        "ceph": {"external": "false"},
    }


def test_snap_set_and_get_untyped():
    cache = snap.SnapCache()
    lxd = cache["lxd"]
    try:
        lxd.ensure(snap.SnapState.Latest, channel="latest")
    except snap.SnapError:
        time.sleep(60)
        lxd.ensure(snap.SnapState.Latest, channel="latest")

    lxd.set({"foo": "true", "bar": True}, typed=False)
    assert lxd.get("foo", typed=False) == "true"
    assert lxd.get("bar", typed=False) == "True"


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

    # We can make the above work w/ arbitrary config.
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


def test_snap_ensure_revision():
    juju = snap.SnapCache()["juju"]

    # Verify that the snap is not installed
    juju.ensure(snap.SnapState.Available)
    assert get_command_path("juju") == ""

    # Install the snap with the revision of latest/edge
    snap_info_juju = run(
        ["snap", "info", "juju"], capture_output=True, encoding="utf-8"
    ).stdout.split("\n")

    edge_revision = None
    for line in snap_info_juju:
        match = re.search(r"3/stable.*\((\d+)\)", line)

        if match:
            edge_revision = match.group(1)
            break
    assert edge_revision is not None

    juju.ensure(snap.SnapState.Present, revision=edge_revision)

    assert get_command_path("juju") == "/snap/bin/juju"

    snap_info_juju = run(
        ["snap", "info", "juju"],
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()

    assert "installed" in snap_info_juju
    for line in snap_info_juju.split("\n"):
        if "installed" in line:
            match = re.search(r"installed.*\((\d+)\)", line)

            assert match is not None
            assert match.group(1) == edge_revision


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

    assert len(kp.logs(num_lines=15).splitlines()) >= 4


def test_snap_restart():
    cache = snap.SnapCache()
    kp = cache["kube-proxy"]
    kp.ensure(snap.SnapState.Latest, classic=True, channel="latest/stable")

    try:
        kp.restart()
    except CalledProcessError as e:
        pytest.fail(e.stderr)


def test_snap_hold_refresh():
    cache = snap.SnapCache()
    hw = cache["hello-world"]
    hw.ensure(snap.SnapState.Latest, channel="latest/stable")

    hw.hold(duration=timedelta(hours=24))
    assert hw.held


def test_snap_unhold_refresh():
    cache = snap.SnapCache()
    hw = cache["hello-world"]
    hw.ensure(snap.SnapState.Latest, channel="latest/stable")

    hw.unhold()
    assert not hw.held


def test_snap_connect():
    cache = snap.SnapCache()
    vlc = cache["vlc"]
    vlc.ensure(snap.SnapState.Latest, classic=True, channel="latest/stable")

    try:
        vlc.connect("jack1")
    except CalledProcessError as e:
        pytest.fail(e.stderr)


def test_hold_refresh():
    hold_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    snap.hold_refresh()
    result = check_output(["snap", "refresh", "--time"])
    assert f"hold: {hold_date}" in result.decode()


def test_forever_hold_refresh():
    snap.hold_refresh(forever=True)
    result = check_output(["snap", "get", "system", "refresh.hold"])
    assert "forever" in result.decode()


def test_reset_hold_refresh():
    snap.hold_refresh()
    snap.hold_refresh(0)
    result = check_output(["snap", "refresh", "--time"])
    assert "hold: " not in result.decode()


def test_alias():
    cache = snap.SnapCache()
    lxd = cache["lxd"]
    lxd.alias("lxc", "testlxc")
    result = check_output(["snap", "aliases"], text=True)
    found = any(line.split() == ["lxd.lxc", "testlxc", "manual"] for line in result.splitlines())
    assert found, result
