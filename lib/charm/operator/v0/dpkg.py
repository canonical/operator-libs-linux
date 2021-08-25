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

"""Representations of the system's Debian/Ubuntu repository and package
   information.

   The `dpkg` module contains abstractions and wrappers around Debian/Ubuntu-style
    repositories and packages, in order to easily provide an idiomatic and Pythonic
    mechanism for adding packages and/or repositories to systems for use in machine
    charms.

    A sane default configuration is attainable through nothing more than insantiation
    of the appropriate classes. :class:`DebianRepository`

    :class:`PackageCache` will build a dict-like :class:`ABC.MutableMapping` of both
    installed and available packages, indexed by package name. Retrieving a value will
    return the installed version (if any), otherwise the most recent package version
    known to apt-cache, as a :class:`DebianPackage` object.

      Typical usage example:

      cache = dpkg.PackageCache()
      vim = cache["vim"]
      vim.ensure(dpkg.PackageState.Latest)
      # alternatively
      vim.state = dpkg.PackageState.Latest

    :class:`RepositoryList` will return a dict-like object containing enabled system
    repositories and their properties (available groups, baseuri. gpg key). This class can
    add, disable, or manipulate repositories. Items can be retrieved as :class:`DebianRepository`
    objects.

      Typical usage example:

      repositories = dpkg.RepositoryList()
      repositories.add(DebianRepository(
        enabled=True, repotype="deb", uri="https://example.com", release="focal",
        groups=["universe"]
      ))
"""

import fileinput
import glob
import logging
import os
import re
import subprocess

from collections.abc import Mapping
from enum import IntEnum
from itertools import chain
from subprocess import check_call, check_output, CalledProcessError
from typing import Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


class Error(Exception):
    """Base class of most errors raised by this library."""

    def __repr__(self):
        return "<{}.{} {}>".format(type(self).__module__, type(self).__name__, self.args)

    @property
    def name(self):
        """Return a string representation of the model plus class."""
        return "<{}.{}>".format(type(self).__module__, type(self).__name__)

    @property
    def message(self):
        """Return the message passed as an argument."""
        return self.args[0]


class StateBase(IntEnum):
    Present = 1
    Absent = 2


class PackageError(Error):
    """Raised when there's an error installing or removing a package"""


class PackageStateBase(IntEnum):
    """A parent class to combine IntEnums, since Python does not otherwise allow this."""

    Latest = 3
    Available = 4


PackageState = IntEnum(
    "PackageState", [(i.name, i.value) for i in chain(StateBase, PackageStateBase)]
)


class DebianPackage(object):
    """Represents a traditional system package and its utility functions.

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

      When :class:`PackageCache` is initialized, the state of a given
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
        return "<{}.{}: {}>".format(self.__module__, self.__class__.__name__, self.__dict__)

    def __str__(self):
        """A human-readable representation of the package"""
        return "<{}: {}-{}.{} -- {}>".format(
            self.__class__.__name__,
            self._name,
            self._version,
            self._arch,
            str(self._state),
        )

    @staticmethod
    def _apt(
        command: str, package_names: Union[str, List], optargs: Optional[List[str]] = None
    ) -> None:
        """Wrap package management commands for Debian/Ubuntu systems

        Args:
          command: the command given to `apt-get`
          pacakge_names: a package name or list of package names to operate on
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
            raise PackageError(f"Could not {command} package(s) [{[*package_names]}]: {e.output}")

    def _add(self) -> None:
        """Add a package to the system"""
        self._apt("install", f"{self.name}={self.fullversion}", optargs=["--allow-downgrades"])

    def _remove(self) -> None:
        """Removes a package from the system. Implementation-specific"""
        return self._apt("remove", f"{self.name}={self.fullversion}")

    @property
    def name(self) -> str:
        """Returns the name of the package"""
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
        return self._state is PackageState.Present

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


