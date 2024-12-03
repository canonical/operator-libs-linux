#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
import os
import subprocess
from typing import List
from urllib.request import urlopen

from charms.operator_libs_linux.v0 import apt
from helpers import get_command_path

logger = logging.getLogger(__name__)


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
    """Test the ability to install a package used by the hardware-observer charm.

    Here we follow the order of operations and arguments used in the charm:
        for key in HP_KEYS:
            apt.import_key(key)

        repositories = apt.RepositoryMapping()
        repo = apt.DebianRepository.from_repo_line(...)
        repositories.add(repo)

        apt.add_package(self.pkg, update_cache=True)
    """
    line = "deb http://downloads.linux.hpe.com/SDR/repo/mcp stretch/current non-free"
    repo_id = apt.DebianRepository.from_repo_line(
        line, write_file=False
    )._get_identifier()  # pyright: ignore[reportPrivateUsage]
    repos_before = apt.RepositoryMapping()
    assert repo_id not in repos_before
    assert not get_command_path("ssacli")

    key_files: List[str] = []  # just for cleanup
    ## begin steps
    for key in HP_KEYS:
        key_file = apt.import_key(key)
        key_files.append(key_file)
    repositories = apt.RepositoryMapping()
    repo = apt.DebianRepository.from_repo_line(line)  # write_file=True by default
    # repo added to system but repositories doesn't know about it yet
    assert repo_id not in repositories
    repositories.add(repo)  # update_cache=False by default
    # `add` call is redundant with `from_repo_line` from system pov
    # but it does add an entry to the RepositoryMapping
    assert repo_id in repositories
    apt.add_package("ssacli", update_cache=True)
    assert get_command_path("ssacli")
    # install succeed here as update_cache=True
    ## end steps

    ## cleanup
    for key_file in key_files:
        os.remove(key_file)
    repos_clean = repositories._remove(  # pyright: ignore[reportPrivateUsage]
        repo, update_cache=True
    )
    assert repo_id not in repos_clean
    apt.remove_package("ssacli")
    assert not get_command_path("ssacli")


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
    key_file = apt.import_key(key)
    ## if: use implicit write_file
    repo = apt.DebianRepository.from_repo_line(line)  # write_file=True by default
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
    os.remove(key_file)
    repos_after._remove(repo, update_cache=False)  # pyright: ignore[reportPrivateUsage]
    assert repo_id not in repos_after
    repos_before_update = apt.RepositoryMapping()
    assert repo_id in repos_before_update  # update hasn't been called yet!
    apt.update()
    repos_clean = apt.RepositoryMapping()
    assert repo_id not in repos_clean
    apt.remove_package("mongodb-org", autoremove=True)  # mongodb-org is a metapackage
    assert not get_command_path("mongod")


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
    repos_after = repos_before.add(repo)  # update_cache=False by default
    assert repo_id in repos_after
    key_file = apt.import_key(INKSCAPE_KEY)
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
    os.remove(key_file)
    repos_clean = repos_after._remove(  # pyright: ignore[reportPrivateUsage]
        repo, update_cache=True
    )
    assert repo_id not in repos_clean
    apt.remove_package("inkscape")
    assert not get_command_path("inkscape")


def test_from_apt_cache_error():
    try:
        apt.DebianPackage.from_apt_cache("ceci-n'est-pas-un-paquet")
    except apt.PackageError as e:
        assert "No packages found" in str(e)


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
"""Static parameters for keys."""

