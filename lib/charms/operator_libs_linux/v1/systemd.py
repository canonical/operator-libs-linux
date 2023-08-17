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


"""Abstractions for stopping, starting and managing system services via systemd.

This library assumes that your charm is running on a platform that uses systemd. E.g.,
Centos 7 or later, Ubuntu Xenial (16.04) or later.

For the most part, we transparently provide an interface to a commonly used selection of
systemd commands, with a few shortcuts baked in. For example, service_pause and
service_resume with run the mask/unmask and enable/disable invocations.

Example usage:
```python
from charms.operator_libs_linux.v0.systemd import service_running, service_reload

# Start a service
if not service_running("mysql"):
    success = service_start("mysql")

# Attempt to reload a service, restarting if necessary
success = service_reload("nginx", restart_on_failure=True)
```

"""

import functools
import logging
import subprocess

__all__ = [  # Don't export `_systemctl`. (It's not the intended way of using this lib.)
    "daemon_reload",
    "service_disable",
    "service_enable",
    "service_failed",
    "service_pause",
    "service_reload",
    "service_restart",
    "service_resume",
    "service_running",
    "service_start",
    "service_stop",
]

logger = logging.getLogger(__name__)

# The unique Charmhub library identifier, never change it
LIBID = "045b0d179f6b4514a8bb9b48aee9ebaf"

# Increment this major API version when introducing breaking changes
LIBAPI = 1

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 3


class SystemdError(Exception):
    """Custom exception for SystemD related errors."""


def _systemctl(*args) -> bool:
    """Control a system service using systemctl.

    Args:
        *args: Arguments to pass to systemctl.
    """
    cmd = ["systemctl", *args]
    logger.debug(f"Executing command: {cmd}")
    proc = subprocess.run(
        [*cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8"
    )
    logger.debug(proc.stdout)
    if proc.returncode == 1 and "is-failed" in cmd:
        return False
    elif proc.returncode == 3 and "is-active" in cmd:
        return False
    elif proc.returncode == 0:
        return True
    else:
        raise SystemdError(f"Command {cmd} failed. systemctl output:\n{proc.stdout}")


service_running = functools.partial(_systemctl, "--quiet", "is-active")
service_running.__doc__ = "Determine whether a system service is running."
service_failed = functools.partial(_systemctl, "--quiet", "is-failed")
service_failed.__doc__ = "Determine whether a system service has failed."
service_start = functools.partial(_systemctl, "start")
service_start.__doc__ = "Start a system service."
service_stop = functools.partial(_systemctl, "stop")
service_stop.__doc__ = "Stop a system service."
service_restart = functools.partial(_systemctl, "restart")
service_restart.__doc__ = "Restart a system service."
service_enable = functools.partial(_systemctl, "enable")
service_enable.__doc__ = "Enable a system service."
service_disable = functools.partial(_systemctl, "disable")
service_disable.__doc__ = "Disable a system service."
daemon_reload = functools.partial(_systemctl, "daemon-reload")
daemon_reload.__doc__ = "Reload systemd manager configuration."


def service_reload(service_name: str, restart_on_failure: bool = False) -> bool:
    """Reload a system service, optionally falling back to restart if reload fails.

    Args:
        service_name: the name of the service to reload
        restart_on_failure: boolean indicating whether to fall back to a restart if the
          reload fails.
    """
    try:
        return _systemctl("reload", service_name)
    except SystemdError:
        if restart_on_failure:
            return service_restart(service_name)
        else:
            raise


def service_pause(service_name: str) -> bool:
    """Pause a system service.

    Stop it, and prevent it from starting again at boot.

    Args:
        service_name: the name of the service to pause
    """
    service_disable("--now", service_name)
    _systemctl("mask", service_name)

    if not service_running(service_name):
        return True

    raise SystemdError(f"Attempted to pause '{service_name}', but it is still running.")


def service_resume(service_name: str) -> bool:
    """Resume a system service.

    Re-enable starting again at boot. Start the service.

    Args:
        service_name: the name of the service to resume
    """
    _systemctl("unmask", service_name)
    service_enable("--now", service_name)

    if service_running(service_name):
        return True

    raise SystemdError(f"Attempted to resume '{service_name}', but it is not running.")
