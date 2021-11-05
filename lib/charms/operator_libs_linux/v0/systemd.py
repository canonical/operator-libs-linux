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

TODO: do we want to add some magic to service_start and service_restart, so that you can
run them without checking to see if the service is running first? E.g., service_start
either starts or restarts a service, and service_restart either restarts or starts the
service.

Example usage:
```python
from systemd import *

# Start a service
if not service_running("mysql"):
    success = service_start("mysql")

# Attempt to reload a service, restarting if necessary
success = service_reload("nginx", restart_on_failure=True)

```

"""

import logging
import subprocess

__all__ = [  # Don't export `service`. (It's not the intended way of using this lib.)
    "service_pause",
    "service_reload",
    "service_restart",
    "service_resume",
    "service_running",
    "service_start",
    "service_stop",
]

logger = logging.getLogger(__name__)


def service(action: str, service_name: str) -> bool:
    """Control a system service.

    :param action: the action to take on the service
    :param service_name: the name of the service to perform th action on
    """
    cmd = ["systemctl", action, service_name]
    if action != "is_active":
        logger.debug("Attempting to {} '{}' with command {}.".format(action, service_name, cmd))
    else:
        logger.debug("Checking if '{}' is active".format(service_name))
    return subprocess.call(cmd) == 0


def service_running(service_name: str) -> bool:
    """Determine whether a system service is running.

    :param service_name: the name of the service
    """
    return service("is-active", service_name)


def service_start(service_name: str) -> bool:
    """Start a system service.

    :param service_name: the name of the service to stop
    """
    return service("start", service_name)


def service_stop(service_name: str) -> bool:
    """Stop a system service.

    :param service_name: the name of the service to stop
    """
    return service("stop", service_name)


def service_restart(service_name: str) -> bool:
    """Restart a system service.

    :param service_name: the name of the service to restart
    """
    return service("restart", service_name)


def service_reload(service_name: str, restart_on_failure: bool = False) -> bool:
    """Reload a system service, optionally falling back to restart if reload fails.

    :param service_name: the name of the service to reload
    :param restart_on_failure: boolean indicating whether to fallback to a
                               restart if the reload fails.
    """
    service_result = service("reload", service_name)
    if not service_result and restart_on_failure:
        service_result = service("restart", service_name)
    return service_result


def service_pause(service_name: str) -> bool:
    """Pause a system service.

    Stop it, and prevent it from starting again at boot.

    :param service_name: the name of the service to pause
    """
    stopped = True
    if service_running(service_name):
        stopped = service_stop(service_name)
    service("disable", service_name)
    service("mask", service_name)
    return stopped


def service_resume(service_name: str) -> bool:
    """Resume a system service.

    Re-enable starting again at boot. Start the service.

    :param service_name: the name of the service to resume
    """
    service("unmask", service_name)
    service("enable", service_name)
    started = service_running(service_name)

    if not started:
        started = service_start(service_name)
    return started
