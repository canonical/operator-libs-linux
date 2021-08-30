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

"""Representations of the system's users and groups, and abstractions around managing them.

    In the `passwd` module, :class:`UserCache` creates a dict-like mapping of
    :class:`User` objects at instantiation, and :class:`GroupCache` does the same for groups.
    Users and groups are fully populated, referencing the object types of both.

    Groups are initialized upon instantiation of `UserCache` if this is not already done.

    Typical usage:
      try:
          user.add("test", )
      except UserError as e:
          logger.error(e.message)

      ---------------------------
      cache = passwd.UserCache()
      try:
          snap = cache["snap"]
          snap.ensure(passwd.UserState.NoLogin)
      except UserNotFoundError:
          logger.error("User snap not found!")
"""

import os
import logging
import re
import subprocess

from collections.abc import Mapping
from enum import Enum
from subprocess import CalledProcessError
from typing import Iterable, List, Optional, Union


logger = logging.getLogger(__name__)


def _cache_init(func):
    if _GroupCache.cache is None:
        _GroupCache.cache = GroupCache()

    if _UserCache.cache is None:
        _UserCache.cache = UserCache()

    _GroupCache.cache._realize_users()

    def inner(*args, **kwargs):
        return func(*args, **kwargs)

    return inner


@_cache_init
def _initialize() -> bool:
    """Warm all of the caches in the correct order."""
    return True


class MetaCache(type):
    @property
    def cache(cls) -> Union["UserCache", "GroupCache"]:
        return cls._cache

    @cache.setter
    def cache(cls, cache: Union["UserCache", "GroupCache"]) -> None:
        cls._cache = cache

    def __getitem__(cls, name) -> Union["User", "Group"]:
        return cls._cache[name]


class _UserCache(object, metaclass=MetaCache):
    _cache = None


class _GroupCache(object, metaclass=MetaCache):
    _cache = None


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


class UserState(Enum):
    """The state of a snap on the system or in the cache."""

    Present = "present"
    Absent = "absent"
    Disabled = "disabled"
    NoLogin = "nologin"


class UserError(Error):
    """Raised when there's an error managing a user account."""


class UserNotFoundError(Error):
    """Raised when a requested user is not known to the system."""


