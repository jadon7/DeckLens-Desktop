# ADR: Desktop UI Polish and Website Rebuild

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

The desktop app needed small interaction polish after the 0.2.1 release:
non-input UI text should not be selectable, PPT history truncation should not
animate, preview mode needed more bottom breathing room, update downloads
needed visible progress, and the top-right panel entry focus style should not
show the browser default yellow outline.

The public website also needed to match the saved Variant design exported by
the user, preserving the adjusted copy and visual structure while replacing
placeholder links with production download and repository destinations.

The macOS frameless window had a recurring conflict between the draggable title
area and the top-right PPT list/settings entry buttons: expanding the drag
region could block clicks, while prioritizing clicks made the top area feel
undraggable.

## Decision

- Disable text selection for non-input desktop UI while preserving text
  selection inside text fields.
- Remove the padding transition that made PPT history ellipsis feel animated.
- Add bottom padding to the background element merge/delete preview page.
- Replace default focus outlines on the PPT list and settings entry buttons
  with the existing blue focus treatment.
- Add a settings update progress bar for checking/downloading states.
- Rebuild `site/index.html` from the user's saved Variant export, preserving
  the exported design and copy while wiring navigation, GitHub, and Cloudflare
  download links.
- Use the user's exported UI icons for settings, PPT history, open, reveal in
  Finder, and delete actions.
- Separate the macOS draggable top region from the right-side controls and keep
  the controls above it with explicit `no-drag` behavior.

## Consequences

- Desktop UI interactions feel less browser-like and more app-like.
- Update download progress is visible in the settings panel.
- The website now matches the user's saved design export and has production
  links suitable for Cloudflare Pages deployment.
- The top-right app controls remain clickable while the empty top area remains
  usable for moving the window.
