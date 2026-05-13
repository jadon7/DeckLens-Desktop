# 2026-05-12: Per-Conversion Inpaint Cleanup Tiers

## Status

Superseded by [2026-05-12-fast-inpaint-only.md](2026-05-12-fast-inpaint-only.md)

## Context

DeckLens previously selected text removal through a process-wide environment variable. That made it hard to compare cleanup quality in the product UI and forced users to choose between the fast OpenCV path and the heavier LaMa path before starting the app.

## Decision

Expose cleanup as a per-conversion setting with three local tiers:

- `fast`: OpenCV Telea inpaint. This remains the default because it is CPU-friendly, quick, and has no model download.
- `quality`: enhanced OpenCV Telea with a wider text mask and larger default radius. This keeps the UI tier CPU-friendly and avoids large model downloads.
- `experimental`: OpenCV Navier-Stokes inpaint with a larger default radius. This gives users a third local comparison path without adding large generative model dependencies.

The engine still accepts legacy `DECKLENS_INPAINT_BACKEND` aliases so CLI and existing scripts keep working, including explicit `lama` for high-memory testing outside the default UI tiers.

## Consequences

Each task now records its cleanup tier and passes it through standard restore, element preview, and AI smart layering. LaMa, Stable Diffusion, or PowerPaint-style generative cleanup remains out of the default desktop UI because those models are too large for ordinary desktop defaults and can alter slide design details instead of faithfully restoring the original background.

## Required Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
