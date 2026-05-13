# Small Text Overlap Guard

## Status

Accepted

## Context

OCR boxes can have small coordinate and size errors. After DeckLens re-renders
recognized text as editable PowerPoint text boxes, these small errors can make
adjacent text overlap even when the original design did not.

Intentional text stacking and decorative overlap can also exist, so the product
should avoid broad geometry rewrites.

## Decision

Add a conservative post-processing pass after text style normalization:

- Detect text box intersections by overlap area relative to the smaller box.
- Only adjust small overlaps.
- Preserve large overlaps as possible intentional design.
- Move same-row boxes horizontally and same-column boxes vertically.
- Cap each movement to a small page-relative distance.

## Consequences

- Common OCR jitter should produce fewer overlapping editable text boxes.
- Large decorative overlaps are less likely to be damaged.
- Dense layouts may still keep some overlaps if resolving them would require a large movement.

## Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
