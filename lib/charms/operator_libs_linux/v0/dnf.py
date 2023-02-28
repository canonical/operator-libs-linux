#!/usr/bin/env python3
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

import copy
import itertools
import os
import shutil
import subprocess
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from functools import wraps
from io import StringIO
from typing import Callable, Dict, List, Literal, Optional, Union


class _PackageState(Enum):
    INSTALLED = "installed"
    AVAILABLE = "available"
    ABSENT = "absent"


class DNFExecutionError(Exception):
    """Raise when dnf encounters an execution error."""


def _dnf(
    command: str,
    args: Optional[Union[Union[str, os.PathLike], List[Union[str, os.PathLike]]]] = None,
    preargs: Optional[List[str]] = None,
    postargs: Optional[List[str]] = None,
) -> subprocess.CompletedProcess[str]:
    """Execute DNF command.

    Args:
        command (str): Command to execute.
        args (Optional[Union[Union[str, os.PathLike], List[Union[str, os.PathLike]]]]):
            Arguments to operate on. (Default: None).
        preargs (Optional[List[str]], optional):
            Optional arguments to prepend before command. (Default: None).
        postargs (Optional[List[str]], optional):
            Optional arguments to append after command. (Default: None).

    Raises:
        DNFExecutionError: Raised if specified DNF command fails to execute.

    Returns:
        (subprocess.CompletedProcess[str]):
            returncode, stdout, and stderr of completed DNF command.
    """
    args = [args] if type(args) == str else args if type(args) == list else []
    preargs = preargs if preargs is not None else []
    postargs = postargs if postargs is not None else []
    cmd = ["dnf", "-y", *preargs, command, *postargs, *args]
    try:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except subprocess.CalledProcessError as e:
        raise DNFExecutionError(
            f"Failed to perform command {' '.join(cmd)}. Reason:\n\n{e.stderr}"
        )


class PackageInfo:
    """Dataclass representing DNF package information."""

    def __init__(self, data: Dict[str, Union[str, _PackageState]]) -> None:
        self.__data = data

    @property
    def installed(self) -> bool:
        """Determine if package is marked 'installed'.

        Returns:
            (bool): True if package is installed; False if otherwise.
        """
        return self.__data["state"] == _PackageState.INSTALLED

    @property
    def available(self) -> bool:
        """Determine if package is marked 'available'.

        Returns:
            (bool): True if package is available; False if otherwise.
        """
        return self.__data["state"] == _PackageState.AVAILABLE

    @property
    def absent(self) -> bool:
        """Determine if package is marked 'absent'.

        Returns:
            (bool) True if package is absent; False if otherwise.
        """
        return self.__data["state"] == _PackageState.ABSENT

    @property
    def name(self) -> str:
        """Get name of package.

        Returns:
            (str): Name of package.
        """
        return self.__data["name"]

    @property
    def arch(self) -> Optional[str]:
        """Get architecture of package.

        Returns:
            (Optional[str]):
                Architecture of package. Defaults to None if package is absent.
        """
        return self.__data.get("arch", None)

    @property
    def epoch(self) -> Optional[str]:
        """Get epoch of package.

        Returns:
            (Optional[str]):
                Epoch of package. Defaults to None if package is absent.
        """
        return self.__data.get("epoch", None)

    @property
    def version(self) -> Optional[str]:
        """Get version of package.

        Returns:
            (Optional[str]):
                Version number of package. Defaults to None if package is absent.
        """
        return self.__data.get("version", None)

    @property
    def fullversion(self) -> Optional[str]:
        """Get full version of package.

        Returns:
            (Optional[str]):
                Full version of package. Defaults to None if package is absent.
        """
        if self.absent:
            return None

        return (
            f"{(f'{self.epoch}:' if self.epoch else '')}"
            f"{self.version}{(f'-{self.release}' if self.release else '')}"
        )

    @property
    def release(self) -> Optional[str]:
        """Get release of package.

        Returns:
            (Optional[str]):
                Release of package. Defaults to None if package is absent.
        """
        return self.__data.get("release", None)

    @property
    def repo(self) -> Optional[str]:
        """Get repository package is from.

        Returns:
            (Optional[str]):
                Repository of package: Defaults to None if package is absent.
        """
        return self.__data.get("repo", None)


def _load_cache(
    cache_type: Literal["installed", "available"]
) -> List[Dict[str, Union[str, _PackageState]]]:
    """Load DNF cache information.

    Args:
        cache_type (Literal["installed", "available"]):
            Cache information category to load.

    Raises:
        DNFExecutionError: Raised if incorrect cache type is passed.

    Returns:
        (List[Dict[str, Union[str, _PackageState]]]):
            Loaded cache information.
    """
    if cache_type not in ["installed", "available"]:
        raise DNFExecutionError(
            f"Cache type must be either installed or available, not {cache_type}"
        )

    result = []
    state = {"installed": _PackageState.INSTALLED, "available": _PackageState.AVAILABLE}
    for pkg_name, pkg_version, pkg_repo in itertools.filterfalse(
        lambda x: len(x) != 3,
        [
            line.strip("\n").strip().split()
            for line in StringIO(
                _dnf("list", postargs=[f"--{cache_type}"]).stdout.strip("\n"),
            )
        ],
    ):
        placeholder = pkg_name.split(".")
        epoch = None  # Not every DNF package has an epoch.
        charset, buffer = deque(itertools.chain(pkg_version)), []
        while charset:
            char = charset.popleft()
            if char == ":":
                epoch = "".join(buffer)
                buffer.clear()
            elif char == "-":
                version = "".join(buffer)
                buffer.clear()
            else:
                buffer.append(char)

        result.append(
            {
                "name": ".".join(placeholder[:-1]),
                "arch": ".".join(placeholder[-1:]),
                "epoch": epoch,
                "version": version,
                "release": "".join(buffer),
                "repo": pkg_repo[1:] if pkg_repo.startswith("@") else pkg_repo,
                "state": state[cache_type],
            }
        )

    return result


