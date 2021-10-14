# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Representations of the system's Debian/Ubuntu package information.

The `apt` module contains abstractions and wrappers around Debian/Ubuntu-style
repositories and packages, in order to easily provide an idiomatic and Pythonic
mechanism for adding packages and/or repositories to systems for use in machine
charms.

A sane default configuration is attainable through nothing more than instantiation
of the appropriate classes.

Typical usage example:

    try:
        # Run `apt-get update`
        apt.update()
        apt.add_package("zsh")
        apt.add_package(["vim", "htop", "wget"])
    except PackageNotFoundError:
        logger.error("A specified package not found in package cache or on system")
    except PackageError as e:
        logger.error(f"Could not install package. Reason: {e.message}")
"""

import logging
import re
import subprocess

from enum import Enum
from pathlib import Path
from subprocess import check_output, CalledProcessError
from typing import Dict, List, Optional, Tuple, Union


logger = logging.getLogger(__name__)


class Error(Exception):
    """Base class of most errors raised by this library."""

    def __repr__(self):
        return f"<{type(self).__module__}.{type(self).__name__} {self.args}>"

    @property
    def name(self):
        """Return a string representation of the model plus class."""
        return f"<{type(self).__module__}.{type(self).__name__}>"

    @property
    def message(self):
        """Return the message passed as an argument."""
        return self.args[0]


class PackageError(Error):
    """Raised when there's an error installing or removing a package."""


class PackageNotFoundError(Error):
    """Raised when a requested package is not known to the system."""


class PackageState(Enum):
    """A class to represent possible package states."""

    Present = "present"
    Absent = "absent"
    Latest = "latest"
    Available = "available"


