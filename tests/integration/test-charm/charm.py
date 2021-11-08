#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from subprocess import check_output
from urllib.request import urlopen

from charms.operator_libs_linux.v0 import apt, passwd, snap
from ops.charm import ActionEvent, CharmBase, StartEvent
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class TesterCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_start)
        
        # Debian packaging actions
        self.framework.observe(self.on.apt_install_action, self._on_apt_install_action)
        self.framework.observe(
            self.on.apt_install_external_repo_action, self._on_apt_install_external_repo_action
        )

        # Snap packaging actions
        self.framework.observe(self.on.snap_install_action, self._on_snap_install_action)
        self.framework.observe(self.on.snap_install_bare_action, self._on_snap_install_bare_action)

        # User and group management actions
        self.framework.observe(self.on.add_user_action, self._on_add_user_action)
        self.framework.observe(
            self.on.add_user_with_params_action, self._on_add_user_with_params_action)

    def _on_start(self, _: StartEvent):
        self.unit.status = ActiveStatus()

    def _on_apt_install_action(self, event: ActionEvent):
        try:
            apt.update()
            apt.add_package("zsh")
            apt.add_package(["golang-cfssl", "jq"])
        except apt.PackageNotFoundError:
            logger.error("A specified package not found in package cache or on system")
        except apt.PackageError as e:
            logger.error(f"Could not install package. Reason: {e.message}")

        paths = [self._get_command_path(c) for c in ["zsh", "cfssl", "jq"]]
        event.set_results({"installed": paths})

    def _on_apt_install_external_repo_action(self, event: ActionEvent):
        repositories = apt.RepositoryMapping()

        # Get the Hashicorp GPG key
        key = urlopen("https://apt.releases.hashicorp.com/gpg").read().decode()

        # Add the hashicorp repository if it doesn't already exist
        if "deb-apt.releases.hashicorp.com-focal" not in repositories:
            line = "deb [arch=amd64] https://apt.releases.hashicorp.com focal main"
            repo = apt.DebianRepository.from_repo_line(line)
            # Import the repository's key
            repo.import_key(key)
            repositories.add(repo)

        apt.update()
        apt.add_package("terraform")
        event.set_results({"installed": [self._get_command_path("terraform")]})

    def _on_snap_install_action(self, event: ActionEvent):
        # Try by initialising the cache first, then using ensure
        try:
            cache = snap.SnapCache()
            juju = cache["juju"]
            if not juju.present:
                juju.ensure(snap.SnapState.Latest, classic="True", channel="stable")
        except snap.SnapError as e:
            logger.error(f"An exception occurred when installing Juju. Reason: {e.message}")

        event.set_results({"installed": [self._get_command_path("juju")]})

    def _on_snap_install_bare_action(self, event: ActionEvent):
        snap.add(["charmcraft"], state=snap.SnapState.Latest, classic=True, channel="candidate")
        event.set_results({"installed": [self._get_command_path("charmcraft")]})
    
    def _on_add_user_action(self, event: ActionEvent):
        p = passwd.Passwd()
        user = passwd.User(name="test-user-0", state=passwd.UserState.Present)
        p.add_user(user)

        with open("/etc/passwd", "r") as f:
            lines = f.readlines()
        
        event.set_results({"created": lines[-1]})

    def _on_add_user_with_params_action(self, event: ActionEvent):
        p = passwd.Passwd()
        user = passwd.User(
            name="test-user-1", 
            state=passwd.UserState.Present, 
            shell="/bin/bash",
            group="admin"
        )
        p.add_user(user)

        with open("/etc/passwd", "r") as f:
            lines = f.readlines()
        
        event.set_results({"created": lines[-1]})

    def _get_command_path(self, command):
        return check_output(["which", command]).decode().strip()


if __name__ == "__main__":
    main(TesterCharm)
