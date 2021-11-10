#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

from subprocess import check_output


def get_command_path(command):
    return check_output(["which", command]).decode().strip()
