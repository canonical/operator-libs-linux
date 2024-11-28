# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

# pyright: reportPrivateUsage=false

import os
import typing
import unittest
from unittest.mock import ANY, mock_open, patch

import pytest
from charms.operator_libs_linux.v0 import apt
from pyfakefs.fake_filesystem_unittest import TestCase as PyFakeFsTestCase

sources_list = """## This is a comment which should be ignored!
deb http://us.archive.ubuntu.com/ubuntu focal main restricted universe multiverse

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


class TestRepositoryMapping(PyFakeFsTestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.fs.create_file("/etc/apt/sources.list", contents=sources_list)
        self.fs.create_file(
            "/etc/apt/sources.list.d/nodesource.list", contents=nodesource_sources_list
        )
        self.fs.create_file("/etc/apt/sources.list.list/debug.list", contents=debug_sources_list)

    def test_can_load_repositories(self):
        r = apt.RepositoryMapping()

        self.assertIn("deb-http://us.archive.ubuntu.com/ubuntu-focal", r)
        self.assertEqual(len(r), 5)

    def test_can_get_repository_details(self):
        r = apt.RepositoryMapping()
        repo = r["deb-http://us.archive.ubuntu.com/ubuntu-focal"]
        self.assertEqual(repo.enabled, True)
        self.assertEqual(repo.repotype, "deb")
        self.assertEqual(repo.groups, ["main", "restricted", "universe", "multiverse"])
        self.assertEqual(repo.release, "focal")
        self.assertEqual(repo.filename, "/etc/apt/sources.list")
        self.assertEqual(repo.uri, "http://us.archive.ubuntu.com/ubuntu")

    def test_raises_on_invalid_repositories(self):
        r = apt.RepositoryMapping()

        self.fs.create_file("/tmp/bad.list", contents=bad_sources_list)
        with self.assertRaises(apt.InvalidSourceError) as ctx:
            r.load("/tmp/bad.list")

        self.assertEqual(
            "<charms.operator_libs_linux.v0.apt.InvalidSourceError>", ctx.exception.name
        )
        self.assertIn(
            "all repository lines in '/tmp/bad.list' were invalid!", ctx.exception.message
        )

    def test_can_disable_repositories(self):
        r = apt.RepositoryMapping()
        repo = r["deb-http://us.archive.ubuntu.com/ubuntu-focal"]
        other = r["deb-https://deb.nodesource.com/node_16.x-focal"]

        repo.disable()
        self.assertIn(
            "# {} {} {} {}\n".format(repo.repotype, repo.uri, repo.release, " ".join(repo.groups)),
            open(repo.filename).readlines(),
        )

        r.disable(other)
        self.assertIn(
            "# {} [signed-by={}] {} {} {}\n".format(
                other.repotype, other.gpg_key, other.uri, other.release, " ".join(other.groups)
            ),
            open(other.filename).readlines(),
        )

    @pytest.mark.skip("RepositoryMapping.add now calls apt-add-repository")
    def test_can_add_repositories(self):
        r = apt.RepositoryMapping()
        d = apt.DebianRepository(
            True,
            "deb",
            "http://example.com",
            "test",
            ["group"],
            "/etc/apt/sources.list.d/example-test.list",
        )
        r.add(d, default_filename=False)
        self.assertIn(
            "{} {} {} {}\n".format(d.repotype, d.uri, d.release, " ".join(d.groups)),
            open(d.filename).readlines(),
        )

    def test_can_add_repositories_from_string(self):
        d = apt.DebianRepository.from_repo_line("deb https://example.com/foo focal bar baz")
        self.assertEqual(d.enabled, True)
        self.assertEqual(d.repotype, "deb")
        self.assertEqual(d.uri, "https://example.com/foo")
        self.assertEqual(d.release, "focal")
        self.assertEqual(d.groups, ["bar", "baz"])
        self.assertEqual(d.filename, "/etc/apt/sources.list.d/foo-focal.list")
        self.assertIn("deb https://example.com/foo focal bar baz\n", open(d.filename).readlines())

    @pytest.mark.skip("RepositoryMapping.add now calls apt-add-repository")
    def test_valid_list_file(self):
        line = "deb https://repo.example.org/fiz/baz focal/foo-bar/5.0 multiverse"
        d = apt.DebianRepository.from_repo_line(line)
        self.assertEqual(d.filename, "/etc/apt/sources.list.d/fiz-baz-focal-foo-bar-5.0.list")

        r = apt.RepositoryMapping()
        d = apt.DebianRepository(
            True,
            "deb",
            "https://repo.example.org/fiz/baz",
            "focal/foo-bar/5.0",
            ["multiverse"],
        )
        r.add(d, default_filename=False)
        assert os.path.exists("/etc/apt/sources.list.d/fiz-baz-focal-foo-bar-5.0.list")

    def test_can_add_repositories_from_string_with_options(self):
        d = apt.DebianRepository.from_repo_line(
            "deb [signed-by=/foo/gpg.key arch=amd64] https://example.com/foo focal bar baz"
        )
        self.assertEqual(d.enabled, True)
        self.assertEqual(d.repotype, "deb")
        self.assertEqual(d.uri, "https://example.com/foo")
        self.assertEqual(d.release, "focal")
        self.assertEqual(d.groups, ["bar", "baz"])
        self.assertEqual(d.filename, "/etc/apt/sources.list.d/foo-focal.list")
        self.assertEqual(d.gpg_key, "/foo/gpg.key")
        self.assertEqual(d.options["arch"], "amd64")
        self.assertIn(
            "deb [arch=amd64 signed-by=/foo/gpg.key] https://example.com/foo focal bar baz\n",
            open(d.filename).readlines(),
        )


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

ubuntu_sources_one_line = """
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://nz.archive.ubuntu.com/ubuntu/ noble main restricted universe multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://nz.archive.ubuntu.com/ubuntu/ noble-updates main restricted universe multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://nz.archive.ubuntu.com/ubuntu/ noble-backports main restricted universe multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse
"""


class TestRepositoryMappingDeb822Behaviour(unittest.TestCase):
    def test_iter_deb822_paragraphs_ubuntu_sources(self):
        lines = ubuntu_sources_deb822.strip().split("\n")
        paras = list(apt._iter_deb822_stanzas(lines))
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
        paras = list(apt._iter_deb822_stanzas(lines))
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
        paras = list(apt._iter_deb822_stanzas(lines))
        opts = [apt._Deb822Stanza._get_options(p) for p in paras]
        opts_0, opts_1 = opts
        opts_0_options, opts_0_line_numbers = opts_0
        opts_1_options, opts_1_line_numbers = opts_1
        assert opts_0_options == {
            "Types": "deb",
            "URIs": "http://nz.archive.ubuntu.com/ubuntu/",
            "Components": "main restricted universe multiverse",
            "Suites": "noble noble-updates noble-backports",
            "Signed-By": "/usr/share/keyrings/ubuntu-archive-keyring.gpg",
        }
        assert opts_0_line_numbers == {
            "Types": 0,
            "URIs": 1,
            "Suites": 2,
            "Components": 3,
            "Signed-By": 4,
        }
        assert opts_1_options == {
            "Types": "deb",
            "URIs": "http://security.ubuntu.com/ubuntu",
            "Components": "main restricted universe multiverse",
            "Suites": "noble-security",
            "Signed-By": "/usr/share/keyrings/ubuntu-archive-keyring.gpg",
        }
        assert opts_1_line_numbers == {
            "Types": 6,
            "URIs": 7,
            "Suites": 8,
            "Components": 9,
            "Signed-By": 10,
        }

    def test_get_deb822_options_w_comments(self):
        lines = ubuntu_sources_deb822_with_comments.strip().split("\n")
        paras = list(apt._iter_deb822_stanzas(lines))
        opts = [apt._Deb822Stanza._get_options(p) for p in paras]
        opts_0, opts_1 = opts
        opts_0_options, opts_0_line_numbers = opts_0
        opts_1_options, opts_1_line_numbers = opts_1
        assert opts_0_options == {
            "Components": "main restricted universe multiverse",
            "Types": "deb",
            "URIs": "http://nz.archive.ubuntu.com/ubuntu/",
            "Suites": "noble noble-updates noble-backports",
        }
        assert opts_0_line_numbers == {
            "Components": 0,
            "Types": 1,
            "URIs": 2,
            "Suites": 8,
        }
        assert opts_1_options == {"Foo": "Bar"}
        assert opts_1_line_numbers == {"Foo": 10}

    def test_parse_deb822_paragraph_ubuntu_sources(self):
        lines = ubuntu_sources_deb822.strip().split("\n")
        main, security = apt._iter_deb822_stanzas(lines)
        repos = apt._Deb822Stanza(main).repositories
        assert len(repos) == 3
        for repo, suite in zip(repos, ("noble", "noble-updates", "noble-backports")):
            assert repo.enabled
            assert repo.repotype == "deb"
            assert repo.uri == "http://nz.archive.ubuntu.com/ubuntu/"
            assert repo.release == suite
            assert repo.groups == ["main", "restricted", "universe", "multiverse"]
            assert repo.filename == ""
            assert repo.gpg_key == "/usr/share/keyrings/ubuntu-archive-keyring.gpg"
        repos = apt._Deb822Stanza(security).repositories
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
        ok_para, bad_para = apt._iter_deb822_stanzas(lines)
        repos = apt._Deb822Stanza(ok_para).repositories
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
            apt._Deb822Stanza(bad_para)

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

    def test_load_deb822_ubuntu_sources(self):
        def isnt_file(f: str) -> bool:
            return False

        def iglob_nothing(s: str) -> typing.Iterable[str]:
            return []

        with patch("os.path.isfile", new=isnt_file):
            with patch("glob.iglob", new=iglob_nothing):
                repository_mapping = apt.RepositoryMapping()
        assert not repository_mapping._repository_map

        with patch("builtins.open", new_callable=mock_open, read_data=ubuntu_sources_deb822):
            repository_mapping.load_deb822("")
        assert sorted(repository_mapping._repository_map.keys()) == [
            "deb-http://nz.archive.ubuntu.com/ubuntu/-noble",
            "deb-http://nz.archive.ubuntu.com/ubuntu/-noble-backports",
            "deb-http://nz.archive.ubuntu.com/ubuntu/-noble-updates",
            "deb-http://security.ubuntu.com/ubuntu-noble-security",
        ]

    def test_load_deb822_w_comments(self):
        def isnt_file(f: str) -> bool:
            return False

        def iglob_nothing(s: str) -> typing.Iterable[str]:
            return []

        with patch("os.path.isfile", new=isnt_file):
            with patch("glob.iglob", new=iglob_nothing):
                repository_mapping = apt.RepositoryMapping()
        assert not repository_mapping._repository_map

        with patch(
            "builtins.open", new_callable=mock_open, read_data=ubuntu_sources_deb822_with_comments
        ):
            with patch.object(apt.logger, "debug") as debug:
                repository_mapping.load_deb822("FILENAME")
        assert sorted(repository_mapping._repository_map.keys()) == [
            "deb-http://nz.archive.ubuntu.com/ubuntu/-noble",
            "deb-http://nz.archive.ubuntu.com/ubuntu/-noble-backports",
            "deb-http://nz.archive.ubuntu.com/ubuntu/-noble-updates",
        ]
        debug.assert_called_once_with(
            ANY,
            1,  # number of errors
            "Missing key 'Types' for entry starting on line 11 in FILENAME.",
        )

    def test_init_with_deb822(self):
        """Mock file opening to initialise a RepositoryMapping from deb822 and one-line-style.

        They should be equivalent with the sample data being used.
        """

        def isnt_file(f: str) -> bool:
            return False

        def iglob_list(s: str) -> typing.Iterable[str]:
            if s.endswith(".list"):
                return ["FILENAME"]
            return []

        def iglob_sources(s: str) -> typing.Iterable[str]:
            if s.endswith(".sources"):
                return ["FILENAME"]
            return []

        with patch("builtins.open", new_callable=mock_open, read_data=ubuntu_sources_one_line):
            with patch("os.path.isfile", new=isnt_file):
                with patch("glob.iglob", new=iglob_list):
                    repository_mapping_list = apt.RepositoryMapping()

        with patch("builtins.open", new_callable=mock_open, read_data=ubuntu_sources_deb822):
            with patch("os.path.isfile", new=isnt_file):
                with patch("glob.iglob", new=iglob_sources):
                    repository_mapping_sources = apt.RepositoryMapping()

        list_keys = sorted(repository_mapping_list._repository_map.keys())
        sources_keys = sorted(repository_mapping_sources._repository_map.keys())
        assert sources_keys == list_keys

        for list_key, sources_key in zip(list_keys, sources_keys):
            list_repo = repository_mapping_list[list_key]
            sources_repo = repository_mapping_sources[sources_key]
            assert list_repo.enabled == sources_repo.enabled
            assert list_repo.repotype == sources_repo.repotype
            assert list_repo.uri == sources_repo.uri
            assert list_repo.release == sources_repo.release
            assert list_repo.groups == sources_repo.groups
            assert list_repo.gpg_key == sources_repo.gpg_key
            assert (
                list_repo.options  # pyright: ignore[reportUnknownMemberType]
                == sources_repo.options  # pyright: ignore[reportUnknownMemberType]
            )
