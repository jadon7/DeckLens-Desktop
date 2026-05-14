# ADR: Website Icons and Window Drag Area

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

The rebuilt product website used local files exported from Variant for
Phosphor icons. Those files included an extensionless script and repeated
stylesheet exports. On Cloudflare Pages the extensionless script is served with
a generic content type, and the exported icon styles referenced font files that
were not part of the deployed site. With `nosniff`, this made website icons fail
to render.

The Electron macOS shell also still had too small of a draggable area. Users
could move the window only when the pointer was very close to the top edge,
while the fixed PPT history and settings buttons still needed to stay clickable.

## Decision

- Replace Variant's exported helper script and repeated icon stylesheets with
  explicit self-hosted Phosphor regular and bold stylesheets under
  `site/vendor/phosphor/`.
- Commit the matching `.woff2` icon fonts and keep the CSS pointed only at
  those local font files.
- Rename the website's feature section anchor from `pricing` to
  `capabilities`, because that section describes capability depth rather than
  price.
- Increase the invisible macOS drag region height and keep it below the
  top-right buttons, preserving those buttons as explicit `no-drag` controls.

## Consequences

- Website icons render from stable local assets on Cloudflare Pages.
- The website no longer exposes a misleading `pricing` anchor.
- The desktop window can be dragged from a larger top area without sacrificing
  the PPT history and settings click targets.
