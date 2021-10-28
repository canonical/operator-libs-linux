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
tox -e lint      # code style
tox -e unit      # unit tests
tox              # runs 'lint' and 'unit' environments
```

## Build charm

Build the charm in this git repository using:

```shell
charmcraft pack
```
