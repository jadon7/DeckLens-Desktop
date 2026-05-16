---
name: decklens-convert
description: Use when a user gives image, screenshot, or PDF files and wants DeckLens to convert or split them into an editable PPTX deck through the local CLI.
metadata:
  decklens:
    version: "0.2.8"
    min_app_version: "0.2.8"
    update_channel: stable
    source: decklens
---

# DeckLens Convert

Use the DeckLens product CLI to convert image-like presentation pages into PPTX.

## Workflow

1. Locate the DeckLens Desktop repository or an installed DeckLens CLI.
2. If the CLI is available, run `decklens install-skills` once when the user asks to install the Agent skill globally.
3. If the user asks to check or update this skill, run `decklens skills status` or `decklens skills update`. Use `--force` only after the user confirms overwriting local skill edits.
4. If DeckLens is not installed, ask the user whether they want you to install it. If they agree, use the direct platform download link below instead of sending them to the homepage, then retry after the app has been launched once.
5. Verify the user-provided files exist and are images or PDFs.
6. For image-like slide pages, prefer `--mode element` unless the user explicitly asks for a flat/standard restore or AI mode.
7. Before running DeckLens, inspect the original source image and make a brief vectorization plan from the original visual appearance. Do not wait for segmentation output to decide what is vectorizable, because extracted masks can introduce fuzzy edges, halo pixels, and fragments that make clean source shapes look complex.
8. Run `decklens convert` from the repository root. If `decklens` is not on `PATH`, use `./bin/decklens.cjs convert`.
9. Run `decklens inspect <output.pptx> --json` to review slide item order, editable text boxes, image layers, and media paths before modifying the PPTX.
10. Post-process the layered PPTX according to the pre-conversion vectorization plan.
11. Re-run `decklens inspect <final.pptx> --json` after post-processing when layer order or object replacement changed.
12. Return the generated `.pptx` path and summarize the mode used, the vector targets replaced, and any targets intentionally left raster.
13. If the requested output already exists, ask before using `--overwrite`.

## Direct Downloads

- macOS: `https://updates.dsxzai.com/download/mac`
- Windows: `https://updates.dsxzai.com/download/windows`
- Auto-detect: `https://updates.dsxzai.com/download`

## Commands

Standard restore:

```bash
decklens convert "/path/to/input.png" --output "/path/to/output.pptx"
```

Multiple pages:

```bash
decklens convert "/path/to/page1.png" "/path/to/page2.png" --output "/path/to/deck.pptx"
```

PDF input:

```bash
decklens convert "/path/to/file.pdf" --output "/path/to/deck.pptx"
```

Element layering without interactive preview:

```bash
decklens convert "/path/to/input.png" --mode element --output "/path/to/deck.pptx"
```

AI layered restore with fal.ai:

```bash
FAL_KEY="$FAL_KEY" decklens convert "/path/to/input.png" --mode ai --qwen-layers 4 --output "/path/to/deck.pptx"
```

Machine-readable output:

```bash
decklens convert "/path/to/input.png" --json
```

Repository fallback when the CLI is not installed globally:

```bash
./bin/decklens.cjs convert "/path/to/input.png" --output "/path/to/output.pptx"
```

Install or refresh this skill in user-global Agent skill folders:

```bash
decklens install-skills
```

Check or update installed DeckLens Agent skills:

```bash
decklens skills status
decklens skills update
```

Find bundled icons for PPT post-processing:

```bash
decklens icons libraries
decklens icons find mail --style outline --json
decklens icons find arrow-right --json
```

Inspect generated PPTX structure:

```bash
decklens inspect "/path/to/deck.pptx" --json
```

Render a bundled icon without installing npm packages:

```bash
decklens icons render mail --style outline --color 111111 --format svg --output "/path/to/mail.svg" --json
decklens icons render mail --style outline --color 111111 --format png --size 512 --output "/path/to/mail.png" --json
```

Repository fallback:

```bash
./bin/decklens.cjs install-skills
```

Installed app fallback on macOS:

```bash
node "/Applications/DeckLens.app/Contents/Resources/cli/decklens.cjs" install-skills
```

Installed app fallback on Windows:

```powershell
node "$env:LOCALAPPDATA\Programs\DeckLens\resources\cli\decklens.cjs" install-skills
```

## Notes

- Supported inputs: `.png`, `.jpg`, `.jpeg`, `.pdf`.
- Default output is next to the first input if `--output` is omitted.
- Use `--inpaint-backend lama` for the product default, or `--inpaint-backend local_mean` for faster simple backgrounds.
- Use `DECKLENS_DEVICE=cpu` unless the machine is known to have a working accelerated backend.
- Existing output files are not replaced unless `--overwrite` is passed.
- Do not ask the user to install internal Python dependencies for this skill. If DeckLens or its CLI is missing, ask for permission and help the user install DeckLens from the direct platform download link instead.
- Do not call `decklens_cli.py` directly from a skill. It is an internal backend adapter behind the product CLI.

## Pre-conversion vectorization plan

