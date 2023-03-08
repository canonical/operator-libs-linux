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

"""Abstractions for the system's DNF package information and repositories.

This charm library contains abstractions and wrappers around Enterprise Linux
(CentOS Stream, AlmaLinux, Rocky Linux, Cloud Linux, etc.) repositories and packages
to provide an idiomatic and Pythonic mechanism for managing packages and repositories
within machine charms deployed to an Enterprise Linux base.

To install packages using the library:

```python
import charms.operator_libs_linux.v0.dnf as dnf

try:
    dnf.install("epel-release")
    dnf.install("slurm-slurmd", "slurm-slurmctld", "slurm-slurmdbd", "slurm-slurmrestd")
except dnf.Error:
    logger.error("Failed to install requested packages.")
```

To upgrade specific packages and/or entire system using the library:

```python
import charms.operator_libs_linux.v0.dnf as dnf

try:
    # To upgrade a specific package.
    dnf.upgrade("slurm-slurmd")
    # To upgrade the whole system.
    dnf.upgrade()
except dnf.Error:
    logger.error("Failed to perform requested package upgrades.")
```

__Important:__ If no packages are passed to `dnf.upgrade(...)`, all packages with newer
versions available in the system's known repositories will be upgraded.

To remove packages using the library:

```python
import charms.operator_libs_linux.v0.dnf as dnf

try:
    dnf.remove("slurm-slurmd", "slurm-slurmctld", "slurm-slurmdbd", "slurm-slurmrestd")
    dnf.remove("epel-release")
except dnf.Error:
    logger.error("Failed to remove requested packages.")
```

Packages can have three possible states: installed, available, and absent. "installed"
means that the package is currently installed on the system. "available" means that the
package is available within the system's known package repositories, but is not currently
installed. "absent" means that the package was not found either or the system on within
the system's known package repositories.

To find details of a specific package using the library:

```python
import charms.operator_libs_linux.v0.dnf as dnf

try:
    package = dnf.fetch("slurm-slurmd")
    assert package.installed
    assert package.version == "22.05.6"
except AssertionError:
    logger.error("Package slurm-slurmd is not installed or is not expected version.")
```

__Important:__ `dnf.fetch(...)` will only match exact package names, not aliases. Ensure
that you are using the exact package name, otherwise the fetched package will be marked
as "absent". e.g. use the exact package name "python2.7" and not the alias "python2".

To add a new package repository using the library:

```python
import charms.operator_libs_linux.v0.dnf as dnf

try:
    dnf.add_repo("http://mirror.stream.centos.org/9-stream/HighAvailability/x86_64/os")
    dnf.install("pacemaker")
except dnf.Error:
    logger.error("Failed to install pacemaker package from HighAvailability repository.")
```
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

# The unique Charmhub library identifier, never change it
LIBID = "1e93f444444d4a4a8df06c1c16b33aaf"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1


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
    _state: _PackageState
    arch: str = None
    epoch: str = None
    version: str = None
    release: str = None
    repo: str = None

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


def upgrade(*packages: Optional[str]) -> None:
    """Upgrade one or more packages.

    Args:
        *packages:
            Packages to upgrade on system. If packages is omitted,
            upgrade all packages on the system.
    """
    _dnf("upgrade", *packages)


def install(*packages: Union[str, os.PathLike]) -> None:
    """Install one or more packages.

    Args:
        *packages: Packages to install on the system.
    """
    if not packages:
        raise TypeError("No packages specified.")
    _dnf("install", *packages)


def remove(*packages: str) -> None:
    """Remove one or more packages from the system.

    Args:
        *packages: Packages to remove from system.
    """
    if not packages:
        raise TypeError("No packages specified.")
    _dnf("remove", *packages)


def fetch(package: str) -> PackageInfo:
    """Fetch information about a package.

    Args:
        package: Package to get information about.

    Returns:
        PackageInfo: Information about package.

    Notes:
        `package` needs to exactly match the name of the package that you are fetching.
        For example, if working with the `python2` package on select EL distributions,
        `dnf.install("python2")` will succeed, but `dnf.fetch("python2")` will return
        the package in ABSENT state. This is because the name of the python2 package is
        python2.7, not python2. To get info about the python2 package, you need to use
        its exact name: `dnf.fetch("python2.7")`.
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
            return PackageInfo(name=package, _state=_PackageState.ABSENT)

        pkg_name, pkg_version, pkg_repo = info.split()
        name, arch = pkg_name.rsplit(".", 1)

        # Version should be good, but if not mark absent since package
        # is probably in a bad state then.
        version_match = re.match(r"(?:(.*):)?(.*)-(.*)", pkg_version)
        if not version_match:
            return PackageInfo(name=package, _state=_PackageState.ABSENT)
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
        return PackageInfo(name=package, _state=_PackageState.ABSENT)


def add_repo(repo: str) -> None:  # pragma: no cover
    """Add a new repository to DNF.

    Args:
        repo: URL of new repository to add.
    """
    if not fetch("dnf-plugins-core").installed:
        install("dnf-plugins-core")
    _dnf("config-manager", "--add-repo", repo)


def _dnf(*args: str) -> str:
    """Execute a DNF command.

    Args:
        *args: Arguments to pass to `dnf` executable.

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
            text=True,
            check=True,
        ).stdout.strip("\n")
    except FileNotFoundError:
        raise Error(f"dnf not found on PATH {os.getenv('PATH')}")
    except subprocess.CalledProcessError as e:
        raise Error(f"{e} Reason:\n{e.stderr}")
