---
name: decklens-convert
description: Use when a user gives image, screenshot, or PDF files and wants DeckLens to convert or split them into an editable PPTX deck through the local CLI.
metadata:
  decklens:
    version: "0.2.6"
    min_app_version: "0.2.6"
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
6. Run `decklens convert` from the repository root. If `decklens` is not on `PATH`, use `./bin/decklens.cjs convert`.
7. Return the generated `.pptx` path and summarize the mode used.
8. If the requested output already exists, ask before using `--overwrite`.

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

## Post-processing layered output

When using `--mode element`, inspect the generated PPTX before returning it:

1. Before running or accepting element layering, inspect the source image regions that are likely to become independent layers. Do not rely only on the extracted layer mask, because segmentation can create fuzzy edges, halo pixels, and small fragments that make a simple original shape look complex.
2. Mark vector candidates from the original visual appearance first: flat or low-detail rectangles, rounded rectangles, circles, ellipses, straight lines, arrows, badges, dividers, common UI icons, logos with simple geometry, and other regular shapes that look clean and not visually complex.
3. Prefer replacement over tracing for common icons. If an icon clearly matches an SF Symbol, Material Design icon, or another standard symbol available to the target environment, replace it with that symbol first. If no reliable symbol match exists, redraw it as SVG or native PPT shapes.
4. Use SVG/native shapes for regular but non-standard graphics. Preserve position, size, opacity, fill, stroke, corner radius, rotation, and approximate visual weight. Simplify tiny mask noise instead of reproducing it.
5. Exclude unsuitable elements even if the segmentation produced a separate layer: photographs, 3D renders, realistic illustrations, complex gradients, heavy shadows, textures, soft glows, detailed logos, screenshots, noisy masks, and anything whose fidelity would be worse after vectorization.
6. Open or parse the PPTX and review the extracted picture layers in slide order. Replace only the raster layers that correspond to the pre-marked vector candidates.
7. Maintain stacking order. Insert replacement vectors at the same z-order position as the original raster shape so foreground/background relationships do not change.
8. If a candidate becomes ambiguous after extraction, compare it against the original source crop. Keep the raster layer when replacement would reduce visual fidelity or break ordering, and mention that it was intentionally left unchanged.