Before running `decklens convert --mode element`, inspect the original page image and list semantic vector targets, using the clean source appearance rather than segmentation artifacts.

Pre-mark these as vector candidates when they are visually simple in the source image:

- Page backgrounds, rounded slide frames, panels, cards, buttons, pills, badges, dividers, underlines, progress bars, and simple decorative bands.
- Flat-color or gradient circles/ellipses used as icon containers.
- Straight lines, arrows, connectors, and simple geometric marks.
- Common UI icons and presentation icons that clearly match a known symbol set.
- Text-like content should remain editable text when OCR quality is acceptable; manually correct obvious OCR spacing or punctuation errors after conversion.

Record vector targets semantically, not by future layer count. For example, "contact pill with globe icon, divider, mail icon" or "four metric cards with icon badges" is better than "image4.png". A single semantic vector target may later correspond to multiple DeckLens output layers, or one output layer may contain several fragments of a single target.

Exclude these from vector replacement unless the user explicitly asks for a rough redraw:

- Photographs, complex screenshots, realistic illustrations, 3D renders, detailed logos, complex gradients, heavy shadows, soft glows, noisy textures, and any target whose fidelity would be worse as a vector.

## Post-processing layered output

When using `--mode element`, inspect the generated PPTX before returning it:

1. Open or parse the PPTX and review the extracted picture layers in slide order.
2. Map extracted layers back to the pre-conversion semantic vector targets. Do not decide vector eligibility from the extracted masks alone.
3. Replace all raster layers that belong to each pre-marked vector target. If one semantic vector target was split into multiple DeckLens picture layers, delete or hide every corresponding raster layer before inserting the replacement. If multiple semantic targets were merged into one raster layer, replace the relevant area only when the final stacking and fidelity remain clear.
4. Draw vector replacements at the full semantic-object extent, not just the tight visible mask. For example, redraw a full card, full pill, full icon badge, full CTA bar, or full divider rather than only the extracted interior pixels. Preserve position, size, opacity, fill, stroke, corner radius, rotation, approximate shadow, and visual weight.
5. For common icons, do not hand-draw an approximate icon. Prefer bundled DeckLens icon libraries in this order:
   - `lucide-static` SVG icons for clean outline UI symbols.
   - `@tabler/icons` SVG icons when Lucide does not have a close semantic match, or when filled variants are needed.
   - `heroicons` SVG icons for Apple-like outline/solid UI symbols.
   - `phosphor-icons` only when its font/CSS assets are appropriate for the target renderer; otherwise prefer the SVG libraries above.
6. Do not run `npm install`, fetch icon packages from the network, or ask the user to install icon dependencies during conversion. If a needed icon package is not already bundled or installed, choose the closest bundled equivalent, redraw with native PPT geometry, or keep the raster icon and report why.
7. Resolve icons semantically before drawing. Prefer stable names such as `mail`, `phone`, `arrow-right`, `calendar`, `user`, `check`, or `globe`, then run `decklens icons find <name> --json` to get local bundled SVG paths. Use `decklens icons render <name> --format svg|png --output <file>` when an actual insertable asset is needed. Avoid copying noisy segmented pixels as the source of truth for icon shape.
8. Never use emoji, dingbats, Unicode pictograms, or ordinary text characters as substitutes for icons, even when they look visually close in a preview. Symbols such as checkboxes, smileys, arrows, currency marks, people marks, or document marks must be drawn as native PPT geometry or inserted from one standard icon family.
9. Keep icon style consistent within a slide. Do not mix filled icons, outline icons, emoji-like symbols, SF Symbols, Material Symbols, and hand-drawn approximations on the same page unless the source image intentionally uses mixed icon systems. Choose one icon family/style for all comparable UI icons, then match stroke width, cap/join style, optical size, and color across the page.
10. Keep icons as vector sources when the target PPT renderer supports them. Use official SVG icons or native PPT shapes where possible. If a local previewer renders embedded SVG icons as document placeholders or broken-image markers, do not ship that preview-broken deck as the only output. Use `decklens icons render <name> --format png --size 512 --output <file>` to create a transparent high-resolution PNG fallback while preserving one consistent icon style, or rebuild the icons with native PPT shapes. Report this fallback clearly.
11. Use native PPT shapes or SVG for regular non-icon graphics such as cards, circles, pills, dividers, arrows, and simple decorative shapes. Simplify tiny mask noise instead of reproducing it.
12. Maintain stacking order. Insert replacement vectors at the same z-order position as the removed raster layer group so foreground/background relationships do not change.
13. Keep unsuitable elements raster even if segmentation produced a separate layer: photographs, 3D renders, realistic illustrations, complex gradients, heavy shadows, textures, soft glows, detailed logos, screenshots, noisy masks, and anything whose fidelity would be worse after vectorization.
14. Correct obvious OCR errors introduced during conversion, especially missing spaces, punctuation, and merged words, while preserving editable text boxes.
15. Verify the final PPTX structure and report:
   - conversion mode used,
   - vector targets replaced,
   - standard icon source used,
   - icon consistency check result,
   - remaining raster targets and why they were kept.
