# Linux Libraries for Operator Framework Charms

## Description

The `operator-libs-linux` charm provides a set of [charm libraries] which can be used for managing and manipulating Debian packages, [snap packages], system repositories, users and groups, and other operations
that charm authors may need to carry out when authoring machine charms.

This charm is **not meant to be deployed** itself, and is used as a mechanism for hosting libraries
only.

## Usage

Each library contains information on usage and code examples. They are meant to be complete as
standalone libraries, and should be managed as [charm libraries], with installation via `fetch-lib`,
after which they may be imported and used as normal charms.

- [apt] - a library that enables the installation of Debian packages and management of system package repositories.
- [snap] - a library for installing and working with [snap packages].
- [passwd] - a library for manipulating Linux users and groups.

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this
charm following best practice guidelines, and `CONTRIBUTING.md` for developer guidance.

[charm libraries]: https://juju.is/docs/sdk/libraries
[snap packages]: https://snapcraft.io
[apt]: https://charmhub.io/operator-libs-linux/libraries/apt
[snap]: https://charmhub.io/operator-libs-linux/libraries/snap
[passwd]: https://charmhub.io/operator-libs-linux/libraries/passwd
