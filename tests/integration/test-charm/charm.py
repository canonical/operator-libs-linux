#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path
from subprocess import check_output
from urllib.request import urlopen

from charms.operator_libs_linux.v0 import apt, passwd, snap
from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus
from yaml import safe_load as load_yaml


def _get_command_path(command: str) -> str:
    """Naive method to get the path to a given command as a string if it exists in $PATH."""
    return check_output(["which", command]).decode().strip()


def _get_last_line_in_file(filename: str) -> str:
    """Get the last line of a give file as a string."""
    with open(filename, "r") as f:
        lines = f.readlines()
    return lines[-1].strip()


class TesterCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        # Get the list of action events in the order they're defined in actions.yaml
        actions = load_yaml(Path("actions.yaml").read_text()).keys()

        # Bind an '_on_<event_name>' handler to each action event
        for action_name in actions:
            name = f"{action_name.replace('-', '_')}_action"
            self.framework.observe(getattr(self.on, name), getattr(self, f"_on_{name}"))

        self.unit.status = ActiveStatus()

    def _on_apt_install_action(self, _):
        """Simple test for adding packages from the default package list."""
        apt.update()
        apt.add_package("zsh")
        apt.add_package(["golang-cfssl", "jq"])

        paths = [_get_command_path(c) for c in ["zsh", "cfssl", "jq"]]
        assert paths == ["/usr/bin/zsh", "/usr/bin/cfssl", "/usr/bin/jq"]

    def _on_apt_install_external_repo_action(self, _):
        """Test for adding a GPG-signed apt repository and installing a package from it."""
        # Get the Hashicorp GPG key
        key = urlopen("https://apt.releases.hashicorp.com/gpg").read().decode()

        # Initialise the repository mapping for the system
        repositories = apt.RepositoryMapping()

        # Add the hashicorp repository if it doesn't already exist
        if "deb-apt.releases.hashicorp.com-focal" not in repositories:
            line = "deb [arch=amd64] https://apt.releases.hashicorp.com focal main"
            repo = apt.DebianRepository.from_repo_line(line)
            # Import the repository's key
            repo.import_key(key)
            repositories.add(repo)

        # Update the package lists and install terraform
        apt.update()
        apt.add_package("terraform")

        assert _get_command_path("terraform") == "/usr/bin/terraform"

    def _on_snap_install_action(self, _):
        """Install a snap by initialising the cache and checking for presence before installing."""
        # Try by initialising the cache first, then using ensure
        cache = snap.SnapCache()
        juju = cache["juju"]
        if not juju.present:
            juju.ensure(snap.SnapState.Latest, classic="True", channel="stable")

        assert _get_command_path("juju") == "/snap/bin/juju"

    def _on_snap_install_bare_action(self, _):
        """Install a snap using the simple bare method."""
        snap.add(["charmcraft"], state=snap.SnapState.Latest, classic=True, channel="candidate")

        assert _get_command_path("charmcraft") == "/snap/bin/charmcraft"

    def _on_add_user_action(self, _):
        """Add a user by just specifying a username."""
        p = passwd.Passwd()
        user = passwd.User(name="test-user-0", state=passwd.UserState.Present)
        p.add_user(user)

        passwd_line = _get_last_line_in_file("/etc/passwd")
        assert passwd_line == "test-user-0:x:1001:1001::/home/test-user-0:/bin/sh"
        group_line = _get_last_line_in_file("/etc/group")
        assert group_line == "test-user-0:x:1001:"

    def _on_add_user_with_params_action(self, _):
        """Add a user, specifying a username, shell, and group."""
        p = passwd.Passwd()
        user = passwd.User(
            name="test-user-1", state=passwd.UserState.Present, shell="/bin/bash", group="admin"
        )
        p.add_user(user)

        passwd_line = _get_last_line_in_file("/etc/passwd")
        assert passwd_line == "test-user-1:x:1002:116::/home/test-user-1:/bin/bash"

    def _on_add_group_action(self, _):
        """Add a simple POSIX group to the system."""
        passwd.Group(name="test-group", users=[]).add()

        group_line = _get_last_line_in_file("/etc/group")
        assert group_line == "test-group:x:1002:"

    def _on_add_group_with_gid_action(self, _):
        """Add a simple POSIX group to the system, specifying a GID."""
        passwd.Group(name="test-group-1099", users=[], gid=1099).add()

        group_line = _get_last_line_in_file("/etc/group")
        assert group_line == "test-group-1099:x:1099:"

    def _on_remove_group_action(self, _):
        """Test removal of a POSIX group."""
        passwd.Group(name="test-group-1099", users=[], gid=1099).remove()

        group_line = _get_last_line_in_file("/etc/group")
        assert group_line != "test-group-1099:x:1099:"


if __name__ == "__main__":
    main(TesterCharm)
