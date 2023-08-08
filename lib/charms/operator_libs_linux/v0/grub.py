# Copyright 2023 Canonical Ltd.
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

"""Simple library for managing Linux kernel configuration via GRUB.

This library is only used for setting additional parameters that will be stored in the
"/etc/default/grub.d/95-juju-charm.cfg" config file and not for editing other
configuration files. It's intended to be used in charms to help configure the machine.

Configurations for individual charms will be stored in "/etc/default/grub.d/90-juju-<charm>",
but these configurations will only have informational value as all configurations will be merged
to "/etc/default/grub.d/95-juju-charm.cfg".

Example of use:

```python
class UbuntuCharm(CharmBase):
    def __init__(self, *args):
        ...
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.remove, self._on_remove)
        self.grub = grub.GrubConfig(self.meta.name)
        log.debug("found keys %s in GRUB config file", self.grub.keys())

    def _on_install(self, _):
        try:
            self.grub.update(
                {"GRUB_CMDLINE_LINUX_DEFAULT": "$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G"}
            )
        except grub.ValidationError as error:
            self.unit.status = BlockedStatus(f"[{error.key}] {error.message}")

    def _on_update_status(self, _):
        if self.grub["GRUB_CMDLINE_LINUX_DEFAULT"] != "$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G":
            self.unit.status = BlockedStatus("wrong GRUB configuration")

    def _on_remove(self, _):
        self.grub.remove()
```
"""

import filecmp
import io
import logging
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Mapping, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# The unique Charmhub library identifier, never change it
LIBID = "1f73a0e0c78349bc88850022e02b33c7"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 3

GRUB_DIRECTORY = Path("/etc/default/grub.d/")
CHARM_CONFIG_PREFIX = "90-juju"
GRUB_CONFIG = GRUB_DIRECTORY / "95-juju-charm.cfg"
CONFIG_HEADER = f"""# This config file was produced by GRUB lib v{LIBAPI}.{LIBPATCH}.
# https://charmhub.io/operator-libs-linux/libraries/grub
"""
FILE_LINE_IN_DESCRIPTION = "#   {path}"
CONFIG_DESCRIPTION = """
# This file represents the output of the GRUB lib, which can combine multiple
# configurations into a single file like this.
#
# Original files:
{configs}
#
# If you change this file, run 'update-grub' afterwards to update
# /boot/grub/grub.cfg.
# For full documentation of the options in this file, see:
#   info -f grub -n 'Simple configuration'
"""


class ValidationError(ValueError):
    """Exception representing value validation error."""

    def __init__(self, key: str, message: str) -> None:
        super().__init__(message)
        self.key = key
        self.message = message

    def __str__(self) -> str:
        """Return string representation of error."""
        return self.message


class IsContainerError(Exception):
    """Exception if local machine is container."""


class ApplyError(Exception):
    """Exception if applying new config failed."""


def _split_config_line(line: str) -> Tuple[str, str]:
    """Split GRUB config line to obtain key and value."""
    key, raw_value = line.split("=", 1)
    value, *not_expected_values = shlex.split(raw_value)
    if not_expected_values:
        logger.error("unexpected value %s for %s key", raw_value, key)
        raise ValueError(f"unexpected value {raw_value} for {key} key")

    return key, value


def _parse_config(stream: io.TextIOWrapper) -> Dict[str, str]:
    """Parse config file lines."""
    config = {}
    for line in stream:
        line = line.strip()
        if not line or line.startswith("#"):
            logger.debug("skipping line `%s`", line)
            continue

        key, value = _split_config_line(line)
        if key in config:
            logger.warning("key %s is duplicated in config", key)

        config[key] = value

    return config


def _load_config(path: Path) -> Dict[str, str]:
    """Load config file from /etc/default/grub.d/ directory."""
    if not path.exists():
        raise FileNotFoundError("GRUB config file %s was not found", path)

    with open(path, "r", encoding="UTF-8") as file:
        config = _parse_config(file)

    logger.info("GRUB config file %s was loaded", path)
    logger.debug("config file %s", config)
    return config


def _save_config(path: Path, config: Dict[str, str], header: str = CONFIG_HEADER) -> None:
    """Save GRUB config file."""
    if path.exists():
        logger.debug("GRUB config %s already exist and it will overwritten", path)

    with open(path, "w", encoding="UTF-8") as file:
        file.write(header)
        for key, value in config.items():
            file.write(f"{key}={shlex.quote(value)}\n")

    logger.info("GRUB config file %s was saved", path)


def _update_config(path: Path, config: Dict[str, str], header: str = CONFIG_HEADER) -> None:
    """Update existing GRUB config file."""
    if path.exists():
        original_config = _load_config(path)
        original_config.update(config)
        config = original_config.copy()

    _save_config(path, config, header)


