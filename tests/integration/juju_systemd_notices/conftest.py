#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Configure integration tests for the juju_systemd_notices library."""

import shutil
from pathlib import Path

import pytest
from pytest_operator.plugin import OpsTest

test_charm_root = Path("tests/integration/juju_systemd_notices/notices-charm")
lib_root = Path("lib/charms/operator_libs_linux")
systemd_path = lib_root / "v1/systemd.py"
notices_path = lib_root / "v0/juju_systemd_notices.py"


@pytest.fixture(scope="module", autouse=True)
def copy_machine_libs_into_test_charm(ops_test: OpsTest):
    """Copy the systemd and juju_systemd_notices to the test charm."""
    shutil.copy(systemd_path, test_charm_root / systemd_path)
    shutil.copy(notices_path, test_charm_root / notices_path)


@pytest.fixture(scope="module")
async def test_charm(ops_test: OpsTest):
    return await ops_test.build_charm("tests/integration/juju_systemd_notices/notices-charm")


def pytest_sessionfinish(session, exitstatus):
    """Clean up integration test after it has completed."""
    (test_charm_root / systemd_path).unlink(missing_ok=True)
    (test_charm_root / notices_path).unlink(missing_ok=True)
