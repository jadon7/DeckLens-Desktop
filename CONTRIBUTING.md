# Contributing

Thanks for taking the time to improve DeckLens.

## Development

```bash
npm install
npm run electron:dev
```

For the Python backend, create a Python 3.11 or 3.12 virtual environment and
install `requirements.txt`.

## Checks

Before opening a pull request, run the checks that match your change:

```bash
node --check electron/main.cjs
node --check electron/preload.cjs
.venv312/bin/python -m compileall -q app.py engine.py scripts
```

For UI and conversion changes, also run the local smoke tests documented in
`README.md`.

## Pull Requests

- Keep changes focused.
- Include documentation updates for user-facing behavior or release workflow
  changes.
- Do not commit local uploads, generated outputs, model weights, credentials,
  or release artifacts.