def check_update_grub() -> bool:
    """Report whether an update to /boot/grub/grub.cfg is available."""
    main_grub_cfg = Path("/boot/grub/grub.cfg")
    tmp_path = Path("/tmp/tmp_grub.cfg")
    try:
        subprocess.check_call(
            ["/usr/sbin/grub-mkconfig", "-o", f"{tmp_path}"], stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as error:
        logger.exception(error)
        raise ApplyError from error

    return not filecmp.cmp(main_grub_cfg, tmp_path)


def is_container() -> bool:
    """Report whether the local machine is a container."""
    try:
        output = subprocess.check_output(
            ["/usr/bin/systemd-detect-virt", "--container"], stderr=subprocess.STDOUT
        ).decode()
        logger.debug("detect virt type %s", output)
        return True
    except subprocess.CalledProcessError:
        return False


class Config(Mapping[str, str]):
    """Manages GRUB configuration.

    This object will load current configuration option for GRUB and provide option
    to update it with simple validation, remove charm option and apply those changes.
    """

    _lazy_data: Optional[Dict[str, str]] = None

    def __init__(self, charm_name: str) -> None:
        """Initialize the GRUB config."""
        self._charm_name = charm_name

    def __contains__(self, key: str) -> bool:
        """Check if key is in config."""
        return key in self._data

    def __len__(self):
        """Get size of config."""
        return len(self._data)

    def __iter__(self):
        """Iterate over config."""
        return iter(self._data)

    def __getitem__(self, key: str) -> str:
        """Get value for key form config."""
        return self._data[key]

    @property
    def _data(self) -> Dict[str, str]:
        """Data property."""
        if self._lazy_data is None:
            try:
                self._lazy_data = _load_config(GRUB_CONFIG)
            except FileNotFoundError:
                logger.debug("there is no GRUB config file %s yet", GRUB_CONFIG)
                self._lazy_data = {}

        return self._lazy_data

    def _save_grub_configuration(self) -> None:
        """Save current GRUB configuration."""
        logger.info("saving new GRUB config to %s", GRUB_CONFIG)
        applied_configs = {self.path, *self.applied_configs}  # using set to drop duplicity
        registered_configs = "\n".join(
            FILE_LINE_IN_DESCRIPTION.format(path=path) for path in applied_configs
        )
        header = CONFIG_HEADER + CONFIG_DESCRIPTION.format(configs=registered_configs)
        _save_config(GRUB_CONFIG, self._data, header)

    def _set_value(self, key: str, value: str, blocked_keys: Set[str]) -> bool:
        """Set new value for key."""
        logger.debug("[%s] setting new value %s for key %s", self.charm_name, value, key)
        current_value = self._data.get(key)
        if current_value == value:
            return False

        # validation
        if key in self and current_value != value and key in blocked_keys:
            logger.error(
                "[%s] tries to overwrite key %s, which has value %s, with value %s",
                self.charm_name,
                key,
                current_value,
                value,
            )
            raise ValidationError(
                key, f"key {key} already exists and its value is {current_value}"
            )

        self._data[key] = value
        return True

    def _update(self, config: Dict[str, str]) -> Set[str]:
        """Update data in object."""
        logger.debug("[%s] updating current config", self.charm_name)
        changed_keys = set()
        blocked_keys = self.blocked_keys
        for key, value in config.items():
            changed = self._set_value(key, value, blocked_keys)
            if changed:
                changed_keys.add(key)

        return changed_keys

    @property
    def applied_configs(self) -> Dict[Path, Dict[str, str]]:
        """Return list of charms configs which registered config in LIB_CONFIG_DIRECTORY."""
        configs = {}
        for path in sorted(GRUB_DIRECTORY.glob(f"{CHARM_CONFIG_PREFIX}-*")):
            configs[path] = _load_config(path)
            logger.debug("load config file %s", path)

        return configs

    @property
    def blocked_keys(self) -> Set[str]:
        """Get set of configured keys by other charms."""
        return {
            key
            for path, config in self.applied_configs.items()
            if path != self.path
            for key in config
        }

    @property
    def charm_name(self) -> str:
        """Get charm name or use value obtained from JUJU_UNIT_NAME env."""
        return self._charm_name

    @property
    def path(self) -> Path:
        """Return path for charm config."""
        return GRUB_DIRECTORY / f"{CHARM_CONFIG_PREFIX}-{self.charm_name}"

    def apply(self):
        """Check if an update to /boot/grub/grub.cfg is available."""
        if not check_update_grub():
            logger.info("[%s] no available GRUB updates found", self.charm_name)
            return

        try:
            subprocess.check_call(["/usr/sbin/update-grub"], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            logger.error(
                "[%s] applying GRUB config failed with errors: %s", self.charm_name, error.stdout
            )
            raise ApplyError("New config check failed.") from error

    def remove(self, apply: bool = True) -> Set[str]:
        """Remove config for charm.

        This function will remove config file for charm and re-create the `95-juju-charm.cfg`
        GRUB config file without changes made by this charm.
        """
        if not self.path.exists():
            logger.debug("[%s] there is no charm config file %s", self.charm_name, self.path)
            return set()

        self.path.unlink()
        logger.info("[%s] charm config file %s was removed", self.charm_name, self.path)
        config = {}
        for _config in self.applied_configs.values():
            config.update(_config)

        changed_keys = set(self._data) - set(config.keys())
        self._lazy_data = config
        self._save_grub_configuration()
        if apply:
            self.apply()

        return changed_keys

    def update(self, config: Dict[str, str], apply: bool = True) -> Set[str]:
        """Update the Grub configuration."""
        if is_container():
            raise IsContainerError("Could not configure GRUB config on container.")

        snapshot = self._data.copy()
        try:
            changed_keys = self._update(config)
            if changed_keys:
                self._save_grub_configuration()
                if apply:
                    self.apply()
        except ValidationError as error:
            logger.error("[%s] validation failed with message: %s", self.charm_name, error.message)
            self._lazy_data = snapshot
            logger.info("[%s] restored snapshot for Config object", self.charm_name)
            raise
        except ApplyError as error:
            logger.error(
                "[%s] applying new GRUB config failed with error: %s", self.charm_name, error
            )
            self._lazy_data = snapshot
            self._save_grub_configuration()  # save snapshot copy of grub config
            logger.info(
                "[%s] restored snapshot for Config object and GRUB configuration", self.charm_name
            )
            raise

        logger.debug("[%s] saving copy of charm config to %s", self.charm_name, GRUB_DIRECTORY)
        _update_config(self.path, config)
        return changed_keys