class User(object):
    """Represents a user and its properties.

    :class:`User` exposes the following properties about a user:
      - name: the username of a user
      - uid: an `int` representing a useruid
      - gid: an `int` representing a group
      - group: a :class:`Group` representing a user's group
      - homedir: a user's homedir
      - shell: a user's shell
      - state: a :class:`UserState` represnding a user's state
      - gecos: an (Optional) comment describing user information
    """

    def __init__(
        self,
        name,
        uid: int,
        group: Union[int, "Group"],
        homedir: str,
        shell: str,
        state: "UserState",
        gecos: Optional[str] = "",
        groups: Optional[List[Union["str", "Group"]]] = None,
    ) -> None:
        # Make sure groups can be resolved
        if _GroupCache.cache is None:
            _GroupCache.cache = GroupCache()

        self._name = name
        self._uid = uid
        self._homedir = homedir
        self._shell = shell
        self._state = state
        self._gecos = gecos if gecos else "Added by Juju"
        self._primary_group = group if type(group) is Group else GroupCache[group]
        self._groups = [g if type(g) is Group else GroupCache[g] for g in groups]

    def __hash__(self):
        """A basic hash so this class can be used in Mappings and dicts."""
        return hash((self._name, self._uid))

    def __repr__(self):
        """A representation of the snap."""
        return "<{}.{}: {}>".format(self.__module__, self.__class__.__name__, self.__dict__)

    def __str__(self):
        """A human-readable representation of the snap"""
        return "<{}: {}-{}.{}: {} -- {}>".format(
            self.__class__.__name__,
            self._name,
            self._uid,
            self._homedir,
            self.groups,
            str(self._state),
        )

    @property
    def name(self) -> str:
        """Returns the name of the user."""
        return self._name

    @property
    def uid(self) -> int:
        """Returns the ID of a user."""
        return self._uid

    @property
    def homedir(self) -> str:
        """Returns the homedir of a user."""
        return self._homedir

    @property
    def shell(self) -> str:
        """Returns the shell for a user."""
        return self._shell

    @property
    def gecos(self) -> str:
        """Returns the GECOS for a user."""
        return self._gecos

    @property
    def primary_group(self) -> "Group":
        """Returns the primary group of a user."""
        return self._primary_group

    @property
    def groups(self) -> List["Group"]:
        """Returns the groups for this user."""
        return self._groups

    def ensure(
        self,
        state: UserState,
    ):
        """Ensures that a user is in a given state.

        Args:
          state: a :class:`SnapState` to reconcile to.

        Raises:
          UserError if an error is encountered
        """
        self._state = state
        {
            UserState.NoLogin: lambda: self._disable_login(),
            UserState.Disabled: lambda: self._disable_account(),
            UserState.Present: lambda: self._add(),
        }[state]()

    def _add(self) -> None:
        """Add a user to to the system."""
        if self.present:
            return

        try:
            args = [
                "useradd",
                "-c",
                self.gecos,
                "-g",
                self.primary_group.gid,
                "-s",
                self.shell,
                "-d",
                self.homedir,
                "-u",
                self.uid,
            ]

            if self.uid < 1000:
                args.append("-r")

            subprocess.check_call(["useradd", *args, self.name])
        except CalledProcessError as e:
            raise UserError(
                "Could not add user '{}' to the system: {}".format(self.name, e.output)
            )

    def _remove(self) -> None:
        """Removes a user from the system."""
        if not self.present:
            return

        try:
            subprocess.check_call(["userdel", self.name])
        except CalledProcessError as e:
            raise UserError(
                "Could not remove user '{}' to the system: {}".format(self.name, e.output)
            )

    def _disable_login(self):
        """Disable logins for a user by setting the shell to `/sbin/nologin."""
        self._check_if_present(add_if_absent=True)
        try:
            subprocess.check_call(["usermod", "-s", "/sbin/nologin", self.name])
        except CalledProcessError as e:
            raise UserError(
                "Could not disable login for user account {}: {}".format(self.name, e.output)
            )

    def _disable_account(self):
        """Disable a user account by locking it."""
        self._check_if_present(add_if_absent=True)
        try:
            subprocess.check_call(["usermod", "-L", self.name])
        except CalledProcessError as e:
            raise UserError("Could not disable user account {}: {}".format(self.name, e.output))

    def _check_if_present(self, add_if_absent: Optional[bool] = False) -> bool:
        """Ensures a user is present in /etc/passwd.

        Args:
            add_if_absent: an (Optional) boolean for whether the user should be added if not found. Default `false`.

        Raises:
            UserNotFoundError if add_if_absent is `false` and the account is not found.

        """
        matcher = (
            rf"{self.name}:{'!' if self.state is UserState.Disabled else 'x'}:{self.uid}:"
            + "{self.primary_group.gid}:{self.gecos}:{self.homedir}:{self.shell}"
        )
        found = False

        with open("/etc/passwd", "r") as f:
            for line in f:
                if re.match(matcher, line.strip()):
                    found = True
                    break

        if not found and add_if_absent:
            self._add()
            return True
        elif not found:
            raise UserNotFoundError(
                "User {} was not found on the system and was not force-added!".format(self.name)
            )

        return found

    @property
    def present(self) -> bool:
        """Returns whether or not a user is present."""
        return self._state in self._check_if_present()

    @property
    def state(self) -> UserState:
        """Returns the current state of a user."""
        return self._state

    @state.setter
    def state(self, state: UserState) -> None:
        """Sets the user state to a given value.

        Args:
          state: a :class:`UserState` to reconcile the user to.

        Raises:
          UserError if an error is encountered
        """
        if self._state is not state:
            self.ensure(state)
        self._state = state


