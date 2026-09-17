# Security policy

## Reporting a vulnerability

Please report security problems **privately**. Do not open a public issue, pull request or discussion for a suspected vulnerability — a public report discloses the problem before it can be fixed.

To report privately:

1. Go to this repository's **Security** tab on GitHub.
2. Choose **Report a vulnerability**. This opens a private advisory that only you and the maintainer, Bill Ravelo, can see.

Include what you found, how to reproduce it, and what you believe the impact is. You will get an acknowledgement, and the fix and any disclosure will be coordinated with you in that private advisory.

## Scope

cannae-kernel is a research library. It holds no credentials, stores nothing, makes no network calls and never submits to a settlement rail. Reports are still welcome — in particular anything that would let two different values produce the same canonical bytes or digest, let a tampered journal verify, or let an unauthorized actor kind pass as an authorizer.

## Supported versions

Only the latest commit on `main` is supported. There are no releases yet.