class Version(object):
    """An abstraction around package versions. This seems like it should
    be strictly unnecessary, except that `apt_pkg` is not usable inside a
    venv, and wedging version comparisions into :class:`DebianPackage` would
    overcomplicate it
    """

    def __init__(self, version: str, epoch: str):
        self._version = version
        self._epoch = epoch or ""

    def __repr__(self):
        """A representation of the package."""
        return "<{}.{}: {}>".format(self.__module__, self.__class__.__name__, self.__dict__)

    def __str__(self):
        """A human-readable representation of the package"""
        return "{}{}".format("{}".format(f"{self._epoch}:" if self._epoch else ""), self._version)

    @property
    def epoch(self):
        """Returns the epoch for a package. May be empty"""
        return self._epoch

    @property
    def number(self):
        """Returns the version number for a package."""
        return self._version

    def _compare_version(self, other, op: str) -> int:
        try:
            rc = check_call(["dpkg", "--compare-versions", str(self), op, str(other)])
            return rc
        except CalledProcessError as e:
            # This may not be a bad thing, since `dpkg --compare-version` does not always
            # return 0
            return e.returncode

    def __lt__(self, other) -> bool:
        return self._compare_version(other, "lt") == 0

    def __eq__(self, other) -> bool:
        return self._compare_version(other, "eq") == 0

    def __gt__(self, other) -> bool:
        return self._compare_version(other, "gt") == 0

    def __le__(self, other) -> bool:
        return self.__eq__(other) or self.__lt__(other)

    def __ge__(self, other) -> bool:
        return self.__gt__(other) or self.__eq__(other)

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)


class PackageCache(Mapping):
    """An abstraction to represent installed/available packages.

    Instantiating :class:`PackageCache` will parse out the list of
    available packages from `apt-cache`, then the list of installed packages
    from `dpkg -l`, setting the :class:`PackageState` value of the
    :class:`DebianPackage` objects stored in :class:`PackageState` to
    `Present` or `Latest`, depending on version comparisons.

    cache = dpkg.PackageCache()
    vim = cache["vim"]
    vim.ensure(dpkg.PackageState.Latest)
    # alternatively
    vim.state = dpkg.PackageState.Latest
    """

    def __init__(self):
        self._package_map = {}
        self._merge_with_cache(self._generate_packages_from_apt_cache())
        self._merge_with_cache(self._generate_packages_from_dpkg())

    def __contains__(self, key: str) -> bool:
        return key in self._package_map

    def __len__(self) -> int:
        return len(self._package_map)

    def __iter__(self) -> Iterable["DebianPackage"]:
        return iter(self._package_map.values())

    def __getitem__(self, package_name: str) -> DebianPackage:
        """Return either the installed version or latest version for a given package."""
        pkgs = self._package_map[package_name]
        for p in pkgs:
            if p.state is PackageState.Present:
                return p
        else:
            return pkgs[0]

    def get_all(self, package_name: str) -> List["DebianPackage"]:
        """Return all known packages for a given package name.

        Args:
          package_name: the base name of a package

        Returns:
          A list of packages with that name, sorted by version. The most recent version
            will be the first value, whether that is the currently installed version or not.
        """
        return self._package_map[package_name]

    def _merge_with_cache(self, packages: Dict) -> None:
        """Update the cache with new packages and reconcile their state."""
        for pkg in packages:
            packages[pkg].sort(key=lambda x: x.version, reverse=True)

            if pkg in self._package_map:
                for p in packages[pkg]:
                    if p.state == PackageState.Present and p in self._package_map[pkg]:
                        # Since the list is sorted, we know that the first value will
                        # be the latest version
                        latest = self._package_map[pkg].index(p) == 0
                        if latest:
                            self._package_map[pkg].remove(p)
                            p.state = PackageState.Latest

                # Don't get duplicates in the list in case `dpkg -l` and `apt-cache` have the
                # same entries which don't match above
                unique = list(set(packages[pkg]) | set(self._package_map[pkg]))

                # Re-sort the list
                unique.sort(key=lambda x: x.version, reverse=True)

                self._package_map[pkg] = unique
            else:
                self._package_map[pkg] = packages[pkg]

    def _generate_packages_from_apt_cache(self) -> Dict:
        """Add the list of packages apt-cache knows about to the map."""
        pkgs = {}
        output = ""

        try:
            output = check_output(["apt-cache", "dumpavail"], universal_newlines=True)
        except CalledProcessError as e:
            raise PackageError("Could not list packages in apt-cache: {}".format(e.output))

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

            epoch, version = self._get_epoch_from_version(vals["Version"])
            pkg = DebianPackage(
                vals["Package"],
                version,
                epoch,
                vals["Architecture"],
                PackageState.Available,
            )

            if vals["Package"] in pkgs:
                pkgs[vals["Package"]].append(pkg)
            else:
                pkgs[vals["Package"]] = [pkg]

        return pkgs

    @staticmethod
    def _get_epoch_from_version(version: str) -> Tuple[str, str]:
        """Pull the epoch, if any, out of a version string"""
        epoch_matcher = re.compile(r"^((?P<epoch>\d+):)?(?P<version>.*)")
        matches = epoch_matcher.search(version).groupdict()
        return matches.get("epoch", ""), matches.get("version")

    def _generate_packages_from_dpkg(self) -> Dict:
        """Parse the list of installed packages into the cache."""
        output = ""
        try:
            output = check_output(["dpkg", "-l"], universal_newlines=True)
        except CalledProcessError as e:
            raise PackageError("Could not list packages: {}".format(e.output))

        # Pop off the output from `dpkg -l' because there's no flag to
        # omit it`
        lines = str(output).splitlines()[5:]

        # Regexps are a really terrible way to do this. Thanks dpkg
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

        pkgs = {}
        for line in lines:
            matches = dpkg_matcher.search(line).groupdict()
            epoch, version = self._get_epoch_from_version(matches["version"])
            pkg = DebianPackage(
                matches["package_name"],
                version,
                epoch,
                matches["arch"],
                PackageState.Present,
            )

            if matches["package_name"] in pkgs:
                pkgs[matches["package_name"]].append(pkg)
            else:
                pkgs[matches["package_name"]] = [pkg]

        return pkgs


