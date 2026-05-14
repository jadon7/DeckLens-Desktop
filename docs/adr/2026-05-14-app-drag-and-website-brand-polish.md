# ADR: App Drag and Website Brand Polish

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

The desktop app still had a hit-test conflict around the macOS frameless window
top area. The fixed PPT history and settings buttons needed to stay clickable,
but the surrounding top area also needed to behave like a reliable draggable
window region.

The product website also needed small brand and copy polish after deployment:
the visible logo should match the desktop app icon, the capability labels should
read as product tiers rather than internal all-caps tags, and the footer should
attribute the author brand.

## Decision

- Keep the top-right fixed buttons outside the drag handler so clicks always
  reach the PPT history and settings actions.
- Use a small renderer-to-main IPC bridge for topbar dragging instead of relying
  on overlapping `-webkit-app-region` hit testing, then move the BrowserWindow
  by pointer deltas from the topbar's empty area.
- Apply the requested preview padding, floating action spacing, processing flow
  spacing, and progress bar color updates.
- Use `/assets/app-icon.png` as the visible website logo in the nav and footer.
- Add an icon beside the "元素分层可人工校对" website heading and rename the
  capability labels to Basic, Intermediate, and Advanced.
- Replace the generic open-source footer copyright with the author brand.

## Consequences

- The app window can be dragged from the topbar's empty area while history and
  settings remain clickable.
- Website branding is consistent with the packaged app icon and author identity.