class DebianPackage:
    """Represents a traditional Debian package and its utility functions.

    :class:`DebianPackage` wraps information and functionality around a known
      package, whether installed or available. The version, epoch, name, and
      architecture can be easily queried and compared against other
      :class:`DebianPackage` objects to determine the latest version or to
      install a specific version.

      The representation of this object as a string mimics the output from
      `dpkg` for familiarity.

      Installation and removal of packages is handled through the `state` property
      or `ensure` method, with the following options:

        dpkg.PackageState.Absent
        dpkg.PackageState.Available
        dpkg.PackageState.Present
        dpkg.PackageState.Latest

      When :class:`DebianPackage` is initialized, the state of a given
      :class:`DebianPackage` object will be set to `Available`, `Present`, or
      `Latest`, with `Absent` implemented as a convenience for removal (though it
      operates essentially the same as `Available`).

    """

    def __init__(
        self, name: str, version: str, epoch: str, arch: str, state: PackageState
    ) -> None:
        self._name = name
        self._arch = arch
        self._state = state
        self._version = Version(version, epoch)

    def __eq__(self, other) -> bool:
        """Equality for comparison.

        Args:
          other: a :class:`DebianPackage` object for comparison

        Returns:
          A boolean reflecting equality
        """
        return (
            isinstance(other, self.__class__)
            and (
                self._name,
                self._version.number,
            )
            == (other._name, other._version.number)
        )

    def __hash__(self):
        """A basic hash so this class can be used in Mappings and dicts."""
        return hash((self._name, self._version.number))

    def __repr__(self):
        """A representation of the package."""
        return f"<{self.__module__}.{self.__class__.__name__}: {self.__dict__}>"

    def __str__(self):
        """A human-readable representation of the package."""
        return "<{}: {}-{}.{} -- {}>".format(
            self.__class__.__name__,
            self._name,
            self._version,
            self._arch,
            str(self._state),
        )

    @staticmethod
    def _apt(
        command: str,
        package_names: Union[str, List],
        optargs: Optional[List[str]] = None,
    ) -> None:
        """Wrap package management commands for Debian/Ubuntu systems

        Args:
          command: the command given to `apt-get`
          package_names: a package name or list of package names to operate on
          optargs: an (Optional) list of additioanl arguments

        Raises:
          PackageError if an error is encountered
        """
        optargs = optargs if optargs is not None else []
        if isinstance(package_names, str):
            package_names = [package_names]
        _cmd = ["apt-get", "-y", *optargs, command, *package_names]
        try:
            subprocess.check_call(_cmd)
        except CalledProcessError as e:
            raise PackageError(
                f"Could not {command} package(s) [{[*package_names]}]: {e.output}"
            ) from None

    def _add(self) -> None:
        """Add a package to the system."""
        self._apt(
            "install",
            f"{self.name}={self.version}",
            optargs=["--option=Dpkg::Options::=--force-confold"],
        )

    def _remove(self) -> None:
        """Removes a package from the system. Implementation-specific."""
        return self._apt("remove", f"{self.name}={self.version}")

    @property
    def name(self) -> str:
        """Returns the name of the package."""
        return self._name

    def ensure(self, state: PackageState):
        """Ensures that a package is in a given state.

        Args:
          state: a :class:`PackageState` to reconcile the package to

        Raises:
          PackageError from the underlying call to apt
        """
        if self._state is not state:
            if state not in (PackageState.Present, PackageState.Latest):
                self._remove()
            else:
                self._add()
        self._state = state

    @property
    def present(self) -> bool:
        """Returns whether or not a package is present."""
        return self._state in (PackageState.Present, PackageState.Latest)

    @property
    def latest(self) -> bool:
        """Returns whether the package is the most recent version."""
        return self._state is PackageState.Latest

    @property
    def state(self) -> PackageState:
        """Returns the current package state."""
        return self._state

    @state.setter
    def state(self, state: PackageState) -> None:
        """Sets the package state to a given value.

        Args:
          state: a :class:`PackageState` to reconcile the package to

        Raises:
          PackageError from the underlying call to apt
        """
        if state in (PackageState.Latest, PackageState.Present):
            self._add()
        else:
            self._remove()
        self._state = state

    @property
    def version(self) -> "Version":
        """Returns the version for a package."""
        return self._version

    @property
    def epoch(self) -> str:
        """Returns the epoch for a package. May be unset."""
        return self._version.epoch

    @property
    def arch(self) -> str:
        """Returns the architecture for a package."""
        return self._arch

    @property
    def fullversion(self) -> str:
        """Returns the name+epoch for a package."""
        return f"{self._version}.{self._arch}"

    @staticmethod
    def _get_epoch_from_version(version: str) -> Tuple[str, str]:
        """Pull the epoch, if any, out of a version string."""
        epoch_matcher = re.compile(r"^((?P<epoch>\d+):)?(?P<version>.*)")
        matches = epoch_matcher.search(version).groupdict()
        return matches.get("epoch", ""), matches.get("version")

    @classmethod
    def from_system(
        cls, package: str, version: Optional[str] = "", arch: Optional[str] = ""
    ) -> "DebianPackage":
        """Locates a package, either on the system or known to apt, and serializes the information.

        Args:
            package: a string representing the package
            version: an optional string if a specific version isr equested
            arch: an optional architecture, defaulting to `dpkg --print-architecture`. If an architecture is not specified, this will be used for selection.

        """
        try:
            return DebianPackage.from_installed_package(package, version, arch)
        except PackageNotFoundError:
            logger.debug(
                f"Package {package} is not currently installed or has the wrong architecture."
            )

        # Ok, try `apt-cache ...`
        try:
            return DebianPackage.from_apt_cache(package, version, arch)
        except (PackageNotFoundError, PackageError):
            # If we get here, it's not known to the systems.
            # This seems unnecessary, but virtually all `apt` commands have a return code of `100`, and
            # providing meaningful error messages without this is ugly.
            raise PackageNotFoundError(
                f"Package '{package}{f'.{arch}' if arch else ''}' could not be found on the system or in the apt cache!"
            ) from None

    @classmethod
    def from_installed_package(
        cls, package: str, version: Optional[str] = "", arch: Optional[str] = ""
    ) -> "DebianPackage":
        """Check whether the package is already installed and return an instance.

        Args:
            package: a string representing the package
            version: an optional string if a specific version isr equested
            arch: an optional architecture, defaulting to `dpkg --print-architecture`. If an architecture is not specified, this will be used for selection.
        """
        system_arch = check_output(
            ["dpkg", "--print-architecture"], universal_newlines=True
        ).strip()
        arch = arch if arch else system_arch

        # Regexps are a really terrible way to do this. Thanks dpkg
        output = ""
        try:
            output = check_output(["dpkg", "-l", package], universal_newlines=True)
        except CalledProcessError:
            raise PackageNotFoundError(f"Package is not installed: {package}") from None

        # Pop off the output from `dpkg -l' because there's no flag to
        # omit it`
        lines = str(output).splitlines()[5:]

        dpkg_matcher = re.compile(
            r"""
        ^(?P<package_status>\w+?)\s+
        (?P<package_name>.*?)(?P<throwaway_arch>:\w+?)?\s+
        (?P<version>.*?)\s+
        (?P<arch>\w+?)\s+
        (?P<description>.*)
        """,
            re.VERBOSE,
        )

        for line in lines:
            try:
                matches = dpkg_matcher.search(line).groupdict()
                epoch, split_version = DebianPackage._get_epoch_from_version(matches["version"])
                pkg = DebianPackage(
                    matches["package_name"],
                    split_version,
                    epoch,
                    matches["arch"],
                    PackageState.Present,
                )
                if pkg.arch == arch and (version == "" or str(pkg.version) == version):
                    return pkg
            except AttributeError:
                logger.warning(f"dpkg matcher could not parse line: {line}")

        # If we didn't find it, fail through
        raise PackageNotFoundError(f"Package {package}.{arch} is not installed!")

    @classmethod
    def from_apt_cache(
        cls, package: str, version: Optional[str] = "", arch: Optional[str] = ""
    ) -> "DebianPackage":
        """Check whether the package is already installed and return an instance.

        Args:
            package: a string representing the package
            version: an optional string if a specific version isr equested
            arch: an optional architecture, defaulting to `dpkg --print-architecture`. If an architecture is not specified, this will be used for selection.
        """
        system_arch = check_output(
            ["dpkg", "--print-architecture"], universal_newlines=True
        ).strip()
        arch = arch if arch else system_arch

        # Regexps are a really terrible way to do this. Thanks dpkg
        keys = ("Package", "Architecture", "Version")

        try:
            output = check_output(["apt-cache", "show", package], universal_newlines=True)
        except CalledProcessError as e:
            raise PackageError(f"Could not list packages in apt-cache: {e.output}") from None

        pkg_groups = output.strip().split("\n\n")
        keys = ("Package", "Architecture", "Version")

        for pkg_raw in pkg_groups:
            lines = str(pkg_raw).splitlines()
            vals = {}
            for line in lines:
                if line.startswith(keys):
                    items = line.split(":", 1)
                    vals[items[0]] = items[1].strip()
                else:
                    continue

            epoch, split_version = DebianPackage._get_epoch_from_version(vals["Version"])
            pkg = DebianPackage(
                vals["Package"],
                split_version,
                epoch,
                vals["Architecture"],
                PackageState.Available,
            )

            if pkg.arch == arch and (version == "" or str(pkg.version) == version):
                return pkg

        # If we didn't find it, fail through
        raise PackageNotFoundError(f"Package {package}.{arch} is not in the apt cache!")


