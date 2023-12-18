# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import subprocess
import unittest
from unittest.mock import patch

from charms.operator_libs_linux.v0 import apt

dpkg_output_zsh = """Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name                                 Version                                                                   Architecture Description
+++-====================================-=========================================================================-============-===============================================================================
ii  zsh                                  5.8-3ubuntu1                                                              amd64        shell with lots of features
"""

dpkg_output_vim = """Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name                                 Version                                                                   Architecture Description
+++-====================================-=========================================================================-============-===============================================================================
ii  vim                           2:8.1.2269-1ubuntu5                                                       amd64          Vi IMproved - Common files
"""

dpkg_output_all_arch = """Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name                                 Version                                                                   Architecture Description
+++-====================================-=========================================================================-============-===============================================================================
ii  postgresql                           12+214ubuntu0.1                                                           all         object-relational SQL database (supported version)
"""

dpkg_output_multi_arch = """Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name                                 Version                                                                   Architecture Description
+++-====================================-=========================================================================-============-===============================================================================
ii  vim                           2:8.1.2269-1ubuntu5                                                       amd64          Vi IMproved - Common files
ii  vim                           2:8.1.2269-1ubuntu5                                                       i386          Vi IMproved - Common files
"""

dpkg_output_not_installed = """Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name                              Version               Architecture          Description
+++-=================================-=====================-=====================-========================================================================
rc  ubuntu-advantage-tools            27.2.2~16.04.1        amd64                 management tools for Ubuntu Advantage
"""

apt_cache_mocktester = """
Package: mocktester
Architecture: amd64
Version: 1:1.2.3-4
Priority: optional
Section: test
Origin: Ubuntu
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Original-Maintainer: Debian GNOME Maintainers <pkg-gnome-maintainers@lists.alioth.debian.org>
Bugs: https://bugs.launchpad.net/ubuntu/+filebug
Installed-Size: 1234
Depends: vim-common
Recommends: zsh
Suggests: foobar
Filename: pool/main/m/mocktester/mocktester_1:1.2.3-4_amd64.deb
Size: 65536
MD5sum: a87e414ad5aede7c820ce4c4e6bc7fa9
SHA1: b21d6ce47cb471c73fb4ec07a24c6f4e56fd19fc
SHA256: 89e7d5f61a0e3d32ef9aebd4b16e61840cd97e10196dfa186b06b6cde2f900a2
Homepage: https://wiki.gnome.org/Apps/MockTester
Description: Testing Package
Task: ubuntu-desktop
Description-md5: e7f99df3aa92cf870d335784e155ec33
"""

apt_cache_mocktester_all_arch = """
Package: mocktester
Architecture: all
Version: 1:1.2.3-4
Priority: optional
Section: test
Origin: Ubuntu
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Original-Maintainer: Debian GNOME Maintainers <pkg-gnome-maintainers@lists.alioth.debian.org>
Bugs: https://bugs.launchpad.net/ubuntu/+filebug
Installed-Size: 1234
Depends: vim-common
Recommends: zsh
Suggests: foobar
Filename: pool/main/m/mocktester/mocktester_1:1.2.3-4_amd64.deb
Size: 65536
MD5sum: a87e414ad5aede7c820ce4c4e6bc7fa9
SHA1: b21d6ce47cb471c73fb4ec07a24c6f4e56fd19fc
SHA256: 89e7d5f61a0e3d32ef9aebd4b16e61840cd97e10196dfa186b06b6cde2f900a2
Homepage: https://wiki.gnome.org/Apps/MockTester
Description: Testing Package
Task: ubuntu-desktop
Description-md5: e7f99df3aa92cf870d335784e155ec33
"""

