#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for dnf charm library."""

import pathlib
import unittest

from cleantest.control import Env
from cleantest.data import File
from cleantest.provider import LXDArchon, lxd


@lxd.target("test-ubuntu-jammy")
def fail_on_ubuntu() -> None:
    import sys

    try:
        from charms.operator_libs_linux.v0.dnf import dnf  # noqa F401

        sys.exit(1)
    except ImportError:
        sys.exit(0)


@lxd.target("test-alma-9")
def install_package() -> None:
    import sys

    try:
        from charms.operator_libs_linux.v0.dnf import dnf

        dnf.update()
        dnf.install("epel-release")
        dnf.install("slurm-slurmd", "slurm-slurmctld", "slurm-slurmdbd", "slurm-slurmrestd")
        assert dnf["epel-release"].installed is True
        assert dnf["slurm-slurmd"].installed is True
        assert dnf["slurm-slurmctld"].installed is True
        assert dnf["slurm-slurmdbd"].installed is True
        assert dnf["slurm-slurmrestd"].installed is True
        sys.exit(0)
    except (ImportError, AssertionError):
        sys.exit(1)


@lxd.target("test-alma-9")
def query_dnf_and_package() -> None:
    import sys

    try:
        from charms.operator_libs_linux.v0.dnf import dnf

        assert dnf.version == "4.12.0"
        package = dnf["slurm-slurmd"]
        assert package.installed is True
        assert package.available is False
        assert package.absent is False
        assert package.name == "slurm-slurmd"
        assert package.arch == "x86_64"
        assert package.epoch is None
        assert package.version == "22.05.6"
        assert package.release == "3.el9"
        assert package.fullversion == "22.05.6-3.el9"
        assert package.repo == "epel"
        sys.exit(0)
    except (ImportError, AssertionError):
        sys.exit(1)


@lxd.target("test-alma-9")
def remove_package() -> None:
    import sys

    try:
        from charms.operator_libs_linux.v0.dnf import dnf

        dnf.remove("slurm-slurmdbd")
        dnf.purge("slurm-slurmrestd")
        assert dnf["slurm-slurmdbd"].available is True
        assert dnf["slurm-slurmrestd"].available is True
        sys.exit(0)
    except (ImportError, AssertionError):
        sys.exit(1)


@lxd.target("test-alma-9")
def check_absent() -> None:
    import sys

    try:
        from charms.operator_libs_linux.v0.dnf import dnf

        bogus = dnf["nuccitheboss"]
        assert bogus.installed is False
        assert bogus.available is False
        assert bogus.absent is True
        assert bogus.name == "nuccitheboss"
        assert bogus.arch is None
        assert bogus.epoch is None
        assert bogus.version is None
        assert bogus.release is None
        assert bogus.fullversion is None
        assert bogus.repo is None
    except (ImportError, AssertionError):
        sys.exit(1)


@lxd.target("test-alma-9")
def add_repo() -> None:
    import sys

    try:
        from charms.operator_libs_linux.v0.dnf import dnf

        dnf.add_repo("https://repo.almalinux.org/almalinux/9/HighAvailability/x86_64/os")
        dnf.install("pacemaker")
        assert dnf["pacemaker"].installed is True
        sys.exit(0)
    except (ImportError, AssertionError):
        sys.exit(1)


class TestDNF(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        archon = LXDArchon()
        archon.add("test-ubuntu-jammy", image="ubuntu-jammy-amd64")
        archon.add("test-alma-9", image="almalinux-9-amd64")
        charm_library = (
            pathlib.Path(__file__).parent.parent.parent
            / "lib"
            / "charms"
            / "operator_libs_linux"
            / "v0"
            / "dnf.py"
        )
        charm_lib_path = "/root/lib/charms/operator_libs_linux/v0"
        archon.execute(["test-ubuntu-jammy", "test-alma-9"], f"mkdir -p {charm_lib_path}")
        archon.push("test-ubuntu-jammy", data_obj=File(charm_library, f"{charm_lib_path}/dnf.py"))
        archon.push("test-alma-9", data_obj=File(charm_library, f"{charm_lib_path}/dnf.py"))
        Env().add({"PYTHONPATH": "/root/lib"})

    def test_fail_on_ubuntu(self) -> None:
        for name, result in fail_on_ubuntu():
            self.assertEqual(result.exit_code, 0)

    def test_install_package(self) -> None:
        for name, result in install_package():
            self.assertEqual(result.exit_code, 0)

    def test_query_dnf(self) -> None:
        for name, result in query_dnf_and_package():
            self.assertEqual(result.exit_code, 0)

    def test_remove_package(self) -> None:
        for name, result in query_dnf_and_package():
            self.assertEqual(result.exit_code, 0)

    def test_check_absent(self) -> None:
        for name, result in check_absent():
            self.assertEqual(result.exit_code, 0)

    def test_add_repo(self) -> None:
        for name, result in add_repo():
            self.assertEqual(result.exit_code, 0)

    @classmethod
    def tearDownClass(cls) -> None:
        LXDArchon().destroy()