class Version:
    """An abstraction around package versions. This seems like it should
    be strictly unnecessary, except that `apt_pkg` is not usable inside a
    venv, and wedging version comparisions into :class:`DebianPackage` would
    overcomplicate it.

    This class implements the algorithm found here:
    https://www.debian.org/doc/debian-policy/ch-controlfields.html#version
    """

    def __init__(self, version: str, epoch: str):
        self._version = version
        self._epoch = epoch or ""

    def __repr__(self):
        """A representation of the package."""
        return f"<{self.__module__}.{self.__class__.__name__}: {self.__dict__}>"

    def __str__(self):
        """A human-readable representation of the package."""
        return f"{f'{self._epoch}:' if self._epoch else ''}{self._version}"

    @property
    def epoch(self):
        """Returns the epoch for a package. May be empty."""
        return self._epoch

    @property
    def number(self) -> str:
        """Returns the version number for a package."""
        return self._version

    def _get_parts(self, version: str) -> Tuple[str, str]:
        """Separate the version into component upstream and Debian pieces."""
        try:
            version.rindex("-")
        except ValueError:
            # No hyphens means no Debian version
            return version, "0"

        upstream, debian = version.rsplit("-", 1)
        return upstream, debian

    def _listify(self, revision: str) -> List[str]:
        """Split a revision string into a listself.

        This list is comprised of  alternating between strings and numbers,
        padded on either end to always be "str, int, str, int..." and
        always be of even length.  This allows us to trivially implement the
        comparison algorithm described.
        """
        result = []
        while revision:
            rev_1, remains = self._get_alphas(revision)
            rev_2, remains = self._get_digits(remains)
            result.extend([rev_1, rev_2])
            revision = remains
        return result

    def _get_alphas(self, revision: str) -> Tuple[str, str]:
        """Return a tuple of the first non-digit characters of a revision (which
        may be empty) and the remainder."""
        # get the index of the first digit
        for i, char in enumerate(revision):
            if char.isdigit():
                if i == 0:
                    return "", revision
                return revision[0:i], revision[i:]
        # string is entirely alphas
        return revision, ""

    def _get_digits(self, revision: str) -> Tuple[int, str]:
        """Return a tuple of the first integer characters of a revision (which
        may be empty) and the remainder."""
        # If the string is empty, return (0,'')
        if not revision:
            return 0, ""
        # get the index of the first non-digit
        for i, char in enumerate(revision):
            if not char.isdigit():
                if i == 0:
                    return 0, revision
                return int(revision[0:i]), revision[i:]
        # string is entirely digits
        return int(revision), ""

    def _dstringcmp(self, a, b):
        """Debian package version string section lexical sort algorithm.

        The lexical comparison is a comparison of ASCII values modified so
        that all the letters sort earlier than all the non-letters and so that
        a tilde sorts before anything, even the end of a part.
        """

        if a == b:
            return 0
        try:
            for i, char in enumerate(a):
                if char == b[i]:
                    continue
                # "a tilde sorts before anything, even the end of a part"
                # (emptyness)
                if char == "~":
                    return -1
                if b[i] == "~":
                    return 1
                # "all the letters sort earlier than all the non-letters"
                if char.isalpha() and not b[i].isalpha():
                    return -1
                if not char.isalpha() and b[i].isalpha():
                    return 1
                # otherwise lexical sort
                if ord(char) > ord(b[i]):
                    return 1
                if ord(char) < ord(b[i]):
                    return -1
        except IndexError:
            # a is longer than b but otherwise equal, greater unless there are tildes
            if char == "~":
                return -1
            return 1
        # if we get here, a is shorter than b but otherwise equal, so check for tildes...
        if b[len(a)] == "~":
            return 1
        return -1

    def _compare_revision_strings(self, first: str, second: str):
        """Compare two debian revision strings."""
        if first == second:
            return 0

        # listify pads results so that we will always be comparing ints to ints
        # and strings to strings (at least until we fall off the end of a list)
        first_list = self._listify(first)
        second_list = self._listify(second)
        if first_list == second_list:
            return 0
        try:
            for i, item in enumerate(first_list):
                # explicitly raise IndexError if we've fallen off the edge of list2
                if i >= len(second_list):
                    raise IndexError
                # if the items are equal, next
                if item == second_list[i]:
                    continue
                # numeric comparison
                if isinstance(item, int):
                    if item > second_list[i]:
                        return 1
                    if item < second_list[i]:
                        return -1
                else:
                    # string comparison
                    return self._dstringcmp(item, second_list[i])
        except IndexError:
            # rev1 is longer than rev2 but otherwise equal, hence greater
            # ...except for goddamn tildes
            if first_list[len(second_list)][0][0] == "~":
                return 1
            return 1
        # rev1 is shorter than rev2 but otherwise equal, hence lesser
        # ...except for goddamn tildes
        if second_list[len(first_list)][0][0] == "~":
            return -1
        return -1

    def _compare_version(self, other) -> int:
        if (self.number, self.epoch) == (other.number, other.epoch):
            return 0

        if self.epoch < other.epoch:
            return -1
        if self.epoch > other.epoch:
            return 1

        # If none of these are true, follow the algorithm
        upstream_version, debian_version = self._get_parts(self.number)
        other_upstream_version, other_debian_version = self._get_parts(other.number)

        upstream_cmp = self._compare_revision_strings(upstream_version, other_upstream_version)
        if upstream_cmp != 0:
            return upstream_cmp

        debian_cmp = self._compare_revision_strings(debian_version, other_debian_version)
        if debian_cmp != 0:
            return debian_cmp

        return 0

    def __lt__(self, other) -> bool:
        return self._compare_version(other) < 0

    def __eq__(self, other) -> bool:
        return self._compare_version(other) == 0

    def __gt__(self, other) -> bool:
        return self._compare_version(other) > 0

    def __le__(self, other) -> bool:
        return self.__eq__(other) or self.__lt__(other)

    def __ge__(self, other) -> bool:
        return self.__gt__(other) or self.__eq__(other)

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)