apt_cache_mocktester_multi = """
Package: mocktester
Architecture: amd64
Version: 1:1.2.3-4
Priority: optional
Section: test
Origin: Ubuntu
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Original-Maintainer: Debian GNOME Maintainers <pkg-gnome-maintainers@lists.alioth.debian.org>
Bugs: https://bugs.launchpad.net/ubuntu/+filebug
Installed-Size: 1234
Depends: vim-common
Recommends: zsh
Suggests: foobar
Filename: pool/main/m/mocktester/mocktester_1:1.2.3-4_amd64.deb
Size: 65536
MD5sum: a87e414ad5aede7c820ce4c4e6bc7fa9
SHA1: b21d6ce47cb471c73fb4ec07a24c6f4e56fd19fc
SHA256: 89e7d5f61a0e3d32ef9aebd4b16e61840cd97e10196dfa186b06b6cde2f900a2
Homepage: https://wiki.gnome.org/Apps/MockTester
Description: Testing Package
Task: ubuntu-desktop
Description-md5: e7f99df3aa92cf870d335784e155ec33

Package: mocktester
Architecture: i386
Version: 1:1.2.3-4
Priority: optional
Section: test
Origin: Ubuntu
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Original-Maintainer: Debian GNOME Maintainers <pkg-gnome-maintainers@lists.alioth.debian.org>
Bugs: https://bugs.launchpad.net/ubuntu/+filebug
Installed-Size: 1234
Depends: vim-common
Recommends: zsh
Suggests: foobar
Filename: pool/main/m/mocktester/mocktester_1:1.2.3-4_amd64.deb
Size: 65536
MD5sum: a87e414ad5aede7c820ce4c4e6bc7fa9
SHA1: b21d6ce47cb471c73fb4ec07a24c6f4e56fd19fc
SHA256: 89e7d5f61a0e3d32ef9aebd4b16e61840cd97e10196dfa186b06b6cde2f900a2
Homepage: https://wiki.gnome.org/Apps/MockTester
Description: Testing Package
Task: ubuntu-desktop
Description-md5: e7f99df3aa92cf870d335784e155ec33
"""

apt_cache_aisleriot = """
Package: aisleriot
Architecture: amd64
Version: 1:3.22.9-1
Priority: optional
Section: games
Origin: Ubuntu
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Original-Maintainer: Debian GNOME Maintainers <pkg-gnome-maintainers@lists.alioth.debian.org>
Bugs: https://bugs.launchpad.net/ubuntu/+filebug
Installed-Size: 8800
Depends: dconf-gsettings-backend | gsettings-backend, guile-2.2-libs, libatk1.0-0 (>= 1.12.4), libc6 (>= 2.14), libcairo2 (>= 1.10.0), libcanberra-gtk3-0 (>= 0.25), libcanberra0 (>= 0.2), libgdk-pixbuf2.0-0 (>= 2.22.0), libglib2.0-0 (>= 2
.37.3), libgtk-3-0 (>= 3.19.12), librsvg2-2 (>= 2.32.0)
Recommends: yelp
Suggests: gnome-cards-data
Filename: pool/main/a/aisleriot/aisleriot_3.22.9-1_amd64.deb
Size: 843864
MD5sum: a87e414ad5aede7c820ce4c4e6bc7fa9
SHA1: b21d6ce47cb471c73fb4ec07a24c6f4e56fd19fc
SHA256: 89e7d5f61a0e3d32ef9aebd4b16e61840cd97e10196dfa186b06b6cde2f900a2
Homepage: https://wiki.gnome.org/Apps/Aisleriot
Description: GNOME solitaire card game collection
Task: ubuntu-desktop, ubuntukylin-desktop, ubuntu-budgie-desktop
Description-md5: e7f99df3aa92cf870d335784e155ec33
"""

