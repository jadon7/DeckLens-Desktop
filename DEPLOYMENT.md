# DeckLens Deployment

DeckLens is a Flask + Gunicorn web service that converts image/PDF pages into editable PPTX files. It runs heavy OCR and image-processing work in-process, so the safe production shape is a single worker with persistent storage.

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8080` | HTTP port used by Flask/Gunicorn |
| `DECKLENS_DATA_DIR` | project directory | Base directory for `uploads/` and `outputs/` |
| `DECKLENS_DEVICE` | `cpu` | Inference device hint; cloud should use `cpu` |
| `DECKLENS_MAX_UPLOAD_MB` | `100` | Flask upload limit |
| `DECKLENS_MAX_PROCESS_MP` | `3.0` | Max megapixels used for local processing |
| `DECKLENS_MAX_PROCESS_SIDE` | `2200` | Max long side used for local processing |
| `DECKLENS_PDF_DPI` | request value, normally `300` | PDF render DPI before safety downscaling |
| `DECKLENS_INPAINT_BACKEND` | `lama` | Text-removal backend; set to `opencv` for the lightweight fallback |
| `DECKLENS_INPAINT_RADIUS` | `3` | OpenCV inpaint radius |
| `DECKLENS_LAMA_MAX_SIDE` | `1024` | Long-side cap for LaMa cleanup inference |
| `DECKLENS_INPAINT_FALLBACK` | `true` | Fall back to OpenCV when LaMa fails |
| `DECKLENS_ENABLE_SAM` | unset/false | Set to `1` to enable local SAM |
| `DECKLENS_SAM_MODEL` | `vit_b` | SAM model when enabled |
| `DECKLENS_SAM_POINTS_PER_SIDE` | `16` | SAM sampling density when enabled |
| `FAL_KEY` | unset | Enables fal.ai Qwen smart layering |

## Local Production Smoke Test

```bash
cd /Users/jadon7/Documents/SynologyDrive/code/DeckLens
python -m pip install -r requirements.txt
DECKLENS_DATA_DIR="$(pwd)/.data" gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 900 app:app
```

Health check:

```bash
curl --noproxy '*' -fsS http://127.0.0.1:8080/healthz
```

## Docker

```bash
docker build -t decklens .
docker run --rm -p 8080:8080 \
  -e FAL_KEY="$FAL_KEY" \
  -v "$PWD/.data:/data" \
  decklens
```

The Dockerfile defaults to CPU-safe settings and stores user files under `/data`.

## Desktop Packaging

The Electron desktop shell is configured in `package.json` and supports macOS and Windows builds through `electron-builder`.

```bash
npm install
npm run electron:pack
npm run electron:dist:mac
npm run electron:dist:win
```

Packaging intentionally includes only:

- Electron main/preload/setup files
- `app.py`, `engine.py`, `requirements.txt`
- `templates/`, `static/`, `font_matcher/`

It excludes virtual environments, model caches, uploads, outputs, logs, and Docker-only assets. Python dependencies are installed into the user's application data directory on first launch. Feature-specific model files, such as SAM checkpoints, remain opt-in downloads.

Local macOS builds are unsigned by default to avoid accidentally selecting the wrong local signing certificate. Before external distribution, configure a single Developer ID identity and notarization workflow.

## Render Blueprint

This repo includes `render.yaml` for a Docker web service with:

- `healthCheckPath: /healthz`
- persistent `/data` disk for uploads and generated PPTX files
- `FAL_KEY` declared as a secret environment variable
- one Gunicorn worker

Deploy flow:

1. Push the repository to GitHub/GitLab.
2. Create a Render Blueprint from the repo.
3. Set `FAL_KEY` only if AI smart layering should be available.
4. Use a paid plan with enough memory for PaddleOCR and image processing.

## Production Notes

- Keep `--workers 1` while task state is stored in process memory.
- Use `DECKLENS_INPAINT_BACKEND=opencv` and keep local SAM disabled when a deployment must minimize memory and first-run model downloads.
- Qwen/fal smart layering uploads cleaned slide images to fal.ai; disclose this if files may contain sensitive content.
- Files under `/data/uploads` and `/data/outputs` are user data. Add retention cleanup before public launch.
- For multi-instance scaling, move task state and jobs to Redis/Celery or another queue and store artifacts in object storage.
