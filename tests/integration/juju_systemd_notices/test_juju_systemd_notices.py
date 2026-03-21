#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for juju_systemd_notices charm library."""

import logging

import jubilant
import pytest

logger = logging.getLogger(__name__)
APP_NAME = "test"
UNIT_NAME = f"{APP_NAME}/0"


@pytest.mark.abort_on_fail
@pytest.mark.order(1)
def test_service_start(juju: jubilant.Juju, test_charm) -> None:
    """Test that service_test_started event is properly handled by test charm."""
    logger.info("Deploying test charm with internal test daemon")
    juju.deploy(test_charm, app=APP_NAME, num_units=1, base="ubuntu@22.04")
    logger.info("Waiting for test daemon to start...")
    status = juju.wait(lambda status: jubilant.all_active(status, APP_NAME), timeout=1000)
    unit_status = status.apps[APP_NAME].units[UNIT_NAME]
    assert unit_status.workload_status.message == "test service running :)"


@pytest.mark.abort_on_fail
@pytest.mark.order(2)
def test_service_stop(juju: jubilant.Juju) -> None:
    """Test that service_test_stopped event is properly handled by test charm."""
    logger.info("Stopping internal test daemon")
    task = juju.run(UNIT_NAME, "stop-service")
    task.raise_on_failure()
    logger.info("Waiting for test daemon to stop...")
    status = juju.wait(lambda status: jubilant.all_blocked(status, APP_NAME), timeout=1000)
    unit_status = status.apps[APP_NAME].units[UNIT_NAME]
    assert unit_status.workload_status.message == "test service not running :("
