#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
import subprocess
from urllib.request import urlopen

from charms.operator_libs_linux.v0 import apt
from helpers import get_command_path

logger = logging.getLogger(__name__)
INKSCAPE_KEY = """
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


def test_install_hardware_observer_ssacli():
    _line = "deb http://downloads.linux.hpe.com/SDR/repo/mcp stretch/current non-free"


def test_install_package_from_external_repository():
    repo_id = "deb-https://repo.mongodb.org/apt/ubuntu-jammy/mongodb-org/8.0"
    repos_before = apt.RepositoryMapping()
    assert repo_id not in repos_before
    assert not get_command_path("mongod")

    key = urlopen("https://www.mongodb.org/static/pgp/server-8.0.asc").read().decode()
    line = "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/8.0 multiverse"
    ## this is one valid order of operations:
    ## apt.import_key(...)  # before add
    ## apt.RepositoryMapping.add(repo, update_cache=True)
    ## apt.add_package(...)
    apt.import_key(key)
    ## if: use implicit write_file
    repo = apt.DebianRepository.from_repo_line(line)
    apt.update()
    repos_after = apt.RepositoryMapping()
    ## if: don't use implicit write_file
    # repo = apt.DebianRepository.from_repo_line(line, write_file=False)
    # repos_after = repos_before.add(repo, update_cache=True)
    ## fi
    assert repo_id in repos_after
    apt.add_package("mongodb-org")
    assert get_command_path("mongod")
    subprocess.run(["mongod", "--version"], check=True)

    ## cleanup
    apt.remove_package("mongodb-org", autoremove=True)  # mongodb-org is a metapackage
    assert not get_command_path("mongod")
    repos_after._remove(repo, update_cache=False)  # pyright: ignore[reportPrivateUsage]
    assert repo_id not in repos_after
    apt.update()
    repos_clean = apt.RepositoryMapping()
    assert repo_id not in repos_clean


def test_install_higher_version_package_from_external_repository():
    repo_id = "deb-https://ppa.launchpadcontent.net/inkscape.dev/stable/ubuntu/-jammy"
    repos_before = apt.RepositoryMapping()
    assert repo_id not in repos_before

    # version before
    if not get_command_path("inkscape"):
        apt.add_package("inkscape")
    version_before = subprocess.run(
        ["inkscape", "--version"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    apt.remove_package("inkscape")
    assert not get_command_path("inkscape")

    repo = apt.DebianRepository(
        enabled=True,
        repotype="deb",
        uri="https://ppa.launchpadcontent.net/inkscape.dev/stable/ubuntu/",
        release="jammy",
        groups=["main"],
    )
    ## this is a different, valid order of operations:
    ## apt.RepositoryMapping.add(..., update_cache=False)
    ## apt.import_key(...)  # before update but after add
    ## apt.update()
    ## apt.add_package(...)
    repos_after = repos_before.add(repo, update_cache=False)  # default update_cache option
    assert repo_id in repos_after
    apt.import_key(INKSCAPE_KEY)
    apt.update()
    apt.add_package("inkscape")
    assert get_command_path("inkscape")
    version_after = subprocess.run(
        ["inkscape", "--version"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    assert version_after > version_before  # lexical comparison :(

    ## cleanup
    apt.remove_package("inkscape")
    assert not get_command_path("inkscape")
    repos_clean = repos_after._remove(  # pyright: ignore[reportPrivateUsage]
        repo, update_cache=True
    )
    assert repo_id not in repos_clean


def test_from_apt_cache_error():
    try:
        apt.DebianPackage.from_apt_cache("ceci-n'est-pas-un-paquet")
    except apt.PackageError as e:
        assert "No packages found" in str(e)
