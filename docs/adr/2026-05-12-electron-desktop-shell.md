# ADR: Electron Desktop Shell With Lazy Python Runtime

- Status: Accepted
- Date: 2026-05-12

## Context

DeckLens currently runs as a Flask web application. The next product shape needs a macOS and Windows desktop app while keeping installer size reasonable.

Bundling the full Python environment, PaddleOCR/PaddlePaddle/Torch, SAM checkpoints, and optional inpainting/model assets would make the installer very large and platform-specific. It would also force every user to download heavy resources even if they only use standard conversion.

## Decision

Add an Electron shell that reuses the existing Flask application instead of rewriting the app UI or Python engine.

The Electron main process:

- creates a secure BrowserWindow with Node integration disabled and context isolation enabled;
- ships the lightweight Python backend as unpacked Electron `extraResources`;
- copies those unpacked backend files into the Electron user data directory;
- detects Python 3.11 or 3.12 on the user's system, including common macOS locations that Finder-launched apps do not receive through shell `PATH`;
- creates a venv under the user data directory on first use;
- installs Python dependencies there;
- starts Flask through Waitress on a random localhost port;
- loads the local DeckLens web UI after `/healthz` succeeds.

The UI should present as a desktop workbench, not as a public web landing page: task-focused central conversion controls, compact mode cards, and explicit processing/result panels. The first screen should open directly on useful task controls; decorative preview panels, empty sidebar chrome, or intro cards that are not backed by real task data or real view switching should not be shown as features.

The workbench visual style should stay close to the Variant reference: white canvas, a sparse top rail with only the centered mark, centered 960px work area, black/gray heading hierarchy, minimal border-only mode cards, and a large quiet upload target. The first screen should not show a separate primary action when the upload target already handles file selection and the file list owns conversion start. Buttons and link-buttons in the workbench should use the same centered pill geometry. Avoid blue dashboard chrome or heavy shadows in the first screen.

On macOS, the Electron window should use a hidden inset titlebar so the traffic lights sit directly on the workbench background. The page provides only an invisible top drag region and offsets the workbench title away from the system controls; it should not render a separate titlebar-like strip.

The packaged app includes only the Electron shell and lightweight Python source/assets. The backend source/assets must remain outside `app.asar` so the runtime installer can copy `templates`, `static`, and Python files as normal filesystem entries. Large dependencies and models are downloaded when the runtime or feature needs them.

Required confirmation:

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Consequences

The macOS/Windows installer stays smaller because it does not include `.venv`, Python wheels, PaddleOCR model caches, SAM checkpoints, LaMa model files, uploads, or outputs.

The tradeoff is that first launch requires Python 3.11/3.12 and a network connection to install dependencies. A future iteration can improve this by offering a managed runtime download per platform, but that should still remain separate from the base installer.

The desktop app uses Waitress instead of Gunicorn because Gunicorn is not supported on Windows.

Local macOS builds are unsigned by default. Release signing and notarization should be configured separately with a single explicit Developer ID identity.

Packaged builds should be smoke-checked by verifying that `Contents/Resources/backend/app.py` and `Contents/Resources/backend/templates/index.html` exist before launching the app.

Desktop startup must not import heavyweight model stacks. `torch`, `paddle`, `paddleocr`, `simple_lama_inpainting`, and `segment_anything` stay lazy until the user starts a conversion or explicitly enables the corresponding feature. Task cleanup releases OCR and optional model singletons by default; `DECKLENS_KEEP_OCR_MODEL=1` can be used only when repeated conversions should trade memory for lower latency. The smoke suite covers startup import weight plus the main image, PDF, and local element-layering API flows.
