#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
from urllib.request import urlopen

from charms.operator_libs_linux.v0 import apt
from helpers import get_command_path

logger = logging.getLogger(__name__)


def test_install_package():
    try:
        apt.update()
        apt.add_package("zsh")
        apt.add_package(["golang-cfssl", "jq"])
    except apt.PackageNotFoundError:
        logger.error("A specified package not found in package cache or on system")
    except apt.PackageError as e:
        logger.error(f"Could not install package. Reason: {e.message}")

    assert get_command_path("zsh") == "/usr/bin/zsh"
    assert get_command_path("cfssl") == "/usr/bin/cfssl"
    assert get_command_path("jq") == "/usr/bin/jq"


def test_remove_package():
    # First ensure the package is present
    cfssl = apt.DebianPackage.from_apt_cache("golang-cfssl")
    if not cfssl.present:
        apt.add_package("golang-cfssl")
    assert get_command_path("cfssl") == "/usr/bin/cfssl"
    # Now remove the package and check its bins disappear too
    apt.remove_package("golang-cfssl")
    assert get_command_path("cfssl") == ""


def test_install_package_external_repository():
    repositories = apt.RepositoryMapping()

    # Get the Hashicorp GPG key
    key = urlopen("https://apt.releases.hashicorp.com/gpg").read().decode()

    # Add the hashicorp repository if it doesn't already exist
    if "deb-apt.releases.hashicorp.com-focal" not in repositories:
        line = "deb [arch=amd64] https://apt.releases.hashicorp.com focal main"
        repo = apt.DebianRepository.from_repo_line(line)
        # Import the repository's key
        repo.import_key(key)
        repositories.add(repo)

    apt.update()
    apt.add_package("terraform")

    assert get_command_path("terraform") == "/usr/bin/terraform"


def test_list_file_generation_external_repository():
    repositories = apt.RepositoryMapping()

    # Get the mongo GPG key
    key = urlopen(" https://www.mongodb.org/static/pgp/server-5.0.asc").read().decode()

    # Add the mongo repository if it doesn't already exist
    if "https://repo.mongodb.org/apt/ubuntu" not in repositories:
        line = "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/5.0 multiverse"
        repo = apt.DebianRepository.from_repo_line(line)
        # Import the repository's key
        repo.import_key(key)
        repositories.add(repo)

    apt.update()
    apt.add_package("mongodb-org")

    assert get_command_path("mongod") == "/usr/bin/mongod"
