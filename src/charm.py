#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.


"""A placeholder charm for the Operator Linux Libs."""

from ops.charm import CharmBase
from ops.main import main


class OperatorLibsLinuxCharm(CharmBase):
    """Placeholder charm for Operator Linux Libs."""

    pass


if __name__ == "__main__":
    main(OperatorLibsLinuxCharm)
