# Cloudflare Product Website

## Status

Accepted

## Context

The GitHub repository homepage previously pointed at the Electron auto-update
feed. That endpoint is operationally correct for app updates, but it is not a
product website and looks confusing when opened by a person.

DeckLens Desktop needs a public website that can explain the app, link to the
open-source repository, and keep the update feed separate from user-facing
marketing/documentation.

## Decision

- Add a static product website under `site/`.
- Use a real DeckLens desktop screenshot as the primary visual asset.
- Deploy the site to Cloudflare Pages as `decklens-site`.
- Serve the public website at `https://deck.dsxzai.com/`.
- Keep `https://updates.dsxzai.com/` only for Electron auto-update metadata and
  release artifacts.
- Add `wrangler` as a development dependency so Cloudflare deployment commands
  are reproducible from this repository.
- Use fast unsigned validation flows during development; signed builds remain a
  release-only step.

## Consequences

- Repository Website/Homepage should point to `https://deck.dsxzai.com/`.
- Website changes can be deployed independently from desktop app releases.
- Release documentation must continue to distinguish the website domain from the
  update feed domain.

## Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
