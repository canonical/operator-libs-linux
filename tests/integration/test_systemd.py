#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging

from charms.operator_libs_linux.v0.systemd import (
    service_pause,
    service_reload,
    service_restart,
    service_resume,
    service_running,
    service_start,
    service_stop,
)

logger = logging.getLogger(__name__)


def test_service():
    # Cron is pre-installed in the lxc images we are using.
    assert service_running("cron")
    # Foo is made up, and should not be running.
    assert not service_running("foo")


def test_pause_and_resume():
    # Verify that we can disable and re-enable a service.
    assert service_pause("cron")
    assert not service_running("cron")
    assert service_resume("cron")
    assert service_running("cron")


def test_restart():
    # Verify that we seem to be able to restart a service.
    assert service_restart("cron")


def test_stop_and_start():
    # Verify that we can stop and start a service.
    assert service_stop("cron")
    assert not service_running("cron")
    assert service_start("cron")
    assert service_running("cron")


def test_reload():
    # Verify that we can reload services that support reload.
    assert not service_reload("cron")
    assert service_reload("apparmor")

    # The following is observed behavior. Not sure how happy I am about it.
    assert service_reload("cron", restart_on_failure=True)
