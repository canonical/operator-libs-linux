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

Example usage.
"""

import logging
import os
import subprocess

_UPSTART_CONF = "/etc/init/{}.conf"
_INIT_D_CONF = "/etc/init.d/{}"
SYSTEMD_SYSTEM = "/run/systemd/system"
logger = logging.getLogger(__name__)


def _is_trusty() -> dict:
    """Check to see if we are running in trusty."""
    d = {}
    with open("/etc/os-release", "r") as os_release:
        for line in os_release:
            s = line.split("=")
            if len(s) != 2:
                continue
            d[s[0].strip()] = s[1].strip()

    return d["VERSION_CODENAME"] == "trusty"


def service_running(service_name: str, **kwargs) -> str:
    """Determine whether a system service is running.

    :param service_name: the name of the service
    :param **kwargs: additional args to pass to the service command. This is
                     used to pass additional key=value arguments to the
                     service command line for managing specific instance
                     units (e.g. service ceph-osd status id=2). The kwargs
                     are ignored in systemd services.
    """
    if init_is_systemd(service_name=service_name):
        return service("is-active", service_name)
    else:
        if os.path.exists(_UPSTART_CONF.format(service_name)):
            try:
                cmd = ["status", service_name]
                for key, value in kwargs.items():
                    parameter = "%s=%s" % (key, value)
                    cmd.append(parameter)
                output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("UTF-8")
            except subprocess.CalledProcessError:
                return False
            else:
                # This works for upstart scripts where the "service" command
                # returns a consistent string to represent running
                # "start/running"
                if "start/running" in output:
                    return True
                if "is running" in output:
                    return True
                if "up and running" in output:
                    return True
        elif os.path.exists(_INIT_D_CONF.format(service_name)):
            # Check System V scripts init script return codes
            return service("status", service_name)
        return False


def init_is_systemd(service_name=None):
    """Returns whether the host uses systemd for the specified service.

    @param Optional[str] service_name: specific name of service
    """
    if str(service_name).startswith("snap."):
        return True
    if _is_trusty():
        return False
    return os.path.isdir(SYSTEMD_SYSTEM)


def service(action: str, service_name: str, **kwargs) -> bool:
    """Control a system service.

    :param action: the action to take on the service
    :param service_name: the name of the service to perform th action on
    :param **kwargs: additional params to be passed to the service command in
                    the form of key=value.
    """
    if init_is_systemd(service_name=service_name):
        cmd = ["systemctl", action, service_name]
    else:
        cmd = ["service", service_name, action]
        for key, value in kwargs.items():
            parameter = "%s=%s" % (key, value)
            cmd.append(parameter)
    return subprocess.call(cmd) == 0


def service_start(service_name: str, **kwargs) -> bool:
    """Start a system service.

    The specified service name is managed via the system level init system.
    Some init systems (e.g. upstart) require that additional arguments be
    provided in order to directly control service instances whereas other init
    systems allow for addressing instances of a service directly by name (e.g.
    systemd).

    The kwargs allow for the additional parameters to be passed to underlying
    init systems for those systems which require/allow for them. For example,
    the ceph-osd upstart script requires the id parameter to be passed along
    in order to identify which running daemon should be reloaded. The follow-
    ing example stops the ceph-osd service for instance id=4:

    service_stop("ceph-osd", id=4)

    :param service_name: the name of the service to stop
    :param **kwargs: additional parameters to pass to the init system when
                     managing services. These will be passed as key=value
                     parameters to the init system"s commandline. kwargs
                     are ignored for systemd enabled systems.
    """
    return service("start", service_name, **kwargs)


def service_stop(service_name: str, **kwargs) -> bool:
    """Stop a system service.

    The specified service name is managed via the system level init system.
    Some init systems (e.g. upstart) require that additional arguments be
    provided in order to directly control service instances whereas other init
    systems allow for addressing instances of a service directly by name (e.g.
    systemd).

    The kwargs allow for the additional parameters to be passed to underlying
    init systems for those systems which require/allow for them. For example,
    the ceph-osd upstart script requires the id parameter to be passed along
    in order to identify which running daemon should be reloaded. The follow-
    ing example stops the ceph-osd service for instance id=4:

    service_stop("ceph-osd", id=4)

    :param service_name: the name of the service to stop
    :param **kwargs: additional parameters to pass to the init system when
                     managing services. These will be passed as key=value
                     parameters to the init system"s commandline. kwargs
                     are ignored for systemd enabled systems.
    """
    return service("stop", service_name, **kwargs)


def service_restart(service_name: str, **kwargs) -> bool:
    """Restart a system service.

    The specified service name is managed via the system level init system.
    Some init systems (e.g. upstart) require that additional arguments be
    provided in order to directly control service instances whereas other init
    systems allow for addressing instances of a service directly by name (e.g.
    systemd).

    The kwargs allow for the additional parameters to be passed to underlying
    init systems for those systems which require/allow for them. For example,
    the ceph-osd upstart script requires the id parameter to be passed along
    in order to identify which running daemon should be restarted. The follow-
    ing example restarts the ceph-osd service for instance id=4:

    service_restart("ceph-osd", id=4)

    :param service_name: the name of the service to restart
    :param **kwargs: additional parameters to pass to the init system when
                     managing services. These will be passed as key=value
                     parameters to the  init system"s commandline. kwargs
                     are ignored for init systems not allowing additional
                     parameters via the commandline (systemd).
    """
    return service("restart", service_name)


def service_reload(service_name: str, restart_on_failure: bool = False, **kwargs) -> bool:
    """Reload a system service, optionally falling back to restart if reload fails.

    The specified service name is managed via the system level init system.
    Some init systems (e.g. upstart) require that additional arguments be
    provided in order to directly control service instances whereas other init
    systems allow for addressing instances of a service directly by name (e.g.
    systemd).

    The kwargs allow for the additional parameters to be passed to underlying
    init systems for those systems which require/allow for them. For example,
    the ceph-osd upstart script requires the id parameter to be passed along
    in order to identify which running daemon should be reloaded. The follow-
    ing example restarts the ceph-osd service for instance id=4:

    service_reload("ceph-osd", id=4)

    :param service_name: the name of the service to reload
    :param restart_on_failure: boolean indicating whether to fallback to a
                               restart if the reload fails.
    :param **kwargs: additional parameters to pass to the init system when
                     managing services. These will be passed as key=value
                     parameters to the  init system"s commandline. kwargs
                     are ignored for init systems not allowing additional
                     parameters via the commandline (systemd).
    """
    service_result = service("reload", service_name, **kwargs)
    if not service_result and restart_on_failure:
        service_result = service("restart", service_name, **kwargs)
    return service_result


def service_pause(
    service_name: str, init_dir: str = "/etc/init", initd_dir: str = "/etc/init.d", **kwargs
) -> bool:
    """Pause a system service.

    Stop it, and prevent it from starting again at boot.

    :param service_name: the name of the service to pause
    :param init_dir: path to the upstart init directory
    :param initd_dir: path to the sysv init directory
    :param **kwargs: additional parameters to pass to the init system when
                     managing services. These will be passed as key=value
                     parameters to the init system"s commandline. kwargs
                     are ignored for init systems which do not support
                     key=value arguments via the commandline.
    """
    stopped = True
    if service_running(service_name, **kwargs):
        stopped = service_stop(service_name, **kwargs)
    upstart_file = os.path.join(init_dir, "{}.conf".format(service_name))
    sysv_file = os.path.join(initd_dir, service_name)
    if init_is_systemd(service_name=service_name):
        service("disable", service_name)
        service("mask", service_name)
    elif os.path.exists(upstart_file):
        override_path = os.path.join(init_dir, "{}.override".format(service_name))
        with open(override_path, "w") as fh:
            fh.write("manual\n")
    elif os.path.exists(sysv_file):
        subprocess.check_call(["update-rc.d", service_name, "disable"])
    else:
        raise ValueError(
            "Unable to detect {0} as SystemD, Upstart {1} or"
            " SysV {2}".format(service_name, upstart_file, sysv_file)
        )
    return stopped


def service_resume(
    service_name: str, init_dir: str = "/etc/init", initd_dir: str = "/etc/init.d", **kwargs
) -> bool:
    """Resume a system service.

    Re-enable starting again at boot. Start the service.

    :param service_name: the name of the service to resume
    :param init_dir: the path to the init dir
    :param initd dir: the path to the initd dir
    :param **kwargs: additional parameters to pass to the init system when
                     managing services. These will be passed as key=value
                     parameters to the init system"s commandline. kwargs
                     are ignored for systemd enabled systems.
    """
    upstart_file = os.path.join(init_dir, "{}.conf".format(service_name))
    sysv_file = os.path.join(initd_dir, service_name)
    if init_is_systemd(service_name=service_name):
        service("unmask", service_name)
        service("enable", service_name)
    elif os.path.exists(upstart_file):
        override_path = os.path.join(init_dir, "{}.override".format(service_name))
        if os.path.exists(override_path):
            os.unlink(override_path)
    elif os.path.exists(sysv_file):
        subprocess.check_call(["update-rc.d", service_name, "enable"])
    else:
        raise ValueError(
            "Unable to detect {0} as SystemD, Upstart {1} or"
            " SysV {2}".format(service_name, upstart_file, sysv_file)
        )
    started = service_running(service_name, **kwargs)

    if not started:
        started = service_start(service_name, **kwargs)
    return started
