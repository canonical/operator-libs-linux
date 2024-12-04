# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

# pyright: reportPrivateUsage=false

import itertools
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from charms.operator_libs_linux.v0 import apt

TEST_DATA_DIR = Path(__file__).parent / "data"
FAKE_APT_DIRS = TEST_DATA_DIR / "fake-apt-dirs"
SOURCES_DIR = TEST_DATA_DIR / "individual-files"


@pytest.fixture
def repo_mapping():
    with patch.object(
        apt.RepositoryMapping,
        "_apt_dir",
        str(FAKE_APT_DIRS / "empty"),
    ):
        repository_mapping = apt.RepositoryMapping()
    return repository_mapping


def test_init_no_files():
    with patch.object(
        apt.RepositoryMapping,
        "_apt_dir",
        str(FAKE_APT_DIRS / "empty"),
    ):
        repository_mapping = apt.RepositoryMapping()
    assert not repository_mapping._repository_map


def test_init_with_good_sources_list():
    with patch.object(
        apt.RepositoryMapping,
        "_apt_dir",
        str(FAKE_APT_DIRS / "bionic"),
    ):
        repository_mapping = apt.RepositoryMapping()
    assert repository_mapping._repository_map


def test_init_with_bad_sources_list_no_fallback():
    with patch.object(
        apt.RepositoryMapping,
        "_apt_dir",
        str(FAKE_APT_DIRS / "noble-no-sources"),
    ):
        with pytest.raises(apt.InvalidSourceError):
            apt.RepositoryMapping()


def test_init_with_bad_sources_list_fallback_ok():
    with patch.object(
        apt.RepositoryMapping,
        "_apt_dir",
        str(FAKE_APT_DIRS / "noble"),
    ):
        repository_mapping = apt.RepositoryMapping()
    assert repository_mapping._repository_map


def test_init_with_bad_ubuntu_sources():
    with patch.object(
        apt.RepositoryMapping,
        "_apt_dir",
        str(FAKE_APT_DIRS / "noble-empty-sources"),
    ):
        with pytest.raises(apt.InvalidSourceError):
            apt.RepositoryMapping()


def test_init_with_third_party_inkscape_source():
    with patch.object(
        apt.RepositoryMapping,
        "_apt_dir",
        str(FAKE_APT_DIRS / "noble-with-inkscape"),
    ):
        repository_mapping = apt.RepositoryMapping()
    assert repository_mapping._repository_map


def test_init_w_comments():
    with patch.object(
        apt.RepositoryMapping,
        "_apt_dir",
        str(FAKE_APT_DIRS / "noble-with-comments-etc"),
    ):
        repository_mapping = apt.RepositoryMapping()
    assert repository_mapping._repository_map


def test_deb822_format_equivalence():
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


def test_load_deb822_missing_components(repo_mapping: apt.RepositoryMapping):
    with pytest.raises(apt.InvalidSourceError):
        repo_mapping.load_deb822(
            str(SOURCES_DIR / "bad-stanza-components-missing-without-exact-path.sources")
        )
    assert len(repo_mapping._last_errors) == 1
    [error] = repo_mapping._last_errors
    assert isinstance(error, apt.MissingRequiredKeyError)
    assert error.key == "Components"


def test_load_deb822_components_with_exact_path(repo_mapping: apt.RepositoryMapping):
    with pytest.raises(apt.InvalidSourceError):
        repo_mapping.load_deb822(
            str(SOURCES_DIR / "bad-stanza-components-present-with-exact-path.sources")
        )
    assert len(repo_mapping._last_errors) == 1
    [error] = repo_mapping._last_errors
    assert isinstance(error, apt.BadValueError)
    assert error.key == "Components"


def test_load_deb822_bad_enabled_value(repo_mapping: apt.RepositoryMapping):
    with pytest.raises(apt.InvalidSourceError):
        repo_mapping.load_deb822(str(SOURCES_DIR / "bad-stanza-enabled-bad.sources"))
    assert len(repo_mapping._last_errors) == 1
    [error] = repo_mapping._last_errors
    assert isinstance(error, apt.BadValueError)
    assert error.key == "Enabled"


