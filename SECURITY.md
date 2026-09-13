# Security Policy

## Supported versions

Security fixes are released in the latest stable version. Older releases and
pre-releases (betas) are not patched separately, so please update to the latest
release through HACS.

| Version               | Supported |
| --------------------- | --------- |
| Latest stable release | Yes       |
| Older releases        | No        |
| Pre-releases (betas)  | No        |

## Reporting a vulnerability

Please **do not** report security problems in a public issue, pull request or
discussion.

Report them privately through GitHub instead:
[Report a vulnerability](https://github.com/krissen/polleninformation/security/advisories/new)
(the Security tab of this repository, then "Report a vulnerability").

A useful report includes:

- the affected version of the integration and of Home Assistant
- a description of the problem and its impact
- steps to reproduce, or a proof of concept
- any suggested fix, if you have one

## What happens next

This project is maintained by one volunteer, so handling is best effort. The
aim is to:

1. acknowledge the report within 7 days,
2. confirm or dismiss the issue, and keep you updated in the private advisory,
3. prepare a fix privately and publish it in a new release,
4. publish a GitHub security advisory once the fix is out, crediting you if you
   wish.

## Scope

In scope:

- the integration code in `custom_components/polleninformation/`
- the release assets published from this repository
- this repository's GitHub Actions workflows

Out of scope, please report these to their own maintainers:

- the polleninformation.at API and its data
- Home Assistant core
- HACS
