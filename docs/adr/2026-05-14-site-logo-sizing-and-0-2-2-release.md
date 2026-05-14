# ADR: Site Logo Sizing And 0.2.2 Release

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

The homepage logo needed a larger fixed display size in the header and footer.
The desktop app also needed a new public release after the latest UI and
website changes.

## Decision

Set the shared website logo image to `32px` square with a `40px` maximum bound,
and set the footer variant to `40px` square. Bump the desktop package version to
`0.2.2` so Electron Builder emits versioned update metadata and release
artifacts.

## Consequences

- The website header logo appears at a readable size while still respecting a
  hard maximum asset box.
- The footer logo uses the larger brand mark requested for the bottom section.
- The next macOS release and update feed identify the app as `0.2.2`.
