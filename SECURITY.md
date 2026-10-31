# Security Policy

## Supported versions

Security fixes are provided for the latest published V.I.S.O.R. release. Upgrade
to the current version before reporting a problem that may already be fixed.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's
**Report a vulnerability** form in the repository Security tab:

https://github.com/dibun75/visor/security/advisories/new

Include the affected version, operating system, reproduction steps, impact, and
any suggested mitigation. Remove credentials, private source code, and personal
data from reports and logs.

You should receive an acknowledgement within seven days. Confirmed reports will
be coordinated privately until a fix and disclosure timeline are available.

## Security boundaries

V.I.S.O.R. indexes local source code and exposes context to configured local
agent clients. It does not upload source code by itself. Installing or
configuring an external agent may transmit retrieved context under that
provider's terms, so review client configuration and repository sensitivity
before enabling an integration.
