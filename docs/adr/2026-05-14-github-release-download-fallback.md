# ADR: GitHub Release Download Fallback

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

DeckLens `0.2.2` release artifacts were published to GitHub Releases, but the
Cloudflare R2 update bucket upload is blocked until Wrangler OAuth is completed.
Keeping the homepage pointed at the Cloudflare update feed would continue to
serve the previous installer.

## Decision

Point public website download links at the versioned GitHub Release assets for
`v0.2.2` until the Cloudflare R2 update feed can be updated.

## Consequences

- Website users download the current `0.2.2` installers immediately.
- The Cloudflare auto-update feed still needs the `0.2.2` assets uploaded after
  Wrangler R2 authorization is available.
