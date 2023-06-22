#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for dnf charm library."""

import charms.operator_libs_linux.v0.dnf as dnf


def test_install_package() -> None:
    dnf.install("epel-release")
    dnf.install("slurm-slurmd", "slurm-slurmctld", "slurm-slurmdbd", "slurm-slurmrestd")
    assert dnf.fetch("epel-release").installed
    assert dnf.fetch("slurm-slurmd").installed
    assert dnf.fetch("slurm-slurmctld").installed
    assert dnf.fetch("slurm-slurmdbd").installed
    assert dnf.fetch("slurm-slurmrestd").installed


def test_query_dnf_and_package() -> None:
    assert dnf.version() == "4.14.0"
    package = dnf.fetch("slurm-slurmd")
    assert package.installed
    assert not package.available
    assert not package.absent
    assert package.name == "slurm-slurmd"
    assert package.arch == "x86_64"
    assert package.epoch is None
    assert package.version == "22.05.9"
    assert package.release == "1.el9"
    assert package.full_version == "22.05.9-1.el9"
    assert package.repo == "epel"


def test_remove_package() -> None:
    dnf.remove("slurm-slurmdbd")
    dnf.remove("slurm-slurmd", "slurm-slurmrestd", "slurm-slurmctld")
    assert dnf.fetch("slurm-slurmdbd").available
    assert dnf.fetch("slurm-slurmd").available
    assert dnf.fetch("slurm-slurmrestd").available
    assert dnf.fetch("slurm-slurmctld").available


def test_check_absent() -> None:
    bogus = dnf.fetch("nuccitheboss")
    assert not bogus.installed
    assert not bogus.available
    assert bogus.absent
    assert bogus.name == "nuccitheboss"
    assert bogus.arch is None
    assert bogus.epoch is None
    assert bogus.version is None
    assert bogus.release is None
    assert bogus.full_version is None
    assert bogus.repo is None


def test_add_repo() -> None:
    dnf.add_repo("http://mirror.stream.centos.org/9-stream/HighAvailability/x86_64/os")
    dnf.install("pacemaker")
    assert dnf.fetch("pacemaker").installed
