# Electron Auto Update

## Status

Accepted

## Context

DeckLens is now distributed as an Electron desktop app. Users should be able to
receive app updates without manually replacing the installed bundle.

The app also carries a local Python backend and model/runtime assets, so updates
need to be predictable and avoid background replacement while a conversion task
is running.

## Decision

- Use `electron-updater` with a generic Cloudflare-hosted update feed at
  `https://updates.dsxzai.com/`.
- Serve update artifacts from an R2 bucket through a small Worker so metadata
  and installer files can have different cache behavior.
- Check once after the packaged app starts, then expose manual check, download,
  and restart-to-install actions inside the app settings panel.
- Keep the top-level shell visually quiet: a single settings button opens local
  runtime preferences, fal.ai API Key configuration, update status, and version
  information.
- Keep automatic download off. Users explicitly start the download after an
  update is found.
- Keep development mode update checks disabled so local debugging does not call
  the release feed.
- Sign macOS release artifacts with Developer ID Application, hardened runtime,
  and electron-builder notarization through a local `decklens-notary` Keychain
  profile.

## Consequences

- Release builds must publish matching electron-builder artifacts and update
  metadata to the Cloudflare update feed.
- Cloudflare should serve metadata files such as `latest-mac.yml` with short or
  no caching; versioned installer artifacts can use long-lived cache headers.
- Production macOS releases require a valid Developer ID Application certificate
  in Keychain and `APPLE_KEYCHAIN_PROFILE=decklens-notary` during the release
  build.
- The app shell and bundled backend can update through the release artifact; the
  user-data Python runtime remains managed by the existing runtime bootstrap.

## Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
