# Security

## Reporting a vulnerability

Please report a vulnerability privately, through this repository's **Security → Report a vulnerability** form
(GitHub private vulnerability reporting). Do not open a public issue.

Say what is affected, how to reproduce it, and what it lets an attacker do. We aim to acknowledge a report within
5 working days, and agree on a disclosure date with you.

## Scope

- The code on `main`, the only supported version.
- The live deployment at https://mvradar.web.app: its site, `/api` and `/api/mcp`.

## How the system is meant to be safe

- The browser reads only the public read model and the public Firebase web config. Firestore and Storage deny every
  other read and every write from a client (`contracts/firebase/`).
- Writes go through the server with an admin claim, or as proposals a person approves. Outside agents hold scoped,
  expiring tokens, kept only as their digests.
- Model calls run server-side only, under spend caps.
- No secret is ever committed. The gates run on a `demo-` project with no credentials.
