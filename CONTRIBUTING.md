# Contributing to operator-libs-linux

## Bugs and pull requests

- Generally, before developing enhancements to this charm, you should consider explaining your use
  case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach
  us at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev)
  or [Discourse](https://discourse.charmhub.io/).
- All enhancements require review before being merged. Apart from code quality and test coverage,
  the review will also take into account the resulting user experience for Juju administrators
  using this charm.

## Setup

A typical setup using [snaps](https://snapcraft.io/) can be found in the [Juju
docs](https://juju.is/docs/sdk/dev-setup).

## Developing

You can use the environments created by `tox` for development:

```shell
tox --notest -e unit
source .tox/unit/bin/activate
```

### Testing

```shell
tox -e fmt       # update your code according to linting rules
tox -e lint      # code style -- some linting currently disabled for certain files
tox -e static    # static type checking -- currently enabled only for select libs
tox -e unit      # unit tests
tox              # runs 'lint', 'static', and 'unit' environments
```

## Build charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

## Release process

Commits to `main` which bump the charm-lib version numbers (`LIBAPI` and `LIBPATCH`) for any libs
will trigger automatic releases of those libs to charmhub. These version numbers are defined as
variables in each lib's `.py` file. PRs should bump them where appropriate.

`LIBPATCH` should be bumped whenever a change with user-facing consequences is made to a lib,
whether a bugfix, feature, or documentation improvement. If changes are being made to a lib in a
series of PRs, `LIBPATCH` should typically only be bumped in the final PR of the batch.

`LIBAPI` must be bumped whenever breaking changes to a lib's API are made. An exception may be made
if the original behaviour is considered a bug, though this depends on whether existing charms rely
on the original behaviour. Bumping `LIBAPI` also requires resetting `LIBPATCH` to `0`, and moving
the lib's `.py` file to the appropriate `v{N}` subfolder. In general, prefer to make non-breaking
changes if possible.
