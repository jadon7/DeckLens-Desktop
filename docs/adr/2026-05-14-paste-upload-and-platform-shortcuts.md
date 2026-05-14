# ADR: Paste Upload And Platform Shortcuts

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

DeckLens import currently supports file picker and drag-and-drop. Users also
capture screenshots or copy image assets directly, so pasting should feed the
same local upload flow. Element preview shortcut labels also used Windows-style
`Ctrl` text on macOS.

## Decision

Handle document-level paste events when the clipboard contains files or images.
Clipboard files are normalized to supported image/PDF file names and then reuse
the existing selected-file list and conversion flow. Pasting into editable form
controls is left alone so API keys and text inputs keep normal paste behavior.

Preview shortcut labels now derive the platform modifier from the Electron
platform class or browser platform. macOS shows `⌘`; Windows and other platforms
show `Ctrl`. The keyboard handler follows the same platform-specific modifier.

## Consequences

- Users can import screenshots by copying and pasting without opening the file
  picker.
- Pasted uploads share the same validation and rendering path as picked or
  dropped files.
- Element preview controls present shortcuts that match the current operating
  system.
