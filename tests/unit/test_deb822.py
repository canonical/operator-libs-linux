# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

# pyright: reportPrivateUsage=false

import typing
import unittest
from pathlib import Path
from unittest.mock import ANY, mock_open, patch

from charms.operator_libs_linux.v0 import apt

TEST_DATA_DIR = Path(__file__).parent / "data"
FAKE_APT_DIRS = TEST_DATA_DIR / "fake-apt-dirs"


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
        stanzas = list(apt._iter_deb822_stanzas(lines))
        assert len(stanzas) == 2
        stanza_1, stanza_2 = stanzas
        assert len(stanza_1) == 5
        assert len(stanza_2) == 5
        line_numbers = [n for stanza in stanzas for n, _line in stanza]
        assert len(set(line_numbers)) == len(line_numbers)  # unique line numbers

    def test_iter_deb822_paragraphs_ubuntu_sources_w_comments(self):
        lines = ubuntu_sources_deb822_with_comments.strip().split("\n")
        stanzas = list(apt._iter_deb822_stanzas(lines))
        assert len(stanzas) == 2
        stanza_1, stanza_2 = stanzas
        assert len(stanza_1) == 4
        assert len(stanza_2) == 1
        line_numbers = [n for stanza in stanzas for n, _line in stanza]
        assert len(set(line_numbers)) == len(line_numbers)  # unique line numbers

    def test_get_deb822_options_ubuntu_sources(self):
        lines = ubuntu_sources_deb822.strip().split("\n")
        paras = list(apt._iter_deb822_stanzas(lines))
        opts = [apt._deb822_stanza_to_options(p) for p in paras]
        opts_0, opts_1 = opts
        opts_0_options, _opts_0_line_numbers = opts_0
        opts_1_options, _opts_1_line_numbers = opts_1
        assert opts_0_options == {
            "Types": "deb",
            "URIs": "http://nz.archive.ubuntu.com/ubuntu/",
            "Components": "main restricted universe multiverse",
            "Suites": "noble noble-updates noble-backports",
            "Signed-By": "/usr/share/keyrings/ubuntu-archive-keyring.gpg",
        }
        assert opts_1_options == {
            "Types": "deb",
            "URIs": "http://security.ubuntu.com/ubuntu",
            "Components": "main restricted universe multiverse",
            "Suites": "noble-security",
            "Signed-By": "/usr/share/keyrings/ubuntu-archive-keyring.gpg",
        }

    def test_get_deb822_options_w_comments(self):
        lines = ubuntu_sources_deb822_with_comments.strip().split("\n")
        paras = list(apt._iter_deb822_stanzas(lines))
        opts = [apt._deb822_stanza_to_options(p) for p in paras]
        opts_0, opts_1 = opts
        opts_0_options, _opts_0_line_numbers = opts_0
        opts_1_options, _opts_1_line_numbers = opts_1
        assert opts_0_options == {
            "Components": "main restricted universe multiverse",
            "Types": "deb",
            "URIs": "http://nz.archive.ubuntu.com/ubuntu/",
            "Suites": "noble noble-updates noble-backports",
        }
        assert opts_1_options == {"Foo": "Bar"}

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
        ok_stanza, bad_stanza = apt._iter_deb822_stanzas(lines)
        repos = apt._Deb822Stanza(ok_stanza).repositories
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
            apt._Deb822Stanza(bad_stanza)

    def test_parse_deb822_lines_ubuntu_sources(self):
        lines = ubuntu_sources_deb822.strip().split("\n")
        repos, errors = apt.RepositoryMapping._parse_deb822_lines(lines)
        assert len(repos) == 4
        assert not errors

    def test_parse_deb822_lines_w_comments(self):
        lines = ubuntu_sources_deb822_with_comments.strip().split("\n")
        repos, errors = apt.RepositoryMapping._parse_deb822_lines(lines)
        assert len(repos) == 3
        assert len(errors) == 1
        [error] = errors
        assert isinstance(error, apt.InvalidSourceError)

    def test_init_no_files(self):
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "empty"),
        ):
            repository_mapping = apt.RepositoryMapping()
        assert not repository_mapping._repository_map

    def test_init_with_good_sources_list(self):
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "bionic"),
        ):
            repository_mapping = apt.RepositoryMapping()
        assert repository_mapping._repository_map

    def test_init_with_bad_sources_list_no_fallback(self):
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "noble-no-sources"),
        ):
            with self.assertRaises(apt.InvalidSourceError):
                apt.RepositoryMapping()

    def test_init_with_bad_sources_list_fallback_ok(self):
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "noble"),
        ):
            repository_mapping = apt.RepositoryMapping()
        assert repository_mapping._repository_map

    def test_init_with_bad_ubuntu_sources(self):
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "noble-empty-sources"),
        ):
            with self.assertRaises(apt.InvalidSourceError):
                apt.RepositoryMapping()

    def test_init_with_third_party_inkscape_source(self):
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "noble-with-inkscape"),
        ):
            repository_mapping = apt.RepositoryMapping()
        assert repository_mapping._repository_map

    def test_load_deb822_ubuntu_sources(self):
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "empty"),
        ):
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
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "noble-with-comments-etc"),
        ):
            repository_mapping = apt.RepositoryMapping()
        # TODO: split cases into separate files and test load_deb822 instead
        # this will make things a lot more understandable and maintainable

        assert sorted(repository_mapping._repository_map.keys()) == [
            "deb-http://archive.ubuntu.com/ubuntu/-noble",
            "deb-http://archive.ubuntu.com/ubuntu/-noble-backports",
            "deb-http://archive.ubuntu.com/ubuntu/-noble-updates",
            "deb-http://nz.archive.ubuntu.com/ubuntu/-an/exact/path/",
            "deb-http://nz.archive.ubuntu.com/ubuntu/-noble",
            "deb-http://nz.archive.ubuntu.com/ubuntu/-noble-backports",
            "deb-http://nz.archive.ubuntu.com/ubuntu/-noble-updates",
            "deb-src-http://archive.ubuntu.com/ubuntu/-noble",
            "deb-src-http://archive.ubuntu.com/ubuntu/-noble-backports",
            "deb-src-http://archive.ubuntu.com/ubuntu/-noble-updates",
            "deb-src-http://nz.archive.ubuntu.com/ubuntu/-noble",
            "deb-src-http://nz.archive.ubuntu.com/ubuntu/-noble-backports",
            "deb-src-http://nz.archive.ubuntu.com/ubuntu/-noble-updates",
        ]
        errors = tuple(repository_mapping._last_errors)
        assert len(errors) == 4
        (
            missing_types,
            components_not_ommitted,
            components_not_present,
            bad_enabled_value,
        ) = errors
        assert isinstance(missing_types, apt.MissingRequiredKeyError)
        assert missing_types.key == "Types"
        assert isinstance(components_not_ommitted, apt.BadValueError)
        assert components_not_ommitted.key == "Components"
        assert components_not_ommitted.value == "main"
        assert isinstance(components_not_present, apt.MissingRequiredKeyError)
        assert components_not_present.key == "Components"
        assert isinstance(bad_enabled_value, apt.BadValueError)
        assert bad_enabled_value.key == "Enabled"
        assert bad_enabled_value.value == "bad"

    def test_init_with_deb822(self):
        """Mock file opening to initialise a RepositoryMapping from deb822 and one-line-style.

        They should be equivalent with the sample data being used.
        """
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "noble"),
        ):
            repos_deb822 = apt.RepositoryMapping()

        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "noble-in-one-per-line-format"),
        ):
            repos_one_per_line = apt.RepositoryMapping()

        list_keys = sorted(repos_one_per_line._repository_map.keys())
        sources_keys = sorted(repos_deb822._repository_map.keys())
        assert sources_keys == list_keys

        for list_key, sources_key in zip(list_keys, sources_keys):
            list_repo = repos_one_per_line[list_key]
            sources_repo = repos_deb822[sources_key]
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

    def test_disable_with_deb822(self):
        with patch.object(
            apt.RepositoryMapping,
            "_apt_dir",
            str(FAKE_APT_DIRS / "empty"),
        ):
            repository_mapping = apt.RepositoryMapping()
        repo = apt.DebianRepository(
            enabled=True,
            repotype="deb",
            uri="http://nz.archive.ubuntu.com/ubuntu/",
            release="noble",
            groups=["main", "restricted"],
        )
        repo._deb822_stanza = apt._Deb822Stanza(numbered_lines=[])
        with self.assertRaises(NotImplementedError):
            repository_mapping.disable(repo)
