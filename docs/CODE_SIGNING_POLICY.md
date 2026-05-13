# Code Signing Policy

DeckLens intends to use free code signing provided by
[SignPath.io](https://about.signpath.io), certificate by
[SignPath Foundation](https://signpath.org), for Windows release artifacts.

## Scope

Only release artifacts built from the public DeckLens Desktop repository should
be submitted for signing:

- Windows NSIS installer
- update metadata and related blockmap files when required by the release flow

Local developer builds, private test artifacts, third-party upstream binaries,
and files not produced by the public CI workflow must not be submitted for
DeckLens project signing.

## Build Provenance

Windows release artifacts are built by GitHub Actions from the public source
repository:

- Repository: <https://github.com/jadon7/DeckLens-Desktop>
- Workflow: `.github/workflows/windows-build.yml`

Each signed release should be traceable to a Git tag, commit, and workflow run.

## Team Roles

- Committers and reviewers: repository collaborators with write access to
  <https://github.com/jadon7/DeckLens-Desktop>
- Approvers: repository owner and maintainers authorized to approve release
  signing requests

All maintainers involved in release signing should use multi-factor
authentication for GitHub and SignPath accounts.

## Privacy Policy

DeckLens processes user-selected files locally by default.

The app does not transfer files to networked systems unless the user explicitly
chooses a network-backed feature or configures a third-party API key. The
AI smart layering mode uses the user's configured fal.ai API key and sends the
selected processed page image to fal.ai for that specific operation.

Update checks contact the configured update feed to determine whether a new app
version is available.

Users should not include private API keys, signing credentials, or confidential
documents in bug reports or public issues.
