# 2026-05-13: Local Cleanup and Layering Experiments

## Status

Accepted

## Context

DeckLens needs predictable local behavior for standard restore and element
layering. Recent local comparisons showed two useful product-facing changes:
FastSAM-s is the preferred local element-layering default, and the text cleanup
path should expose both LaMa and a lightweight local mean option for direct
comparison on user materials.

Several research scripts were also added to keep segmentation, text cleanup,
and vectorization experiments reproducible outside the product path.

## Decision

Use FastSAM-s as the product default for local element layering, with OpenCV
mask generation as a fallback. Keep LaMa as the default text cleanup backend and
expose the local mean cleanup backend as a selectable alternative. Keep research
scripts separate from app integration so candidate algorithms can be compared
before becoming product features.

## Consequences

Element layering is more stable on local machines that can run FastSAM-s, while
the fallback preserves a no-model path. Standard restore can compare cleanup
backends without changing the surrounding OCR and PPTX generation flow.
Research artifacts remain reproducible but do not add vectorization behavior to
the product.

## Required Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
