# Original vs Rendered Text Overlap Detection

## Status

Accepted

## Context

Some restored editable text can still overlap after style normalization. Checking
only final OCR boxes is not enough because PowerPoint renders text according to
font metrics, and the visible text can occupy more space than the saved OCR box.

The source image can also contain intentional overlap, so overlap correction
must compare against the original OCR geometry before changing coordinates.

## Decision

- Preserve the original OCR bbox on each `TextBlock`.
- Estimate the final rendered text footprint after font and style normalization.
- Compare original overlap against generated overlap.
- Only adjust text when generated overlap grows beyond the source geometry.
- Preserve heavily overlapped original text as possible intentional design.

## Consequences

- Adjacent text that only overlaps after restoration can be separated more reliably.
- Intentional source overlap is less likely to be damaged.
- The estimate is still heuristic because PowerPoint's final renderer is not
  available inside the Python generation step.

## Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
