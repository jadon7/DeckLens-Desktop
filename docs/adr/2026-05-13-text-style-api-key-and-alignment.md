# Text Style, API Key, and Alignment Updates

## Status

Accepted

## Context

Recent desktop testing found three product issues:

- AI smart layering needed a per-task fal.ai API key field without exposing model selection.
- Repeated text styles from OCR could drift across otherwise identical labels.
- Normalized text could still look misaligned when OCR boxes jittered by a few pixels.

## Decision

- Keep AI smart layering on the fixed `fal-ai/qwen-image-layered` model and accept only an optional API key from the UI.
- Normalize repeated OCR text by visual style, including font family, size, color, bold state, and conservative geometry alignment.
- Keep geometry alignment scoped to blocks already grouped as the same visual style.
- Guard Electron backend log forwarding when the main window is destroyed.

## Consequences

- Users can provide their own fal.ai key for one task without changing the model.
- Repeated menus and labels are more likely to keep consistent style and alignment in the generated PPTX.
- Intentional layout differences are preserved because geometry snapping only applies inside repeated-style groups.

## Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
