# DeckLens

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

DeckLens converts image-like presentation pages into editable PowerPoint decks. It is designed for AI-generated presentation images and flattened PPT screenshots that need to be edited again. PDF files are supported as a page-image import source; DeckLens renders each page to an image before processing.

## What It Does

- Upload one or more images, or import PDF pages as images.
- Rebuild each page as a PPTX slide.
- Keep the visual page as a cleaned background.
- Recreate detected text as editable PowerPoint text boxes.
- Optionally split visual elements into editable picture layers.
- Export all pages as one `.pptx` file.
- Keep generated PPTX files available from the desktop history sidebar, with
  actions to open, reveal in the local folder, or delete the output.

## Code Signing Policy

DeckLens Desktop prepares Windows releases for SignPath Foundation review.
The project code signing policy is documented in
[docs/CODE_SIGNING_POLICY.md](docs/CODE_SIGNING_POLICY.md).

## Current Modes

| Mode | Behavior | Notes |
| --- | --- | --- |
| Standard restore | Clean background + editable text | Fastest and safest default |
| Element layering | Preview detected elements, merge/delete, then export | Uses lightweight OpenCV segmentation by default |
| AI smart layering | Uses fal.ai Qwen-Image-Layered when `FAL_KEY` is set | Uploads the cleaned page to fal.ai |

## Current Defaults

DeckLens now defaults to higher-quality local cleanup:

- OCR: PaddleOCR.
- Text removal: PyTorch LaMa inpaint by default, using the OCR text boxes as a hard mask.
- OpenCV Telea remains available with `DECKLENS_INPAINT_BACKEND=opencv`.
- Local SAM: disabled by default to avoid high memory peaks.
- SAM opt-in: set `DECKLENS_ENABLE_SAM=1`.
- Input processing cap: `DECKLENS_MAX_PROCESS_MP=3.0` and `DECKLENS_MAX_PROCESS_SIDE=2200`.
- Page fonts: unified per slide into at most three font groups: Chinese, English, and numeric. Mixed Chinese/English/numeric text uses the Chinese font group.
- Desktop startup: heavyweight model stacks are lazy-loaded only during conversion, and task cleanup releases OCR/optional model singletons by default.

## Repository Scope

This repository is scoped to the DeckLens Desktop client. It keeps the Electron
shell, the lightweight local Flask backend that is packaged into the app,
desktop release/update infrastructure, signing documentation, and architecture
decision records. Historical web deployment files, local experiment scripts, and
generated test/build artifacts are intentionally excluded from the client repo.

## Run Desktop Shell

DeckLens Desktop runs on macOS and Windows. The UI is structured as a desktop
workbench. The installer intentionally does not bundle Python dependencies,
PaddleOCR models, SAM checkpoints, or other large model assets. On first launch,
the app asks the user to install the local Python runtime into the Electron user
data directory. The packaged app stores the lightweight Flask backend under
Electron `extraResources` as `Contents/Resources/backend` on macOS, outside
`app.asar`, so first-launch runtime installation can copy templates and static
assets as normal files.

Development run:

```bash
npm install
npm run electron:dev
```

Build unpacked app:

```bash
npm run electron:pack
```

Use this unpacked build for day-to-day validation. It avoids notarized installer
generation and keeps UI/flow checks fast. Signed installer builds are reserved
for release publishing.

Smoke-check a packaged macOS build:

```bash
test -f release/mac-arm64/DeckLens.app/Contents/Resources/backend/app.py
test -f release/mac-arm64/DeckLens.app/Contents/Resources/backend/templates/index.html
open -n release/mac-arm64/DeckLens.app
```

Fast unsigned builds for validation:

```bash
npm run electron:dist:mac:unsigned
npm run electron:dist:win:unsigned
```

Build signed release installers:

```bash
npm run electron:dist:mac
npm run electron:dist:win
```

Windows CI builds are produced by `.github/workflows/windows-build.yml`. The
workflow currently uploads unsigned artifacts and is prepared for SignPath
Foundation integration after the project is approved.

