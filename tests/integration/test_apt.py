#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
import os
import subprocess
from pathlib import Path
from typing import List
from urllib.request import urlopen

from charms.operator_libs_linux.v0 import apt
from helpers import get_command_path

logger = logging.getLogger(__name__)

KEY_DIR = Path(__file__).parent / "keys"


def test_install_packages():
    apt.update()
    apt.add_package("zsh")
    assert get_command_path("zsh") == "/usr/bin/zsh"
    apt.add_package(["golang-cfssl", "jq"])
    assert get_command_path("cfssl") == "/usr/bin/cfssl"
    assert get_command_path("jq") == "/usr/bin/jq"


def test_install_package_error():
    package = apt.DebianPackage(
        name="ceci-n'est-pas-un-paquet",
        version="1.0",
        epoch="",
        arch="amd64",
        state=apt.PackageState.Available,
    )
    try:
        package.ensure(apt.PackageState.Present)
    except apt.PackageError as e:
        assert "Unable to locate package" in str(e)


def test_remove_package():
    # First ensure the package is present
    cfssl = apt.DebianPackage.from_apt_cache("golang-cfssl")
    assert not cfssl.present
    # Add package
    apt.add_package("golang-cfssl")
    assert get_command_path("cfssl")
    subprocess.run(["cfssl", "version"], check=True)
    # Now remove the package and check its bins disappear too
    apt.remove_package("golang-cfssl")
    assert not get_command_path("cfssl")


def test_install_package_from_external_repository():
    repo_id = "deb-https://repo.mongodb.org/apt/ubuntu-jammy/mongodb-org/8.0"
    repos = apt.RepositoryMapping()
    assert repo_id not in repos
    assert not get_command_path("mongod")
    ## steps
    key = urlopen("https://www.mongodb.org/static/pgp/server-8.0.asc").read().decode()
    key_file = apt.import_key(key)
    line = (
        "deb [ arch=amd64,arm64 signed-by={} ]"
        " https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/8.0 multiverse"
    ).format(key_file)
    ## if: use implicit write_file
    repo = apt.DebianRepository.from_repo_line(line)  # write_file=True by default
    assert repo_id not in repos
    ## if: don't use implicit write_file
    # repo = apt.DebianRepository.from_repo_line(line, write_file=False)
    # repos.add(repo)
    # assert repo_id in repos
    ## fi
    assert repo_id in apt.RepositoryMapping()
    apt.update()
    apt.add_package("mongodb-org")
    assert get_command_path("mongod")
    subprocess.run(["mongod", "--version"], check=True)
    ## cleanup
    os.remove(key_file)
    apt._add_repository(repo, remove=True)  # pyright: ignore[reportPrivateUsage]
    assert repo_id not in apt.RepositoryMapping()
    apt.update()
    apt.remove_package("mongodb-org")
    assert get_command_path("mongod")  # mongodb-org is a metapackage
    subprocess.run(["apt", "autoremove"], check=True)
    assert not get_command_path("mongod")


def test_install_higher_version_package_from_external_repository():
    repo_id = "deb-https://ppa.launchpadcontent.net/fish-shell/release-3/ubuntu/-jammy"
    repos = apt.RepositoryMapping()
    assert repo_id not in repos
    ## version before
    if not get_command_path("fish"):
        apt.add_package("fish")
    assert get_command_path("fish")
    version_before = subprocess.run(
        ["fish", "--version"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    apt.remove_package("fish")
    assert not get_command_path("fish")
    ## steps
    repo = apt.DebianRepository(
        enabled=True,
        repotype="deb",
        uri="https://ppa.launchpadcontent.net/fish-shell/release-3/ubuntu/",
        release="jammy",
        groups=["main"],
    )
    repos.add(repo)  # update_cache=False by default
    assert repo_id in repos
    assert repo_id in apt.RepositoryMapping()
    key_file = apt.import_key((KEY_DIR / "FISH_KEY.asc").read_text())
    apt.update()
    apt.add_package("fish")
    assert get_command_path("fish")
    version_after = subprocess.run(
        ["fish", "--version"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    assert version_after > version_before  # lexical comparison :(
    ## cleanup
    os.remove(key_file)
    apt._add_repository(repo, remove=True)  # pyright: ignore[reportPrivateUsage]
    assert repo_id not in apt.RepositoryMapping()
    apt.update()
    apt.remove_package("fish")
    assert not get_command_path("fish")


def test_install_hardware_observer_ssacli():
    """Test the ability to install a package used by the hardware-observer charm.

    Here we follow the order of operations and arguments used in the charm:
        for key in HP_KEYS:
            apt.import_key(key)

        repositories = apt.RepositoryMapping()
        repo = apt.DebianRepository.from_repo_line(...)
        repositories.add(repo)

        apt.add_package(self.pkg, update_cache=True)
    """
    line = "deb https://downloads.linux.hpe.com/SDR/repo/mcp stretch/current non-free"
    repo_id = apt._repo_to_identifier(  # pyright: ignore[reportPrivateUsage]
        apt.DebianRepository.from_repo_line(line, write_file=False)
    )
    assert repo_id not in apt.RepositoryMapping()
    assert not get_command_path("ssacli")
    key_files: List[str] = []  # just for cleanup
    ## steps
    for path in (
        KEY_DIR / "HPEPUBLICKEY2048_KEY1.asc",
        KEY_DIR / "HPPUBLICKEY2048_KEY1.asc",
        KEY_DIR / "HPPUBLICKEY2048.asc",
        KEY_DIR / "HPPUBLICKEY1024.asc",
    ):
        key_file = apt.import_key(path.read_text())
        key_files.append(key_file)
    repos = apt.RepositoryMapping()
    repo = apt.DebianRepository.from_repo_line(line)  # write_file=True by default
    assert repo_id in apt.RepositoryMapping()
    # repo added to system but repos doesn't know about it yet
    assert repo_id not in repos
    repos.add(repo)
    assert repo_id in repos
    # `add` call is redundant with `from_repo_line` from system pov
    # but adds an entry to the RepositoryMapping
    apt.add_package("ssacli", update_cache=True)
    # apt.update not required since update_cache=True
    assert get_command_path("ssacli")
    ## cleanup
    for key_file in key_files:
        os.remove(key_file)
    apt._add_repository(repo, remove=True)  # pyright: ignore[reportPrivateUsage]
    assert repo_id not in apt.RepositoryMapping()
    apt.update()
    apt.remove_package("ssacli")
    assert not get_command_path("ssacli")


def test_from_apt_cache_error():
    try:
        apt.DebianPackage.from_apt_cache("ceci-n'est-pas-un-paquet")
    except apt.PackageError as e:
        assert "No packages found" in str(e)
