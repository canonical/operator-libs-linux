# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

# pyright: reportPrivateUsage=false

import typing
import unittest
from unittest.mock import ANY, mock_open, patch

from charms.operator_libs_linux.v0 import apt

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

inkscape_sources_deb822 = """
Types: deb
URIs: https://ppa.launchpadcontent.net/inkscape.dev/stable/ubuntu/
Suites: noble
Components: main
Signed-By:
 -----BEGIN PGP PUBLIC KEY BLOCK-----
 .
 mQINBGY0ViQBEACsQsdIRXzyEkk38x2oDt1yQ/Kt3dsiDKJFNLbs/xiDHrgIW6cU
 1wZB0pfb3lCyG3/ZH5uvR0arCSHJvCvkdCFTqqkZndSA+/pXreCSLeP8CNawf/RM
 3cNbdJlE8jXzaX2qzSEC9FDNqu4cQHIHR7xMAbSCPW8rxKvRCWmkZccfndDuQyN2
 vg3b2x9DWKS3DBRffivglF3yT49OuLemG5qJHujKOmNJZ32JoRniIivsuk1CCS1U
 NDK6xWkr13aNe056QhVAh2iPF6MRE85zail+mQxt4LAgl/aLR0JSDSpWkbQH7kbu
 5cJVan8nYF9HelVJ3QuMwdz3VQn4YVO2Wc8s0YfnNdQttYaUx3lz35Fct6CaOqjP
 pgsZ4467lmB9ut74G+wDCQXmT232hsBkTz4D0DyVPB/ziBgGWUKti0AWNT/3kFww
 2VM/80XADaDz0Sc/Hzi/cr9ZrbW3drMwoVvKtfMtOT7FMbeuPRWZKYZnDbvNm62e
 ToKVudE0ijfsksxbcHKmGdvWntCxlinp0i39Jfz6y54pppjmbHRQgasmqm2EQLfA
 RUNW/zB7gX80KTUCGjcLOTPajBIN5ZfjVITetryAFjv7fnK0qpf2OpqwF832W4V/
 S3GZtErupPktYG77Z9jOUxcJeEGYjWbVlbit8mTKDRdQUXOeOO6TzB4RcwARAQAB
 tCVMYXVuY2hwYWQgUFBBIGZvciBJbmtzY2FwZSBEZXZlbG9wZXJziQJOBBMBCgA4
 FiEEVr3/0vHJaz0VdeO4XJoLhs0vyzgFAmY0ViQCGwMFCwkIBwIGFQoJCAsCBBYC
 AwECHgECF4AACgkQXJoLhs0vyzh3RBAAo7Hee8i2I4n03/iq58lqml/OVJH9ZEle
 amk3e0wsiVS0QdT/zB8/AMVDB1obazBfrHKJP9Ck+JKH0uxaGRxYBohTbO3Y3sBO
 qRHz5VLcFzuyk7AA53AZkNx8Zbv6D0O4JTCPDJn9Gwbd/PpnvJm9Ri+zEiVPhXNu
 oSBryGM09un2Yvi0DA+ulouSKTy9dkbI1R7flPZ2M/mKT8Lk0n1pJu5FvgPC4E6R
 PT0Njw9+k/iHtP76U4SqHJZZx2I/TGlXMD1memyTK4adWZeGLaAiFadsoeJsDoDE
 MkHFxFkr9n0E4wJhRGgL0OxDWugJemkUvHbzXFNUaeX5Spw/aO7r1CtTh8lyqiom
 4ebAkURjESRFOFzcsM7nyQnmt2OgQkEShSL3NrDMkj1+3+FgQtd8sbeVpmpGBq87
 J3iq0YMsUysWq8DJSz4RnBTfeGlJWJkl3XxB9VbG3BqqbN9fRp+ccgZ51g5/DEA/
 q8jYS7Ur5bAlSoeA4M3SvKSlQM8+aT35dteFzejvo1N+2n0E0KoymuRsDBdzby0z
 lJDKe244L5D6UPJo9YTmtE4kG/fGNZ5/JdRA+pbe7f/z84HVcJ3ziGdF/Nio/D8k
 uFjZP2M/mxC7j+WnmKAruqmY+5vkAEqUPTobsloDjT3B+z0rzWk8FG/G5KFccsBO
 2ekz6IVTXVA=
 =VF33
 -----END PGP PUBLIC KEY BLOCK-----
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
            "Missing required entry 'Types' for entry starting on line 12 in FILENAME.",
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

