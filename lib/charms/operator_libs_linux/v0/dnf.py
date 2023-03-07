# Copyright 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Abstractions for system's DNF package information and repositories."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Union


class Error(Exception):
    """Raise when dnf encounters an execution error."""


class _PackageState(Enum):
    INSTALLED = "installed"
    AVAILABLE = "available"
    ABSENT = "absent"


@dataclass(frozen=True)
class PackageInfo:
    """Dataclass representing DNF package information."""

    name: str
    arch: str = None
    epoch: str = None
    version: str = None
    release: str = None
    repo: str = None
    _state: _PackageState = _PackageState.ABSENT

    @property
    def installed(self) -> bool:
        """Determine if package is marked 'installed'."""
        return self._state == _PackageState.INSTALLED

    @property
    def available(self) -> bool:
        """Determine if package is marked 'available'."""
        return self._state == _PackageState.AVAILABLE

    @property
    def absent(self) -> bool:
        """Determine if package is marked 'absent'."""
        return self._state == _PackageState.ABSENT

    @property
    def full_version(self) -> Optional[str]:
        """Get full version of package."""
        if self.absent:
            return None

        full_version = [self.version, f"-{self.release}"]
        if self.epoch:
            full_version.insert(0, f"{self.epoch}:")

        return "".join(full_version)


def version() -> str:
    """Get version of `dnf` executable."""
    return _dnf("--version").splitlines()[0]


def installed() -> bool:
    """Determine if the `dnf` executable is available on PATH."""
    return shutil.which("dnf") is not None


def update() -> None:
    """Update all packages on the system."""
    _dnf("update")


def upgrade(*packages: str) -> None:
    """Upgrade one or more packages.

    Args:
        *packages (str): Packages to upgrade on system.
    """
    if not packages:
        _dnf("upgrade")
    else:
        _dnf("upgrade", *packages)


def install(*packages: Union[str, os.PathLike]) -> None:
    """Install one or more packages.

    Args:
        *packages (Union[str, os.PathLine]): Packages to install on the system.
    """
    if not packages:
        raise TypeError("No packages specified.")
    _dnf("install", *packages)


def remove(*packages: str) -> None:
    """Remove one or more packages from the system.

    Args:
        *packages (str): Packages to remove from system.
    """
    if not packages:
        raise TypeError("No packages specified.")
    _dnf("remove", *packages)


def purge(*packages: str) -> None:
    """Purge one or more packages from the system.

    Args:
        *packages (str): Packages to purge from system.
    """
    if not packages:
        raise TypeError("No packages specified.")
    _dnf("remove", *packages)


def fetch(package: str) -> PackageInfo:
    """Fetch information about a package.

    Args:
        package (str): Package to get information about.

    Returns:
        PackageInfo: Information about package.
    """
    try:
        stdout = _dnf("list", "-q", package)
        # Only take top two lines of output.
        status, info = stdout.splitlines()[:2]

        # Check if package is in states INSTALLED or AVAILABLE. If not, mark absent.
        if "Installed" in status:
            state = _PackageState.INSTALLED
        elif "Available" in status:
            state = _PackageState.AVAILABLE
        else:
            raise Error(f"{package} is not installed or available but {status} instead.")

        pkg_name, pkg_version, pkg_repo = info.split()
        name, arch = pkg_name.rsplit(".", 1)

        # Version should be good, but if not mark absent since package
        # is probably in a bad state then.
        version_match = re.match(r"(?:(.*):)?(.*)-(.*)", pkg_version)
        if not version_match:
            raise Error(f"Bad version {pkg_version}. Marking {package} absent.")
        else:
            epoch, version, release = version_match.groups()

        return PackageInfo(
            name=name,
            arch=arch,
            epoch=epoch,
            version=version,
            release=release,
            repo=pkg_repo[1:] if pkg_repo.startswith("@") else pkg_repo,
            _state=state,
        )
    except Error:
        return PackageInfo(name=package)


def add_repo(repo: str) -> None:
    """Add a new repository to DNF.

    Args:
        repo (str): URL of new repository to add.
    """
    if not fetch("dnf-plugins-core").installed:
        install("dnf-plugins-core")
    _dnf("config-manager", "--add-repo", repo)


def _dnf(*args: str) -> str:
    """Execute a DNF command.

    Args:
        *args (str): Arguments to pass to `dnf` executable.

    Raises:
        Error: Raised if DNF command execution fails.

    Returns:
        str: Captured stdout of executed DNF command.
    """
    try:
        return subprocess.run(
            ["dnf", "-y", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        ).stdout.strip("\n")
    except FileNotFoundError:
        raise Error(f"dnf not found on PATH {os.getenv('PATH')}")
    except subprocess.CalledProcessError as e:
        raise Error(f"{e} Reason:\n{e.stderr}")