HPPUBLICKEY1024 = """
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1.4.0 (MingW32)

mQGiBEIxWpoRBADb06sJgnD7MJnm2Ny1nmTFLDSZ8vkubP+pmfn9N9TE26oit+KI
OnVTRVbSPl3F15wTjSBGR453MEfnzp1NrMk1GIa/m1nKAmgQ4t1714C4jQab0to+
gP51XhPhtAGt7BggorQw2RXa4KdTCh8ByOIaDKRYcESmMazSZ+Pscy2XRwCgm771
21RCM0RcG2dmHZZgKH8fTscD/RiY3CHI2jJl9WosIYXbZpOySzrLn0lRCRdNdpew
Y5m1f3lhqoSvJk7pXjs4U+3XlOlUhgWl5HiXuWSVyPu2ilfGdfgpJslawI85fBQg
Ul5kcrjLHHsApeG8oGStFJE2JAc+0D+whmGmJbjWKwuZJmgpm9INplA4h1BYJbx+
6A3MBACFiMTttDPpJ+5eWr1VSZwxCZNqvPWmjpL5Nh9F8xzE7q+ad2CFKSebvRrv
Jf7Y2m+wY9bmo5nJ3wHYEX3Aatt+QVF10G6wTdIz/Ohm/Pc4Li4NhzYOv7FKxVam
97UN0O8Rsl4GhE2eE8H+Q3QYFvknAWoTj3Rq3/A5FA6FsRFhxbQwSGV3bGV0dC1Q
YWNrYXJkIENvbXBhbnkgKEhQIENvZGVzaWduaW5nIFNlcnZpY2UpiGQEExECACQF
AkIxWpoCGwMFCRLMAwAGCwkIBwMCAxUCAwMWAgECHgECF4AACgkQUnvFOiaJuIc1
2wCgj2UotUgSegPHmcKdApY+4WFaz/QAnjI58l5bDD8eElBCErHVoq9uPMczuQIN
BEIxWqUQCADnBXqoU8QeZPEy38oI0GrN2q7nvS+4UBQeIRVy8x+cOqDRDcE8PHej
7NtxP698U0WFGK47GszjiV4WTnvexuJk0B5AMEBHana8fVj7uRUcmyYZqOZd7EXn
Q3Ivi8itfkTICkhZi7bmGsSF0iJ0eAI5n2bCqJykNQvJ6a3dWJKP8EgaBCZj+TGL
WWJHDZsrn8g4BeaNS/MbmsCLAk8N6bWMGzAKfgxUraMCwuZ9fVyHFavHdeChUtna
qnF4uw0hHLaGWmTJjziXVvVC1a8+inTxPZkVpAvD0A+/LNlkP7TtAdaVOJqv3+a3
ybMQL851bRTFyt+H0XGHhzhhtuu9+DyfAAMFCADRWGxIfniVG7O4wtwLD3sWzR/W
LmFlJYu4s9rSDgn3NDjigQzZoVtbuv3Z9IZxBMoYa50MuybuVDp55z/wmxvYoW2G
25kOFDKx/UmkKkUBLdokb5V1p9j5SJorGBSfsNAHflhmBhyuMP4CDISbBUSN7oO1
Oj41jNxpqhy+8ayygSVcTNwMe909J/HdC//xFANLDhjKPf3ZAulWNhOvjTlpF46B
yt1l8ZNinIeE7CFL7H+LlMl2Ml6wsOkrxsSauBis6nER4sYVqrMdzpUU2Sr2hj6Q
sJ+9TS+IURcnxL/M851KCwLhwZKdphQjT3mXXsoCx/l3rI6cxpwYgjiKiZhOiE8E
GBECAA8FAkIxWqUCGwwFCRLMAwAACgkQUnvFOiaJuIenewCdHcEvMxBYprqRjKUw
04EypyFtZTgAn0wds0nbpd2+VZ5WHbVRfU4y5Y5Y
=+cX+
-----END PGP PUBLIC KEY BLOCK-----
"""

HPPUBLICKEY2048 = """
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1.4.10 (MingW32)

mQENBFC+QboBCAC1bodHD7AmR00SkDMB4u9MXy+Z5vv8wbmGRaKDBYScpAknOljX
d5tBADffAetd1hgLnrLKN8vHdIsYkmUyeEeEsnIUKtwvbx/f6PoZZPOIIIRh1d2W
Mjw9qXIE+tgr2gWlq0Gi5BZzaKse1+khRQ2rewJBppblSGWgcmCMIq8OwAsrdbtr
z7+37c/g/Y2VfAahc23YZW9LQ5MiaI4nS4JMZbWPYtBdF78B/D2t5FvmvDG0Cgjk
Qi1U9IVjiFKixuoi6nRsvBLFYL/cI+vo4iyUC5x7qmKd8gN7A030gS67VrleNRki
q0vaF6J46XpIl4o58t23FSAKKRbTwavYzdMpABEBAAG0NEhld2xldHQtUGFja2Fy
ZCBDb21wYW55IFJTQSAoSFAgQ29kZXNpZ25pbmcgU2VydmljZSmJAT4EEwECACgF
AlC+QboCGwMFCRLMAwAGCwkIBwMCBhUIAgkKCwQWAgMBAh4BAheAAAoJELBwaApc
4tR2x7sH/A3D4XxEEyrX6Z3HeWSSA80+n+r5QwfXm5unxsWEL3JyNg6sojlrJY4K
8k4ih4nkY4iblChTCSQwnqKXqkL5U+RIr+AJoPx+55M98u4eRTVYMHZD7/jFq85z
ZFGUkFkars9E2aRzWhqbz0LINb9OUeX0tT5qQseHflO2PaJykxNPC14WhsBKC2lg
dZWnGhO5QJFp69AnSp4k+Uo/1LMk87YEJIL1NDR0lrlKgRvFfFyTpRBt+Qb1Bb7g
rjN0171g8t5GaPWamN3Oua/v4aZg15f3xydRF8y9TsYjiNz+2TzRjKv7AkpZaJST
06CqMjCgiZ6UFFGN0/oqLnwxdP3Mmh4=
=aphN
-----END PGP PUBLIC KEY BLOCK-----
"""