def test_load_deb822_missing_required_keys(repo_mapping: apt.RepositoryMapping):
    with pytest.raises(apt.InvalidSourceError):
        repo_mapping.load_deb822(str(SOURCES_DIR / "bad-stanza-missing-required-keys.sources"))
    assert len(repo_mapping._last_errors) == 1
    [error] = repo_mapping._last_errors
    assert isinstance(error, apt.MissingRequiredKeyError)
    assert error.key in ("Types", "URIs", "Suites")


def test_load_deb822_comments(repo_mapping: apt.RepositoryMapping):
    filename = str(SOURCES_DIR / "good-stanza-comments.sources")
    repo_mapping.load_deb822(filename)
    repotypes = ("deb", "deb-src")
    uris = ("http://nz.archive.ubuntu.com/ubuntu/", "http://archive.ubuntu.com/ubuntu/")
    suites = ("noble", "noble-updates", "noble-backports")
    assert len(repo_mapping) == len(repotypes) * len(uris) * len(suites)
    for repo, (repotype, uri, suite) in zip(
        repo_mapping, itertools.product(repotypes, uris, suites)
    ):
        assert isinstance(repo, apt.DebianRepository)
        assert repo.enabled
        assert repo.repotype == repotype
        assert repo.uri == uri
        assert repo.release == suite
        assert repo.groups == ["main", "restricted", "universe", "multiverse"]
        assert repo.filename == filename
        assert repo.gpg_key == ""


def test_load_deb822_enabled_no(repo_mapping: apt.RepositoryMapping):
    filename = str(SOURCES_DIR / "good-stanza-enabled-no.sources")
    repo_mapping.load_deb822(filename)
    for repo in repo_mapping:
        assert isinstance(repo, apt.DebianRepository)
        assert not repo.enabled


def test_load_deb822_exact_path(repo_mapping: apt.RepositoryMapping):
    filename = str(SOURCES_DIR / "good-stanza-exact-path.sources")
    repo_mapping.load_deb822(filename)
    [repo] = repo_mapping
    assert isinstance(repo, apt.DebianRepository)
    assert repo.uri
    assert repo.release.endswith("/")
    assert not repo.groups


def test_load_deb822_fully_commented_out_stanzas(repo_mapping: apt.RepositoryMapping):
    with pytest.raises(apt.InvalidSourceError):
        repo_mapping.load_deb822(str(SOURCES_DIR / "stanzas-fully-commented-out.sources"))
    assert not repo_mapping._repository_map
    assert not repo_mapping._last_errors  # no individual errors, just no good entries


def test_load_deb822_one_good_stanza_one_bad(repo_mapping: apt.RepositoryMapping):
    repo_mapping.load_deb822(str(SOURCES_DIR / "stanzas-one-good-one-bad-comments.sources"))
    repos = repo_mapping._repository_map.values()
    errors = repo_mapping._last_errors
    assert len(repos) == 1  # one good stanza defines one repository
    assert len(errors) == 1  # one stanza was bad
    [error] = errors
    assert isinstance(error, apt.MissingRequiredKeyError)


def test_load_deb822_ubuntu_sources(repo_mapping: apt.RepositoryMapping):
    assert not repo_mapping._repository_map
    repo_mapping.load_deb822(str(SOURCES_DIR / "stanzas-noble.sources"))
    assert sorted(repo_mapping._repository_map.keys()) == [
        "deb-http://nz.archive.ubuntu.com/ubuntu/-noble",
        "deb-http://nz.archive.ubuntu.com/ubuntu/-noble-backports",
        "deb-http://nz.archive.ubuntu.com/ubuntu/-noble-updates",
        "deb-http://security.ubuntu.com/ubuntu-noble-security",
    ]
    assert not repo_mapping._last_errors


