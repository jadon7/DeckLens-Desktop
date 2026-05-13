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

## Run Locally

```bash
cd /Users/jadon7/Documents/SynologyDrive/code/DeckLens
DECKLENS_DATA_DIR="$(pwd)" .venv312/bin/gunicorn \
  --bind 127.0.0.1:8080 \
  --workers 1 \
  --threads 4 \
  --timeout 900 \
  app:app
```

Open <http://127.0.0.1:8080>.

To run in a persistent tmux session:

```bash
tmux new-session -d -s decklens 'cd /Users/jadon7/Documents/SynologyDrive/code/DeckLens && DECKLENS_DATA_DIR="$(pwd)" .venv312/bin/gunicorn --bind 127.0.0.1:8080 --workers 1 --threads 4 --timeout 900 app:app'
```

Stop it with:

```bash
tmux kill-session -t decklens
```

## Run Desktop Shell

DeckLens also has an Electron desktop shell for macOS and Windows. The UI is structured as a desktop workbench with a left navigation rail, central conversion task area, and right-side task summary instead of a marketing-style web page. The installer intentionally does not bundle Python dependencies, PaddleOCR models, SAM checkpoints, or other large model assets. On first launch, the app asks the user to install the local Python runtime into the Electron user data directory. The packaged app stores the lightweight Flask backend under Electron `extraResources` as `Contents/Resources/backend` on macOS, outside `app.asar`, so first-launch runtime installation can copy templates and static assets as normal files.

Development run:

```bash
npm install
npm run electron:dev
```

Build unpacked app:

```bash
npm run electron:pack
```

Smoke-check a packaged macOS build:

```bash
test -f release/mac-arm64/DeckLens.app/Contents/Resources/backend/app.py
test -f release/mac-arm64/DeckLens.app/Contents/Resources/backend/templates/index.html
open -n release/mac-arm64/DeckLens.app
```

Build installers:

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
`decklens-updates` R2 bucket on `updates.dsxzai.com`.

The desktop runtime expects Python 3.11 or 3.12 to be available on the machine. On macOS it searches common Homebrew, framework, and user-local Python locations because Finder-launched apps do not inherit a normal shell `PATH`. A custom interpreter can be provided with `DECKLENS_PYTHON=/path/to/python`.

## Optional High-Memory Local Mode

Use this only when you explicitly want local SAM at the cost of high RAM and runtime:

```bash
DECKLENS_ENABLE_SAM=1 DECKLENS_DATA_DIR="$(pwd)" .venv312/bin/gunicorn \
  --bind 127.0.0.1:8080 \
  --workers 1 \
  --threads 4 \
  --timeout 900 \
  app:app
```

## Useful Checks

```bash
.venv312/bin/python -m compileall -q app.py engine.py scripts/test_font_normalization.py scripts/test_sam_checkpoint_cache.py
.venv312/bin/python scripts/test_startup_lightweight.py
.venv312/bin/python scripts/test_font_normalization.py
.venv312/bin/python scripts/test_sam_checkpoint_cache.py
.venv312/bin/python scripts/smoke_main_flows.py
curl --noproxy '*' -fsS http://127.0.0.1:8080/healthz
```

## Documentation Map

- [方案文档.md](方案文档.md): current technical architecture.
- [开发记录.md](开发记录.md): implementation history and current version notes.
- [DEPLOYMENT.md](DEPLOYMENT.md): Docker/Render/cloud deployment.
- [docs/ROADMAP.md](docs/ROADMAP.md): current product and engineering backlog.
- [docs/adr/](docs/adr/): decision records required for code/config commits.
- [docs/Leadpages风格参考.md](docs/Leadpages风格参考.md): retained UI style reference.

## Commit Gate

This checkout uses a local `pre-commit` hook. Staged code/config changes must include both documentation updates and an ADR under `docs/adr/`; otherwise the commit is blocked. Reinstall the hook with:

```bash
cp scripts/hooks/pre-commit-doc-adr-check.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
