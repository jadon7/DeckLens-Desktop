# 2026-05-15 fal.ai API guide and 0.2.3 release

## Context

AI layered restore depends on the user's own fal.ai API key. The settings panel already persists the key locally, but it did not provide a direct onboarding path for users who do not know how to create one.

The product site also needs to point at the current release assets so new users download the build that includes this settings update.

## Decision

- Add a small help link below the fal.ai API key field in Settings.
- Localize the help link in Chinese and English.
- Bump the desktop package version to 0.2.3.
- Update website download links to the Cloudflare update/download routes so
  ordinary users do not depend on GitHub Release asset delivery.

## ADR checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