apt_cache_freeipmi_tools = """
Package: freeipmi-tools
Architecture: amd64
Version: 1.6.9-2~bpo20.04.1
Priority: extra
Section: admin
Source: freeipmi
Origin: Ubuntu
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Original-Maintainer: Fabio Fantoni <fantonifabio@tiscali.it>
Bugs: https://bugs.launchpad.net/ubuntu/+filebug
Installed-Size: 3102
Depends: freeipmi-common (= 1.6.9-2~bpo20.04.1), libc6 (>= 2.15), libfreeipmi17 (>= 1.6.2), libipmiconsole2 (>= 1.4.4), libipmidetect0 (>= 1.1.5)
Suggests: freeipmi-bmc-watchdog, freeipmi-ipmidetect
Filename: pool/main/f/freeipmi/freeipmi-tools_1.6.9-2~bpo20.04.1_amd64.deb
Size: 637216
MD5sum: fa4105fb6b0fb48969d56f005c7d32e8
SHA1: 4625f8601a3af2e787389a30b7c5b8027c908cad
SHA256: 247667a2835c5e775a9f68ec12e27f4a01c30dfd6a6306c29f10a3b52a255947
SHA512: b553c00327ec3304a0249ba238bbbe226fd293af6f3fc5aeb52b7ee3f90a8216d316e34ea4e8c69b9781beb9a746fc210fee34186d96202251439c33302b24db
Homepage: https://www.gnu.org/software/freeipmi/
Description-en: GNU implementation of the IPMI protocol - tools
 FreeIPMI is a collection of Intelligent Platform Management IPMI
 system software. It provides in-band and out-of-band software and a
 development library conforming to the Intelligent Platform Management
 Interface (IPMI v1.5 and v2.0) standards.
 .
 This package contains assorted IPMI-related tools:
  * bmc-config - configure BMC values
  * bmc-info - display BMC information
  * ipmi-chassis - IPMI chassis management utility
  * ipmi-fru - display FRU information
  * ipmi-locate - IPMI probing utility
  * ipmi-oem - IPMI OEM utility
  * ipmi-pet - decode Platform Event Traps
  * ipmi-raw - IPMI raw communication utility
  * ipmi-sel - display SEL entries
  * ipmi-sensors - display IPMI sensor information
  * ipmi-sensors-config - configure sensors
  * ipmiconsole - IPMI console utility
  * ipmiping - send IPMI Get Authentication Capability request
  * ipmipower - IPMI power control utility
  * pef-config - configure PEF values
  * rmcpping - send RMCP Ping to network hosts
Description-md5: 6752c6921b38f7d4192531a8ab33783c


Package: freeipmi-tools
Architecture: amd64
Version: 1.6.4-3ubuntu1.1
Priority: extra
Section: admin
Source: freeipmi
Origin: Ubuntu
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Original-Maintainer: Bernd Zeimetz <bzed@debian.org>
Bugs: https://bugs.launchpad.net/ubuntu/+filebug
Installed-Size: 3099
Depends: libc6 (>= 2.15), libfreeipmi17 (>= 1.6.2), libipmiconsole2 (>= 1.4.4), libipmidetect0 (>= 1.1.5), freeipmi-common (= 1.6.4-3ubuntu1.1)
Suggests: freeipmi-ipmidetect, freeipmi-bmc-watchdog
Filename: pool/main/f/freeipmi/freeipmi-tools_1.6.4-3ubuntu1.1_amd64.deb
Size: 636384
MD5sum: bc7c1ec3484d07d3627ba92bb0300693
SHA1: b5851b2160d5139d141e3c1b29b946f6fd895871
SHA256: 6d0a643fcb62404b17d7574baf854b9b39443a2f0067c2076f5f663437d39968
SHA512: 8f89796c86a8a410c71996d8fb229293492c949a664476e0fa63fd3fe7b1523a3174997172fe82f6eed6fb59c0a4fde221273d6149b45d4e18da7e99faed02d6
Homepage: http://www.gnu.org/software/freeipmi/
Description-en: GNU implementation of the IPMI protocol - tools
 FreeIPMI is a collection of Intelligent Platform Management IPMI
 system software. It provides in-band and out-of-band software and a
 development library conforming to the Intelligent Platform Management
 Interface (IPMI v1.5 and v2.0) standards.
 .
 This package contains assorted IPMI-related tools:
  * bmc-config - configure BMC values
  * bmc-info - display BMC information
  * ipmi-chassis - IPMI chassis management utility
  * ipmi-fru - display FRU information
  * ipmi-locate - IPMI probing utility
  * ipmi-oem - IPMI OEM utility
  * ipmi-pet - decode Platform Event Traps
  * ipmi-raw - IPMI raw communication utility
  * ipmi-sel - display SEL entries
  * ipmi-sensors - display IPMI sensor information
  * ipmi-sensors-config - configure sensors
  * ipmiconsole - IPMI console utility
  * ipmiping - send IPMI Get Authentication Capability request
  * ipmipower - IPMI power control utility
  * pef-config - configure PEF values
  * rmcpping - send RMCP Ping to network hosts
Description-md5: 6752c6921b38f7d4192531a8ab33783c
"""


