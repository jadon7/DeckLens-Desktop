# 2026-05-15 Cloudflare download hardening

## Context

DeckLens desktop updates and website downloads are served through
`updates.dsxzai.com`, backed by the `decklens-updates` Worker and R2 bucket.
Large download spikes should not depend on GitHub release delivery, and release
artifacts should be cacheable while update metadata remains fresh.

The current Cloudflare OAuth credentials can deploy Workers, Pages, R2, and KV,
but cannot modify zone WAF/ruleset rate limiting. Zone-level WAF should still be
added when a token with Rulesets/WAF edit permissions is available.

## Decision

- Keep metadata files such as `latest-mac.yml` and `latest.yml` on
  `no-cache, no-store, must-revalidate`.
- Keep installer artifacts on `public, max-age=31536000, immutable`.
- Route website downloads through `https://updates.dsxzai.com/download/...`.
- Make `/download/mac` prefer the `.dmg` artifact for website downloads while
  Electron auto-update continues using the `path:` ZIP from `latest-mac.yml`.
- Add a Cloudflare KV-backed Worker rate limit:
  - 30 download redirect requests per IP per minute.
  - 120 direct artifact requests per IP per minute.

## ADR checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