class UserCache(Mapping):
    """An abstraction to represent users present on the system.

    When instantiated, :class:`UserCache` iterates through the list of installed
    enabled users by parsing `/etc/passwd` to get details.
    """

    def __init__(self):
        self._user_map = {}
        self._load_users()

    def __contains__(self, key: str) -> bool:
        return key in self._user_map

    def __len__(self) -> int:
        return len(self._user_map)

    def __iter__(self) -> Iterable["User"]:
        return iter(self._user_map.values())

    def __getitem__(self, user_name: str) -> "User":
        """Return details about a user."""
        try:
            return self._user_map[user_name]
        except KeyError:
            raise UserNotFoundError("User '{}' not found!".format(user_name))

    def _load_users(self) -> None:
        """Parse /etc/passwd to get information about available passwd."""
        if not os.path.isfile("/etc/passwd"):
            raise UserError("/etc/passwd not found on the system!")

        with open("/etc/passwd", "r") as f:
            for line in f:
                if line.strip():
                    self._parse(line)

    def _parse(self, line) -> None:
        """Get values out of /etc/passwd and turn them into a :class:`User` object to cache."""
        fields = line.split(":")
        name = fields[0]
        uid = fields[2]
        gid = fields[3]
        gecos = fields[4]
        homedir = fields[5]
        shell = fields[6]
        self._user_map[name] = User(name, uid, gid, homedir, shell, UserState.Present, gecos)


class GroupError(Error):
    """Raised when there's an error managing a user account."""


class GroupNotFoundError(Error):
    """Raised when a requested group is not known to the system."""


class Group(object):
    """Represents a group and its properties.

    :class:`Group` exposes the following properties about a group:
        - name: the username of a user
        - gid: an `int` representing a group
        - users: a list of user IDs belonging to the group
    """

    def __init__(self, name: str, gid: int, users: Union[List[str], List[User]]):
        self._name = name
        self._gid = gid
        self._users = [user.name if type(user) == User else user for user in users]

    @property
    def name(self) -> str:
        """Returns the name of the group."""
        return self._name

    @property
    def gid(self) -> int:
        """Returns the ID of the group."""
        return self._gid

    @property
    def users(self) -> List[User]:
        return self._users

    @users.setter
    def users(self, users: List[User]) -> None:
        """Convert the existing users to the appropriate object types."""
        self._users = users


class GroupCache(Mapping):
    """An abstraction to represent groups present on the system.

    When instantiated, :class:`GroupCache` iterates through the list of installed
    enabled users by parsing `/etc/group` to get details.
    """

    def __init__(self):
        self._group_map = {}
        self._load_groups()

    def __contains__(self, key: str) -> bool:
        return key in self._group_map

    def __len__(self) -> int:
        return len(self._group_map)

    def __iter__(self) -> Iterable["Group"]:
        return iter(self._group_map.values())

    def __getitem__(self, group_name: str) -> "Group":
        """Return details about a group."""
        try:
            return self._group_map[group_name]
        except KeyError:
            raise GroupNotFoundError("Snap '{}' not found!".format(group_name))

    def _load_groups(self) -> None:
        """Parse /etc/group to get information about available groups."""
        if not os.path.isfile("/etc/group"):
            raise GroupError("/etc/group not found on the system!")

        with open("/etc/group", "r") as f:
            for line in f:
                if line.strip():
                    self._parse(line)

    def _parse(self, line) -> None:
        """Get values out of /etc/group and turn them into a :class:`Group` object to cache."""
        fields = line.split(":")
        name = fields[0]
        gid = fields[2]
        usernames = fields[3].split(",")
        self._group_map[name] = Group(name, gid, usernames)

    def _realize_users(self) -> None:
        """Map user strings to :class:`User` objects with the cache warmed up."""
        for k, v in self._group_map.items():
            v.users = [UserCache[uname] if type(uname) is not User else uname for uname in v.users]
            self._group_map[k] = v
