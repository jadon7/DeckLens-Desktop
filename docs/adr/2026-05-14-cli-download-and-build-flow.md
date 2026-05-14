# ADR: CLI, Download Routes, and Fast Builds

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

DeckLens needs to support Agent-driven conversion outside the Electron UI, a
stable website download button, and faster local validation builds that do not
trigger signing or notarization.

## Decision

Add `decklens_cli.py` as a thin local wrapper around the existing engine
conversion APIs. The CLI accepts images or PDFs, supports standard, element,
and AI modes, and can emit JSON for Agents. The repository also includes a
`skills/decklens-convert` skill that documents the Agent usage pattern.

Expose stable Cloudflare update Worker routes at `/download`, `/download/mac`,
and `/download/windows`. These routes read the current electron-builder
metadata from R2 and redirect to versioned installer artifacts. The website can
therefore link to stable routes while release uploads remain versioned.

Add explicit unsigned build scripts for local validation. Signed and notarized
builds remain reserved for release publishing.

## Consequences

- Agents can convert local files without driving the Electron UI.
- Website download links can stay stable across releases.
- R2 artifacts remain cacheable with long immutable headers, while latest
  metadata and download redirects stay fresh.
- Developers can run fast local builds without accidentally entering the
  signing or notarization flow.
