# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import subprocess
import unittest
from unittest.mock import patch
from lib.charm.operator.v0 import apt

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

dpkg_output_multi_arch = """Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name                                 Version                                                                   Architecture Description
+++-====================================-=========================================================================-============-===============================================================================
ii  vim                           2:8.1.2269-1ubuntu5                                                       amd64          Vi IMproved - Common files
ii  vim                           2:8.1.2269-1ubuntu5                                                       i386          Vi IMproved - Common files
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


class TestApt(unittest.TestCase):
    @patch("lib.charm.operator.v0.apt.check_output")
    def test_can_load_from_dpkg(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_vim]

        vim = apt.DebianPackage.from_installed_package("vim")
        self.assertEqual(vim.epoch, "2")
        self.assertEqual(vim.arch, "amd64")
        self.assertEqual(vim.fullversion, "2:8.1.2269-1ubuntu5.amd64")
        self.assertEqual(str(vim.version), "2:8.1.2269-1ubuntu5")

    @patch("lib.charm.operator.v0.apt.check_output")
    def test_can_load_from_dpkg_with_version(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_zsh]

        zsh = apt.DebianPackage.from_installed_package("zsh", version="5.8-3ubuntu1")
        self.assertEqual(zsh.epoch, "")
        self.assertEqual(zsh.arch, "amd64")
        self.assertEqual(zsh.fullversion, "5.8-3ubuntu1.amd64")
        self.assertEqual(str(zsh.version), "5.8-3ubuntu1")

    @patch("lib.charm.operator.v0.apt.check_output")
    def test_will_not_load_from_system_with_bad_version(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_zsh]

        with self.assertRaises(apt.PackageNotFoundError) as ctx:
            d = apt.DebianPackage.from_installed_package("zsh", version="1.2-3")

    @patch("lib.charm.operator.v0.apt.check_output")
    def test_can_load_from_dpkg_with_arch(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_zsh]

        zsh = apt.DebianPackage.from_installed_package("zsh", arch="amd64")
        self.assertEqual(zsh.epoch, "")
        self.assertEqual(zsh.arch, "amd64")
        self.assertEqual(zsh.fullversion, "5.8-3ubuntu1.amd64")
        self.assertEqual(str(zsh.version), "5.8-3ubuntu1")

    @patch("lib.charm.operator.v0.apt.check_output")
    def test_can_load_from_dpkg_multi_arch(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", dpkg_output_multi_arch]

        vim = apt.DebianPackage.from_installed_package("vim", arch="i386")
        self.assertEqual(vim.epoch, "2")
        self.assertEqual(vim.arch, "i386")
        self.assertEqual(vim.fullversion, "2:8.1.2269-1ubuntu5.i386")
        self.assertEqual(str(vim.version), "2:8.1.2269-1ubuntu5")

    @patch("lib.charm.operator.v0.apt.check_output")
    def test_can_load_from_apt_cache(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", apt_cache_mocktester]

        tester = apt.DebianPackage.from_apt_cache("mocktester")
        self.assertEqual(tester.epoch, "1")
        self.assertEqual(tester.arch, "amd64")
        self.assertEqual(tester.fullversion, "1:1.2.3-4.amd64")
        self.assertEqual(str(tester.version), "1:1.2.3-4")

    @patch("lib.charm.operator.v0.apt.check_output")
    def test_can_load_from_apt_cache_multi_arch(self, mock_subprocess):
        mock_subprocess.side_effect = ["amd64", apt_cache_mocktester_multi]

        tester = apt.DebianPackage.from_apt_cache("mocktester", arch="i386")
        self.assertEqual(tester.epoch, "1")
        self.assertEqual(tester.arch, "i386")
        self.assertEqual(tester.fullversion, "1:1.2.3-4.i386")
        self.assertEqual(str(tester.version), "1:1.2.3-4")

    @patch("lib.charm.operator.v0.apt.check_output")
    @patch("lib.charm.operator.v0.apt.subprocess.check_call")
    def test_can_run_apt_commands(self, mock_subprocess_call, mock_subprocess_output):
        mock_subprocess_call.return_value = 0
        mock_subprocess_output.side_effect = [
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "mocktester"]),
            "amd64",
            apt_cache_mocktester,
        ]

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
            ]
        )
        self.assertEqual(pkg.state, apt.PackageState.Latest)

        pkg.state = apt.PackageState.Absent
        mock_subprocess_call.assert_called_with(
            ["apt-get", "-y", "remove", "mocktester=1:1.2.3-4"]
        )

    @patch("lib.charm.operator.v0.apt.check_output")
    @patch("lib.charm.operator.v0.apt.subprocess.check_call")
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

        self.assertEqual("<lib.charm.operator.v0.apt.PackageError>", ctx.exception.name)
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
    @patch("lib.charm.operator.v0.apt.check_output")
    @patch("lib.charm.operator.v0.apt.subprocess.check_call")
    def test_can_run_bare_changes_on_single_package(self, mock_subprocess, mock_subprocess_output):
        mock_subprocess.return_value = 0
        mock_subprocess_output.side_effect = [
            "amd64",
            subprocess.CalledProcessError(returncode=100, cmd=["dpkg", "-l", "aisleriot"]),
            "amd64",
            apt_cache_aisleriot,
        ]

        foo = apt.add_package("aisleriot")[0]
        mock_subprocess.assert_called_with(
            [
                "apt-get",
                "-y",
                "--option=Dpkg::Options::=--force-confold",
                "install",
                "aisleriot=1:3.22.9-1",
            ]
        )
        self.assertEqual(foo.present, True)

        mock_subprocess_output.side_effect = ["amd64", dpkg_output_zsh]
        bar = apt.remove_package("zsh")[0]
        bar.ensure(apt.PackageState.Absent)
        mock_subprocess.assert_called_with(["apt-get", "-y", "remove", "zsh=5.8-3ubuntu1"])
        self.assertEqual(bar.present, False)

    @patch("lib.charm.operator.v0.apt.check_output")
    @patch("lib.charm.operator.v0.apt.subprocess.check_call")
    def test_can_run_bare_changes_on_multiple_packages(
        self, mock_subprocess, mock_subprocess_output
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

        foo = apt.add_package(["aisleriot", "mocktester"])
        mock_subprocess.assert_any_call(
            [
                "apt-get",
                "-y",
                "--option=Dpkg::Options::=--force-confold",
                "install",
                "aisleriot=1:3.22.9-1",
            ]
        )
        mock_subprocess.assert_any_call(
            [
                "apt-get",
                "-y",
                "--option=Dpkg::Options::=--force-confold",
                "install",
                "mocktester=1:1.2.3-4",
            ]
        )
        self.assertEqual(foo[0].present, True)
        self.assertEqual(foo[1].present, True)

        mock_subprocess_output.side_effect = ["amd64", dpkg_output_vim, "amd64", dpkg_output_zsh]
        bar = apt.remove_package(["vim", "zsh"])
        mock_subprocess.assert_any_call(["apt-get", "-y", "remove", "vim=2:8.1.2269-1ubuntu5"])
        mock_subprocess.assert_any_call(["apt-get", "-y", "remove", "zsh=5.8-3ubuntu1"])
        self.assertEqual(bar[0].present, False)
        self.assertEqual(bar[1].present, False)

    @patch("lib.charm.operator.v0.apt.check_output")
    @patch("lib.charm.operator.v0.apt.subprocess.check_call")
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
        pkg = apt.add_package("aisleriot")[0]
        mock_subprocess.assert_any_call(["apt-get", "update"])
        self.assertEqual(pkg.name, "aisleriot")
        self.assertEqual(pkg.present, True)

    @patch("lib.charm.operator.v0.apt.check_output")
    @patch("lib.charm.operator.v0.apt.subprocess.check_call")
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
        mock_subprocess.assert_any_call(["apt-get", "update"])
        self.assertEqual("<lib.charm.operator.v0.apt.PackageError>", ctx.exception.name)
        self.assertIn("Failed to install packages: nothere", ctx.exception.message)
