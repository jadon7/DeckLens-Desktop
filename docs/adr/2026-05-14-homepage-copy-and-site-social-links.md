# ADR: Homepage Copy and Site Social Links

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

The desktop home screen mode labels needed clearer user-facing names. The
website also rendered the app icon at its intrinsic image size in some places
because the exported utility classes did not constrain image dimensions
reliably.

The website hero needed direct social media links so visitors can reach the
author channels without scrolling to the footer.

## Decision

- Rename the desktop home mode labels from "标准还原" to "文字提取" and from
  "元素分层" to "进阶分层", including related Chinese homepage copy and English
  mode labels.
- Add explicit website logo CSS classes instead of relying on utility classes
  for image sizing.
- Add Douyin, Xiaohongshu, and Bilibili links below the hero primary actions.

## Consequences

- The desktop first screen uses clearer mode names.
- The website app icon stays at normal nav/footer logo sizes.
- Social media links are visible in the first viewport.