def test_load_deb822_with_gpg_key(repo_mapping: apt.RepositoryMapping):
    filename = str(SOURCES_DIR / "good-stanza-with-gpg-key.sources")
    repo_mapping.load_deb822(filename)
    [repo] = repo_mapping
    assert isinstance(repo, apt.DebianRepository)
    # DebianRepository.gpg_key is expected to be a string file path
    # the inkscape sources file provides the key inline
    # in this case the library imports the key to a file on first access
    with tempfile.TemporaryDirectory() as tmpdir:
        assert not list(Path(tmpdir).iterdir())
        with patch.object(apt, "_GPG_KEY_DIR", tmpdir):
            inkscape_key_file = repo.gpg_key
        key_paths = list(Path(tmpdir).iterdir())
        assert len(key_paths) == 1
        [key_path] = key_paths
        assert Path(inkscape_key_file).name == key_path.name
        assert Path(inkscape_key_file).parent == key_path.parent
    # the filename is cached for subsequent access
    with tempfile.TemporaryDirectory() as tmpdir:
        assert not list(Path(tmpdir).iterdir())
        with patch.object(apt, "_GPG_KEY_DIR", tmpdir):
            inkscape_key_file_cached = repo.gpg_key
        assert not list(Path(tmpdir).iterdir())
    assert inkscape_key_file == inkscape_key_file_cached


def test_load_deb822_stanza_ubuntu_main_etc(repo_mapping: apt.RepositoryMapping):
    filename = str(SOURCES_DIR / "good-stanza-noble-main-etc.sources")
    repo_mapping.load_deb822(filename)
    assert len(repo_mapping) == 3
    for repo, suite in zip(repo_mapping, ("noble", "noble-updates", "noble-backports")):
        assert isinstance(repo, apt.DebianRepository)
        assert repo.enabled
        assert repo.repotype == "deb"
        assert repo.uri == "http://nz.archive.ubuntu.com/ubuntu/"
        assert repo.release == suite
        assert repo.groups == ["main", "restricted", "universe", "multiverse"]
        assert repo.filename == filename
        assert repo.gpg_key == "/usr/share/keyrings/ubuntu-archive-keyring.gpg"


def test_load_deb822_stanza_ubuntu_security(repo_mapping: apt.RepositoryMapping):
    filename = str(SOURCES_DIR / "good-stanza-noble-security.sources")
    repo_mapping.load_deb822(filename)
    assert len(repo_mapping) == 1
    [repo] = repo_mapping
    assert isinstance(repo, apt.DebianRepository)
    assert repo.enabled
    assert repo.repotype == "deb"
    assert repo.uri == "http://security.ubuntu.com/ubuntu"
    assert repo.release == "noble-security"
    assert repo.groups == ["main", "restricted", "universe", "multiverse"]
    assert repo.filename == filename
    assert repo.gpg_key == "/usr/share/keyrings/ubuntu-archive-keyring.gpg"


def test_disable_with_deb822(repo_mapping: apt.RepositoryMapping):
    repo = apt.DebianRepository(
        enabled=True,
        repotype="deb",
        uri="http://nz.archive.ubuntu.com/ubuntu/",
        release="noble",
        groups=["main", "restricted"],
    )
    repo._deb822_stanza = apt._Deb822Stanza(numbered_lines=[])
    with pytest.raises(NotImplementedError):
        repo_mapping.disable(repo)


def test_add_with_deb822(repo_mapping: apt.RepositoryMapping):
    with (SOURCES_DIR / "good-stanza-exact-path.sources").open() as f:
        repos, errors = repo_mapping._parse_deb822_lines(f)
    assert len(repos) == 1
    assert not errors
    [repo] = repos
    identifier = apt._repo_to_identifier(repo)
    with patch.object(apt.subprocess, "run") as mock_run_1:
        repo_mapping.add(repo)
    assert identifier in repo_mapping
    mock_run_1.assert_called_once_with(
        [
            "add-apt-repository",
            "--yes",
            "--sourceslist=deb http://nz.archive.ubuntu.com/ubuntu/ an/exact/path/ ",
            "--no-update",
        ],
        check=True,
        capture_output=True,
    )
    # we re-raise CalledProcessError after logging
    error = apt.CalledProcessError(1, "cmd")
    error.stdout = error.stderr = b""
    with patch.object(apt.logger, "error") as mock_logging_error:
        with patch.object(apt.subprocess, "run", side_effect=error):
            with pytest.raises(apt.CalledProcessError):
                repo_mapping.add(repo)
    mock_logging_error.assert_called_once()
    # call add with a disabled repository
    repo._enabled = False
    with pytest.raises(ValueError):
        repo_mapping.add(repo)