class _Cache:
    """Track the current state of the DNF package cache."""

    def __new__(cls) -> "_Cache":
        """Create new  _Cache object.

        Returns:
            (_Cache): New _Cache object.
        """
        if not hasattr(cls, f"{cls.__name__}__instance"):
            cls.__instance = super(_Cache, cls).__new__(cls)
            cls.__instance.__initialized = False
        return cls.__instance

    def __init__(self) -> None:
        if self.__initialized:
            return

        self.__initialized = True
        self.refresh()

    @property
    def installed(self) -> List[Dict[str, Union[str, _PackageState]]]:
        """Get installed packages.

        Returns:
            (List[Dict[str, Union[str, _PackageState]]]):
                Cache of installed packages.
        """
        return copy.deepcopy(self.__installed)

    @property
    def available(self) -> List[Dict[str, Union[str, _PackageState]]]:
        """Get available packages.

        Returns:
            (List[Dict[str, Union[str, _PackageState]]]):
                Cache of available packages.
        """
        return copy.deepcopy(self.__available)

    def refresh(self) -> None:
        """Refresh current package cache."""
        with ThreadPoolExecutor() as executor:
            installed = executor.submit(_load_cache, "installed")
            available = executor.submit(_load_cache, "available")
            self.__installed = installed.result()
            self.__available = available.result()


def _refresh(func: Callable) -> Callable:
    """Refresh cache after function call.

    Args:
        func (Callable): Function to wrap.
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> None:
        func(*args, **kwargs)
        _Cache().refresh()

    return wrapper


def _search(
    cache: List[Dict[str, Union[str, _PackageState]]], name: str
) -> Optional[Dict[str, Union[str, _PackageState]]]:
    """Search DNF package cache.

    Args:
        cache (List[Dict[str, Union[str, _PackageState]]]):
            DNF package cache to search.
        name (str):
            Name of package to locate.

    Returns:
        (Optional[Dict[str, Union[str, _PackageState]]]):
            Located cache entry. Returns None if package is not found in cache.
    """
    for entry in cache:
        if entry["name"] == name:
            return entry

    return None


class _MetaDNF(type):
    """Metaclass for `dnf`.

    Notes:
        This metaclass will raise an ImportError if the dnf executable
        is not found on your PATH.
    """

    def __new__(cls, name, bases, attrs) -> "_MetaDNF":
        if shutil.which("dnf") is None:
            raise ImportError(
                (
                    f"Executable dnf not found on PATH {os.getenv('PATH')}. "
                    "Cannot import dnf library."
                )
            )

        return super(_MetaDNF, cls).__new__(cls, name, bases, attrs)

    @property
    def version(cls) -> str:
        """Get version of DNF package manager.

        Returns:
            (str): Version of DNF.
        """
        return StringIO(_dnf("", preargs=["--version"]).stdout).readline().strip("\n")

    def __getitem__(cls, package_name: str) -> PackageInfo:
        """Get information about DNF package.

        Args:
            package_name (str): Name of package.

        Returns:
            (PackageInfo): DNF package information.
        """
        # Package cache can be large so perform searches in threads.
        with ThreadPoolExecutor() as executor:
            installed = executor.submit(_search, _Cache().installed, package_name)
            available = executor.submit(_search, _Cache().available, package_name)

            # See if package is in installed first.
            result = installed.result()
            if result:
                return PackageInfo(result)

            # If not installed, check available.
            result = available.result()
            if result:
                return PackageInfo(result)

            # If not in either installed or available, return default.
            return PackageInfo({"name": package_name, "state": _PackageState.ABSENT})


class dnf(metaclass=_MetaDNF):  # noqa N802
    @staticmethod
    @_refresh
    def update() -> None:
        """Update all packages on the system."""
        _dnf("update")

    @staticmethod
    @_refresh
    def upgrade(*packages: str) -> None:
        """Upgrade one or more packages.

        Args:
            *packages (str): Packages to upgrade on system.
        """
        if len(packages) == 0:
            raise DNFExecutionError("No packages specified.")
        _dnf("upgrade", args=[*packages])

    @staticmethod
    @_refresh
    def install(*packages: Union[str, os.PathLike]) -> None:
        """Install one or more packages.

        Args:
            *packages (Union[str, os.PathLine]):
                Packages to install on the system.
        """
        if len(packages) == 0:
            raise DNFExecutionError("No packages specified.")
        _dnf("install", args=[*packages])

    @staticmethod
    @_refresh
    def remove(*packages: str) -> None:
        """Remove one or more packages from the system.

        Args:
            *packages (str): Packages to remove from system.
        """
        if len(packages) == 0:
            raise DNFExecutionError("No packages specified.")
        _dnf("remove", args=[*packages])

    @staticmethod
    @_refresh
    def purge(*packages: str) -> None:
        """Purge one or more packages from the system.

        Args:
            *packages (str): Packages to purge from system.
        """
        if len(packages) == 0:
            raise DNFExecutionError("No packages specified.")
        _dnf("purge", args=[*packages])

    @staticmethod
    @_refresh
    def add_repo(repo: str) -> None:
        """Add a new repository to DNF.

        Args:
            repo (str): URL of new repository to add.
        """
        _dnf("config-manager", postargs=["--add-repo"], args=[repo])
