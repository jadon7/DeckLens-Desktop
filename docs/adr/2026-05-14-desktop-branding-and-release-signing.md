# ADR: Desktop Branding And Release Signing

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

DeckLens desktop needs to ship with the product icon and author social icons
provided by the project assets. The public macOS download also showed the
Gatekeeper "damaged" warning when users opened a downloaded unsigned build.

## Decision

Use the provided product PNG as the desktop app icon source and commit generated
macOS `.icns` and Windows `.ico` files under `build/`. Electron Builder now
references those icon files for packaged macOS and Windows releases. Use the
provided social platform SVGs in the settings author section instead of
CSS-drawn placeholders.

macOS public release artifacts must be built with the Developer ID signing
identity and notarized before uploading to the Cloudflare R2 update bucket. The
Cloudflare update feed should point `latest-mac.yml` at the notarized ZIP so
downloaded apps pass Gatekeeper on user machines.

## Consequences

- Packaged desktop apps use the same product icon across macOS and Windows.
- Settings displays real platform icons for the author links.
- Public macOS downloads require a signed and notarized release build before
  being published to the update feed.
- Fast local validation can still use unsigned development runs; signing is
  only required for public release artifacts.
