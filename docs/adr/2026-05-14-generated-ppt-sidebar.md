# ADR: Generated PPT Sidebar

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

DeckLens desktop users generate multiple PPTX files while comparing restore
modes and sample inputs. The previous UI only exposed the current task download
link, so users had to find outputs manually after leaving the result panel.

## Decision

Add a collapsed right-side PPT history sidebar in the Electron UI. Its entry
button sits to the left of the settings button. The sidebar lists PPTX files
from the desktop output directory and lets users open a deck with the system
default app, reveal it in the local folder, or delete it.

The sidebar uses a Codex-like two-area layout: the main workbench keeps the
white canvas and shrinks from the left edge, while the history panel uses a
muted side background without an overlay shadow. The top history/settings entry
buttons keep a fixed position above the workbench and sidebar. The history
entry button is the only open/close control, and the panel omits a separate
header, close button, and refresh button to keep the side rail lightweight.
When a conversion completes, DeckLens refreshes and opens this history panel
directly instead of showing a separate result card.

The file operations are implemented in the Electron main process. The renderer
passes only output file names, and the main process resolves them inside
`app.getPath("userData")/data/outputs` before opening, revealing, or deleting.

## Consequences

- Generated output management stays inside the desktop shell and does not
  require a new Flask API.
- The list includes PPTX files generated across app sessions.
- File actions are constrained to DeckLens output PPTX files instead of
  allowing arbitrary renderer-provided paths.
- Users land on the generated output list immediately after conversion, so the
  old download/continue card is no longer needed.
