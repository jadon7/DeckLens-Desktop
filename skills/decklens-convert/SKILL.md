---
name: decklens-convert
description: Use when a user gives image, screenshot, or PDF files and wants DeckLens to convert or split them into an editable PPTX deck through the local CLI.
---

# DeckLens Convert

Use the repository CLI to convert image-like presentation pages into PPTX.

## Workflow

1. Locate the DeckLens Desktop repository.
2. Verify the user-provided files exist and are images or PDFs.
3. Run the CLI from the repository root.
4. Return the generated `.pptx` path and summarize the mode used.
5. If the requested output already exists, ask before using `--overwrite`.

## Commands

Standard restore:

```bash
python3 decklens_cli.py "/path/to/input.png" --output "/path/to/output.pptx"
```

Multiple pages:

```bash
python3 decklens_cli.py "/path/to/page1.png" "/path/to/page2.png" --output "/path/to/deck.pptx"
```

PDF input:

```bash
python3 decklens_cli.py "/path/to/file.pdf" --output "/path/to/deck.pptx"
```

Element layering without interactive preview:

```bash
python3 decklens_cli.py "/path/to/input.png" --mode element --output "/path/to/deck.pptx"
```

AI layered restore with fal.ai:

```bash
FAL_KEY="$FAL_KEY" python3 decklens_cli.py "/path/to/input.png" --mode ai --qwen-layers 4 --output "/path/to/deck.pptx"
```

Machine-readable output:

```bash
python3 decklens_cli.py "/path/to/input.png" --json
```

## Notes

- Supported inputs: `.png`, `.jpg`, `.jpeg`, `.pdf`.
- Default output is next to the first input if `--output` is omitted.
- Use `--inpaint-backend lama` for the product default, or `--inpaint-backend local_mean` for faster simple backgrounds.
- Use `DECKLENS_DEVICE=cpu` unless the machine is known to have a working accelerated backend.
- Existing output files are not replaced unless `--overwrite` is passed.
