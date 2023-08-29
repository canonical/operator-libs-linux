#!/usr/bin/python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test daemon used within the minimal test charm."""

import textwrap
import time
from datetime import datetime
from pathlib import Path


def create() -> None:
    """Create service file for test daemon."""
    Path("/etc/systemd/system/test.service").write_text(
        textwrap.dedent(
            f"""
            [Unit]
            Description=Test service
            After=multi-user.target

            [Service]
            Type=simple
            Restart=always
            ExecStart=/usr/bin/python3 {__file__}

            [Install]
            WantedBy=multi-user.target
            """
        ).strip()
    )


if __name__ == "__main__":
    while True:
        print(f"The current time is {datetime.now()}")
        time.sleep(60)
