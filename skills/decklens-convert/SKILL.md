---
name: decklens-convert
description: Use when a user gives image, screenshot, or PDF files and wants DeckLens to convert or split them into an editable PPTX deck through the local CLI.
metadata:
  decklens:
    version: "0.2.4"
    min_app_version: "0.2.4"
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

1. Open or parse the PPTX and review the extracted picture layers in slide order.
2. Identify simple graphic elements that are better as editable vectors: flat-color rectangles, rounded rectangles, circles, ellipses, straight lines, simple icons, and other low-color shapes with clean edges.
3. Redraw suitable elements as SVG or native PPT shapes, then replace the corresponding raster layer. Preserve the original position, size, opacity, fill color, stroke, and rotation as closely as possible.
4. Maintain stacking order. Insert replacement vectors at the same z-order position as the original raster shape so foreground/background relationships do not change.
5. Do not vectorize photographs, 3D renders, gradients, shadows, textured elements, or noisy masks. Keep those as raster layers.
6. If replacement would reduce visual fidelity or break ordering, keep the original raster layer and mention that it was intentionally left unchanged.
