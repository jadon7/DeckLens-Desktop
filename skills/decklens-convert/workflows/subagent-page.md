# Subagent Page Workflow

Use this workflow for one DeckLens page. The page subagent owns page-level visual reconstruction quality. Program segmentation is only a draft.

Before doing any page work, read `workflows/quality-rules.md`. This file only describes the subagent page procedure; `quality-rules.md` contains the full quality contract.

## Required inputs

- Page number.
- Original page image.
- DeckLens review assets or `inspect` output.
- Output directory.
- Main Agent acceptance requirements.

If any required input is missing, report the missing item instead of guessing.

## Page mission

For this page, produce a PPT page that is editable and semantically layered:

- Complex photos, screenshots, 3D renders, textures and detailed illustrations may remain bitmap, but each semantic image should be one picture layer.
- Flat icons, bar/column charts, standalone rectangles/circles/card containers/dividers and standalone backgrounds must be redrawn.
- Vector drawing scope is limited to rectangles, circles, icons, and dividers. Keep arrows, hand-drawn marks, complex decorations and other non-basic shapes in their original bitmap construction unless they are standard icons matched by the DeckLens icon library.
- Pie, donut, line, area, radar and complex charts should not be redrawn unless explicitly requested.
- Text should remain editable when OCR quality is acceptable.
- Replaced source picture layers must be deleted or hidden.

## Hard rules

| Case | Required action | Failure |
| --- | --- | --- |
| Program splits one visual image into fragments | Crop the original image region as one bitmap and delete fragments | Delivering many selectable fragments |
| Program merges flat objects into a large picture | Manually split by original-image semantics and redraw flat objects | Keeping the large picture only because no mask exists |
| Flat icon | Replace through DeckLens icon library first | Keeping as picture, or using emoji/Unicode/text as icon |
| Flat bar/column chart | Redraw as PPT rectangles, lines and text | Keeping as picture |
| Non-bar chart | Keep as bitmap unless explicitly requested | Overdrawing as SVG and distorting data |
| Standalone flat rectangle/circle/rounded rectangle/button container/divider | Redraw as PPT native shape | Keeping as picture, changing radius/style arbitrarily, or using SVG |
| Standalone flat background | Rebuild as PPT background, rectangle, or gradient | Keeping as ordinary picture |
| New shape/SVG/icon/merged bitmap replaces source content | Delete or hide corresponding source picture layers | New object stacked over old picture |
| Icon insertion | Keep 1:1 ratio and center in original box | Stretching icon to non-square box |
| Any approved in-scope flat candidate exists | Generate at least one shape/SVG/icon/vector object for the page | Returning a page with zero vector objects |
| Complex/bitmap object | Keep or merge as bitmap | Overvectorizing screenshots, logos, photos, 3D, complex illustrations or non-bar charts |

## Flat element definition

Treat an element as flat when it:

- Uses solid colors, few colors, simple opacity, or simple linear gradient.
- Has no photo detail, paper/noise texture, 3D material, complex glow, realistic shadow, or dense illustration strokes.
- Can be approximated by rectangles, circles, icon libraries, dividers, or bar/column chart primitives.
- Is an independent semantic object, not a local color region inside a screenshot, photo, logo, 3D render, complex illustration, or non-bar chart.

Segmentation artifacts do not make a flat object complex. If the original image shows a flat icon but the mask has rough edges, still replace it.

Only keep a flat-looking object as bitmap when it is actually part of a complex screenshot/photo/illustration/logo/non-bar chart or when vector reconstruction would clearly reduce fidelity. Do not overdraw these internal regions as SVG. Record the reason in the audit table.

## Manual split and merge

Use the original page image as authority.

Merge manually when:

- A photo, 3D object, complex illustration, texture, screenshot, project preview, or black image area is split into multiple pictures.
- Multiple fragments overlap, nest, or share one visible boundary.
- A selected area shows many handles but the original image has one semantic image object.

Split or rebuild manually when:

- A large picture contains flat cards, icons, bar/column charts, standalone backgrounds, standalone rectangles/circles, dividers, button containers, or text.
- A flat object has no separate mask.
- A card contains both a vector container and bitmap content. Rebuild the container as shape, keep only complex internal image content as bitmap.

## Required page process

1. Inspect the original page image first. List these candidates:
   - Flat icons.
   - Flat bar/column charts.
   - Non-bar charts to preserve as bitmap.
   - Flat rectangles/circles/rounded rectangles/dividers/button containers.
   - Flat backgrounds.
   - Cards.
   - Complex image groups to merge.
   - Text areas.
2. Inspect DeckLens output or review masks.
3. Build a replacement list. For every semantic object, map source picture layer(s) to target object:
   - PPT shape.
   - PPT text.
   - SVG only for icon-library output. Use PPT shapes for rectangles, circles, card/button containers and dividers.
   - PNG icon.
   - Merged bitmap crop.
   - Kept bitmap with reason.