apt_cache_policy_freeipmi_tools_focal = """
freeipmi-tools:
  Installed: (none)
  Candidate: 1.6.4-3ubuntu1.1
  Version table:
     1.6.9-2~bpo20.04.1 100
        100 http://archive.ubuntu.com/ubuntu focal-backports/main amd64 Packages
     1.6.4-3ubuntu1.1 500
        500 http://archive.ubuntu.com/ubuntu focal-updates/main amd64 Packages
     1.6.4-3ubuntu1 500
        500 http://archive.ubuntu.com/ubuntu focal/main amd64 Packages
"""


class TestApt(unittest.TestCase):
    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_can_load_from_dpkg(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_vim]

        vim = apt.DebianPackage.from_installed_package("vim")
        self.assertEqual(vim.epoch, "2")
        self.assertEqual(vim.arch, "amd64")
        self.assertEqual(vim.fullversion, "2:8.1.2269-1ubuntu5.amd64")
        self.assertEqual(str(vim.version), "2:8.1.2269-1ubuntu5")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_can_load_from_dpkg_with_version(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_zsh]

        zsh = apt.DebianPackage.from_installed_package("zsh", version="5.8-3ubuntu1")
        self.assertEqual(zsh.epoch, "")
        self.assertEqual(zsh.arch, "amd64")
        self.assertEqual(zsh.fullversion, "5.8-3ubuntu1.amd64")
        self.assertEqual(str(zsh.version), "5.8-3ubuntu1")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_will_not_load_from_system_with_bad_version(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_zsh]

        with self.assertRaises(apt.PackageNotFoundError):
            apt.DebianPackage.from_installed_package("zsh", version="1.2-3")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_can_load_from_dpkg_with_arch(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_zsh]

        zsh = apt.DebianPackage.from_installed_package("zsh", arch="amd64")
        self.assertEqual(zsh.epoch, "")
        self.assertEqual(zsh.arch, "amd64")
        self.assertEqual(zsh.fullversion, "5.8-3ubuntu1.amd64")
        self.assertEqual(str(zsh.version), "5.8-3ubuntu1")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_can_load_from_dpkg_with_all_arch(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_all_arch]

        postgresql = apt.DebianPackage.from_installed_package("postgresql")
        self.assertEqual(postgresql.epoch, "")
        self.assertEqual(postgresql.arch, "all")
        self.assertEqual(postgresql.fullversion, "12+214ubuntu0.1.all")
        self.assertEqual(str(postgresql.version), "12+214ubuntu0.1")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_can_load_from_dpkg_multi_arch(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_multi_arch]

        vim = apt.DebianPackage.from_installed_package("vim", arch="i386")
        self.assertEqual(vim.epoch, "2")
        self.assertEqual(vim.arch, "i386")
        self.assertEqual(vim.fullversion, "2:8.1.2269-1ubuntu5.i386")
        self.assertEqual(str(vim.version), "2:8.1.2269-1ubuntu5")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_can_load_from_dpkg_not_installed(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_not_installed]

        with self.assertRaises(apt.PackageNotFoundError) as ctx:
            apt.DebianPackage.from_installed_package("ubuntu-advantage-tools")

        self.assertEqual(
            "<charms.operator_libs_linux.v0.apt.PackageNotFoundError>", ctx.exception.name
        )
        self.assertIn(
            "Package ubuntu-advantage-tools.amd64 is not installed!", ctx.exception.message
        )

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_can_load_from_apt_cache(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", apt_cache_mocktester]

        tester = apt.DebianPackage.from_apt_cache("mocktester")
        self.assertEqual(tester.epoch, "1")
        self.assertEqual(tester.arch, "amd64")
        self.assertEqual(tester.fullversion, "1:1.2.3-4.amd64")
        self.assertEqual(str(tester.version), "1:1.2.3-4")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_can_load_from_apt_cache_all_arch(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", apt_cache_mocktester_all_arch]

        tester = apt.DebianPackage.from_apt_cache("mocktester")
        self.assertEqual(tester.epoch, "1")
        self.assertEqual(tester.arch, "all")
        self.assertEqual(tester.fullversion, "1:1.2.3-4.all")
        self.assertEqual(str(tester.version), "1:1.2.3-4")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_can_load_from_apt_cache_multi_arch(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", apt_cache_mocktester_multi]

        tester = apt.DebianPackage.from_apt_cache("mocktester", arch="i386")
        self.assertEqual(tester.epoch, "1")
        self.assertEqual(tester.arch, "i386")
        self.assertEqual(tester.fullversion, "1:1.2.3-4.i386")
        self.assertEqual(str(tester.version), "1:1.2.3-4")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    @patch("os.environ.copy")
    def test_can_run_apt_commands(
        self, mock_environ, mock_subprocess_call, mock_subprocess_output
    ):
        mock_subprocess_call.return_value = 0
        mock_subprocess_output.side_effect = [
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "mocktester"]),
            "amd64",
            apt_cache_mocktester,
        ]
        mock_environ.return_value = {"PING": "PONG"}

        pkg = apt.DebianPackage.from_system("mocktester")
        self.assertEqual(pkg.present, False)
        self.assertEqual(pkg.version.epoch, "1")
        self.assertEqual(pkg.version.number, "1.2.3-4")

        pkg.ensure(apt.PackageState.Latest)
        mock_subprocess_call.assert_called_with(
            [
                "apt-get",
                "-y",
                "--option=Dpkg::Options::=--force-confold",
                "install",
                "mocktester=1:1.2.3-4",
            ],
            capture_output=True,
            check=True,
            env={"DEBIAN_FRONTEND": "noninteractive", "PING": "PONG"},
        )
        self.assertEqual(pkg.state, apt.PackageState.Latest)

        pkg.state = apt.PackageState.Absent
        mock_subprocess_call.assert_called_with(
            ["apt-get", "-y", "remove", "mocktester=1:1.2.3-4"],
            capture_output=True,
            check=True,
            env={"DEBIAN_FRONTEND": "noninteractive", "PING": "PONG"},
        )

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    def test_will_throw_apt_errors(self, mock_subprocess_call, mock_subprocess_output):
        mock_subprocess_call.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["apt-get", "-y", "install"]
        )
        mock_subprocess_output.side_effect = [
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "mocktester"]),
            "amd64",
            apt_cache_mocktester,
        ]

        pkg = apt.DebianPackage.from_system("mocktester")
        self.assertEqual(pkg.present, False)

        with self.assertRaises(apt.PackageError) as ctx:
            pkg.ensure(apt.PackageState.Latest)

        self.assertEqual("<charms.operator_libs_linux.v0.apt.PackageError>", ctx.exception.name)
        self.assertIn("Could not install package", ctx.exception.message)

    def test_can_compare_versions(self):
        old_version = apt.Version("1.0.0", "")
        old_dupe = apt.Version("1.0.0", "")
        new_version = apt.Version("1.0.1", "")
        new_epoch = apt.Version("1.0.1", "1")

        self.assertEqual(old_version, old_dupe)
        self.assertGreater(new_version, old_version)
        self.assertGreater(new_epoch, new_version)
        self.assertLess(old_version, new_version)
        self.assertLessEqual(new_version, new_epoch)
        self.assertGreaterEqual(new_version, old_version)
        self.assertNotEqual(new_version, old_version)

    def test_can_parse_epoch_and_version(self):
        self.assertEqual((None, "1.0.0"), apt.DebianPackage._get_epoch_from_version("1.0.0"))
        self.assertEqual(
            ("2", "9.8-7ubuntu6"), apt.DebianPackage._get_epoch_from_version("2:9.8-7ubuntu6")
        )