def add_package(
    package_names: Union[str, List[str]],
    version: Optional[str] = "",
    arch: Optional[str] = "",
    update_cache: Optional[bool] = False,
) -> List[DebianPackage]:
    """Add a package or list of packages to the system.
    Args:
        name: the name(s) of the package(s)
        version: an (Optional) version as a string. Defaults to the latest known
        arch: an optional architecture for the package
        update_cache: whether or not to run `apt-get update` prior to operating
    Raises:
        PackageNotFoundError if the package is not in the cache.
    """
    cache_refreshed = False
    if update_cache:
        update()
        cache_refreshed = True

    packages = {"success": [], "retry": [], "failed": []}

    package_names = [package_names] if type(package_names) is str else package_names
    if not package_names:
        raise TypeError("Expected at least one package name to add, received zero!")

    if len(package_names) != 1 and version:
        raise TypeError(
            "Explicit version should not be set if more than one package is being added!"
        )

    for p in package_names:
        pkg, success = _add(p, version, arch)
        if success:
            packages["success"].append(pkg)
        else:
            logger.warn(f"Failed to locate and install/update {pkg}!")
            packages["retry"].append(p)

    if packages["retry"] and not cache_refreshed:
        logger.info("Updating the apt-cache and retrying installation of failed packages.")
        update()

        for p in packages["retry"]:
            pkg, success = _add(p, version, arch)
            if success:
                packages["success"].append(pkg)
            else:
                packages["failed"].append(p)

    if packages["failed"]:
        raise PackageError(f"Failed to install packages: {', '.join(packages['failed'])}")

    return packages["success"]