4. Execute reconstruction:
   - Use `decklens icons find` and `decklens icons render` for flat icons. Do not use emoji/Unicode/text icons.
   - Do not hand-draw flat icons. If icon-library search fails after synonyms, preserve the original bitmap/crop and explain why. Preserve logos as bitmap if the library has no match.
   - Redraw only bar/column charts using rectangles, lines and text. Preserve other chart types as bitmap unless explicitly requested.
   - Redraw flat backgrounds and cards using PPT shapes and gradients.
   - Place every replacement at the original semantic z-order.
   - Crop original image regions for complex image groups.
5. Delete or hide every source picture layer replaced by a new object.
6. Run page-level `inspect` or provide data for the main Agent to inspect.
7. Return the page audit table and self-check.

## Icon rules

- Run `decklens icons find <semantic-name> --json` for icon candidates. This is required for standard icons.
- If the first search fails, try at least two synonyms or close names.
- Render successful icons with `decklens icons render`.
- Prefer `lucide-static` outline, then `tabler-icons`, then `heroicons` when style fits.
- Keep style consistent within the same page, but do not force style consistency across different pages.
- Keep icon width and height equal. Use `min(original_width, original_height)` and center it in the original box.
- Never use emoji, Unicode symbols, font symbols or plain text characters as icon replacements.

If no standard icon fits after synonym search, preserve the original bitmap/crop and record the reason. Do not hand-draw a replacement icon. Preserve brand/social/product logos as bitmap when the library has no good match. Do not keep a standard flat icon as picture just because the first search failed.

## Chart rules

Only bar/column charts must be redrawn:

- Bar/column charts: rectangles.
- Axes/grid/legends: lines and editable text.

Approximate unreadable data by visual proportion, but preserve labels, colors and legend order.

Do not redraw pie, donut, line, area, radar, dashboard or complex charts unless the user explicitly asks for that. Keep them as a single bitmap region and explain the reason.

## Card and background rules

Cards are layout structure, not ordinary pictures. Rebuild card body as:

- Rounded rectangle / rectangle.
- Fill, border, transparency, shadow and gradient.
- Internal text as editable text.
- Internal icon as DeckLens icon-library SVG/PNG only, or original bitmap/crop when no match exists.
- Internal complex screenshot/photo as cropped bitmap.
- Match original corner radius, fill color, border width/color, shadow direction/blur/opacity, gradient direction and visual padding.
- Match original size and corner radius closely. Do not use a default radius or invent a nicer card style.
- Put the card container below its internal text/icon/image. Do not cover card content.

Flat background must be rebuilt:

- Solid background: page background or full-page rectangle.
- Simple gradient: PPT gradient when possible.
- If gradient cannot be matched, crop only the gradient as a bottom/background bitmap and keep foreground text/icons editable.

## Quality audit table

Return this table for the page:

| Item | Required fields |
| --- | --- |
| Page owner | subagent id/name, page number |
| Picture stats | original picture count, final picture count, original small picture count, final small picture count, deleted/hidden picture count |
| Manual split/merge | bad segmentation object count, manually merged count, manually split count, manually rebuilt count, unresolved reasons |
| Flat icons | candidate count, replaced count, icon find calls, render outputs, kept bitmap count and reasons |
| Charts | bar/column candidate count, redrawn count, non-bar kept bitmap count and reasons |
| Flat shapes | candidate count, redrawn count, kept bitmap count and reasons |
| Flat backgrounds | candidate count, redrawn count, kept bitmap count and reasons |
| Cards | candidate count, rebuilt container count, style match for radius/fill/border/shadow/gradient, kept bitmap count and reasons |
| Gradients | candidate count, PPT gradient count, bitmap background count and reasons |
| Duplicate overlay | source layers deleted for new objects, duplicate overlay check |
| Layer order | background/card/image/text/icon order check and any repaired z-order |
| SVG overdraw | objects wrongly vectorized, reverted-to-bitmap count, remaining reasons |
| Final status | pass/fail and exact remaining work |

Pass conditions:

- Standard flat icon kept bitmap count is 0. Preserved brand/social/product logos must have documented failed icon-library attempts and concrete preservation reasons.
- Flat bar/column chart kept bitmap count is 0.
- Standalone flat rectangle/circle/background kept bitmap count is 0.
- If any approved in-scope flat candidate count is greater than 0, generated shape/SVG/icon/vector object count is greater than 0.
- Every unresolved bitmap has a concrete non-flat reason.
- A complex single image is not split into multiple selectable pictures.
- Every new object has corresponding source layer deletion or an explicit no-source reason.
- No emoji/Unicode/text icon replacements exist.
- No hand-drawn flat icon replacements exist.
- Non-bar charts, logos, screenshots, photos, 3D and complex illustrations are not overvectorized.
- Rebuilt card containers visually match original radius, fill, border, shadow and gradient well enough to pass review.
- Layer order matches original visual stacking.

## Return format

Return:

- Page output path or patch description.
- Quality audit table.
- Replacement list.
- Deleted/hidden source layer list.
- Generated SVG/PNG/icon files.
- Remaining bitmap reasons.
- Self-check conclusion.

Do not say the page is complete if any pass condition fails.
