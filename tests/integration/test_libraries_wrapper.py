#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

"""A simple test wrapper for the 'test-charm'.

This wrapper builds and deploys the 'tester' charm, then invokes each of the defined actions in the
order in which they're defined.
"""

from pathlib import Path
from shutil import copytree, rmtree

from pytest import mark
from pytest_operator.plugin import OpsTest
from yaml import safe_load as load_yaml

CHARM_PATH = Path("tests/integration/test-charm")
ACTIONS = load_yaml((Path(CHARM_PATH) / "actions.yaml").read_text())
APP = "tester"


@mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the test charm with libs and deploy into the model."""
    # Copy the libs into the test-charm
    copytree("lib", CHARM_PATH / "lib")
    # Build the charm
    charm = await ops_test.build_charm(CHARM_PATH)
    # Remove the libs from the test-charm dir again
    rmtree(CHARM_PATH / "lib")
    # Deploy the charm and wait for it to be in active/idle state
    await ops_test.model.deploy(charm, application_name=APP)
    await ops_test.model.wait_for_idle(apps=[APP], status="active", timeout=1000)


@mark.abort_on_fail
@mark.parametrize("action_name", ACTIONS.keys())
async def test_action(ops_test, action_name):
    """For each defined action, run the action and assert that it completed successfully."""
    action = await ops_test.model.applications[APP].units[0].run_action(action_name)
    action = await action.wait()
    assert action.results["Code"] == "0"
