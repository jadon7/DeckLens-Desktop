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

The public website also needed to match the newer reference direction: a
minimal product page with centered headline, simple navigation, primary
download action, GitHub action, and a desktop preview visible in the first
viewport.

## Decision

- Disable text selection for non-input desktop UI while preserving text
  selection inside text fields.
- Remove the padding transition that made PPT history ellipsis feel animated.
- Add bottom padding to the background element merge/delete preview page.
- Replace default focus outlines on the PPT list and settings entry buttons
  with the existing blue focus treatment.
- Add a settings update progress bar for checking/downloading states.
- Rebuild `site/index.html` into a simpler, reference-aligned landing page and
  keep stable Cloudflare download links.

## Consequences

- Desktop UI interactions feel less browser-like and more app-like.
- Update download progress is visible in the settings panel.
- The website now matches the current product positioning and has been
  deployed to Cloudflare Pages.
