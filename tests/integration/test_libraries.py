#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
import shutil
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    # Copy the libs into the test-charm
    shutil.copytree("lib", "tests/integration/test-charm/lib")
    # Build the charm
    charm = await ops_test.build_charm("tests/integration/test-charm")
    # Remove the libs from the test-charm dir again
    shutil.rmtree("tests/integration/test-charm/lib")
    await ops_test.model.deploy(charm, application_name="tester")
    await ops_test.model.wait_for_idle(apps=["tester"], status="active", timeout=1000)
    assert ops_test.model.applications["tester"].units[0].workload_status == "active"


@pytest.mark.abort_on_fail
async def test_apt_install(ops_test: OpsTest):
    unit = ops_test.model.applications["tester"].units[0]

    action = await unit.run_action("apt-install")
    action = await action.wait()

    assert action.results["Code"] == "0"
    assert action.results["installed"] == "['/usr/bin/zsh', '/usr/bin/cfssl', '/usr/bin/jq']"


@pytest.mark.abort_on_fail
async def test_apt_install_external_repo(ops_test: OpsTest):
    unit = ops_test.model.applications["tester"].units[0]

    action = await unit.run_action("apt-install-external-repo")
    action = await action.wait()

    assert action.results["Code"] == "0"
    assert action.results["installed"] == "['/usr/bin/terraform']"


@pytest.mark.abort_on_fail
async def test_snap_install(ops_test: OpsTest):
    unit = ops_test.model.applications["tester"].units[0]

    action = await unit.run_action("snap-install")
    action = await action.wait()

    assert action.results["Code"] == "0"
    assert action.results["installed"] == "['/snap/bin/juju']"


@pytest.mark.abort_on_fail
async def test_snap_install_bare(ops_test: OpsTest):
    unit = ops_test.model.applications["tester"].units[0]

    action = await unit.run_action("snap-install-bare")
    action = await action.wait()

    assert action.results["Code"] == "0"
    assert action.results["installed"] == "['/snap/bin/charmcraft']"


@pytest.mark.abort_on_fail
async def test_add_user(ops_test: OpsTest):
    unit = ops_test.model.applications["tester"].units[0]

    action = await unit.run_action("add-user")
    action = await action.wait()

    assert action.results["Code"] == "0"
    assert action.results["created-user"] == "test-user-0:x:1001:1001::/home/test-user-0:/bin/sh"
    assert action.results["created-group"] == "test-user-0:x:1001:"


@pytest.mark.abort_on_fail
async def test_add_user_with_params(ops_test: OpsTest):
    unit = ops_test.model.applications["tester"].units[0]

    action = await unit.run_action("add-user-with-params")
    action = await action.wait()

    assert action.results["Code"] == "0"
    assert action.results["created-user"] == "test-user-1:x:1002:116::/home/test-user-1:/bin/bash"


@pytest.mark.abort_on_fail
async def test_add_group(ops_test: OpsTest):
    unit = ops_test.model.applications["tester"].units[0]

    action = await unit.run_action("add-group")
    action = await action.wait()

    assert action.results["Code"] == "0"
    assert action.results["created-group"] == "test-group:x:1002:"


@pytest.mark.abort_on_fail
async def test_add_group_with_gid(ops_test: OpsTest):
    unit = ops_test.model.applications["tester"].units[0]

    action = await unit.run_action("add-group-with-gid")
    action = await action.wait()

    assert action.results["Code"] == "0"
    assert action.results["created-group"] == "test-group-1099:x:1099:"


@pytest.mark.abort_on_fail
async def test_remove_group(ops_test: OpsTest):
    unit = ops_test.model.applications["tester"].units[0]

    action = await unit.run_action("remove-group")
    action = await action.wait()

    assert action.results["Code"] == "0"
    assert action.results["last-group"] != "test-group-1099:x:1099:"
