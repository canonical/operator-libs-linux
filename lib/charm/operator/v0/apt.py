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

"""Representations of the system's Debian/Ubuntu repository state.

:class:`RepositoryMapping` will return a dict-like object containing enabled system
repositories and their properties (available groups, baseuri. gpg key). This class can
add, disable, or manipulate repositories. Items can be retrieved as :class:`DebianRepository`
objects.

Typical usage example:

    repositories = apt.RepositoryMapping()
    repositories.add(DebianRepository(
    enabled=True, repotype="deb", uri="https://example.com", release="focal",
    groups=["universe"]
    ))
"""

import fileinput
import glob
from io import TextIOWrapper
import logging
import os
import re
import subprocess

from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from subprocess import check_call, check_output, CalledProcessError
from typing import Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import urlparse


logger = logging.getLogger(__name__)

VALID_SOURCE_TYPES = ("deb", "deb-src")


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
        filename: Optional[str] = "",
        gpg_key_filename: Optional[str] = "",
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

    @filename.setter
    def filename(self, fname: str) -> None:
        """Sets the filename used when a repo is written back to diskself.

        Args:
            fname: a filename to write the repository information to.
        """
        if not fname.endswith(".list"):
            raise InvalidSourceError("apt source filenames should end in .list!")

        self._filename = fname

    @property
    def gpg_key(self):
        """Returns the path to the GPG key for this repository."""
        return self._gpg_key_filename

    @classmethod
    def from_repo_line(
        cls, repo_line: str, write_file: Optional[bool] = True
    ) -> "DebianRepository":
        """Instantiate a new :class:`DebianRepository` a `sources.list` entry line.

        Args:
            repo_line: a string representing a repository entry
        """
        repo = RepositoryMapping._parse(repo_line, "UserInput")
        fname = f"{urlparse(repo.uri).path.lstrip('/').replace('/', '-')}-{repo.release}.list"
        repo.filename = fname

        if write_file:
            with open(fname, "wb") as f:
                f.write(
                    f"{'#' if not repo.enabled else ''}"
                    f"{f'[signed-by={repo.gpg_key}]' if repo.gpg_key else ''}{repo.repotype} "
                    f"{repo.uri} {repo.release} {' '.join(repo.groups)}\n".encode("utf-8")
                )

        return repo

    def disable(self) -> None:
        """Remove this repository from consideration. Disable it instead of removing from the repository file."""
        searcher = f"{self.repotype} {f'[signed-by={self.gpg_key}]' if self.gpg_key else ''}{self.uri} {self.release}"
        for line in fileinput.input(self._filename, inplace=True):
            if re.match(rf"^{re.escape(searcher)}\s", line):
                print(f"# {line}", end="")
            else:
                print(line, end="")

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
                self._gpg_key_filename = f"/etc/apt/trusted.gpg.d/{key_name}.gpg"
                self._write_apt_gpg_keyfile(key_name=key_name, key_material=key_gpg)
            else:
                raise GPGKeyError("ASCII armor markers missing from GPG key")
        else:
            logger.warning(
                "PGP key found (looks like Radix64 format). "
                "SECURELY importing PGP key from keyserver; "
                "full key not provided."
            )
            # as of bionic add-apt-repository uses curl with an HTTPS keyserver URL
            # to retrieve GPG keys. `apt-key adv` command is deprecated as is
            # apt-key in general as noted in its manpage. See lp:1433761 for more
            # history. Instead, /etc/apt/trusted.gpg.d is used directly to drop
            # gpg
            key_asc = self._get_key_by_keyid(key)
            # write the key in GPG format so that apt-key list shows it
            key_gpg = self._dearmor_gpg_key(key_asc.encode("utf-8"))
            self._gpg_key_filename = f"/etc/apt/trusted.gpg.d/{key}.gpg"
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


class RepositoryMapping(Mapping):
    """An representation of known repositories.

    Instantiation of :class:`RepositoryMapping` will iterate through the
    filesystem, parse out repository files in `/etc/apt/...`, and create
    :class:`DebianRepository` objects in this list.

    Typical usage:
      repositories = dpkg.RepositoryMapping()
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
        for file in glob.iglob("/etc/apt/sources.list.d/*.list"):
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

        new_filename = (
            f"{urlparse(repo.uri).path.lstrip('/').replace('/', '-')}-{repo.release}.list"
        )

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
        searcher = f"{repo.repotype} {f'[signed-by={repo.gpg_key}]' if repo.gpg_key else ''} {repo.uri} {repo.release}"

        for line in fileinput.input(repo.filename, inplace=True):
            if re.match(rf"^{re.escape(searcher)}\s", line):
                print(f"# {line}", end="")
            else:
                print(line, end="")

        self._repository_map[f"{repo.repotype}-{repo.uri}-{repo.release}"] = repo
