# ADR: Output Naming And Preview Actions

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

Generated PPTX files were named with short task ids. That made the desktop
history list hard to scan because every output looked like an opaque hash. The
background element review screen also exposed duplicate merge and delete
actions in the left rail and the selected-elements toolbar.

## Decision

Name new PPTX outputs from the first uploaded file, the selected restore mode,
and the generation timestamp. Multi-file jobs add a file-count suffix. The
status API returns the generated output name so the desktop history list can
mark the latest result after conversion. The history list marks that latest
result with a small dot next to the title instead of changing the whole row
background.

In the background element merge/delete screen, keep only all-select and reset in
the left rail. Contextual delete appears when one element is selected; merge and
delete appear when multiple elements are selected. The selected-elements toolbar
uses the same quiet card style as the rest of the desktop workbench. The final
actions are reduced to Confirm and Cancel; Cancel exits the preview without
generating.

## Consequences

- New generated files are identifiable in Finder and the in-app PPT list.
- Existing hash-named files remain usable and continue to appear in history.
- Element cleanup actions are closer to the selection context and reduce
  duplicated controls.
