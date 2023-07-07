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

"""Simple library for managing Linux kernel configuration via grub.

NOTE: This library is not capable to read grub config file containes

TODO: add more detailed description
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Set

logger = logging.getLogger(__name__)

# The unique Charmhub library identifier, never change it
LIBID = "1f73a0e0c78349bc88850022e02b33c7"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

LIB_CONFIG_DIRECTORY = Path("/var/lib/charm-grub/")
GRUB_CONFIG = Path("/etc/default/grub.d/") / "95-juju-charm.cfg"
CONFIG_HEADER = f"""
# This config file was produced by grub lib v{LIBAPI}.{LIBPATCH}.
# https://charmhub.io/operator-libs-linux/libraries/grub
"""
FILE_LINE_IN_DESCRIPTION = "#   {path}"
CONFIG_DESCRIPTION = """
# This file represents the output of the grub lib, which can combine multiple
# configurations into a single file like this.
#
# Original files:
#  {configs}
#
# If you change this file, run 'update-grub' afterwards to update
# /boot/grub/grub.cfg.
# For full documentation of the options in this file, see:
#   info -f grub -n 'Simple configuration'
"""


class ValidationError(ValueError):
    """Exception representing value validation error."""


def _parse_config(data: str) -> Dict[str, str]:
    """Parse config file lines.

    This function is capable to update single key value if it's used with $ symbol.
    """
    config = {}
    lines = data.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            logger.debug("skipping line `%s`", line)
            continue

        key, value = line.split("=", 1)
        if key in config:
            logger.warning("key %s is duplicated in config", key)

        config[key] = value

    return config


def _load_config(path: Path) -> Dict[str, str]:
    """Load config file from /etc/default/grub.d/ directory."""
    if not path.exists():
        raise FileNotFoundError("grub config file %s was not found", path)

    with open(path, "r", encoding="UTF-8") as file:
        data = file.read()
        config = _parse_config(data)

    logger.info("grub config file %s was loaded", path)
    logger.debug("config file %s", config)
    return config


def _save_config(path: Path, config: Dict[str, str], header: str = CONFIG_HEADER) -> None:
    """Save grub config file."""
    if path.exists():
        logger.debug("grub config %s already exist and it will overwritten", path)

    context = [f"{key}={value}" for key, value in config.items()]
    with open(path, "w", encoding="UTF-8") as file:
        file.writelines([header, *context])

    logger.info("grub config file %s was saved", path)


class GrubConfig(Mapping[str, str]):
    """Grub config object.

    This object will load current configuration option for grub and provide option
    to update it with simple validation.

    There is only one public function `update`, which should handle everything. It will
    raise exception if there is already different value configured and return set of
    changed keys to help charm check which keys where changed.
    """

    _lazy_data: Optional[Dict[str, str]] = None

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
        data = self._lazy_data
        if data is None:
            data = self._lazy_data = _load_config(GRUB_CONFIG)

        return data

    def _set_value(self, key: str, value: str) -> bool:
        """Set new value for key."""
        logger.debug("setting new value %s for key %s", value, key)
        current_value = self._data.get(key)
        if current_value is None:
            self._data[key] = value
            return True

        if current_value != value:
            logger.warning(
                "tries to overwrite key %s, which has value %s, with value %s",
                key,
                current_value,
                value,
            )
            raise ValidationError(f"key {key} already exists and its value is {current_value}")

        return False

    @property
    def registered_configs(self) -> List[Path]:
        """Return list of charms which registered config here."""
        return [config.absolute() for config in LIB_CONFIG_DIRECTORY.glob("*") if config.is_file()]

    def update(self, charm_name: str, config: Dict[str, str]) -> Set[str]:
        """Update the Grub configuration."""
        changed_keys = set()
        for key, value in config.items():
            changed = self._set_value(key, value)
            if changed:
                changed_keys.add(key)

        logger.debug("saving copy of charm config to %s", LIB_CONFIG_DIRECTORY)
        _save_config(LIB_CONFIG_DIRECTORY / charm_name, config)
        # TODO: check if config is valid `grub-mkconfig -o <path>``
        logger.info("saving new grub config to %s", GRUB_CONFIG)
        registered_configs = os.linesep.join(
            FILE_LINE_IN_DESCRIPTION.format(path=path) for path in self.registered_configs
        )
        header = CONFIG_HEADER + CONFIG_DESCRIPTION.format(configs=registered_configs)
        _save_config(GRUB_CONFIG, self._data, header)
        # TODO: update grub, https://git.launchpad.net/charm-sysconfig/tree/src/lib/lib_sysconfig.py
        return changed_keys
