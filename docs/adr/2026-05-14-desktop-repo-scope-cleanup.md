# Desktop Repository Scope Cleanup

## Status

Accepted

## Context

DeckLens Desktop is now maintained in the public `DeckLens-Desktop` repository.
The checkout still contained historical web deployment files, local research
scripts, old implementation notes, and generated local artifacts from previous
algorithm experiments. Those files made the public desktop repository harder to
understand and blurred the boundary between the client source tree and local
development scratch data.

## Decision

- Treat this repository as the desktop client source of truth.
- Keep Electron source, packaged backend source, static/templates, font matching
  support, signing/update infrastructure, npm package metadata, repository
  governance docs, and ADRs.
- Remove Docker/Render/web deployment files.
- Remove local research and test scripts that are not part of desktop client
  packaging.
- Remove generated local folders such as uploads, outputs, logs,
  test-materials, Python virtual environments, and release artifacts from the
  working directory. These remain ignored by git.
- Fix the settings button hit target by removing the draggable app-region from
  the workbench nav; the dedicated top drag region remains responsible for
  window dragging.

## Consequences

- Desktop development starts from npm/electron commands instead of old web
  server commands.
- Future experiments should live outside the public client repository unless
  they are promoted into product code.
- If script-based tests are reintroduced, they should be client-focused and
  documented as part of the desktop development workflow.

## Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
