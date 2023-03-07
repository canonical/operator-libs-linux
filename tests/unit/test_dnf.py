#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for dnf charm library; test dnf without installing on an RPM-based instance."""

import subprocess
import unittest
from unittest.mock import patch

import charms.operator_libs_linux.v0.dnf as dnf

example_version_output = """
4.14.0
  Installed: dnf-0:4.14.0-4.el9.noarch at Mon 06 Mar 2023 03:55:24 PM GMT
  Built    : builder@centos.org at Fri 06 Jan 2023 02:23:17 PM GMT

  Installed: rpm-0:4.16.1.3-22.el9.x86_64 at Mon 06 Mar 2023 03:55:23 PM GMT
  Built    : builder@centos.org at Mon 19 Dec 2022 11:57:50 PM GMT
""".strip(
    "\n"
)

example_installed_output = """
Installed Packages
NetworkManager.x86_64 1:1.42.2-1.el9 @baseos
""".strip(
    "\n"
)

example_available_output = """
Available Packages
slurm-slurmd.x86_64 22.05.6-3.el9 epel
""".strip(
    "\n"
)

example_bad_state_output = """
Obsolete Packages
yowzah yowzah yowzah
""".strip(
    "\n"
)

example_bad_version_output = """
Available Packages
slurm-slurmd.x86_64 yowzah epel
""".strip(
    "\n"
)


class TestDNF(unittest.TestCase):
    @patch("shutil.which", return_value=True)
    def test_dnf_installed(self, _):
        self.assertTrue(dnf.installed())

    @patch("shutil.which", return_value=None)
    @patch(
        "subprocess.run",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'dnf'"),
    )
    def test_dnf_not_installed(self, *_):
        self.assertFalse(dnf.installed())
        with self.assertRaises(dnf.Error):
            dnf.upgrade()

    @patch("charms.operator_libs_linux.v0.dnf._dnf", return_value=example_version_output)
    def test_dnf_version(self, _):
        self.assertEqual("4.14.0", dnf.version())

    @patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(
            "dnf upgrade bogus", returncode=0, stdout="Success!"
        ),
    )
    def test_upgrade(self, _):
        dnf.upgrade()
        dnf.upgrade("slurm-slurmd")

    @patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(
            "dnf install bogus", returncode=0, stdout="Success!"
        ),
    )
    def test_install(self, _):
        dnf.install("slurm-slurmd")

    def test_install_invalid_input(self):
        with self.assertRaises(TypeError):
            dnf.install()

    @patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(
            "dnf remove bogus", returncode=0, stdout="Success!"
        ),
    )
    def test_remove(self, _):
        dnf.remove("slurm-slurmd")

    def test_remove_invalid_input(self):
        with self.assertRaises(TypeError):
            dnf.remove()

    @patch("charms.operator_libs_linux.v0.dnf._dnf", return_value=example_installed_output)
    def test_fetch_installed(self, _):
        x = dnf.fetch("NetworkManager")
        self.assertTrue(x.installed)
        self.assertFalse(x.available)
        self.assertFalse(x.absent)
        self.assertEqual(x.name, "NetworkManager")
        self.assertEqual(x.arch, "x86_64")
        self.assertEqual(x.epoch, "1")
        self.assertEqual(x.version, "1.42.2")
        self.assertEqual(x.release, "1.el9")
        self.assertEqual(x.full_version, "1:1.42.2-1.el9")
        self.assertEqual(x.repo, "baseos")

    @patch("charms.operator_libs_linux.v0.dnf._dnf", return_value=example_available_output)
    def test_fetch_available(self, _):
        x = dnf.fetch("slurm-slurmd")
        self.assertFalse(x.installed)
        self.assertTrue(x.available)
        self.assertFalse(x.absent)
        self.assertEqual(x.name, "slurm-slurmd")
        self.assertEqual(x.arch, "x86_64")
        self.assertIsNone(x.epoch)
        self.assertEqual(x.version, "22.05.6")
        self.assertEqual(x.release, "3.el9")
        self.assertEqual(x.full_version, "22.05.6-3.el9")
        self.assertEqual(x.repo, "epel")

    @patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            1, "dnf list -q nuccitheboss", stderr="Error: No matching Packages to list"
        ),
    )
    def test_fetch_absent(self, _):
        x = dnf.fetch("nuccitheboss")
        self.assertFalse(x.installed)
        self.assertFalse(x.available)
        self.assertTrue(x.absent)
        self.assertEqual(x.name, "nuccitheboss")
        self.assertIsNone(x.arch)
        self.assertIsNone(x.epoch)
        self.assertIsNone(x.version)
        self.assertIsNone(x.release)
        self.assertIsNone(x.full_version)
        self.assertIsNone(x.repo)

    @patch("charms.operator_libs_linux.v0.dnf._dnf", return_value=example_bad_state_output)
    def test_fetch_bad_state(self, _):
        self.assertTrue(dnf.fetch("yowzah").absent)

    @patch("charms.operator_libs_linux.v0.dnf._dnf", return_value=example_bad_version_output)
    def test_fetch_bad_version(self, _):
        self.assertTrue(dnf.fetch("yowzah").absent)
