# 2026-05-15 Product CLI skill contract

## Context

The DeckLens Agent skill was documenting direct calls to `python3
decklens_cli.py`. That made the skill depend on an internal implementation
detail instead of the product capability. It also made future backend changes
more expensive because every Agent integration would need to know how the
conversion engine is implemented.

## Decision

- Add `bin/decklens.cjs` as the stable product CLI entry point.
- Expose `decklens convert ...` through `package.json` `bin` metadata and npm
  scripts.
- Package the CLI script into the Electron app resources for release builds.
- Keep `decklens_cli.py` as an internal backend adapter.
- Update `skills/decklens-convert` so Agents call `decklens convert` or the
  local `./bin/decklens.cjs convert` fallback, never `decklens_cli.py`.

## ADR checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

