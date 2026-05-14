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
white canvas and shrinks from the left edge, while the right panel uses a muted
side background without an overlay shadow. The history and settings entry
buttons keep a fixed position above the workbench and side panel, and only one
right-side panel can be open at a time. Each entry button is also its panel's
open/close control, so the panels omit separate close buttons and redundant
headers.

On macOS, a fixed drag region stays above the workbench while leaving the
floating entry buttons outside the draggable hit area and at a higher stacking
level. This preserves window dragging from the app's top area without blocking
the history and settings entry buttons.

History file actions stay hidden until the row is hovered or focused. The
actions use compact icon buttons with tooltips instead of text pills, keeping
the generated PPT list scannable while preserving open, reveal, and delete
actions. The history entry does not show a file-count badge. Settings uses the
same side-panel structure as history instead of a modal overlay. When a
conversion completes, DeckLens refreshes and opens the history panel directly
instead of showing a separate result card.

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
