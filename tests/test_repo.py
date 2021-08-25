# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import subprocess

from pyfakefs.fake_filesystem_unittest import TestCase
from unittest.mock import mock_open, patch

from lib.charm.operator.v0 import dpkg

sources_list = """deb http://us.archive.ubuntu.com/ubuntu focal main restricted universe multiverse
deb http://us.archive.ubuntu.com/ubuntu focal-updates main restricted universe multiverse
# deb http://us.archive.ubuntu.com/ubuntu focal-backports main restricted universe multiverse
"""

debug_sources_list = """# debug symbols
# deb http://ddebs.ubuntu.com focal main restricted universe multiverse
# deb http://ddebs.ubuntu.com focal-updates main restricted universe multiverse
# deb http://ddebs.ubuntu.com focal-proposed main restricted universe multiverse
"""

nodesource_sources_list = """deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_16.x focal main
deb-src [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_16.x focal main #useless comment
"""

bad_sources_list = "dontload http://example.com invalid nogroups"

nodesource_gpg_ring = """
"""


class TestRepositoryList(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.fs.create_file("/etc/apt/sources.list", contents=sources_list)
        self.fs.create_file(
            "/etc/apt/sources.list.d/nodesource.list", contents=nodesource_sources_list
        )
        self.fs.create_file("/etc/apt/sources.list.list/debug.list", contents=debug_sources_list)

    def test_can_load_repositories(self):
        r = dpkg.RepositoryList()

        self.assertIn("deb-http://us.archive.ubuntu.com/ubuntu-focal", r)
        self.assertEqual(len(r), 5)

    def test_can_get_repository_details(self):
        r = dpkg.RepositoryList()
        repo = r["deb-http://us.archive.ubuntu.com/ubuntu-focal"]
        self.assertEqual(repo.enabled, True)
        self.assertEqual(repo.repotype, "deb")
        self.assertEqual(repo.groups, ["main", "restricted", "universe", "multiverse"])
        self.assertEqual(repo.release, "focal")
        self.assertEqual(repo.filename, "/etc/apt/sources.list")
        self.assertEqual(repo.uri, "http://us.archive.ubuntu.com/ubuntu")

    def test_raises_on_invalid_repositories(self):
        r = dpkg.RepositoryList()

        self.fs.create_file("/tmp/bad.list", contents=bad_sources_list)
        with self.assertRaises(dpkg.InvalidSourceError) as ctx:
            r.load("/tmp/bad.list")

        self.assertEqual("<lib.charm.operator.v0.dpkg.InvalidSourceError>", ctx.exception.name)
        self.assertIn("An invalid sources line", ctx.exception.message)

    def test_can_disable_repositories(self):
        r = dpkg.RepositoryList()
        repo = r["deb-http://us.archive.ubuntu.com/ubuntu-focal"]
        other = r["deb-https://deb.nodesource.com/node_16.x-focal"]

        repo.disable()
        self.assertIn(
            f"# {repo.repotype} {repo.uri} {repo.release} {' '.join(repo.groups)}\n",
            open(repo.filename).readlines(),
        )

        r.disable(other)
        self.assertIn(
            f"# {other.repotype} [signed-by={other.gpg_key}] {other.uri} {other.release} {' '.join(other.groups)}\n",
            open(other.filename).readlines(),
        )

    def test_can_add_repositories(self):
        r = dpkg.RepositoryList()
        d = dpkg.DebianRepository(
            True,
            "deb",
            "http://example.com",
            "test",
            ["group"],
            "/etc/apt/sources.list.d/example-test.list",
            "",
        )
        r.add(d)
        self.assertIn(
            f"{d.repotype} {d.uri} {d.release} {' '.join(d.groups)}\n",
            open(d.filename).readlines(),
        )
