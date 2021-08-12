# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import unittest

from unittest.mock import mock_open, patch

from lib.charm.operator.v0 import dpkg

dpkg_l_output = """Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name                                 Version                                                                   Architecture Description
+++-====================================-=========================================================================-============-===============================================================================
ii  vim-common                           2:8.1.2269-1ubuntu5                                                       all          Vi IMproved - Common files
ii  zsh                                  5.8-3ubuntu1                                                              amd64        shell with lots of features
ii  zsh-common                           5.8-3ubuntu1                                                              all          architecture independent files for Zsh
"""

apt_cache_output = """
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

Package: alembic
Architecture: all
Version: 1.1.0-1ubuntu1
Priority: optional
Section: python
Origin: Ubuntu
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Original-Maintainer: Debian Python Modules Team <python-modules-team@lists.alioth.debian.org>
Bugs: https://bugs.launchpad.net/ubuntu/+filebug
Installed-Size: 1866
Depends: python3-alembic (= 1.1.0-1ubuntu1), python3:any, libjs-sphinxdoc (>= 1.0)
Breaks: python-alembic (<< 0.8.8-3), python3-alembic (<< 0.8.8-3)
Replaces: python-alembic (<< 0.8.8-3), python3-alembic (<< 0.8.8-3)
Filename: pool/main/a/alembic/alembic_1.1.0-1ubuntu1_all.deb
Size: 250596
MD5sum: e38a4c060efb98b5f3af66bc83439187
SHA1: b845fee217a9e535db863df5ad233a5badddd8f1
SHA256: de4c7b85ca7d9023af0232aa9e9c88b0ec4ea0b2b140597148b530ff9622a202
Homepage: https://bitbucket.org/zzzeek/alembic
Description: lightweight database migration tool for SQLAlchemy
Description-md5: cd0efbf0f89bffe2d4dc35fa935c7c7e
"""


class DpkgCacheTester(dpkg.PackageCache):
    def __init__(self):
        # Fake out __init__ so we can test methods individually
        self._package_map = {}


class TestDpkgCache(unittest.TestCase):
    @patch("lib.charm.operator.v0.dpkg.check_output")
    def test_can_load_from_dpkg(self, mock_subprocess):
        mock_subprocess.return_value = dpkg_l_output
        d = DpkgCacheTester()
        d._merge_with_cache(d._generate_packages_from_dpkg())
        self.assertIn("zsh", d)
        self.assertEqual(len(d), 3)
        self.assertEqual(d["zsh"].state, dpkg.PackageState.Present)

        vim = d["vim-common"]
        self.assertEqual(vim.epoch, "2")
        self.assertEqual(vim.arch, "all")
        self.assertEqual(vim.fullversion, "2:8.1.2269-1ubuntu5.all")
        self.assertEqual(str(vim.version), "2:8.1.2269-1ubuntu5")

    @patch("lib.charm.operator.v0.dpkg.check_output")
    def test_can_load_from_apt_cache(self, mock_subprocess):
        mock_subprocess.return_value = apt_cache_output
        d = DpkgCacheTester()
        d._merge_with_cache(d._generate_packages_from_apt_cache())

        self.assertEqual(len(d), 2)
        self.assertIn("aisleriot", d)
        self.assertEqual(len(d), 2)
        self.assertEqual(d["aisleriot"].arch, "amd64")
