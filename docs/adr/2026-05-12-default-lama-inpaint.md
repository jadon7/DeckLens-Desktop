# 2026-05-12: Use LaMa as Default Text Cleanup

## Status

Accepted

## Context

Background-only comparisons on the local test materials showed that the PyTorch
LaMa hard-mask result produced better cleaned backgrounds than the OpenCV Telea
path. Feathered mask blending was also tested, but the hard-mask LaMa output was
preferred for the current material set.

## Decision

Use PyTorch LaMa as the default product text-removal backend. The product uses
the OCR text boxes as a hard binary mask, caps LaMa inference to a 1024px long
side by default, and keeps OpenCV Telea as an automatic fallback. Users or
deployments can still force the lightweight path with
`DECKLENS_INPAINT_BACKEND=opencv`.

## Consequences

Standard restore, element preview, and AI smart layering now get higher-quality
cleaned backgrounds by default. First LaMa use may download/load the model and
will cost more memory and time than OpenCV, so the fallback remains important
for lower-resource environments.

## Required Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
