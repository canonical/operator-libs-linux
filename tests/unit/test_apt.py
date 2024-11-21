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

ubuntu_sources_deb822 = """
Types: deb
URIs: http://nz.archive.ubuntu.com/ubuntu/
Suites: noble noble-updates noble-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: http://security.ubuntu.com/ubuntu
Suites: noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
"""

ubuntu_sources_deb822_with_comments = """
Components: main restricted universe multiverse  # this lib doesn't care about order
Types: deb  # this could include deb-src as well or instead
URIs: http://nz.archive.ubuntu.com/ubuntu/
    # there can be multiple space separated URIs
    # sources are specified in priority order
    # apt does some de-duplication of sources after parsing too
#Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
# let's make this insecure! (jk, just testing parsing)
Suites: noble noble-updates noble-backports

Foo: Bar  # this is a separate (malformed) entry

#Types: deb
#URIs: http://security.ubuntu.com/ubuntu
#Suites: noble-security
#Components: main restricted universe multiverse
#Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
## disable security updates while we're at it
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
    def test_will_throw_apt_cache_errors(self, mock_subprocess):
        mock_subprocess.side_effect = [
            "amd64",
            subprocess.CalledProcessError(
                returncode=100,
                cmd=["apt-cache", "show", "mocktester"],
                stderr="N: Unable to locate package mocktester",
            ),
        ]

        with self.assertRaises(apt.PackageError) as ctx:
            apt.DebianPackage.from_apt_cache("mocktester", arch="i386")

        self.assertEqual("<charms.operator_libs_linux.v0.apt.PackageError>", ctx.exception.name)
        self.assertIn("Could not list packages in apt-cache", ctx.exception.message)
        self.assertIn("Unable to locate package", ctx.exception.message)

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
            text=True,
            env={"DEBIAN_FRONTEND": "noninteractive", "PING": "PONG"},
        )
        self.assertEqual(pkg.state, apt.PackageState.Latest)

        pkg.state = apt.PackageState.Absent
        mock_subprocess_call.assert_called_with(
            ["apt-get", "-y", "remove", "mocktester=1:1.2.3-4"],
            capture_output=True,
            check=True,
            text=True,
            env={"DEBIAN_FRONTEND": "noninteractive", "PING": "PONG"},
        )

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    def test_will_throw_apt_errors(self, mock_subprocess_call, mock_subprocess_output):
        mock_subprocess_call.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["apt-get", "-y", "install"],
            stderr="E: Unable to locate package mocktester",
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
        self.assertIn("Unable to locate package", ctx.exception.message)

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

    def test_iter_deb822_paragraphs_ubuntu_sources(self):
        lines = ubuntu_sources_deb822.strip().split("\n")
        paras = list(apt.RepositoryMapping._iter_deb822_paragraphs(lines))
        assert paras == [
            [
                (0, "Types: deb"),
                (1, "URIs: http://nz.archive.ubuntu.com/ubuntu/"),
                (2, "Suites: noble noble-updates noble-backports"),
                (3, "Components: main restricted universe multiverse"),
                (4, "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg"),
            ],
            [
                (6, "Types: deb"),
                (7, "URIs: http://security.ubuntu.com/ubuntu"),
                (8, "Suites: noble-security"),
                (9, "Components: main restricted universe multiverse"),
                (10, "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg"),
            ],
        ]

    def test_iter_deb822_paragraphs_ubuntu_sources_w_comments(self):
        lines = ubuntu_sources_deb822_with_comments.strip().split("\n")
        paras = list(apt.RepositoryMapping._iter_deb822_paragraphs(lines))
        assert paras == [
            [
                (0, "Components: main restricted universe multiverse"),
                (1, "Types: deb"),
                (2, "URIs: http://nz.archive.ubuntu.com/ubuntu/"),
                (8, "Suites: noble noble-updates noble-backports"),
            ],
            [
                (10, "Foo: Bar"),
            ],
        ]

    def test_get_deb822_options_ubuntu_sources(self):
        lines = ubuntu_sources_deb822.strip().split("\n")
        paras = list(apt.RepositoryMapping._iter_deb822_paragraphs(lines))
        opts = [
            apt.RepositoryMapping._get_deb822_options(p)
            for p in paras
        ]
        opts_0, opts_1 = opts
        opts_0_options, opts_0_line_numbers = opts_0
        opts_1_options, opts_1_line_numbers = opts_1
        assert opts_0_options == {
            'Types': 'deb',
            'URIs': 'http://nz.archive.ubuntu.com/ubuntu/',
            'Components': 'main restricted universe multiverse',
            'Suites': 'noble noble-updates noble-backports',
            'Signed-By': '/usr/share/keyrings/ubuntu-archive-keyring.gpg',
        }
        assert opts_0_line_numbers == {
            'Types': 0,
            'URIs': 1,
            'Suites': 2,
            'Components': 3,
            'Signed-By': 4,
        }
        assert opts_1_options == {
            'Types': 'deb',
            'URIs': 'http://security.ubuntu.com/ubuntu',
            'Components': 'main restricted universe multiverse',
            'Suites': 'noble-security',
            'Signed-By': '/usr/share/keyrings/ubuntu-archive-keyring.gpg',
        }
        assert opts_1_line_numbers == {
            'Types': 6,
            'URIs': 7,
            'Suites': 8,
            'Components': 9,
            'Signed-By': 10,
        }

    def test_get_deb822_options_w_comments(self):
        lines = ubuntu_sources_deb822_with_comments.strip().split("\n")
        paras = list(apt.RepositoryMapping._iter_deb822_paragraphs(lines))
        opts = [
            apt.RepositoryMapping._get_deb822_options(p)
            for p in paras
        ]
        opts_0, opts_1 = opts
        opts_0_options, opts_0_line_numbers = opts_0
        opts_1_options, opts_1_line_numbers = opts_1
        assert opts_0_options == {
            'Components': 'main restricted universe multiverse',
            'Types': 'deb',
            'URIs': 'http://nz.archive.ubuntu.com/ubuntu/',
            'Suites': 'noble noble-updates noble-backports',
        }
        assert opts_0_line_numbers == {
            'Components': 0,
            'Types': 1,
            'URIs': 2,
            'Suites': 8,
        }
        assert opts_1_options == {'Foo': 'Bar'}
        assert opts_1_line_numbers == {'Foo': 10}

    def test_parse_deb822_paragraph_ubuntu_sources(self):
        lines = ubuntu_sources_deb822.strip().split("\n")
        main, security = apt.RepositoryMapping._iter_deb822_paragraphs(lines)
        repos = apt.RepositoryMapping._parse_deb822_paragraph(main)
        assert len(repos) == 3
        for repo, suite in zip(repos, ("noble", "noble-updates", "noble-backports")):
            assert repo.enabled
            assert repo.repotype == "deb"
            assert repo.uri == "http://nz.archive.ubuntu.com/ubuntu/"
            assert repo.release == suite
            assert repo.groups == ["main", "restricted", "universe", "multiverse"]
            assert repo.filename == ""
            assert repo.gpg_key == "/usr/share/keyrings/ubuntu-archive-keyring.gpg"
        repos = apt.RepositoryMapping._parse_deb822_paragraph(security)
        assert len(repos) == 1
        [repo] = repos
        assert repo.enabled
        assert repo.repotype == "deb"
        assert repo.uri == "http://security.ubuntu.com/ubuntu"
        assert repo.release == "noble-security"
        assert repo.groups == ["main", "restricted", "universe", "multiverse"]
        assert repo.filename == ""
        assert repo.gpg_key == "/usr/share/keyrings/ubuntu-archive-keyring.gpg"

    def test_parse_deb822_paragraph_w_comments(self):
        lines = ubuntu_sources_deb822_with_comments.strip().split("\n")
        ok_para, bad_para = apt.RepositoryMapping._iter_deb822_paragraphs(lines)
        repos = apt.RepositoryMapping._parse_deb822_paragraph(ok_para)
        assert len(repos) == 3
        for repo, suite in zip(repos, ("noble", "noble-updates", "noble-backports")):
            assert repo.enabled
            assert repo.repotype == "deb"
            assert repo.uri == "http://nz.archive.ubuntu.com/ubuntu/"
            assert repo.release == suite
            assert repo.groups == ["main", "restricted", "universe", "multiverse"]
            assert repo.filename == ""
            assert repo.gpg_key == ""
        with self.assertRaises(apt.InvalidSourceError):
            apt.RepositoryMapping._parse_deb822_paragraph(bad_para)

    def test_parse_deb822_lines_ubuntu_sources(self):
        lines = ubuntu_sources_deb822.strip().split("\n")
        repos, errors = apt.RepositoryMapping._parse_deb822_lines(lines)
        print(repos[0].__dict__)
        assert len(repos) == 4
        assert not errors

    def test_parse_deb822_lines_w_comments(self):
        lines = ubuntu_sources_deb822_with_comments.strip().split("\n")
        repos, errors = apt.RepositoryMapping._parse_deb822_lines(lines)
        assert len(repos) == 3
        assert len(errors) == 1
        [error] = errors
        assert isinstance(error, apt.InvalidSourceError)


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
            text=True,
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
            text=True,
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
            text=True,
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
            text=True,
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
            text=True,
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        mock_subprocess.assert_any_call(
            ["apt-get", "-y", "remove", "zsh=5.8-3ubuntu1"],
            capture_output=True,
            check=True,
            text=True,
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
        mock_subprocess.assert_any_call(
            ["apt-get", "update", "--error-on=any"], capture_output=True, check=True
        )
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
        mock_subprocess.assert_any_call(
            ["apt-get", "update", "--error-on=any"], capture_output=True, check=True
        )
        self.assertEqual("<charms.operator_libs_linux.v0.apt.PackageError>", ctx.exception.name)
        self.assertIn("Failed to install packages: nothere", ctx.exception.message)

    @patch("charms.operator_libs_linux.v0.apt.check_output")
    @patch("charms.operator_libs_linux.v0.apt.subprocess.run")
    def test_remove_package_not_installed(self, mock_subprocess, mock_subprocess_output):
        mock_subprocess_output.side_effect = ["amd64", dpkg_output_not_installed]

        packages = apt.remove_package("ubuntu-advantage-tools")
        mock_subprocess.assert_not_called()
        self.assertEqual(packages, [])
