# Open Source Windows Signing Prep

## Status

Accepted

## Context

DeckLens needs a public open-source repository for Windows signing options such
as SignPath Foundation. SignPath expects project provenance to be tied to a
public source repository and CI-generated artifacts.

The existing private GitHub repository also contains earlier product history, so
publishing that repository history directly is unnecessary and increases the
chance of exposing unrelated material.

## Decision

- Publish a new public GitHub repository from a clean source snapshot instead
  of exposing the existing private repository history.
- Add standard open-source project resources: `LICENSE`, `CONTRIBUTING.md`,
  `SECURITY.md`, and `CODE_OF_CONDUCT.md`.
- Add a GitHub Actions Windows build workflow that produces unsigned installer
  artifacts suitable for later SignPath integration.
- Document the SignPath Foundation preparation path in `docs/SIGNPATH.md`.

## Consequences

- The public repository starts with a clean initial commit.
- Windows release artifacts can be produced by GitHub Actions before paid or
  SignPath-backed signing is available.
- SignPath signing still requires project approval and follow-up CI secret or
  integration configuration after approval.

## Checklist

- [x] Code/config change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
