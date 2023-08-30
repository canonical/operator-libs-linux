#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for juju_systemd_notices charm library."""

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)
APP_NAME = "test"
UNIT_NAME = f"{APP_NAME}/0"


@pytest.mark.abort_on_fail
@pytest.mark.order(1)
async def test_service_start(ops_test: OpsTest, test_charm) -> None:
    """Test that service_test_started event is properly handled by test charm."""
    logger.info("Deploying test charm with internal test daemon")
    await asyncio.gather(
        ops_test.model.deploy(
            str(await test_charm), application_name=APP_NAME, num_units=1, base="ubuntu@22.04"
        )
    )
    logger.info("Waiting for test daemon to start...")
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=1000)
        assert (
            ops_test.model.units.get(UNIT_NAME).workload_status_message
            == "test service running :)"
        )


@pytest.mark.abort_on_fail
@pytest.mark.order(2)
async def test_service_stop(ops_test: OpsTest) -> None:
    """Test that service_test_stopped event is properly handled by test charm."""
    logger.info("Stopping internal test daemon")
    action = await ops_test.model.units.get(UNIT_NAME).run_action("stop-service")
    await action.wait()
    logger.info("Waiting for test daemon to stop...")
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=1000)
        assert (
            ops_test.model.units.get(UNIT_NAME).workload_status_message
            == "test service not running :("
        )
