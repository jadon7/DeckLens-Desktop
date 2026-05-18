# Agent Review CLI

## Context

The interactive "background element merge and delete" step is effective inside the app, but Agent workflows could only call one-shot element conversion. That meant Agents had to fix fragmented picture layers after PPTX generation, where source mask intent and clean preview data were already lost.

## Decision

- Add `decklens review create` to export the element preview stage as an Agent review directory.
- Include numbered previews, per-mask transparent crops, per-mask context crops, contact sheets, `manifest.json`, `decision.template.json`, and suggested merge groups.
- Add `decklens review apply` to apply a merge/delete/keep decision JSON and generate PPTX using the same mask composition strategy as the app preview flow.
- Update the DeckLens Agent skill to prefer `review create` and `review apply` before PPTX post-processing.
- Keep the underlying segmentation and cleanup algorithms unchanged.
- Add a visible animated update progress state for app update downloads.

## Consequences

Agents can make semantic merge/delete decisions before PPTX generation, reducing fragmented picture layers earlier in the pipeline. The app's existing interactive review behavior remains unchanged.

## ADR checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
