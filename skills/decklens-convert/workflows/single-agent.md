# Single Agent Workflow

Use this workflow when the task is a single page, or when subagents are not available. Single-page tasks should use this workflow directly even if the current environment supports subagents.

Before using this file, read `workflows/quality-rules.md`. That file is the full quality contract.

## Role

The single Agent owns the page work. For a single-page task, process it directly and do not create subagents. For a multi-page fallback task, isolate pages strictly and do not process the deck as one vague task.

For each page, run a separate page cycle:

1. Observe original page.
2. Inspect DeckLens output/review assets.
3. Build replacement list.
4. Manually split/merge/rebuild where needed.
5. Delete replaced source picture layers.
6. Run final page check.
7. Fill the page audit table.

Only after one page passes should the Agent proceed to the next page.

## Required rules

Apply the same page rules as `workflows/quality-rules.md` and `workflows/subagent-page.md`:

- Program segmentation is only a draft.
- Use original-image semantics as authority.
- Flat icon must be replaced.
- Flat bar/column chart must be redrawn; other chart types should be preserved as bitmap unless explicitly requested.
- Standalone flat rectangle/circle/rounded rectangle/button container/divider must be redrawn with PPT native shapes.
- Keep arrows, hand-drawn marks, complex decorations and other non-basic shapes in their original bitmap construction unless they are standard icons matched by the DeckLens icon library.
- Standalone flat background must be redrawn.
- Bad program splitting must be manually corrected.
- Bad program merging must be manually split or rebuilt.
- Every added shape/SVG/icon/merged bitmap must delete or hide its source picture layer.
- Do not use emoji, Unicode symbols, font symbols or plain text as icon replacements.
- Do not overvectorize screenshots, logos, photos, 3D, complex illustrations or non-bar charts.
- Preserve layer order.
- Every page must have a quality audit table.
- If any approved in-scope flat candidate exists, the page must generate shape/SVG/icon/vector objects. A page with in-scope flat candidates and zero vector objects fails.

If possible, read `workflows/subagent-page.md` as the page-rule reference even though no subagent is used. Do not skip `workflows/quality-rules.md`.

## Workflow

1. Resolve DeckLens CLI and confirm it supports `review create`, `review apply`, `inspect`, and `icons render`.
2. Create or inspect review assets.
3. For each page independently:
   - List flat icons, bar/column charts, non-bar charts to preserve, flat shapes, flat backgrounds, cards, complex image groups and text areas.
   - Map source picture layer(s) to replacement objects.
   - Replace flat icons via DeckLens icon render; do not use emoji/Unicode/text icons and do not hand-draw flat icons.
   - Redraw only bar/column charts as PPT shapes.
   - Redraw standalone flat rectangles/circles/card or button containers/dividers/backgrounds as PPT native shapes or gradients, matching original size, radius, fill, stroke and shadow.
   - Rebuild cards as vector containers plus internal bitmap/text/icon content, matching original radius/fill/border/shadow/gradient.
   - Merge complex image fragments by cropping the original page region.
   - Delete or hide source picture layers.
   - Restore visual layer order.
   - Run page-level inspect or record data for final inspect.
   - Fill the audit table.
4. Combine pages in original order.
5. Run final `inspect` on the combined PPTX.
6. Re-check every page audit table against final output.

## Quality audit table

Each page must include:

| Item | Required fields |
| --- | --- |
| Page state | page number, single-agent mode, pass/fail |
| Picture stats | original picture count, final picture count, original small picture count, final small picture count, deleted/hidden picture count |
| Manual split/merge | bad segmentation object count, manually merged count, manually split count, manually rebuilt count, unresolved reasons |
| Flat icons | candidate count, replaced count, icon find calls, render outputs, kept bitmap count and reasons |
| Charts | bar/column candidate count, redrawn count, non-bar kept bitmap count and reasons |
| Flat shapes | candidate count, redrawn count, kept bitmap count and reasons |
| Flat backgrounds | candidate count, redrawn count, kept bitmap count and reasons |
| Cards | candidate count, rebuilt container count, style match for radius/fill/border/shadow/gradient, kept bitmap count and reasons |
| Duplicate overlay | source layers deleted for new objects, duplicate overlay check |
| Layer order | background/card/image/text/icon order check |
| SVG overdraw | wrongly vectorized object count, reverted-to-bitmap count, remaining reasons |

Fail a page if:

- Any standard flat icon remains as picture without documented failed icon-library attempts and a concrete preservation reason.
- Any flat bar/column chart remains as picture.
- Any standalone flat rectangle/circle/background remains as ordinary picture.
- Any emoji/Unicode/text object is used as an icon.
- Any flat icon is hand-drawn instead of using DeckLens icon library output or preserved original bitmap/crop.
- Any non-bar chart, logo, screenshot, photo, 3D or complex illustration is overvectorized.
- Any arrow, hand-drawn style, complex decoration or non-basic shape is vectorized outside the icon-library path.
- Any approved in-scope flat candidate exists but no shape/SVG/icon/vector object is generated.
- A complex single image remains split into multiple selectable pictures.
- New objects overlap old source pictures.
- Layer order changes visual stacking.
- The audit table skips candidate/completion counts.

## Final response

Report:

- Final PPTX path.
- State that subagents were unavailable or not used.
- Per-page audit summary.
- Manual split/merge summary.
- Flat icon/bar-chart/shape/background redraw counts.
- Non-bar chart/logo/screenshot/photo/3D/complex illustration preserve decisions.
- Layer order check.
- Remaining bitmap reasons.
- Any page that is not final.

Do not call the deck final if any page fails.