Build a signed and notarized macOS installer on a machine with a Developer ID
Application certificate and the `decklens-notary` notarytool profile saved in
Keychain:

```bash
npm run electron:dist:mac:signed
```

Auto-update builds use the Cloudflare-hosted generic update feed configured at
`https://updates.dsxzai.com/`. After a signed release build, publish the
electron-builder output files to that Cloudflare path. For macOS this includes
`latest-mac.yml`, the `.dmg`, the `.zip`, and matching `.blockmap` files; for
Windows this includes `latest.yml`, the installer `.exe`, and matching
`.blockmap` files. Keep the YAML metadata cache short so clients can discover
new versions quickly; installer files can be cached for longer because their
names are versioned.

Cloudflare update infrastructure is defined in `wrangler.toml` and
`cloudflare/update-worker.js`. The Worker serves files from the
`decklens-updates` R2 bucket on `updates.dsxzai.com`. The stable user-facing
download routes are:

- `https://updates.dsxzai.com/download`
- `https://updates.dsxzai.com/download/mac`
- `https://updates.dsxzai.com/download/windows`

Those routes read the latest electron-builder metadata from R2 and redirect to
the current versioned installer artifact, so the product website does not need
to hard-code release file names. The redirect is not cached and includes the
artifact digest as a query string, while installer artifacts use immutable
caching and proper `Range` responses for cancel/resume downloads.

## CLI Conversion

DeckLens also includes a local CLI wrapper for Agent-driven conversion:

```bash
python3 decklens_cli.py input.png --output output.pptx
python3 decklens_cli.py input.pdf --mode element --output output.pptx
python3 decklens_cli.py input.png input2.jpg --json --output output.pptx
```

The npm shortcut is:

```bash
npm run decklens:convert -- input.png --output output.pptx
```

Supported modes are `standard`, `element`, and `ai`. AI mode requires a fal.ai
API key through `--fal-key` or `FAL_KEY`. The Agent skill source lives at
`skills/decklens-convert/SKILL.md` and documents the preferred calling pattern
for local Agents. Existing output files are preserved unless `--overwrite` is
passed.

## Website

The product website lives in `site/` and is deployed to
<https://deck.dsxzai.com/> with Cloudflare Pages:

```bash
npm run site:deploy
```

Website icon fonts are self-hosted under `site/vendor/phosphor/`. Do not depend
on extensionless Variant export helper files such as `site/web` or duplicated
`site/style*.css` files for production; Cloudflare Pages serves extensionless
scripts with a generic MIME type, which can break icons under `nosniff`.

The GitHub repository Website/Homepage should point to
`https://deck.dsxzai.com/`. The update feed remains separate at
`https://updates.dsxzai.com/` and is only for Electron auto-update metadata and
release artifacts.

The desktop UI supports Chinese and English. On first launch it follows the
system language, and users can override the language from the settings panel.
The runtime setup screen follows the system language as well so first-run
bootstrap and the main workbench stay consistent.

The desktop runtime expects Python 3.11 or 3.12 to be available on the machine. On macOS it searches common Homebrew, framework, and user-local Python locations because Finder-launched apps do not inherit a normal shell `PATH`. A custom interpreter can be provided with `DECKLENS_PYTHON=/path/to/python`.

## Useful Checks

```bash
node --check electron/main.cjs
node --check electron/preload.cjs
npm run electron:pack
```

## Documentation Map

- [docs/adr/](docs/adr/): decision records required for code/config commits.
- [docs/CODE_SIGNING_POLICY.md](docs/CODE_SIGNING_POLICY.md): Windows signing policy.
- [docs/SIGNPATH.md](docs/SIGNPATH.md): SignPath release notes.

## Commit Gate

This checkout uses a local `pre-commit` hook. Staged code/config changes must include both documentation updates and an ADR under `docs/adr/`; otherwise the commit is blocked. Reinstall the hook with:

```bash
cp scripts/hooks/pre-commit-doc-adr-check.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