VALID_SOURCE_TYPES = ("deb", "deb-src")


class InvalidSourceError(Error):
    """Exceptions for invalid source entries."""


class GPGKeyError(Error):
    """Exceptions for GPG keys."""


class DebianRepository:
    """An abstraction to represent a repository."""

    def __init__(
        self,
        enabled: bool,
        repotype: str,
        uri: str,
        release: str,
        groups: List[str],
        filename: str,
        gpg_key_filename: str,
    ):
        self._enabled = enabled
        self._repotype = repotype
        self._uri = uri
        self._release = release
        self._groups = groups
        self._filename = filename
        self._gpg_key_filename = gpg_key_filename

    @property
    def enabled(self):
        """Return whether or not the repository is enabled."""
        return self._enabled

    @property
    def repotype(self):
        """Return whether it is binary or source."""
        return self._repotype

    @property
    def uri(self):
        """Return the URI."""
        return self._uri

    @property
    def release(self):
        """Return which Debian/Ubuntu releases it is valid for."""
        return self._release

    @property
    def groups(self):
        """Return the enabled package groups."""
        return self._groups

    @property
    def filename(self):
        """Returns the filename for a repository."""
        return self._filename

    @property
    def gpg_key(self):
        """Returns the path to the GPG key for this repository."""
        return self._gpg_key_filename

    def disable(self) -> None:
        """Remove this repository. Disable by default."""
        for line in fileinput.input(self._filename, inplace=True):
            if self._uri in str(line):
                line = f"# {line}"

    def import_key(self, key: str) -> None:
        """Import an ASCII Armor key.
        A Radix64 format keyid is also supported for backwards
        compatibility. In this case Ubuntu keyserver will be
        queried for a key via HTTPS by its keyid. This method
        is less preferrable because https proxy servers may
        require traffic decryption which is equivalent to a
        man-in-the-middle attack (a proxy server impersonates
        keyserver TLS certificates and has to be explicitly
        trusted by the system).

        Args:
          key: A GPG key in ASCII armor format,
                      including BEGIN and END markers or a keyid.

        Raises:
          GPGKeyError if the key could not be imported
        """
        key = key.strip()
        if "-" in key or "\n" in key:
            # Send everything not obviously a keyid to GPG to import, as
            # we trust its validation better than our own. eg. handling
            # comments before the key.
            logger.debug("PGP key found (looks like ASCII Armor format)")
            if (
                "-----BEGIN PGP PUBLIC KEY BLOCK-----" in key
                and "-----END PGP PUBLIC KEY BLOCK-----" in key
            ):
                logger.debug("Writing provided PGP key in the binary format")
                key_bytes = key.encode("utf-8")
                key_name = self._get_keyid_by_gpg_key(key_bytes)
                key_gpg = self._dearmor_gpg_key(key_bytes)
                self._gpg_key_filename = "/etc/apt/trusted.gpg.d/{}.gpg".format(key_name)
                self._write_apt_gpg_keyfile(key_name=key_name, key_material=key_gpg)
            else:
                raise GPGKeyError("ASCII armor markers missing from GPG key")
        else:
            logger.warning("PGP key found (looks like Radix64 format)")
            logger.warning("SECURELY importing PGP key from keyserver; " "full key not provided.")
            # as of bionic add-apt-repository uses curl with an HTTPS keyserver URL
            # to retrieve GPG keys. `apt-key adv` command is deprecated as is
            # apt-key in general as noted in its manpage. See lp:1433761 for more
            # history. Instead, /etc/apt/trusted.gpg.d is used directly to drop
            # gpg
            key_asc = self._get_key_by_keyid(key)
            # write the key in GPG format so that apt-key list shows it
            key_gpg = self._dearmor_gpg_key(key_asc.encode("utf-8"))
            self._gpg_key_filename = "/etc/apt/trusted.gpg.d/{}.gpg".format(key)
            self._write_apt_gpg_keyfile(key_name=key, key_material=key_gpg)

    @staticmethod
    def _get_keyid_by_gpg_key(key_material: bytes) -> str:
        """Get a GPG key fingerprint by GPG key material.
        Gets a GPG key fingerprint (40-digit, 160-bit) by the ASCII armor-encoded
        or binary GPG key material. Can be used, for example, to generate file
        names for keys passed via charm options.
        """
        # Use the same gpg command for both Xenial and Bionic
        cmd = ["gpg", "--with-colons", "--with-fingerprint"]
        ps = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            universal_newlines=True,
        )
        out, err = ps.communicate(input=str(key_material))
        if "gpg: no valid OpenPGP data found." in err:
            raise GPGKeyError("Invalid GPG key material provided")
        # from gnupg2 docs: fpr :: Fingerprint (fingerprint is in field 10)
        return re.search(r"^fpr:{9}([0-9A-F]{40}):$", out, re.MULTILINE).group(1)

    @staticmethod
    def _get_key_by_keyid(keyid: str) -> str:
        """Get a key via HTTPS from the Ubuntu keyserver.
        Different key ID formats are supported by SKS keyservers (the longer ones
        are more secure, see "dead beef attack" and https://evil32.com/). Since
        HTTPS is used, if SSLBump-like HTTPS proxies are in place, they will
        impersonate keyserver.ubuntu.com and generate a certificate with
        keyserver.ubuntu.com in the CN field or in SubjAltName fields of a
        certificate. If such proxy behavior is expected it is necessary to add the
        CA certificate chain containing the intermediate CA of the SSLBump proxy to
        every machine that this code runs on via ca-certs cloud-init directive (via
        cloudinit-userdata model-config) or via other means (such as through a
        custom charm option). Also note that DNS resolution for the hostname in a
        URL is done at a proxy server - not at the client side.
        8-digit (32 bit) key ID
        https://keyserver.ubuntu.com/pks/lookup?search=0x4652B4E6
        16-digit (64 bit) key ID
        https://keyserver.ubuntu.com/pks/lookup?search=0x6E85A86E4652B4E6
        40-digit key ID:
        https://keyserver.ubuntu.com/pks/lookup?search=0x35F77D63B5CEC106C577ED856E85A86E4652B4E6

        Args:
          keyid: An 8, 16 or 40 hex digit keyid to find a key for

        Returns:
          A string contining key material for the specified GPG key id


        Raises:
          subprocess.CalledProcessError
        """
        # options=mr - machine-readable output (disables html wrappers)
        keyserver_url = (
            "https://keyserver.ubuntu.com" "/pks/lookup?op=get&options=mr&exact=on&search=0x{}"
        )
        curl_cmd = ["curl", keyserver_url.format(keyid)]
        # use proxy server settings in order to retrieve the key
        return check_output(curl_cmd)

    @staticmethod
    def _dearmor_gpg_key(key_asc: bytes) -> str:
        """Converts a GPG key in the ASCII armor format to the binary format.

        Args:
          key_asc: A GPG key in ASCII armor format.

        Returns:
          A GPG key in binary format as a string

        Raises:
          GPGKeyError
        """
        ps = subprocess.Popen(
            ["gpg", "--dearmor"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            universal_newlines=True,
        )
        out, err = ps.communicate(input=str(key_asc))
        if "gpg: no valid OpenPGP data found." in err:
            raise GPGKeyError(
                "Invalid GPG key material. Check your network setup"
                " (MTU, routing, DNS) and/or proxy server settings"
                " as well as destination keyserver status."
            )
        else:
            return out

    @staticmethod
    def _write_apt_gpg_keyfile(key_name: str, key_material: str) -> None:
        """Writes GPG key material into a file at a provided path.

        Args:
          key_name: A key name to use for a key file (could be a fingerprint)
          key_material: A GPG key material (binary)
        """
        with open(key_name, "wb") as keyf:
            keyf.write(key_material.encode("utf-8"))


class RepositoryList(Mapping):
    """An representation of known repositories.

    Instantiation of :class:`RepositoryList` will iterate through the
    filesystem, parse out repository files in `/etc/apt/...`, and create
    :class:`DebianRepository` objects in this list.

    Typical usage:
      repositories = dpkg.RepositoryList()
      repositories.add(DebianRepository(
        enabled=True, repotype="deb", uri="https://example.com", release="focal",
        groups=["universe"]
      ))
    """

    def __init__(self):
        self._repository_map = {}
        # Repositories that we're adding -- used to implement mode param
        self.default_file = "/etc/apt/sources.list"

        # read sources.list if it exists
        if os.path.isfile(self.default_file):
            self.load(self.default_file)

        # read sources.list.d
        for file in glob.iglob("{}/*.list".format("/etc/apt/sources.list.d")):
            self.load(file)

    def __contains__(self, key: str) -> bool:
        return key in self._repository_map

    def __len__(self) -> int:
        return len(self._repository_map)

    def __iter__(self) -> Iterable[DebianRepository]:
        return iter(self._repository_map.values())

    def __getitem__(self, repository_uri: str) -> DebianRepository:
        """Return a given :class:`DebianRepository`."""
        return self._repository_map[repository_uri]

    def __setitem__(self, repository_uri: str, repository: DebianRepository) -> None:
        """Add a :class:`DebianRepository` to the cache."""
        self._repository_map[repository_uri] = repository

    def load(self, file: str):
        """Load a repository source file into the cache.

        Args:
          file: the path to the repository file
        """
        f = open(file, "r")
        for n, line in enumerate(f):
            repo = self._parse(line, file)
            self._repository_map[f"{repo.repotype}-{repo.uri}-{repo.release}"] = repo

    @staticmethod
    def _parse(line: str, filename: str) -> DebianRepository:
        """Parse a line in a sources.list file.

        Args:
          line: a single line from `load` to parse
          filename: the filename being read

        Raises:
          InvalidSoureError if the source type is unknown
        """
        enabled = True
        repotype = uri = release = gpg_key = ""
        groups = []

        line = line.strip()
        if line.startswith("#"):
            enabled = False
            line = line[1:]

        # Check for another "#" in the line and treat a part after it as a comment, then strip it off.
        i = line.find("#")
        if i > 0:
            line = line[:i]

        # Split a source into substrings to initialize a new repo.
        source = line.strip()
        if source:
            chunks = source.split()
            if chunks[0] not in VALID_SOURCE_TYPES:
                raise InvalidSourceError("An invalid sources line was found in %s!", filename)
            if "[signed-by" in chunks[1]:
                gpg_key = re.sub(r"\[signed-by=(.*?)]", r"\1", chunks[1])
                del chunks[1]
            repotype = chunks[0]
            uri = chunks[1]
            release = chunks[2]
            groups = chunks[3:]

        return DebianRepository(enabled, repotype, uri, release, groups, filename, gpg_key)

    def add(self, repo: DebianRepository, default_filename: Optional[bool] = True) -> None:
        """Add a new repository to the system.

        Args:
          repo: a :class:`DebianRepository` object
          default_filename: an (Optional) filename if the default is not desirable
        """
        if repo.filename and default_filename:
            logger.error(
                "Cannot add a repository with a default filename and a "
                "filename set in the `DebianRepository` object"
            )

        new_filename = "{}-{}.list".format(urlparse(repo.uri).path.replace("/", "-"), repo.release)

        fname = repo.filename or new_filename

        with open(fname, "wb") as f:
            f.write(
                f"{'#' if not repo.enabled else ''}"
                f"{f'[signed-by={repo.gpg_key}]' if repo.gpg_key else ''}{repo.repotype} "
                f"{repo.uri} {repo.release} {' '.join(repo.groups)}\n".encode("utf-8")
            )

        self._repository_map[f"{repo.repotype}-{repo.uri}-{repo.release}"] = repo

    def disable(self, repo: DebianRepository) -> None:
        """Remove a repository. Disable by default.

        Args:
          repo: a :class:`DebianRepository` to disable
        """
        for line in fileinput.input(repo.filename, inplace=True):
            if repo.uri in str(line):
                line = f"# {line}"

        self._repository_map[f"{repo.repotype}-{repo.uri}-{repo.release}"] = repo
