# 2026-05-12: Keep Product Inpaint Path Fast-Only

## Status

Superseded by [2026-05-12-default-lama-inpaint.md](2026-05-12-default-lama-inpaint.md)

## Context

The cleanup tier selector added complexity without producing meaningful final PPTX differences in standard restore. In standard restore, cleaned background differences are often hidden because editable text boxes are placed back over the same regions. The high-quality tier also risked implying materially different model capability while still using local OpenCV variants.

## Decision

Remove the product-facing cleanup selector and keep the app on a single OpenCV Telea text-removal path. Algorithm experiments should be run as separate background-only comparison artifacts, not exposed as normal conversion controls.

## Consequences

The main app has fewer controls and less ambiguity. Users can still compare inpainting algorithms through local test outputs when needed, but regular conversion stays on the fastest stable path.

## Required Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
