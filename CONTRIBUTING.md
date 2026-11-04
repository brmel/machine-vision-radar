# Contributing

Thank you for helping. Machine Vision Radar is maintained by a small team that plans its work in a private tracker.
Issues and pull requests here are welcome; we triage them into that plan.

## Where things go

- **A wrong value in the catalog:** "Report an error" on the product's page at
  [mvradar.web.app](https://mvradar.web.app). The catalog lives in the store, not in this repo.
- **A bug or an idea for the code:** an issue, with its template. Wait for a reply before a large change.
- **A security problem:** never in a public issue; see [SECURITY.md](SECURITY.md).

## Making a change

1. Set up and run the gate as the [README's Quick start](README.md#quick-start) shows. The hooks check every commit,
   and run the whole gate before every push.
2. Follow [AGENTS.md](AGENTS.md): its Standards, its definition of done, and its Commits rules (the commit hook
   checks the message). Each part of the code has its own map: `app/AGENTS.md`, `radar/AGENTS.md`,
   `contracts/AGENTS.md`.
3. Open a pull request from a branch, one topic each. The template lists what it needs.

By contributing, you agree that your contribution is licensed under [Apache-2.0](LICENSE). You also agree to follow
the [Code of Conduct](CODE_OF_CONDUCT.md).