class TestAptBareMethods(unittest.TestCase):
    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    @patch("os.environ.copy")
    def test_can_run_bare_changes_on_single_package(
        self, mock_environ, mock_subprocess, mock_subprocess_output
    ):
        mock_subprocess.return_value = 0
        mock_subprocess_output.side_effect = [
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "aisleriot"]),
            "amd64",
            apt_cache_aisleriot,
        ]
        mock_environ.return_value = {}

        foo = apt.add_package("aisleriot")
        mock_subprocess.assert_called_with(
            [
                "apt-get",
                "-y",
                "--option=Dpkg::Options::=--force-confold",
                "install",
                "aisleriot=1:3.22.9-1",
            ],
            capture_output=True,
            check=True,
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        self.assertEqual(foo.present, True)

        mock_subprocess_output.side_effect = ["amd64", dpkg_output_zsh]
        bar = apt.remove_package("zsh")
        bar.ensure(apt.PackageState.Absent)
        mock_subprocess.assert_called_with(
            ["apt-get", "-y", "remove", "zsh=5.8-3ubuntu1"],
            capture_output=True,
            check=True,
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        self.assertEqual(bar.present, False)

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    @patch("os.environ.copy")
    def test_can_run_bare_changes_on_multiple_packages(
        self, mock_environ, mock_subprocess, mock_subprocess_output
    ):
        mock_subprocess.return_value = 0
        mock_subprocess_output.side_effect = [
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "aisleriot"]),
            "amd64",
            apt_cache_aisleriot,
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "mocktester"]),
            "amd64",
            apt_cache_mocktester,
        ]
        mock_environ.return_value = {}

        foo = apt.add_package(["aisleriot", "mocktester"])
        mock_subprocess.assert_any_call(
            [
                "apt-get",
                "-y",
                "--option=Dpkg::Options::=--force-confold",
                "install",
                "aisleriot=1:3.22.9-1",
            ],
            capture_output=True,
            check=True,
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        mock_subprocess.assert_any_call(
            [
                "apt-get",
                "-y",
                "--option=Dpkg::Options::=--force-confold",
                "install",
                "mocktester=1:1.2.3-4",
            ],
            capture_output=True,
            check=True,
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        self.assertEqual(foo[0].present, True)
        self.assertEqual(foo[1].present, True)

        mock_subprocess_output.side_effect = ["amd64", dpkg_output_vim, "amd64", dpkg_output_zsh]
        bar = apt.remove_package(["vim", "zsh"])
        mock_subprocess.assert_any_call(
            ["apt-get", "-y", "remove", "vim=2:8.1.2269-1ubuntu5"],
            capture_output=True,
            check=True,
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        mock_subprocess.assert_any_call(
            ["apt-get", "-y", "remove", "zsh=5.8-3ubuntu1"],
            capture_output=True,
            check=True,
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        self.assertEqual(bar[0].present, False)
        self.assertEqual(bar[1].present, False)

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    def test_refreshes_apt_cache_if_not_found(self, mock_subprocess, mock_subprocess_output):
        mock_subprocess.return_value = 0
        mock_subprocess_output.side_effect = [
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "nothere"]),
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["apt-cache", "show", "nothere"]),
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "nothere"]),
            "amd64",
            apt_cache_aisleriot,
        ]
        pkg = apt.add_package("aisleriot")
        mock_subprocess.assert_any_call(["apt-get", "update"], capture_output=True, check=True)
        self.assertEqual(pkg.name, "aisleriot")
        self.assertEqual(pkg.present, True)

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    def test_raises_package_not_found_error(self, mock_subprocess, mock_subprocess_output):
        mock_subprocess.return_value = 0
        mock_subprocess_output.side_effect = [
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "nothere"]),
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["apt-cache", "show", "nothere"]),
        ] * 2  # Double up for the retry after update
        with self.assertRaises(apt.PackageError) as ctx:
            apt.add_package("nothere")
        mock_subprocess.assert_any_call(["apt-get", "update"], capture_output=True, check=True)
        self.assertEqual("<charms.operator_libs_linux.v0.apt.PackageError>", ctx.exception.name)
        self.assertIn("Failed to install packages: nothere", ctx.exception.message)

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    def test_remove_package_not_installed(self, mock_subprocess, mock_subprocess_output):
        mock_subprocess_output.side_effect = ["amd64", dpkg_output_not_installed]

        packages = apt.remove_package("ubuntu-advantage-tools")
        mock_subprocess.assert_not_called()
        self.assertEqual(packages, [])

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_get_candidate_version(self, mock_subprocess_output):
        mock_subprocess_output.return_value = apt_cache_policy_freeipmi_tools_focal

        version = apt.get_candidate_version("freeipmi_tools")
        self.assertEqual(version, "1.6.4-3ubuntu1.1")

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_get_candidate_version_package_not_found_error(self, mock_subprocess_output):
        mock_subprocess_output.side_effect = subprocess.CalledProcessError(
            returncode=-1, cmd=["apt-cache", "policy", "fake_package_name"]
        )

        with self.assertRaises(apt.PackageError) as ctx:
            apt.get_candidate_version("fake_package_name")

        self.assertEqual("<charms.operator_libs_linux.v0.apt.PackageError>", ctx.exception.name)
        self.assertIn("Could not list packages in apt-cache:", ctx.exception.message)

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    def test_get_candidate_version_can_not_found_candidate(self, mock_subprocess_output):
        output = apt_cache_policy_freeipmi_tools_focal.replace("Candidate", "candidate")
        mock_subprocess_output.return_value = output
        with self.assertRaises(apt.PackageNotFoundError) as ctx:
            apt.get_candidate_version("freeipmi_tools")

        self.assertEqual(
            "<charms.operator_libs_linux.v0.apt.PackageNotFoundError>", ctx.exception.name
        )
        self.assertIn(
            f"Could not find candidate version package in apt-cache: {output}",
            ctx.exception.message,
        )

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    @patch("os.environ.copy")
    def test_can_run_bare_changes_on_single_package_with_candidate_version(
        self, mock_environ, mock_subprocess, mock_subprocess_output
    ):
        mock_subprocess.return_value = 0
        mock_subprocess_output.side_effect = [
            apt_cache_policy_freeipmi_tools_focal,
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "freeipmi-tools"]),
            "amd64",
            apt_cache_freeipmi_tools,
        ]
        mock_environ.return_value = {}

        # foo = apt.add_package("freeipmi_tools", candidate_version=True)
        foo = apt.add_package("freeipmi_tools", candidate_version=True)
        mock_subprocess.assert_called_with(
            [
                "apt-get",
                "-y",
                "--option=Dpkg::Options::=--force-confold",
                "install",
                "freeipmi-tools=1.6.4-3ubuntu1.1",
            ],
            capture_output=True,
            check=True,
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        self.assertEqual(foo.present, True)
