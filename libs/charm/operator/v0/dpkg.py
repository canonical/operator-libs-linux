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
   information."""

import glob
import os
import re
import subprocess

from collections.abc import Mapping
from enum import IntEnum
from itertools import chain
from subprocess import check_call, check_output, CalledProcessError
from typing import Dict, List, Tuple, Union


VALID_SOURCE_TYPES = ('deb', 'deb-src')

class Error(Exception):
    """Base class of most errors raised by the Pebble client."""

    def __repr__(self):
        return '<{}.{} {}>'.format(type(self).__module__, type(self).__name__, self.args)

    def name(self):
        """Return a string representation of the model plus class."""
        return '<{}.{}>'.format(type(self).__module__, type(self).__name__)

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


PackageState = IntEnum('PackageState', [(i.name, i.value) for i in chain(StateBase, PackageStateBase)])


class DebianPackage(object):
    """Represents a traditional system package."""
    def __init__(self, name: str, version: str, epoch: str, arch: str, state: PackageState) -> None:
        self._name = name
        self._arch = arch
        self._state = state
        self._version = Version(version, epoch)

    def __eq__(self, other):
        """Equality for comparison."""
        return isinstance(other, self.__class__) and \
            (self._name, self._version.number) == (other._name, other._version.number)

    def __hash__(self):
        """A basic hash so this class can be used in Mappings and dicts."""
        return hash((self._name, self._version.number))

    def __repr__(self):
        """A representation of the package."""
        return "<{}.{}: {}>".format(self.__module__, self.__class__.__name__, self.__dict__)

    def __str__(self):
        """A human-readable representation of the package"""
        return "<{}: {}-{}.{} -- {}>".format(self.__class__.__name__, self._name,
                                             self._version, self._arch, self._state)

    @staticmethod
    def _apt(command: str, package_names: Union[str, List]) -> None:
        """Wrap package management commands for Debian/Ubuntu systems"""
        if isinstance(package_names, str):
            package_names = [package_names]
        _cmd = ["apt-get", "-y", "--allow-downgrades", command, *package_names]
        try:
            subprocess.check_call(_cmd)
        except CalledProcessError as e:
            raise PackageError("Could not %s package(s) [%s]: %s",
                               command, *package_names, e.output)

    def _add(self) -> None:
        """Add a package to the system"""
        self._apt("install", f"{self.name}={self.fullversion}")

    def _remove(self) -> None:
        """Removes a package from the system. Implementation-specific"""
        return self._apt("remove", f"{self.name}={self.fullversion}")

    @property
    def name(self) -> str:
        """Returns the name of the package"""
        return self._name

    def ensure(self, state: PackageState):
        """Ensures that a package is in a given state."""
        if self._state is not state:
            if state is not PackageState.Present:
                self._remove()
            else:
                self._add()

    @property
    def present(self) -> bool:
        """Returns whether or not a package is present."""
        return self._state is PackageState.Present

    @property
    def latest(self) -> bool:
        """Returns whether the package is the most recent version."""
        return self._state is PackageState.Latest

    @property
    def version(self) -> str:
        """Returns the version for a package."""
        return self._version.number

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
        return "{}{}".format("{}:".format(self._epoch if self._epoch else ""),
                             self._version)

    @property
    def epoch(self):
        """Returns the epoch for a package. May be empty"""
        return self._epoch

    @property
    def number(self):
        """Returns the version number for a package."""
        return self._version

    def _compare_version(self, other, op):
        try:
            rc = check_call(['dpkg', '--compare-version', str(self), op, str(other)])
            return rc
        except CalledProcessError as e:
            # This may not be a bad thing, since `dpkg --compare-version` does not always
            # return 0
            return e.returncode

    def __lt__(self, other):
        return self._compare_version(other, 'lt') == -1

    def __eq__(self, other):
        return self._compare_version(other, 'eq') == 0

    def __gt__(self, other):
        return self._compare_version(other, 'gt') == 1

    def __le__(self, other):
        return self.__eq__(other) or self.__lt__(other)

    def __ge__(self, other):
        return self.__gt__(other) or self.__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)


class PackageCache(Mapping):
    """An abstraction to represent installed/available packages."""

    def __init__(self):
        self._package_map = {}
        self._merge_with_cache(self._generate_packages_from_apt_cache())
        self._merge_with_cache(self._generate_packages_from_dpkg())

    def __contains__(self, key: str):
        return key in self._package_map

    def __len__(self):
        return len(self._package_map)

    def __iter__(self):
        return iter(self._package_map)

    def __getitem__(self, package_name: str) -> DebianPackage:
        """Return either the installed version or latest version for a given package."""
        pkgs = self._package_map[package_name]
        for p in pkgs:
            if p.state is PackageState.Present:
                return p
        else:
            return pkgs[0]

    def get_all(self, package_name: str) -> List['DebianPackage']:
        """Return all known packages for a given package name."""
        return self._package_map[package_name]

    def _merge_with_cache(self, packages: Dict) -> None:
        """Update the cache with new packages."""
        for pkg in packages:
            pkg.sort(key=lambda x: x.version)
            if pkg in self._package_map:
                for p in pkg:
                    if p.state == PackageState.Present and p in self._package_map[pkg]:
                        # Since the list is sorted, we know that the first value will
                        # be the latest version
                        print("{} is the latest version")
                        latest = self._package_map[pkg].index(p) == 0
                        self._package_map[pkg].remove(p)
                        p.state = PackageState.Latest if latest else PackageState.Present
                unique = list(set(pkg) | set(self._package_map[pkg]))

                # Re-sort the list
                unique.sort(key=lambda x: x.version)
                self._package_map[pkg] = unique
            else:
                self._package_map[pkg] = pkg

    def _generate_packages_from_apt_cache(self) -> Dict:
        pkgs = {}
        output = ""

        try:
            output = check_output(["apt-cache", "dumpavail"], universal_newlines=True)
        except CalledProcessError as e:
            print("Could not list packages in apt-cache: {}".format(e.output))

        pkg_groups = output.strip().split('\n\n')
        keys = ("Package", "Architecture", "Version")

        for pkg_raw in pkg_groups:
            lines = str(pkg_raw).splitlines()
            vals = {}
            for line in lines:
                if line.startswith(keys):
                    items = line.split(':')
                    vals[items[0]] = items[1]
                else:
                    continue

            epoch, version = self._get_epoch_from_version(vals["Version"])
            pkg = DebianPackage(
                vals["Package"],
                version,
                epoch,
                vals["Architecture"],
                PackageState.Available
            )

            if vals["Package"] in pkgs:
                pkgs[vals["Package"]].append(pkg)
            else:
                pkgs[vals["Package"]] = [pkg]

        return pkgs

    @staticmethod
    def _get_epoch_from_version(version: str) -> Tuple[str, str]:
        """Pull the epoch, if any, out of a version string"""
        epoch_matcher = re.compile(r'((?P<epoch>\d+):)?(?P<version>.*)')
        matches = epoch_matcher.search(version).groupdict()
        return matches.get("epoch", ""), matches.get("version")

    def _generate_packages_from_dpkg(self) -> Dict:
        output = ""
        try:
            output = check_output(["dpkg", "-l"], universal_newlines=True)
        except CalledProcessError as e:
            print("Could not list packages: {}".format(e.output))

        # Pop off the output from `dpkg -l' because there's no flag to
        # omit it`
        lines = str(output).splitlines()[5:]

        # Regexps are a really terrible way to do this. Thanks dpkg
        dpkg_matcher = re.compile(r"""
        ^(?P<package_status>\w+?)\s+
        (?P<package_name>.*?)(?P<throwaway_arch>:\w+?)?\s+
        (?P<version>.*?)\s+
        (?P<arch>\w+?)\s+
        (?P<description>.*)
        """, re.VERBOSE)

        pkgs = {}
        for line in lines:
            matches = dpkg_matcher.search(line).groupdict()
            epoch, version = self._get_epoch_from_version(matches["version"])
            pkg = DebianPackage(
                matches["package_name"],
                version,
                epoch,
                matches["arch"],
                PackageState.Present
            )

            if matches["package_name"] in pkgs:
                pkgs[matches["package_name"]].append(pkg)
            else:
                pkgs[matches["package_name"]] = [pkg]

        return pkgs


class InvalidSource(Exception):
    pass


# Simple version of aptsources.sourceslist.SourcesList.
# No advanced logic and no backups inside.
class SourcesList(object):
    def __init__(self, module):
        self.module = module
        self.files = {}  # group sources by file
        # Repositories that we're adding -- used to implement mode param
        self.new_repos = set()
        self.default_file = self._apt_cfg_file('Dir::Etc::sourcelist')

        # read sources.list if it exists
        if os.path.isfile(self.default_file):
            self.load(self.default_file)

        # read sources.list.d
        for file in glob.iglob('%s/*.list' % self._apt_cfg_dir('Dir::Etc::sourceparts')):
            self.load(file)

    def __iter__(self):
        '''Simple iterator to go over all sources. Empty, non-source, and other not valid lines will be skipped.'''
        for file, sources in self.files.items():
            for n, valid, enabled, source, comment in sources:
                if valid:
                    yield file, n, enabled, source, comment

    def _expand_path(self, filename):
        if '/' in filename:
            return filename
        else:
            return os.path.abspath(os.path.join(self._apt_cfg_dir('Dir::Etc::sourceparts'), filename))

    def _suggest_filename(self, line):
        def _cleanup_filename(s):
            filename = self.module.params['filename']
            if filename is not None:
                return filename
            return '_'.join(re.sub('[^a-zA-Z0-9]', ' ', s).split())

        def _strip_username_password(s):
            if '@' in s:
                s = s.split('@', 1)
                s = s[-1]
            return s

        # Drop options and protocols.
        line = re.sub(r'\[[^\]]+\]', '', line)
        line = re.sub(r'\w+://', '', line)

        # split line into valid keywords
        parts = [part for part in line.split() if part not in VALID_SOURCE_TYPES]

        # Drop usernames and passwords
        parts[0] = _strip_username_password(parts[0])

        return '%s.list' % _cleanup_filename(' '.join(parts[:1]))

    def _parse(self, line, raise_if_invalid_or_disabled=False):
        valid = False
        enabled = True
        source = ''
        comment = ''

        line = line.strip()
        if line.startswith('#'):
            enabled = False
            line = line[1:]

        # Check for another "#" in the line and treat a part after it as a comment.
        i = line.find('#')
        if i > 0:
            comment = line[i + 1:].strip()
            line = line[:i]

        # Split a source into substring to make sure that it is source spec.
        # Duplicated whitespaces in a valid source spec will be removed.
        source = line.strip()
        if source:
            chunks = source.split()
            if chunks[0] in VALID_SOURCE_TYPES:
                valid = True
                source = ' '.join(chunks)

        if raise_if_invalid_or_disabled and (not valid or not enabled):
            raise InvalidSource(line)

        return valid, enabled, source, comment

    def load(self, file):
        group = []
        f = open(file, 'r')
        for n, line in enumerate(f):
            valid, enabled, source, comment = self._parse(line)
            group.append((n, valid, enabled, source, comment))
        self.files[file] = group

    def save(self):
        for filename, sources in list(self.files.items()):
            if sources:
                d, fn = os.path.split(filename)
                try:
                    os.makedirs(d)
                except OSError as err:
                    if not os.path.isdir(d):
                        self.module.fail_json("Failed to create directory %s: %s" % (d, to_native(err)))
                fd, tmp_path = tempfile.mkstemp(prefix=".%s-" % fn, dir=d)

                f = os.fdopen(fd, 'w')
                for n, valid, enabled, source, comment in sources:
                    chunks = []
                    if not enabled:
                        chunks.append('# ')
                    chunks.append(source)
                    if comment:
                        chunks.append(' # ')
                        chunks.append(comment)
                    chunks.append('\n')
                    line = ''.join(chunks)

                    try:
                        f.write(line)
                    except IOError as err:
                        self.module.fail_json(msg="Failed to write to file %s: %s" % (tmp_path, to_native(err)))
                self.module.atomic_move(tmp_path, filename)

                # allow the user to override the default mode
                if filename in self.new_repos:
                    this_mode = self.module.params.get('mode', DEFAULT_SOURCES_PERM)
                    self.module.set_mode_if_different(filename, this_mode, False)
            else:
                del self.files[filename]
                if os.path.exists(filename):
                    os.remove(filename)

    def dump(self):
        dumpstruct = {}
        for filename, sources in self.files.items():
            if sources:
                lines = []
                for n, valid, enabled, source, comment in sources:
                    chunks = []
                    if not enabled:
                        chunks.append('# ')
                    chunks.append(source)
                    if comment:
                        chunks.append(' # ')
                        chunks.append(comment)
                    chunks.append('\n')
                    lines.append(''.join(chunks))
                dumpstruct[filename] = ''.join(lines)
        return dumpstruct

    def _choice(self, new, old):
        if new is None:
            return old
        return new

    def modify(self, file, n, enabled=None, source=None, comment=None):
        '''
        This function to be used with iterator, so we don't care of invalid sources.
        If source, enabled, or comment is None, original value from line ``n`` will be preserved.
        '''
        valid, enabled_old, source_old, comment_old = self.files[file][n][1:]
        self.files[file][n] = (n, valid, self._choice(enabled, enabled_old), self._choice(source, source_old), self._choice(comment, comment_old))

    def _add_valid_source(self, source_new, comment_new, file):
        # We'll try to reuse disabled source if we have it.
        # If we have more than one entry, we will enable them all - no advanced logic, remember.
        found = False
        for filename, n, enabled, source, comment in self:
            if source == source_new:
                self.modify(filename, n, enabled=True)
                found = True

        if not found:
            if file is None:
                file = self.default_file
            else:
                file = self._expand_path(file)

            if file not in self.files:
                self.files[file] = []

            files = self.files[file]
            files.append((len(files), True, True, source_new, comment_new))
            self.new_repos.add(file)

    def add_source(self, line, comment='', file=None):
        source = self._parse(line, raise_if_invalid_or_disabled=True)[2]

        # Prefer separate files for new sources.
        self._add_valid_source(source, comment, file=file or self._suggest_filename(source))

    def _remove_valid_source(self, source):
        # If we have more than one entry, we will remove them all (not comment, remove!)
        for filename, n, enabled, src, comment in self:
            if source == src and enabled:
                self.files[filename].pop(n)

    def remove_source(self, line):
        source = self._parse(line, raise_if_invalid_or_disabled=True)[2]
        self._remove_valid_source(source)


class UbuntuSourcesList(SourcesList):

    LP_API = 'https://launchpad.net/api/1.0/~%s/+archive/%s'

    def __init__(self, module, add_ppa_signing_keys_callback=None):
        self.module = module
        self.add_ppa_signing_keys_callback = add_ppa_signing_keys_callback
        self.codename = module.params['codename'] or distro.codename
        super(UbuntuSourcesList, self).__init__(module)

    def __deepcopy__(self, memo=None):
        return UbuntuSourcesList(
            self.module,
            add_ppa_signing_keys_callback=self.add_ppa_signing_keys_callback
        )

    def _get_ppa_info(self, owner_name, ppa_name):
        lp_api = self.LP_API % (owner_name, ppa_name)

        headers = dict(Accept='application/json')
        response, info = fetch_url(self.module, lp_api, headers=headers)
        if info['status'] != 200:
            self.module.fail_json(msg="failed to fetch PPA information, error was: %s" % info['msg'])
        return json.loads(to_native(response.read()))

    def _expand_ppa(self, path):
        ppa = path.split(':')[1]
        ppa_owner = ppa.split('/')[0]
        try:
            ppa_name = ppa.split('/')[1]
        except IndexError:
            ppa_name = 'ppa'

        line = 'deb http://ppa.launchpad.net/%s/%s/ubuntu %s main' % (ppa_owner, ppa_name, self.codename)
        return line, ppa_owner, ppa_name

    def _key_already_exists(self, key_fingerprint):
        rc, out, err = self.module.run_command('apt-key export %s' % key_fingerprint, check_rc=True)
        return len(err) == 0

    def add_source(self, line, comment='', file=None):
        if line.startswith('ppa:'):
            source, ppa_owner, ppa_name = self._expand_ppa(line)

            if source in self.repos_urls:
                # repository already exists
                return

            if self.add_ppa_signing_keys_callback is not None:
                info = self._get_ppa_info(ppa_owner, ppa_name)
                if not self._key_already_exists(info['signing_key_fingerprint']):
                    command = ['apt-key', 'adv', '--recv-keys', '--no-tty', '--keyserver', 'hkp://keyserver.ubuntu.com:80', info['signing_key_fingerprint']]
                    self.add_ppa_signing_keys_callback(command)

            file = file or self._suggest_filename('%s_%s' % (line, self.codename))
        else:
            source = self._parse(line, raise_if_invalid_or_disabled=True)[2]
            file = file or self._suggest_filename(source)
        self._add_valid_source(source, comment, file)

    def remove_source(self, line):
        if line.startswith('ppa:'):
            source = self._expand_ppa(line)[0]
        else:
            source = self._parse(line, raise_if_invalid_or_disabled=True)[2]
        self._remove_valid_source(source)

    @property
    def repos_urls(self):
        _repositories = []
        for parsed_repos in self.files.values():
            for parsed_repo in parsed_repos:
                valid = parsed_repo[1]
                enabled = parsed_repo[2]
                source_line = parsed_repo[3]

                if not valid or not enabled:
                    continue

                if source_line.startswith('ppa:'):
                    source, ppa_owner, ppa_name = self._expand_ppa(source_line)
                    _repositories.append(source)
                else:
                    _repositories.append(source_line)

        return _repositories


def get_add_ppa_signing_key_callback(module):
    def _run_command(command):
        module.run_command(command, check_rc=True)

    if module.check_mode:
        return None
    else:
        return _run_command


def revert_sources_list(sources_before, sources_after, sourceslist_before):
    '''Revert the sourcelist files to their previous state.'''

    # First remove any new files that were created:
    for filename in set(sources_after.keys()).difference(sources_before.keys()):
        if os.path.exists(filename):
            os.remove(filename)
    # Now revert the existing files to their former state:
    sourceslist_before.save()
