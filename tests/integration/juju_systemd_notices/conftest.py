#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Configure integration tests for the juju_systemd_notices library."""

import logging
import os
import pathlib
import shutil
import sys
import time

import jubilant
import pytest

logger = logging.getLogger(__name__)

test_charm_root = pathlib.Path("tests/integration/juju_systemd_notices/notices-charm")
lib_root = pathlib.Path("lib/charms/operator_libs_linux")
systemd_path = lib_root / "v1/systemd.py"
notices_path = lib_root / "v0/juju_systemd_notices.py"


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    """Create a temporary Juju model for running tests."""
    with jubilant.temp_model() as juju:
        yield juju

        if request.session.testsfailed:
            logger.info("Collecting Juju logs...")
            time.sleep(0.5)
            log = juju.debug_log(limit=1000)
            print(log, end="", file=sys.stderr)


@pytest.fixture(scope="module", autouse=True)
def copy_machine_libs_into_test_charm():
    """Copy the systemd and juju_systemd_notices to the test charm."""
    shutil.copy(systemd_path, test_charm_root / systemd_path)
    shutil.copy(notices_path, test_charm_root / notices_path)
    yield
    (test_charm_root / systemd_path).unlink(missing_ok=True)
    (test_charm_root / notices_path).unlink(missing_ok=True)


@pytest.fixture(scope="session")
def test_charm():
    """Return the path of the charm under test."""
    if "CHARM_PATH" in os.environ:
        charm_path = pathlib.Path(os.environ["CHARM_PATH"])
        if not charm_path.exists():
            raise FileNotFoundError(f"Charm does not exist: {charm_path}")
        return charm_path
    charm_paths = list(test_charm_root.glob("*.charm"))
    if not charm_paths:
        raise FileNotFoundError(
            f"No .charm file in {test_charm_root}. "
            "Run 'charmcraft pack' first or set CHARM_PATH."
        )
    if len(charm_paths) > 1:
        path_list = ", ".join(str(p) for p in charm_paths)
        raise ValueError(f"More than one .charm file in {test_charm_root}: {path_list}")
    return charm_paths[0]