HPPUBLICKEY2048_KEY1 = """
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1.4.12 (MingW32)

mQENBFRtGAgBCADlSku65P14hVdx9E/W0n6MwuB3WGqmsyKNoa3HezFdMjWERldI
NNUdi8O28cZ6j2+Hi9L1HeQIQ9+7FHpR3JyQePBJtRX8WSEusfRtML98opDhJxKm
8Jyxb7aTvCwdNHz3yxADINkMtOj5oRm7VCr8XHkG7YU27ELs8B+BXWvjO21oSosi
FurnhT+H3hQsYXfYA55aa21q0qX+L5dFJSNdzZVo7m9ybioVv2R5+PfBvdaSxCnm
OpcGXFaKAsqVHeTW0pd3sdkin1rkbhOBaU5lFBt2ZiMtKpKHpT8TZnqHpFHFbgi8
j2ARJj4IDct2OGILddUIZSFyue6WE2hpV5c/ABEBAAG0OEhld2xldHQtUGFja2Fy
ZCBDb21wYW55IFJTQSAoSFAgQ29kZXNpZ25pbmcgU2VydmljZSkgLSAxiQE+BBMB
AgAoBQJUbRgIAhsDBQkSzAMABgsJCAcDAgYVCAIJCgsEFgIDAQIeAQIXgAAKCRD6
3Y1ksSdeo6BJCADOfIPPLPpIOnFK9jH4t8lLUd+RyMc+alA3uTDPUJa/ZHa6DHfh
42iaPYVEV8OG0tnbMlHmwvsZ5c1/MRMw1UbxCvD88P2qM4SUrUjQUlSCms2GLGvF
ftFXBiOJQ7/yBc9o+yoSvwPrrTxSCk4+Sqm0IfVXVzChDM9dM9YPY2Vzjd+LUaYC
3X+eSuggUDO0TmJLJd7tZdF9fVXq3lr63BZ5PY98MTCuOoeSMDa9FIUQf6vn6UUJ
MDSRZ9OzhpNJOKR+ShVRwDK6My8gtVIW1EAW2w3VQWI2UNF07aLeO8UG6nTNWA23
+OuZkUdgQovjcq01caSefgOkmiQOx6d74CAk
=X+eo
-----END PGP PUBLIC KEY BLOCK-----
"""

HPEPUBLICKEY2048_KEY1 = """
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1.4.12 (GNU/Linux)

mQENBFZp0LkBCACXajRw3b4x7G7dulNYj0hUID4BtVFq/MjEb6PHckTxGxZDoQRX
RK54tiTFA9wq3b4P3yEFnOjbjRoI0d7Ls67FADugFO+cDCtsV9yuDlaYP/U/h2nX
N0R4AdYbsVd5yr6xr+GAy66Hmx5jFH3kbC+zJpOcI0tU9hcyU7gjbxu6KQ1ypI2Q
VRKf8sRBJXgmkOlbYx35ZUMFcmVxrLJXvUuxmAVXgT9f5M3Z3rsGt/ab+/+1TFSb
RsaqHsIPE0QH8ikqW4IeDQAo1T99pCdf7FWr45KFFTo7O4AZdLMWVgqeFHaSoZxJ
307VIINsWiwQoPp0tfU5NOOOwB1Sv3x9QgFtABEBAAG0P0hld2xldHQgUGFja2Fy
ZCBFbnRlcnByaXNlIENvbXBhbnkgUlNBLTIwNDgtMjUgPHNpZ25ocEBocGUuY29t
PokBPQQTAQIAJwUCVmnQuQIbLwUJEswDAAYLCQgHAwIGFQgCCQoLAxYCAQIeAQIX
gAAKCRDCCK3eJsK3l9G+B/0ekblsBeN+xHIJ28pvo2aGb2KtWBwbT1ugI+aIS17K
UQyHZJUQH+ZeRLvosuoiQEdcGIqmOxi2hVhSCQAOV1LAonY16ACveA5DFAEBz1+a
WQyx6sOLLEAVX1VqGlBXxh3XLEUWOhlAf1gZPNtHsmURTUy2h1Lv/Yoj8KLyuK2n
DmrLOS3Ro+RqWocaJfvAgXKgt6Fq/ChDUHOnar7lGswzMsbE/yzLJ7He4y89ImK+
2ktR5HhDuxqgCe9CWH6Q/1WGhUa0hZ3nbluq7maa+kPe2g7JcRzPH/nJuDCAOZ7U
6mHE8j0kMQMYjgaYEx2wc02aQRmPyxhbDLjSbtjomXRr
=voON
-----END PGP PUBLIC KEY BLOCK-----
"""

HP_KEYS = (
    HPEPUBLICKEY2048_KEY1,
    HPPUBLICKEY2048_KEY1,
    HPPUBLICKEY2048,
    HPPUBLICKEY1024,
)