def _add(
    name: str,
    version: Optional[str] = "",
    arch: Optional[str] = "",
) -> Tuple[Union[DebianPackage, str], bool]:
    """Adds a package.
    Args:
        name: the name(s) of the package(s)
        version: an (Optional) version as a string. Defaults to the latest known
        arch: an optional architecture for the package

    Returns: a tuple of :class:`DebianPackage` if found, or a :str: if it is not, and
        a boolean indicating success
    """
    try:
        pkg = DebianPackage.from_system(name, version, arch)
        pkg.ensure(state=PackageState.Present)
        return pkg, True
    except PackageNotFoundError:
        return name, False


def remove_package(package_names: Union[str, List[str]]) -> List[DebianPackage]:
    """Removes a package from the system.

    Args:
        name: the name of a package
    Raises:
        PackageNotFoundError if the package is not found.
    """
    packages = []

    package_names = [package_names] if type(package_names) is str else package_names
    if not package_names:
        raise TypeError("Expected at least one package name to add, received zero!")

    for p in package_names:
        try:
            pkg = DebianPackage.from_installed_package(p)
            pkg.ensure(state=PackageState.Absent)
            packages.append(pkg)
        except PackageNotFoundError:
            logger.info(f"Package {p} was requested for removal, but it was not installed.")

    return packages


def update() -> None:
    """Updates the apt cache via `apt-get update`."""
    subprocess.check_call(["apt-get", "update"])
