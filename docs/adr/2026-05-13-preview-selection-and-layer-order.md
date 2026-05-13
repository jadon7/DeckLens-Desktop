# Preview Selection and Layer Order

## Status

Accepted

## Context

Element preview selection was only reliable from the left-hand list. The right
canvas should participate in the same multi-selection state so users can select,
merge, or delete elements directly from the visual preview.

After background deduplication, layer order also needs to stay stable. PowerPoint
stacks shapes in insertion order, so parent and container elements must be added
before smaller child elements.

## Decision

- Route left-list clicks, right-canvas clicks, and canvas box selection through
  the same selection state.
- Keep Fabric active selections as transient UI state and manage persisted
  selection in `selectedMasks`.
- Sort deduped element masks by descending area before layer creation so larger
  parent/container layers are placed below smaller child/detail layers.

## Consequences

- Users can multi-select from the preview canvas and list interchangeably.
- The merge toolbar appears consistently for both selection paths.
- Generated PPTX layer order is more stable after element background repair.

## Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
